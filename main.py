from fastapi import FastAPI, HTTPException, Depends, Request, Form, Response, Query, Body, UploadFile, File
from sqlalchemy import create_engine, Column, Integer
from sqlalchemy.orm import sessionmaker, Session, joinedload
from pydantic import BaseModel
from typing import List, Optional
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import time
from sqlalchemy.exc import OperationalError
import math
import random
import os
import logging

from brackets.models import Base, Tournament, Team, Bet, Round, Match, MatchStatus, Player

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_HOST = os.getenv("DB_HOST", "db")
DB_NAME = os.getenv("DB_NAME", "tournament_tracker")
SQLALCHEMY_DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"

def get_db_connection():
    retries = 5
    while retries > 0:
        try:
            logger.info(f"Attempting to connect to database: {SQLALCHEMY_DATABASE_URL}")
            engine = create_engine(SQLALCHEMY_DATABASE_URL)
            Base.metadata.create_all(bind=engine)
            logger.info("Successfully connected to the database")
            return engine
        except OperationalError as e:
            logger.error(f"Failed to connect to the database: {str(e)}")
            retries -= 1
            time.sleep(2)
    logger.critical("Could not connect to the database after multiple attempts")
    raise Exception("Could not connect to the database")

engine = get_db_connection()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Pydantic models
class TournamentCreate(BaseModel):
    name: str
    is_active: bool = False

class TournamentResponse(TournamentCreate):
    id: int

    class Config:
        orm_mode = True

class TeamCreate(BaseModel):
    name: str
    tournament_id: int

class TeamResponse(TeamCreate):
    id: int

    class Config:
        orm_mode = True

class BetCreate(BaseModel):
    name: str
    email: str
    amount: float

class BetResponse(BetCreate):
    id: int
    tournament_id: int

    class Config:
        orm_mode = True

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI()

templates = Jinja2Templates(directory="brackets/templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

PLAYER_IMAGE_DIR = "static/player_images"
os.makedirs(PLAYER_IMAGE_DIR, exist_ok=True)

@app.post("/tournaments/", response_model=TournamentResponse)
def create_tournament(tournament: TournamentCreate, db: Session = Depends(get_db)):
    db_tournament = Tournament(**tournament.dict())
    db.add(db_tournament)
    db.commit()
    db.refresh(db_tournament)
    return db_tournament

@app.get("/tournaments/", response_model=List[TournamentResponse])
def read_tournaments(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    tournaments = db.query(Tournament).offset(skip).limit(limit).all()
    return tournaments

@app.post("/teams/", response_model=TeamResponse)
def create_team(team: TeamCreate, db: Session = Depends(get_db)):
    db_team = Team(**team.dict())
    db.add(db_team)
    db.commit()
    db.refresh(db_team)
    return db_team

@app.get("/teams/", response_model=List[TeamResponse])
def read_teams(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    teams = db.query(Team).offset(skip).limit(limit).all()
    return teams

@app.post("/bets/", response_model=BetResponse)
def create_bet(bet: BetCreate, db: Session = Depends(get_db)):
    team = db.query(Team).filter(Team.id == bet.team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    db_bet = Bet(**bet.dict(), tournament_id=team.tournament_id)
    db.add(db_bet)
    db.commit()
    db.refresh(db_bet)
    return db_bet

@app.get("/bets/", response_model=List[BetResponse])
def read_bets(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    bets = db.query(Bet).offset(skip).limit(limit).all()
    return bets

@app.get("/odds/{tournament_id}")
def get_odds(tournament_id: int, db: Session = Depends(get_db)):
    teams = db.query(Team).filter(Team.tournament_id == tournament_id).all()
    total_bets = sum(bet.amount for team in teams for bet in team.bets)
    odds = {}
    for team in teams:
        team_bets = sum(bet.amount for bet in team.bets)
        if team_bets > 0:
            odds[team.name] = round(total_bets / team_bets, 2)
        else:
            odds[team.name] = 0
    return odds

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db)):
    active_tournament = db.query(Tournament).filter(Tournament.is_active == True).first()
    if active_tournament:
        teams = db.query(Team).filter(Team.tournament_id == active_tournament.id).all()
        odds = get_odds(active_tournament.id, db)
        return templates.TemplateResponse("brackets/index.html", {"request": request, "tournament": active_tournament, "teams": teams, "odds": odds})
    return templates.TemplateResponse("brackets/index.html", {"request": request, "message": "No active tournament"})

@app.get("/place_bet/{team_id}", response_class=HTMLResponse)
async def place_bet_form(request: Request, team_id: int, db: Session = Depends(get_db)):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return templates.TemplateResponse("brackets/place_bet.html", {"request": request, "team": team})

@app.post("/place_bet/{team_id}", response_model=BetResponse)
async def place_bet(team_id: int, bet: BetCreate, db: Session = Depends(get_db)):
    try:
        team = db.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")
        db_bet = Bet(**bet.dict(), team_id=team_id, tournament_id=team.tournament_id)
        db.add(db_bet)
        db.commit()
        db.refresh(db_bet)
        return JSONResponse(content={"message": "Bet placed successfully", "bet_id": db_bet.id}, status_code=200)
    except Exception as e:
        db.rollback()
        return JSONResponse(content={"message": f"Error placing bet: {str(e)}"}, status_code=500)

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, show_archived: bool = False, db: Session = Depends(get_db)):
    if show_archived:
        tournaments = db.query(Tournament).filter(Tournament.is_archived == True).options(
            joinedload(Tournament.teams).joinedload(Team.players)
        ).all()
    else:
        tournaments = db.query(Tournament).filter(Tournament.is_archived == False).options(
            joinedload(Tournament.teams).joinedload(Team.players)
        ).all()

    return templates.TemplateResponse("brackets/admin.html", {
        "request": request,
        "tournaments": tournaments,
        "show_archived": show_archived
    })

@app.post("/admin/create_tournament")
async def create_tournament(
    name: str = Form(...),
    description: str = Form(...),
    db: Session = Depends(get_db)
):
    new_tournament = Tournament(name=name, description=description)
    db.add(new_tournament)
    db.commit()
    db.refresh(new_tournament)
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/admin/edit_tournament/{tournament_id}")
async def edit_tournament(
    tournament_id: int,
    name: str = Form(...),
    description: str = Form(...),
    is_active: bool = Form(False),
    db: Session = Depends(get_db)
):
    tournament = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if tournament:
        tournament.name = name
        tournament.description = description
        tournament.is_active = is_active
        db.commit()
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/admin/add_team/{tournament_id}")
async def add_team(
    tournament_id: int,
    team_name: str = Form(...),
    player_names: List[str] = Form(...),
    db: Session = Depends(get_db)
):
    try:
        tournament = db.query(Tournament).filter(Tournament.id == tournament_id).first()
        if not tournament:
            raise HTTPException(status_code=404, detail="Tournament not found")
        
        new_team = Team(name=team_name, tournament_id=tournament_id)
        db.add(new_team)
        db.flush()

        for player_name in player_names:
            new_player = Player(name=player_name, team_id=new_team.id)
            db.add(new_player)

        db.commit()
        return RedirectResponse(url=f"/admin?tournament_id={tournament_id}", status_code=303)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@app.post("/admin/add_player/{team_id}")
async def add_player(
    team_id: int,
    player_name: str = Form(...),
    db: Session = Depends(get_db)
):
    team = db.query(Team).filter(Team.id == team_id).first()
    if team:
        new_player = Player(name=player_name, team_id=team_id)
        db.add(new_player)
        db.commit()
    return RedirectResponse(url=f"/admin/edit_tournament/{team.tournament_id}", status_code=303)

@app.get("/admin/edit_tournament/{tournament_id}", response_class=HTMLResponse)
async def edit_tournament_form(tournament_id: int, request: Request, db: Session = Depends(get_db)):
    tournament = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")
    return templates.TemplateResponse("brackets/edit_tournament.html", {"request": request, "tournament": tournament})

@app.post("/admin/generate_bracket/{tournament_id}")
async def generate_bracket(tournament_id: int, db: Session = Depends(get_db)):
    tournament = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    teams = tournament.teams
    if len(teams) < 2:
        raise HTTPException(status_code=400, detail="Not enough teams to generate a bracket")

    # Delete existing rounds and matches
    db.query(Match).filter(Match.round.has(tournament_id=tournament_id)).delete(synchronize_session=False)
    db.query(Round).filter(Round.tournament_id == tournament_id).delete(synchronize_session=False)

    # Calculate the number of rounds needed
    num_rounds = tournament.calculate_rounds()

    # Create rounds
    rounds = []
    for round_num in range(1, num_rounds + 1):
        new_round = Round(tournament_id=tournament_id, number=round_num)
        db.add(new_round)
        rounds.append(new_round)

    db.flush()

    # Shuffle teams
    teams = list(teams)
    random.shuffle(teams)

    # Create matches for the first round
    first_round = rounds[0]
    num_first_round_matches = math.ceil(len(teams) / 2)
    for i in range(num_first_round_matches):
        team1 = teams[i * 2] if i * 2 < len(teams) else None
        team2 = teams[i * 2 + 1] if i * 2 + 1 < len(teams) else None
        match = Match(
            round_id=first_round.id,
            team1_id=team1.id if team1 else None,
            team2_id=team2.id if team2 else None,
            position=i
        )
        db.add(match)

    # Create empty matches for subsequent rounds
    for round_index, round in enumerate(rounds[1:], 1):
        num_matches = num_first_round_matches // (2 ** round_index)
        for i in range(num_matches):
            match = Match(round_id=round.id, position=i)
            db.add(match)

    db.commit()
    return {"message": "Bracket generated successfully"}

@app.post("/admin/update_match/{match_id}")
async def update_match(
    match_id: int, 
    winner_name: str = Body(...), 
    team1_score: int = Body(...), 
    team2_score: int = Body(...), 
    db: Session = Depends(get_db)
):
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    winner = db.query(Team).filter((Team.id == match.team1_id) | (Team.id == match.team2_id), Team.name == winner_name).first()
    if not winner:
        raise HTTPException(status_code=400, detail="Invalid winner")

    match.winner_id = winner.id
    match.team1_score = team1_score
    match.team2_score = team2_score
    match.status = MatchStatus.COMPLETED
    db.commit()

    # Advance winner to next round
    next_round = db.query(Round).filter(Round.tournament_id == match.round.tournament_id, Round.number == match.round.number + 1).first()
    if next_round:
        next_match_position = match.position // 2
        next_match = db.query(Match).filter(Match.round_id == next_round.id, Match.position == next_match_position).first()
        
        if next_match:
            if next_match.team1_id is None:
                next_match.team1_id = winner.id
            else:
                next_match.team2_id = winner.id
            db.commit()

    return JSONResponse(content={"message": "Match updated successfully"})

@app.get("/tournament/{tournament_id}/bracket")
async def get_tournament_bracket(tournament_id: int, db: Session = Depends(get_db)):
    tournament = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    rounds = db.query(Round).filter(Round.tournament_id == tournament_id).order_by(Round.number).all()
    
    bracket_data = []
    for round in rounds:
        matches = db.query(Match).filter(Match.round_id == round.id).order_by(Match.position).all()
        round_data = {
            "round_number": round.number,
            "matches": [
                {
                    "id": match.id,
                    "team1": match.team1.name if match.team1 else "TBD",
                    "team2": match.team2.name if match.team2 else "TBD",
                    "team1_id": match.team1.id if match.team1 else None,
                    "team2_id": match.team2.id if match.team2 else None,
                    "team1_score": match.team1_score,
                    "team2_score": match.team2_score,
                    "winner": match.winner.name if match.winner else None,
                    "position": match.position
                }
                for match in matches
            ]
        }
        bracket_data.append(round_data)

    return {"bracket": bracket_data}

@app.post("/admin/delete_tournament/{tournament_id}")
async def delete_tournament(tournament_id: int, db: Session = Depends(get_db)):
    tournament = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")
    db.delete(tournament)
    db.commit()
    return {"message": "Tournament deleted successfully"}

@app.post("/admin/archive_tournament/{tournament_id}")
async def archive_tournament(tournament_id: int, db: Session = Depends(get_db)):
    tournament = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")
    tournament.is_archived = True
    db.commit()
    return {"message": "Tournament archived successfully"}

@app.post("/place_bet/{match_id}/{team_id}")
async def place_bet(
    match_id: int,
    team_id: int,
    amount: float = Form(...),
    full_name: str = Form(...),
    db: Session = Depends(get_db)
):
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    new_bet = Bet(
        name=full_name,
        amount=amount,
        team_id=team_id,
        tournament_id=match.round.tournament_id
    )
    db.add(new_bet)
    db.commit()
    
    return {"message": "Bet placed successfully"}

@app.get("/match/{match_id}")
async def get_match_details(match_id: int, db: Session = Depends(get_db)):
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    
    return {
        "id": match.id,
        "team1": {
            "id": match.team1.id if match.team1 else None,
            "name": match.team1.name if match.team1 else "TBD",
            "players": [{"name": player.name} for player in match.team1.players] if match.team1 else []
        },
        "team2": {
            "id": match.team2.id if match.team2 else None,
            "name": match.team2.name if match.team2 else "TBD",
            "players": [{"name": player.name} for player in match.team2.players] if match.team2 else []
        },
        "team1_score": match.team1_score,
        "team2_score": match.team2_score,
        "winner": match.winner.name if match.winner else None
    }
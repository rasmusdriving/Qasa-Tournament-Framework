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
from dotenv import load_dotenv

from brackets.models import Base, Tournament, Team, Bet, Round, Match, MatchStatus, Player

# Load .env file if it exists
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise Exception("DATABASE_URL environment variable is not set")

SQLALCHEMY_DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://')

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
def create_tournament_endpoint(tournament: TournamentCreate, db: Session = Depends(get_db)):
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
    db.add(db_team)  # Changed from db_add to db.add
    db.commit()
    db.refresh(db_team)
    return db_team

@app.get("/teams/", response_model=List[TeamResponse])
def read_teams(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    teams = db.query(Team).offset(skip).limit(limit).all()
    return teams

@app.post("/bets/", response_model=BetResponse)
def create_bet(bet: BetCreate, team_id: int, db: Session = Depends(get_db)):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    db_bet = Bet(**bet.dict(), team_id=team_id, tournament_id=team.tournament_id)
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
async def add_player(team_id: int, request: Request, db: Session = Depends(get_db)):
    try:
        data = await request.json()
        name = data.get('name')
        if not name:
            raise HTTPException(status_code=422, detail="Name is required")
        team = db.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")
        new_player = Player(name=name, team_id=team_id)
        db.add(new_player)
        db.commit()
        db.refresh(new_player)
        return {"success": True, "playerId": new_player.id}
    except Exception as e:
        logger.error(f"Error adding player: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@app.post("/admin/edit_team/{team_id}")
async def edit_team(team_id: int, request: Request, db: Session = Depends(get_db)):
    try:
        data = await request.json()
        name = data.get('name')
        if not name:
            raise HTTPException(status_code=422, detail="Name is required")
        team = db.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")
        team.name = name
        db.commit()
        return {"success": True}
    except Exception as e:
        logger.error(f"Error editing team: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@app.post("/admin/remove_player/{team_id}/{player_id}")
async def remove_player(team_id: int, player_id: int, db: Session = Depends(get_db)):
    player = db.query(Player).filter(Player.id == player_id, Player.team_id == team_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    db.delete(player)
    db.commit()
    return {"success": True}

@app.post("/admin/toggle_ongoing_match/{match_id}")
async def toggle_ongoing_match(match_id: int, data: dict = Body(...), db: Session = Depends(get_db)):
    is_ongoing = data.get('is_ongoing')
    if is_ongoing is None:
        raise HTTPException(status_code=422, detail="Missing 'is_ongoing' field in request body")
    
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    
    match.is_ongoing = is_ongoing
    db.commit()
    return {"success": True}

@app.get("/admin/get_teams/{tournament_id}")
async def get_teams(tournament_id: int, db: Session = Depends(get_db)):
    teams = db.query(Team).filter(Team.tournament_id == tournament_id).all()
    return [{"id": team.id, "name": team.name} for team in teams]

@app.post("/admin/create_bracket/{tournament_id}")
async def create_bracket(tournament_id: int, data: dict = Body(...), db: Session = Depends(get_db)):
    try:
        tournament = db.query(Tournament).filter(Tournament.id == tournament_id).first()
        if not tournament:
            raise HTTPException(status_code=404, detail="Tournament not found")
        
        # Delete existing rounds and matches
        db.query(Match).filter(Match.round.has(tournament_id=tournament_id)).delete(synchronize_session=False)
        db.query(Round).filter(Round.tournament_id == tournament_id).delete(synchronize_session=False)
        
        round_count = int(data['roundCount'])
        matchups = data['matchups']
        
        for i in range(1, round_count + 1):
            new_round = Round(tournament_id=tournament_id, number=i)
            db.add(new_round)
            db.flush()
            
            round_matchups = [m for m in matchups if int(m['round']) == i]
            for match in round_matchups:
                new_match = Match(
                    round_id=new_round.id,
                    team1_id=match.get('team1'),
                    team2_id=match.get('team2'),
                    position=int(match['match'])
                )
                db.add(new_match)
        
        db.commit()
        return {"message": "Bracket created successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating bracket: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An error occurred while creating the bracket: {str(e)}")

@app.post("/admin/delete_team/{team_id}")
async def delete_team(team_id: int, db: Session = Depends(get_db)):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    # Delete all players associated with the team
    db.query(Player).filter(Player.team_id == team_id).delete()
    
    # Delete the team
    db.delete(team)
    db.commit()
    return {"success": True}

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
                    "team1_score": match.team1_score if match.team1_score is not None else "",
                    "team2_score": match.team2_score if match.team2_score is not None else "",
                    "winner": match.winner.name if match.winner else None,
                    "winner_id": match.winner.id if match.winner else None,
                    "position": match.position,
                    "is_ongoing": match.is_ongoing
                }
                for match in matches
            ]
        }
        bracket_data.append(round_data)

    return {"bracket": bracket_data}

@app.post("/admin/remove_bracket/{tournament_id}")
async def remove_bracket(tournament_id: int, db: Session = Depends(get_db)):
    try:
        tournament = db.query(Tournament).filter(Tournament.id == tournament_id).first()
        if not tournament:
            raise HTTPException(status_code=404, detail="Tournament not found")
        
        # Delete all matches associated with the tournament
        db.query(Match).filter(Match.round.has(tournament_id=tournament_id)).delete(synchronize_session=False)
        
        # Delete all rounds associated with the tournament
        db.query(Round).filter(Round.tournament_id == tournament_id).delete(synchronize_session=False)
        
        db.commit()
        return {"success": True, "message": "Bracket removed successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Error removing bracket: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An error occurred while removing the bracket: {str(e)}")

@app.post("/admin/update_match/{match_id}")
async def update_match(
    match_id: int,
    winner_name: Optional[str] = Body(None),
    team1_score: Optional[int] = Body(None),
    team2_score: Optional[int] = Body(None),
    is_ongoing: Optional[bool] = Body(None),
    db: Session = Depends(get_db)
):
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    
    if team1_score is not None:
        match.team1_score = team1_score
    if team2_score is not None:
        match.team2_score = team2_score
    
    if winner_name:
        winner = db.query(Team).filter((Team.id == match.team1_id) | (Team.id == match.team2_id), Team.name == winner_name).first()
        if winner:
            match.winner_id = winner.id
            match.status = MatchStatus.COMPLETED
    elif winner_name == "":
        match.winner_id = None
        match.status = MatchStatus.PENDING
    
    if is_ongoing is not None:
        match.is_ongoing = is_ongoing
    
    db.commit()
    db.refresh(match)
    return {
        "success": True,
        "match": {
            "id": match.id,
            "team1_score": match.team1_score,
            "team2_score": match.team2_score,
            "winner": match.winner.name if match.winner else None,
            "is_ongoing": match.is_ongoing
        }
    }

@app.get("/admin/get_match/{match_id}")
async def get_match(match_id: int, db: Session = Depends(get_db)):
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    return {
        "id": match.id,
        "team1_score": match.team1_score,
        "team2_score": match.team2_score,
        "winner_id": match.winner_id,
        "is_ongoing": match.is_ongoing,
        "status": match.status
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)

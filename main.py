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
    db_add(db_team)
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

@app.get("/")
async def index(request: Request, db: Session = Depends(get_db)):
    active_tournament = db.query(Tournament).filter(Tournament.is_active == True).first()
    if active_tournament:
<<<<<<< Updated upstream
        teams = db.query(Team).filter(Team.tournament_id == active_tournament.id).all()
        odds = get_odds(active_tournament.id, db)
        return templates.TemplateResponse("brackets/index.html", {"request": request, "tournament": active_tournament, "teams": teams, "odds": odds})
    return templates.TemplateResponse("brackets/index.html", {"request": request, "message": "No active tournament"})
=======
        return templates.TemplateResponse("brackets/index.html", {"request": request, "tournament": active_tournament})
    else:
        return templates.TemplateResponse("brackets/no_active_tournament.html", {"request": request})
>>>>>>> Stashed changes

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
async def update_match(match_id: int, data: dict = Body(...), db: Session = Depends(get_db)):
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    if 'team1_score' in data:
        match.team1_score = data['team1_score']
    if 'team2_score' in data:
        match.team2_score = data['team2_score']
    
    if 'winner_name' in data and data['winner_name']:
        winner = db.query(Team).filter(Team.name == data['winner_name']).first()
        if winner:
            match.winner = winner
            match.is_ongoing = False  # Remove ongoing status when a winner is selected

            # Update the next round's match
            next_round = db.query(Round).filter(Round.tournament_id == match.round.tournament_id, 
                                                Round.number == match.round.number + 1).first()
            if next_round:
                next_match_position = match.position // 2
                next_match = db.query(Match).filter(Match.round_id == next_round.id, 
                                                    Match.position == next_match_position).first()
                if next_match:
                    if match.position % 2 == 0:
                        next_match.team1 = winner
                    else:
                        next_match.team2 = winner
        else:
            raise HTTPException(status_code=400, detail="Winner team not found")
    elif 'winner_name' in data and not data['winner_name']:
        match.winner = None  # Clear the winner if an empty string is sent

    db.commit()
    return {"success": True, "message": "Match updated successfully"}

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
                    "winner_id": match.winner.id if match.winner else None,
                    "position": match.position,
                    "is_ongoing": match.is_ongoing
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

@app.post("/admin/edit_team/{team_id}")
async def edit_team(team_id: int, name: str = Body(...), db: Session = Depends(get_db)):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    team.name = name
    db.commit()
    return {"success": True}

@app.post("/admin/add_player/{team_id}")
async def add_player(team_id: int, name: str = Body(...), db: Session = Depends(get_db)):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    new_player = Player(name=name, team_id=team_id)
    db.add(new_player)
    db.commit()
    db.refresh(new_player)
    return {"success": True, "playerId": new_player.id}

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

<<<<<<< Updated upstream
=======
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
            new_round = Round(tournament_id=tournament_id, round_number=i)
            db.add(new_round)
            db.flush()
            
            round_matchups = [m for m in matchups if int(m['round']) == i]
            for match in round_matchups:
                new_match = Match(
                    round_id=new_round.id,
                    team1_id=match.get('team1'),
                    team2_id=match.get('team2'),
                    position=int(match['match']),
                    is_bye=match.get('is_bye', False),
                    bye_description=match.get('bye_description')
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

    rounds = db.query(Round).filter(Round.tournament_id == tournament_id).order_by(Round.round_number).all()  # Changed from Round.number to Round.round_number

    if not rounds:
        return {"message": "Bracket has not been created yet", "bracket": []}

    teams = db.query(Team).filter(Team.tournament_id == tournament_id).all()
    
    bracket_data = []
    for round in rounds:
        matches = db.query(Match).filter(Match.round_id == round.id).order_by(Match.position).all()
        round_data = {
            "round_number": round.round_number,
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
                    "is_ongoing": match.is_ongoing,
                    "is_bye": match.is_bye,  # Add this line
                    "bye_description": match.bye_description  # Add this line
                }
                for match in matches
            ]
        }
        bracket_data.append(round_data)

    return {
        "bracket": bracket_data,
        "teams": [{"id": team.id, "name": team.name} for team in teams]
    }

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
    team1_id: Optional[int] = Body(None),
    team2_id: Optional[int] = Body(None),
    db: Session = Depends(get_db)
):
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    
    if team1_id is not None:
        match.team1_id = team1_id
    if team2_id is not None:
        match.team2_id = team2_id
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
            "team1_id": match.team1_id,
            "team2_id": match.team2_id,
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

@app.get("/betting/{tournament_id}", response_class=HTMLResponse)
async def betting_page(request: Request, tournament_id: int, db: Session = Depends(get_db)):
    tournament = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")
    
    betting_pool = calculate_betting_pool_and_odds(tournament_id, db)
    odds = get_odds(tournament_id, db)
    
    return templates.TemplateResponse("brackets/betting.html", {
        "request": request,
        "tournament": tournament,
        "betting_pool": betting_pool,
        "odds": odds
    })

@app.get("/admin/bets/{tournament_id}")
async def get_tournament_bets(tournament_id: int, db: Session = Depends(get_db)):
    bets = db.query(Bet).filter(Bet.tournament_id == tournament_id).all()
    return [{"id": bet.id, "name": bet.name, "amount": bet.amount, "team_id": bet.team_id, "status": bet.status} for bet in bets]

@app.post("/admin/bets/{bet_id}/accept")
async def accept_bet(bet_id: int, db: Session = Depends(get_db)):
    bet = db.query(Bet).filter(Bet.id == bet_id).first()
    if not bet:
        raise HTTPException(status_code=404, detail="Bet not found")
    bet.status = "accepted"
    db.commit()
    return {"success": True}

@app.post("/admin/bets/{bet_id}/decline")
async def decline_bet(bet_id: int, db: Session = Depends(get_db)):
    bet = db.query(Bet).filter(Bet.id == bet_id).first()
    if not bet:
        raise HTTPException(status_code=404, detail="Bet not found")
    bet.status = "declined"
    db.commit()
    return {"success": True}

@app.delete("/admin/bets/{bet_id}")
async def delete_bet(bet_id: int, db: Session = Depends(get_db)):
    bet = db.query(Bet).filter(Bet.id == bet_id).first()
    if not bet:
        raise HTTPException(status_code=404, detail="Bet not found")
    db.delete(bet)
    db.commit()
    return {"success": True}

@app.post("/admin/delete_tournament/{tournament_id}")
async def delete_tournament(tournament_id: int, db: Session = Depends(get_db)):
    try:
        tournament = db.query(Tournament).filter(Tournament.id == tournament_id).first()
        if not tournament:
            raise HTTPException(status_code=404, detail="Tournament not found")
        
        logger.info(f"Deleting tournament with ID: {tournament_id}")
        
        # Delete all matches associated with the tournament
        matches_deleted = db.query(Match).filter(Match.round.has(tournament_id=tournament_id)).delete(synchronize_session=False)
        logger.info(f"Deleted {matches_deleted} matches")
        
        # Delete all rounds associated with the tournament
        rounds_deleted = db.query(Round).filter(Round.tournament_id == tournament_id).delete(synchronize_session=False)
        logger.info(f"Deleted {rounds_deleted} rounds")
        
        # Delete all bets associated with the tournament
        bets_deleted = db.query(Bet).filter(Bet.tournament_id == tournament_id).delete(synchronize_session=False)
        logger.info(f"Deleted {bets_deleted} bets")
        
        # Delete all players associated with teams in the tournament
        players_deleted = db.query(Player).filter(Player.team.has(tournament_id=tournament_id)).delete(synchronize_session=False)
        logger.info(f"Deleted {players_deleted} players")
        
        # Delete all teams associated with the tournament
        teams_deleted = db.query(Team).filter(Team.tournament_id == tournament_id).delete(synchronize_session=False)
        logger.info(f"Deleted {teams_deleted} teams")
        
        # Delete the tournament
        db.delete(tournament)
        logger.info(f"Deleted tournament")
        
        db.commit()
        logger.info(f"Successfully deleted tournament with ID: {tournament_id}")
        
        return {"success": True, "message": "Tournament deleted successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting tournament: {str(e)}")
        logger.exception("Full traceback:")
        raise HTTPException(status_code=500, detail=f"An error occurred while deleting the tournament: {str(e)}")

>>>>>>> Stashed changes
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)

from fastapi import FastAPI, HTTPException, Depends, Request, Form, Response, Query, Body, UploadFile, File
from sqlalchemy import create_engine, Column, Integer, func  # Add func here
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

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, db: Session = Depends(get_db)):
    # Get the active tournament
    tournament = db.query(Tournament).filter(Tournament.is_active == True).first()
    
    logger.info(f"Active tournament query result: {tournament}")
    if tournament:
        logger.info(f"Found active tournament: ID={tournament.id}, Name={tournament.name}")
    else:
        logger.info("No active tournament found")
    
    return templates.TemplateResponse("brackets/index.html", {
        "request": request,
        "tournament": tournament
    })

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
    is_active: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    try:
        tournament = db.query(Tournament).filter(Tournament.id == tournament_id).first()
        if not tournament:
            raise HTTPException(status_code=404, detail="Tournament not found")

        # Convert checkbox value to boolean - Form data comes as "on" when checked, None when unchecked
        is_active_bool = is_active == "on"
        
        # If this tournament is being set to active, first deactivate all other tournaments
        if is_active_bool:
            db.query(Tournament).filter(Tournament.id != tournament_id).update({"is_active": False})
            db.flush()  # Ensure the update is processed before continuing

        # Update tournament fields
        tournament.name = name
        tournament.description = description
        tournament.is_active = is_active_bool  # Set the is_active value

        db.commit()
        
        # Log the update for debugging
        logger.info(f"Tournament {tournament_id} updated: name={name}, description={description}, is_active={is_active_bool}")
        
        # Verify the update
        db.refresh(tournament)
        logger.info(f"After update verification - Tournament {tournament_id} is_active: {tournament.is_active}")

        return RedirectResponse(url="/admin", status_code=303)
    except Exception as e:
        logger.error(f"Error editing tournament: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

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
async def generate_bracket(tournament_id: int, data: dict = Body(...), db: Session = Depends(get_db)):
    try:
        tournament = db.query(Tournament).filter(Tournament.id == tournament_id).first()
        if not tournament:
            raise HTTPException(status_code=404, detail="Tournament not found")

        # Delete existing bracket if any
        await delete_tournament_bracket(tournament_id, db)

        # Create new rounds based on the specified count
        round_count = data.get('round_count', 1)
        for i in range(round_count):
            new_round = Round(
                tournament_id=tournament_id,
                round_number=i + 1,
                name=f"Round {i + 1}"
            )
            db.add(new_round)

        db.commit()
        return {"success": True, "message": "Bracket created successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Error generating bracket: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

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
    try:
        tournament = db.query(Tournament).filter(Tournament.id == tournament_id).first()
        if not tournament:
            raise HTTPException(status_code=404, detail="Tournament not found")

        rounds = db.query(Round).filter(Round.tournament_id == tournament_id).order_by(Round.round_number).all()
        bracket_data = []

        for round in rounds:
            matches = db.query(Match).filter(Match.round_id == round.id).order_by(Match.order).all()
            match_data = []
            
            for match in matches:
                team1 = db.query(Team).filter(Team.id == match.team1_id).first() if match.team1_id else None
                team2 = db.query(Team).filter(Team.id == match.team2_id).first() if match.team2_id else None
                
                match_info = {
                    "id": match.id,
                    "team1": {"id": team1.id, "name": team1.name, "players": [{"name": p.name} for p in team1.players]} if team1 else None,
                    "team2": {"id": team2.id, "name": team2.name, "players": [{"name": p.name} for p in team2.players]} if team2 else None,
                    "team1_score": match.team1_score,
                    "team2_score": match.team2_score,
                    "winner_id": match.winner_id,
                    "order": match.order,
                    "is_ongoing": match.is_ongoing,
                    "is_bye": match.is_bye,
                    "bye_description": match.bye_description,
                    "is_third_place": match.is_third_place
                }

                match_data.append(match_info)
            
            bracket_data.append({
                "round_id": round.id,
                "round_number": round.round_number,
                "name": round.name,
                "matches": match_data
            })
        
        return {"rounds": bracket_data}
        
    except Exception as e:
        logger.error(f"Error getting tournament bracket: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

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

@app.get("/admin/get_teams/{tournament_id}")
async def get_teams(tournament_id: int, db: Session = Depends(get_db)):
    teams = db.query(Team).filter(Team.tournament_id == tournament_id).all()
    return [{"id": team.id, "name": team.name} for team in teams]

@app.post("/admin/create_bracket/{tournament_id}")
async def create_bracket(
    tournament_id: int,
    data: dict = Body(...),
    db: Session = Depends(get_db)
):
    try:
        tournament = db.query(Tournament).filter(Tournament.id == tournament_id).first()
        if not tournament:
            raise HTTPException(status_code=404, detail="Tournament not found")

        round_count = data.get('round_count', 1)
        
        # Create rounds
        for i in range(round_count):
            new_round = Round(
                tournament_id=tournament_id,
                round_number=i + 1,
                name=f"Round {i + 1}"
            )
            db.add(new_round)
        
        db.commit()
        return {"success": True, "message": "Bracket created successfully"}
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating bracket: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/delete_bracket/{tournament_id}")
async def delete_bracket(tournament_id: int, db: Session = Depends(get_db)):
    try:
        # Delete all matches associated with the tournament's rounds
        matches_deleted = db.query(Match).filter(
            Match.round_id.in_(
                db.query(Round.id).filter(Round.tournament_id == tournament_id)
            )
        ).delete(synchronize_session=False)
        
        # Delete all rounds associated with the tournament
        rounds_deleted = db.query(Round).filter(Round.tournament_id == tournament_id).delete(synchronize_session=False)
        
        db.commit()
        return {
            "success": True,
            "message": f"Bracket deleted successfully. Deleted {matches_deleted} matches and {rounds_deleted} rounds."
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting bracket: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

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

@app.post("/admin/update_round_name/{round_id}")
async def update_round_name(round_id: int, name: str = Body(..., embed=True), db: Session = Depends(get_db)):
    try:
        round = db.query(Round).filter(Round.id == round_id).first()
        if not round:
            raise HTTPException(status_code=404, detail="Round not found")
        
        round.name = name
        db.commit()
        return {"success": True}
    except Exception as e:
        logger.error(f"Error updating round name: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Add this new endpoint
@app.post("/admin/add_match")
async def add_match(
    match_data: dict,
    db: Session = Depends(get_db)
):
    try:
        round_id = match_data.get('round_id')
        round = db.query(Round).filter(Round.id == round_id).first()
        if not round:
            raise HTTPException(status_code=404, detail="Round not found")

        # Get the current max order for this round
        max_order = db.query(func.max(Match.order)).filter(Match.round_id == round_id).scalar() or -1
        
        # Create new match with incremented order
        new_match = Match(
            round_id=round_id,
            team1_id=match_data.get('team1_id') if match_data.get('team1_id') != "" else None,
            team2_id=match_data.get('team2_id') if match_data.get('team2_id') != "" else None,
            is_bye=match_data.get('is_bye', False),
            bye_description=match_data.get('bye_description') if match_data.get('is_bye') else None,
            is_third_place=match_data.get('is_third_place', False),
            order=max_order + 1  # Set the order
        )
        
        db.add(new_match)
        db.commit()
        db.refresh(new_match)
        
        return {"success": True, "match_id": new_match.id}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/teams/{tournament_id}")
async def get_tournament_teams(tournament_id: int, db: Session = Depends(get_db)):
    try:
        teams = db.query(Team).filter(Team.tournament_id == tournament_id).all()
        return [{"id": team.id, "name": team.name} for team in teams]
    except Exception as e:
        logger.error(f"Error getting tournament teams: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/round/{round_id}/matches")
async def get_round_matches(round_id: int, db: Session = Depends(get_db)):
    try:
        round = db.query(Round).filter(Round.id == round_id).first()
        if not round:
            raise HTTPException(status_code=404, detail="Round not found")
        
        # Add order by Match.order to maintain consistent ordering
        matches = db.query(Match).filter(Match.round_id == round_id).order_by(Match.order).all()
        
        tournament_teams = db.query(Team).filter(Team.tournament_id == round.tournament_id).all()
        available_teams = [{"id": team.id, "name": team.name} for team in tournament_teams]
        
        # Get total number of rounds to identify if this is the final round
        total_rounds = db.query(Round).filter(Round.tournament_id == round.tournament_id).count()
        is_final_round = round.round_number == total_rounds
        
        match_data = []
        for match in matches:
            team1 = db.query(Team).filter(Team.id == match.team1_id).first() if match.team1_id else None
            team2 = db.query(Team).filter(Team.id == match.team2_id).first() if match.team2_id else None
            
            match_data.append({
                "id": match.id,
                "team1_id": match.team1_id,
                "team2_id": match.team2_id,
                "team1_name": team1.name if team1 else None,
                "team2_name": team2.name if team2 else None,
                "team1_score": match.team1_score,
                "team2_score": match.team2_score,
                "winner_id": match.winner_id,
                "is_bye": match.is_bye,
                "bye_description": match.bye_description,
                "is_third_place": match.is_third_place,
                "available_teams": available_teams,
                "is_final_round": is_final_round,
                "order": match.order  # Include order in the response
            })
            
        return match_data
    except Exception as e:
        logger.error(f"Error getting round matches: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/match/{match_id}/update")
async def update_match(match_id: int, data: dict = Body(...), db: Session = Depends(get_db)):
    try:
        match = db.query(Match).filter(Match.id == match_id).first()
        if not match:
            raise HTTPException(status_code=404, detail="Match not found")
        
        # Update match fields
        for key, value in data.items():
            if hasattr(match, key):
                setattr(match, key, value)
        
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating match: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/match/{match_id}/delete")
async def delete_match(match_id: int, db: Session = Depends(get_db)):
    try:
        match = db.query(Match).filter(Match.id == match_id).first()
        if not match:
            raise HTTPException(status_code=404, detail="Match not found")
        
        round_id = match.round_id
        db.delete(match)
        db.commit()
        
        return {"success": True, "round_id": round_id}
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting match: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/tournament/{tournament_id}/delete_bracket")
async def delete_tournament_bracket(tournament_id: int, db: Session = Depends(get_db)):
    try:
        # Delete all matches in all rounds
        rounds = db.query(Round).filter(Round.tournament_id == tournament_id).all()
        for round in rounds:
            db.query(Match).filter(Match.round_id == round.id).delete(synchronize_session=False)
        
        # Delete all rounds
        db.query(Round).filter(Round.tournament_id == tournament_id).delete(synchronize_session=False)
        
        db.commit()
        return {"success": True, "message": "Bracket deleted successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting bracket: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/team/{team_id}/update")
async def update_team(team_id: int, data: dict = Body(...), db: Session = Depends(get_db)):
    try:
        team = db.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")
        
        team.name = data.get('name')
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/team/{team_id}/player/{player_id}/remove")
async def remove_player(team_id: int, player_id: int, db: Session = Depends(get_db)):
    try:
        player = db.query(Player).filter(Player.id == player_id, Player.team_id == team_id).first()
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")
        
        db.delete(player)
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/team/{team_id}/player/add")
async def add_player(team_id: int, data: dict = Body(...), db: Session = Depends(get_db)):
    try:
        team = db.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")
        
        new_player = Player(name=data.get('name'), team_id=team_id)
        db.add(new_player)
        db.commit()
        db.refresh(new_player)
        
        return {"success": True, "player_id": new_player.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/team/{team_id}/delete")
async def delete_team(team_id: int, db: Session = Depends(get_db)):
    try:
        team = db.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")
        
        # Delete all players first
        db.query(Player).filter(Player.team_id == team_id).delete(synchronize_session=False)
        
        # Remove team from any matches
        matches = db.query(Match).filter(
            (Match.team1_id == team_id) | 
            (Match.team2_id == team_id) |
            (Match.winner_id == team_id)
        ).all()
        
        for match in matches:
            if match.team1_id == team_id:
                match.team1_id = None
            if match.team2_id == team_id:
                match.team2_id = None
            if match.winner_id == team_id:
                match.winner_id = None
        
        # Delete the team
        db.delete(team)
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/round/{round_id}/match")
async def add_match(round_id: int, data: dict = Body(...), db: Session = Depends(get_db)):
    try:
        # Get the round
        round = db.query(Round).filter(Round.id == round_id).first()
        if not round:
            raise HTTPException(status_code=404, detail="Round not found")

        # Get the current highest order in this round
        max_order = db.query(func.max(Match.order)).filter(Match.round_id == round_id).scalar() or 0

        # Create new match
        new_match = Match(
            round_id=round_id,
            team1_id=data.get('team1_id'),  # Allow None
            team2_id=data.get('team2_id'),  # Allow None
            is_bye=data.get('is_bye', False),
            bye_description=data.get('bye_description'),
            is_third_place=data.get('is_third_place', False),
            order=max_order + 1
        )

        db.add(new_match)
        db.commit()
        db.refresh(new_match)

        return {"success": True, "match_id": new_match.id}
    except Exception as e:
        db.rollback()
        logger.error(f"Error adding match: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/debug/tournaments")
async def debug_tournaments(db: Session = Depends(get_db)):
    tournaments = db.query(Tournament).all()
    return [{
        "id": t.id,
        "name": t.name,
        "is_active": t.is_active,
        "is_archived": t.is_archived
    } for t in tournaments]

@app.get("/debug/active_tournament")
async def debug_active_tournament(db: Session = Depends(get_db)):
    tournament = db.query(Tournament).filter(Tournament.is_active == True).first()
    if tournament:
        return {
            "id": tournament.id,
            "name": tournament.name,
            "is_active": tournament.is_active,
            "description": tournament.description
        }
    return {"message": "No active tournament found"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)


from fastapi import FastAPI, HTTPException, status, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.requests import Request
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import create_engine, select, inspect
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
import logging
from brackets.models import Match, Round, Team  # Import the models from models.py

# Set up logging
logger = logging.getLogger("brackets")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

@router.post("/admin/update_match/{match_id}")
async def update_match(match_id: int, update_data: dict, db: Session = Depends(get_db)):
    try:
        logger.info("=" * 50)
        logger.info(f"Received update request for match {match_id}")
        logger.info(f"Update data: {update_data}")
        
        # Get the match from the database
        match = db.query(Match).filter(Match.id == match_id).first()
        if not match:
            logger.error(f"Match {match_id} not found")
            return {"success": False, "detail": "Match not found"}

        logger.info(f"Current match state: team1_id={match.team1_id}, team2_id={match.team2_id}")

        # Update team1_id if it's in the request data
        if "team1_id" in update_data:
            new_team1_id = update_data["team1_id"]
            logger.info(f"Updating team1_id from {match.team1_id} to {new_team1_id}")
            
            match.team1_id = new_team1_id  # SQLAlchemy will handle the NULL/None conversion
            if match.winner_id == match.team1_id:
                match.winner_id = None

        # Update team2_id if it's in the request data
        if "team2_id" in update_data:
            new_team2_id = update_data["team2_id"]
            logger.info(f"Updating team2_id from {match.team2_id} to {new_team2_id}")
            
            match.team2_id = new_team2_id  # SQLAlchemy will handle the NULL/None conversion
            if match.winner_id == match.team2_id:
                match.winner_id = None

        # Handle other fields...
        if "winner_id" in update_data:
            match.winner_id = update_data["winner_id"]
        
        if "team1_score" in update_data:
            match.team1_score = update_data["team1_score"]
            
        if "team2_score" in update_data:
            match.team2_score = update_data["team2_score"]

        # Save the changes
        logger.info("Saving changes to database")
        db.commit()
        db.refresh(match)
        
        logger.info(f"New match state: team1_id={match.team1_id}, team2_id={match.team2_id}")
        
        return {
            "success": True,
            "match": {
                "id": match.id,
                "team1_id": match.team1_id,
                "team2_id": match.team2_id,
                "team1_score": match.team1_score,
                "team2_score": match.team2_score,
                "winner_id": match.winner_id,
                "status": match.status.value if hasattr(match, 'status') else None
            }
        }
    except Exception as e:
        logger.error(f"Error updating match: {str(e)}")
        logger.error("Exception details:", exc_info=True)
        db.rollback()
        return {"success": False, "detail": str(e)}

@router.get("/admin/round/{round_id}/matches")
async def get_round_matches(round_id: int, db: Session = Depends(get_db)):
    try:
        print(f"Fetching matches for round {round_id}")
        matches = db.query(Match).filter(Match.round_id == round_id).all()
        
        # Get all teams for the tournament
        tournament_id = db.query(Round).filter(Round.id == round_id).first().tournament_id
        available_teams = db.query(Team).filter(Team.tournament_id == tournament_id).all()
        
        matches_data = []
        for match in matches:
            # Force explicit null handling
            team1_id = None if match.team1_id is None else match.team1_id
            team2_id = None if match.team2_id is None else match.team2_id
            
            print(f"Processing match {match.id}")
            print(f"Raw DB values: team1_id={match.team1_id}, team2_id={match.team2_id}")
            print(f"Processed values: team1_id={team1_id}, team2_id={team2_id}")
            
            match_data = {
                "id": match.id,
                "team1_id": team1_id,  # Using explicitly processed value
                "team2_id": team2_id,  # Using explicitly processed value
                "team1_score": match.team1_score if match.team1_score is not None else 0,
                "team2_score": match.team2_score if match.team2_score is not None else 0,
                "winner_id": match.winner_id if match.winner_id is not None else None,
                "is_bye": match.is_bye if hasattr(match, 'is_bye') else False,
                "bye_description": match.bye_description if hasattr(match, 'bye_description') else None,
                "available_teams": [{"id": team.id, "name": team.name} for team in available_teams]
            }
            
            print(f"Returning match data: {match_data}")
            matches_data.append(match_data)
        
        print(f"Returning {len(matches_data)} matches")
        return matches_data
    except Exception as e:
        print(f"Error fetching matches: {str(e)}")
        print("Exception details:", e.__class__.__name__)
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

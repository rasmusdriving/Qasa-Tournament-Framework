from fastapi import FastAPI, HTTPException
from sqlalchemy.orm import Session
from . import models, schemas
from .database import SessionLocal, engine

app = FastAPI()

# ... existing code ...

@app.post("/admin/update_round_name/{round_id}")
def update_round_name(round_id: int, round_data: schemas.RoundUpdate):
    db = SessionLocal()
    db_round = db.query(models.Round).filter(models.Round.id == round_id).first()
    if db_round is None:
        raise HTTPException(status_code=404, detail="Round not found")
    
    db_round.name = round_data.name
    db.commit()
    db.refresh(db_round)
    return {"success": True}

# ... rest of your code ...

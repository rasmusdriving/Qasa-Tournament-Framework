from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Float, Text, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
import enum
import math

Base = declarative_base()

class Tournament(Base):
    __tablename__ = "tournaments"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String)
    is_active = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)  # Add this line
    teams = relationship("Team", back_populates="tournament")
    rounds = relationship("Round", back_populates="tournament")

    def calculate_rounds(self):
        team_count = len(self.teams)
        if team_count <= 1:
            return 0
        return math.ceil(math.log2(team_count))

class Team(Base):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.id"))
    tournament = relationship("Tournament", back_populates="teams")
    players = relationship("Player", back_populates="team")
    bets = relationship("Bet", back_populates="team")  # Add this line

class Player(Base):
    __tablename__ = "players"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"))
    team = relationship("Team", back_populates="players")

class Bet(Base):
    __tablename__ = "bets"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    email = Column(String)
    amount = Column(Float)
    team_id = Column(Integer, ForeignKey("teams.id"))
    tournament_id = Column(Integer, ForeignKey("tournaments.id"))
    team = relationship("Team", back_populates="bets")  # Add this line
    tournament = relationship("Tournament")  # Add this line if you want to access the tournament directly from a bet

class Round(Base):
    __tablename__ = "rounds"
    id = Column(Integer, primary_key=True, index=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.id"))
    number = Column(Integer)
    tournament = relationship("Tournament", back_populates="rounds")
    matches = relationship("Match", back_populates="round")

class MatchStatus(enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"

class Match(Base):
    __tablename__ = "matches"
    id = Column(Integer, primary_key=True, index=True)
    round_id = Column(Integer, ForeignKey("rounds.id"))
    team1_id = Column(Integer, ForeignKey("teams.id"))
    team2_id = Column(Integer, ForeignKey("teams.id"))
    team1_score = Column(Integer, default=0)
    team2_score = Column(Integer, default=0)
    winner_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    status = Column(Enum(MatchStatus), default=MatchStatus.PENDING)
    position = Column(Integer)
    round = relationship("Round", back_populates="matches")
    team1 = relationship("Team", foreign_keys=[team1_id])
    team2 = relationship("Team", foreign_keys=[team2_id])
    winner = relationship("Team", foreign_keys=[winner_id])
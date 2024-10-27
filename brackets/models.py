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
    bets = relationship("Bet", back_populates="team")
    # Add these relationships
    matches_as_team1 = relationship("Match", foreign_keys="Match.team1_id", back_populates="team1")
    matches_as_team2 = relationship("Match", foreign_keys="Match.team2_id", back_populates="team2")
    matches_as_winner = relationship("Match", foreign_keys="Match.winner_id", back_populates="winner")

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
    round_number = Column(Integer)  # Change this line
    name = Column(String, default="")
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
    is_bye = Column(Boolean, default=False)
    bye_description = Column(String, nullable=True)
    round = relationship("Round", back_populates="matches")
    team1 = relationship("Team", foreign_keys=[team1_id], back_populates="matches_as_team1")
    team2 = relationship("Team", foreign_keys=[team2_id], back_populates="matches_as_team2")
    winner = relationship("Team", foreign_keys=[winner_id], back_populates="matches_as_winner")
    is_ongoing = Column(Boolean, default=False, nullable=False)
    is_third_place = Column(Boolean, default=False)  # Add this line instead of title
    order = Column(Integer, nullable=False, default=0)
    
    # Keep only ONE set of these relationships (remove the duplicates below)
    team1 = relationship("Team", foreign_keys=[team1_id], back_populates="matches_as_team1")
    team2 = relationship("Team", foreign_keys=[team2_id], back_populates="matches_as_team2")
    winner = relationship("Team", foreign_keys=[winner_id], back_populates="matches_as_winner")
    
    # Remove these duplicate relationships
    # team1 = relationship("Team", foreign_keys=[team1_id], back_populates="matches_as_team1")
    # team2 = relationship("Team", foreign_keys=[team2_id], back_populates="matches_as_team2")
    # winner = relationship("Team", foreign_keys=[winner_id], back_populates="matches_as_winner")

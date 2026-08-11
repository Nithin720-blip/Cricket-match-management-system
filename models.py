# pyrefly: ignore [missing-import]
from sqlalchemy import Column, Integer, String, Date, ForeignKey, Enum, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Admin(Base):
    __tablename__ = 'admins'
    admin_id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String(255), nullable=False)

class Venue(Base):
    __tablename__ = 'venue'
    venue_id = Column(Integer, primary_key=True, autoincrement=True)
    venue_name = Column(String(255), unique=True, nullable=False)
    city = Column(String(100))
    capacity = Column(Integer)

class Team(Base):
    __tablename__ = 'team'
    team_id = Column(Integer, primary_key=True, autoincrement=True)
    team_name = Column(String(100), unique=True, nullable=False)
    captain_name = Column(String(100))
    coach_name = Column(String(100))
    home_ground = Column(String(100))
    logo = Column(String(255))
    wins = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    draws = Column(Integer, default=0)
    points = Column(Integer, default=0)

    players = relationship("Player", back_populates="team", cascade="all, delete-orphan")

class Player(Base):
    __tablename__ = 'player'
    player_id = Column(Integer, primary_key=True, autoincrement=True)
    player_name = Column(String(100), nullable=False)
    age = Column(Integer)
    role = Column(Enum('Batsman', 'Bowler', 'All-Rounder', 'Wicketkeeper'), nullable=False)
    team_id = Column(Integer, ForeignKey('team.team_id'), nullable=True)
    player_photo = Column(String(255))

    team = relationship("Team", back_populates="players")
    scorecards = relationship("Scorecard", back_populates="player", cascade="all, delete-orphan")

class Match(Base):
    __tablename__ = 'match'
    match_id = Column(Integer, primary_key=True, autoincrement=True)
    match_date = Column(Date, nullable=False)
    team1_id = Column(Integer, ForeignKey('team.team_id'), nullable=True)
    team2_id = Column(Integer, ForeignKey('team.team_id'), nullable=True)
    venue_id = Column(Integer, ForeignKey('venue.venue_id'), nullable=True)

    team1 = relationship("Team", foreign_keys=[team1_id])
    team2 = relationship("Team", foreign_keys=[team2_id])
    venue = relationship("Venue")
    summary = relationship("MatchSummary", back_populates="match", uselist=False, cascade="all, delete-orphan")
    scorecards = relationship("Scorecard", back_populates="match", cascade="all, delete-orphan")

class MatchSummary(Base):
    __tablename__ = 'match_summary'
    summary_id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(Integer, ForeignKey('match.match_id'), unique=True, nullable=False)
    team1_score = Column(Integer, default=0)
    team1_wickets = Column(Integer, default=0)
    team2_score = Column(Integer, default=0)
    team2_wickets = Column(Integer, default=0)
    result = Column(Text)

    match = relationship("Match", back_populates="summary")

class Scorecard(Base):
    __tablename__ = 'scorecard'
    scorecard_id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(Integer, ForeignKey('match.match_id'), nullable=False)
    player_id = Column(Integer, ForeignKey('player.player_id'), nullable=False)
    runs = Column(Integer, default=0)
    wickets = Column(Integer, default=0)
    runs_conceded = Column(Integer, default=0)
    balls_faced_batting = Column(Integer, default=0)
    balls_bowled_bowling = Column(Integer, default=0)

    match = relationship("Match", back_populates="scorecards")
    player = relationship("Player", back_populates="scorecards")

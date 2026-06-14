from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime, date

class UserTeamLink(SQLModel, table=True):
    user_id: Optional[int] = Field(default=None, foreign_key="user.id", primary_key=True)
    team_id: Optional[int] = Field(default=None, foreign_key="team.id", primary_key=True)

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    is_active: bool = Field(default=True)

    teams: List["Team"] = Relationship(back_populates="admins", link_model=UserTeamLink)

class Team(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    season: str
    innings_per_game: int
    max_pitcher_innings_per_game: int
    max_pitcher_innings_per_7_days: int = Field(default=4)
    late_inning_weight: float = Field(default=1.5)
    language: str = Field(default='fr')
    pitch_count_rules_json: str
    division: Optional[str] = None
    classe: Optional[str] = None
    default_league: Optional[str] = None
    lineup_print_version: str = Field(default="baseball_quebec")
    scoresheet_version: str = Field(default="baseball_quebec")

    players: List["Player"] = Relationship(back_populates="team")
    admins: List["User"] = Relationship(back_populates="teams", link_model=UserTeamLink)


class Player(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    team_id: int = Field(foreign_key="team.id")
    first_name: str
    last_name: str
    jersey: int
    default_batting_order: Optional[int] = Field(default=None)
    active: bool = Field(default=True)
    is_substitute: bool = Field(default=False)
    is_coach: bool = Field(default=False)
    coach_type: Optional[str] = Field(default=None)

    team: Optional[Team] = Relationship(back_populates="players")
    position_scores: List["PositionScore"] = Relationship(back_populates="player")

class PlayerCreate(SQLModel):
    first_name: str
    last_name: str
    jersey: int
    default_batting_order: Optional[int] = None
    active: bool = True
    is_substitute: bool = False
    is_coach: bool = False
    coach_type: Optional[str] = None

class PlayerUpdate(SQLModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    jersey: Optional[int] = None
    default_batting_order: Optional[int] = None
    active: Optional[bool] = None
    is_substitute: Optional[bool] = None
    is_coach: Optional[bool] = None
    coach_type: Optional[str] = None

class PositionScore(SQLModel, table=True):
    player_id: int = Field(foreign_key="player.id", primary_key=True)
    position: int = Field(primary_key=True)
    score: int = Field(default=0)
    is_forbidden: bool = Field(default=False)

    player: Optional[Player] = Relationship(back_populates="position_scores")

class Game(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    team_id: int = Field(foreign_key="team.id")
    date: date
    game_number: Optional[str] = None
    opponent: Optional[str] = None
    venue: Optional[str] = None
    home_away: Optional[str] = None  # 'H' or 'A'
    innings_played: Optional[int] = None
    result_runs_for: Optional[int] = None
    result_runs_against: Optional[int] = None
    mode: str = Field(default="compete")  # 'compete' or 'develop'
    game_type: str = Field(default="season")  # 'season', 'postseason', or 'tournament'
    league: Optional[str] = None
    notes: Optional[str] = None

class GameCreate(SQLModel):
    date: date
    game_number: Optional[str] = None
    opponent: Optional[str] = None
    venue: Optional[str] = None
    home_away: Optional[str] = None
    innings_played: Optional[int] = None
    result_runs_for: Optional[int] = None
    result_runs_against: Optional[int] = None
    mode: str = "compete"
    game_type: str = "season"
    league: Optional[str] = None
    notes: Optional[str] = None

class Availability(SQLModel, table=True):
    game_id: int = Field(foreign_key="game.id", primary_key=True)
    player_id: int = Field(foreign_key="player.id", primary_key=True)
    status: str = Field(default="available")  # available, absent, late, injured
    injury_inning: Optional[int] = Field(default=None)

class BattingLine(SQLModel, table=True):
    game_id: int = Field(foreign_key="game.id", primary_key=True)
    player_id: int = Field(foreign_key="player.id", primary_key=True)
    batting_order: Optional[int] = None
    singles: int = Field(default=0)
    doubles: int = Field(default=0)
    triples: int = Field(default=0)
    hr: int = Field(default=0)
    bb: int = Field(default=0)
    bbi: int = Field(default=0)       # intentional walk
    hbp: int = Field(default=0)       # hit by pitch (FA)
    sac: int = Field(default=0)
    intf: int = Field(default=0)      # interference (INT)
    kd: int = Field(default=0)        # K looking
    ke: int = Field(default=0)        # K swinging
    outs_not_k: int = Field(default=0)
    fc: int = Field(default=0)        # fielder's choice (OPT)
    roe: int = Field(default=0)       # reached on error
    rbi: int = Field(default=0)
    r: int = Field(default=0)         # runs scored
    sb: int = Field(default=0)        # stolen bases (BV)

class PitchingAppearance(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    game_id: int = Field(foreign_key="game.id")
    player_id: int = Field(foreign_key="player.id")
    inning_entered: float
    inning_exited: float
    ip_outs: int              # innings pitched × 3 (e.g. 1.2 IP = 5)
    runs_allowed: int = Field(default=0)
    k: int = Field(default=0)
    bb: int = Field(default=0)
    hbp: int = Field(default=0)
    pitch_count: Optional[int] = None

class Lineup(SQLModel, table=True):
    game_id: int = Field(foreign_key="game.id", primary_key=True)
    inning: int = Field(primary_key=True)
    player_id: int = Field(foreign_key="player.id", primary_key=True)
    position: int  # 1-9 field, 0 = bench
    locked: bool = Field(default=False)

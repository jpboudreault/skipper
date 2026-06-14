from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select
from app.models import Team, Player, PositionScore, User, PlayerUpdate, PlayerCreate
from app.db import engine, get_session, create_db_and_tables
from typing import List
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from app.auth import verify_google_token, create_access_token, get_current_user, get_active_team
from datetime import datetime, timedelta

import json
import traceback
import sys
from fastapi.responses import JSONResponse
from fastapi.exception_handlers import http_exception_handler as default_http_exception_handler

def seed_tenants_and_admins():
    config_path = os.path.join(os.path.dirname(__file__), "tenants.json")
    if not os.path.exists(config_path):
        print(f"Tenants config not found at {config_path}, skipping multi-tenant seed.")
        return
        
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            tenants = json.load(f)
    except Exception as e:
        print(f"Failed to read tenants config: {e}")
        return

    with Session(engine) as session:
        from app.models import UserTeamLink
        for tenant in tenants:
            # Check if team already exists by name and season
            team = session.exec(
                select(Team).where(Team.name == tenant["name"], Team.season == tenant["season"])
            ).first()
            
            pitch_rules_str = json.dumps(tenant.get("pitch_count_rules", {}))
            
            if not team:
                print(f"Seeding team: {tenant['name']} for season {tenant['season']}")
                team = Team(
                    name=tenant["name"],
                    season=tenant["season"],
                    innings_per_game=tenant.get("innings_per_game", 6),
                    max_pitcher_innings_per_game=tenant.get("max_pitcher_innings_per_game", 2),
                    max_pitcher_innings_per_7_days=tenant.get("max_pitcher_innings_per_7_days", 4),
                    late_inning_weight=tenant.get("late_inning_weight", 1.5),
                    language=tenant.get("language", "fr"),
                    pitch_count_rules_json=pitch_rules_str,
                    division=tenant.get("division"),
                    classe=tenant.get("classe"),
                    default_league=tenant.get("default_league"),
                    lineup_print_version=tenant.get("lineup_print_version", "baseball_quebec"),
                    scoresheet_version=tenant.get("scoresheet_version", "baseball_quebec"),
                )
                session.add(team)
                session.commit()
                session.refresh(team)
            else:
                # Update existing team settings to keep them synced
                team.innings_per_game = tenant.get("innings_per_game", team.innings_per_game)
                team.max_pitcher_innings_per_game = tenant.get("max_pitcher_innings_per_game", team.max_pitcher_innings_per_game)
                team.max_pitcher_innings_per_7_days = tenant.get("max_pitcher_innings_per_7_days", team.max_pitcher_innings_per_7_days)
                team.late_inning_weight = tenant.get("late_inning_weight", team.late_inning_weight)
                team.language = tenant.get("language", team.language)
                team.pitch_count_rules_json = pitch_rules_str
                team.division = tenant.get("division", team.division)
                team.classe = tenant.get("classe", team.classe)
                team.default_league = tenant.get("default_league", team.default_league)
                team.lineup_print_version = tenant.get("lineup_print_version", team.lineup_print_version)
                team.scoresheet_version = tenant.get("scoresheet_version", team.scoresheet_version)
                session.add(team)
                session.commit()
                session.refresh(team)

            # Seed admins for this team
            for email in tenant.get("admin_emails", []):
                email = email.strip().lower()
                if not email:
                    continue
                user = session.exec(select(User).where(User.email == email)).first()
                if not user:
                    print(f"Seeding admin user: {email}")
                    user = User(email=email, is_active=True)
                    session.add(user)
                    session.commit()
                    session.refresh(user)

                # Link user to team if not already linked
                link = session.exec(
                    select(UserTeamLink).where(UserTeamLink.user_id == user.id, UserTeamLink.team_id == team.id)
                ).first()
                if not link:
                    print(f"Linking user {email} to team {team.name}")
                    new_link = UserTeamLink(user_id=user.id, team_id=team.id)
                    session.add(new_link)
                    session.commit()

app = FastAPI(title="Skipper API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    print("\n" + "="*80)
    print("!!! HTTP 500 INTERNAL SERVER ERROR !!!")
    print(f"Path: {request.url.path}")
    print(f"Method: {request.method}")
    print(f"Exception: {type(exc).__name__}: {exc}")
    print("="*80)
    traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)
    print("="*80 + "\n")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"}
    )

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 500:
        print("\n" + "="*80)
        print("!!! HTTP 500 INTERNAL SERVER ERROR (HTTPException) !!!")
        print(f"Path: {request.url.path}")
        print(f"Method: {request.method}")
        print(f"Detail: {exc.detail}")
        print("="*80 + "\n")
    return await default_http_exception_handler(request, exc)

def run_migrations():
    """Safely apply schema migrations that create_all won't handle (adding columns to existing tables)."""
    from sqlmodel import text
    with engine.connect() as conn:
        migrations = [
            # Add batting_order column to battingline if missing
            ("battingline", "batting_order", "ALTER TABLE battingline ADD COLUMN batting_order INTEGER"),
            # Add is_substitute column to player if missing
            ("player", "is_substitute", "ALTER TABLE player ADD COLUMN is_substitute INTEGER NOT NULL DEFAULT 0"),
            # Add is_coach column to player if missing
            ("player", "is_coach", "ALTER TABLE player ADD COLUMN is_coach INTEGER NOT NULL DEFAULT 0"),
            # Add coach_type column to player if missing
            ("player", "coach_type", "ALTER TABLE player ADD COLUMN coach_type TEXT"),
            # Add hbp column to pitchingappearance if missing
            ("pitchingappearance", "hbp", "ALTER TABLE pitchingappearance ADD COLUMN hbp INTEGER NOT NULL DEFAULT 0"),
            ("team", "division", "ALTER TABLE team ADD COLUMN division TEXT"),
            ("team", "classe", "ALTER TABLE team ADD COLUMN classe TEXT"),
            ("team", "default_league", "ALTER TABLE team ADD COLUMN default_league TEXT"),
            ("team", "lineup_print_version", "ALTER TABLE team ADD COLUMN lineup_print_version TEXT NOT NULL DEFAULT 'baseball_quebec'"),
            ("team", "scoresheet_version", "ALTER TABLE team ADD COLUMN scoresheet_version TEXT NOT NULL DEFAULT 'baseball_quebec'"),
            ("game", "league", "ALTER TABLE game ADD COLUMN league TEXT"),
            ("availability", "injury_inning", "ALTER TABLE availability ADD COLUMN injury_inning INTEGER"),
        ]
        for table, col, sql in migrations:
            try:
                # Check if column exists
                result = conn.execute(text(f"PRAGMA table_info({table})"))
                cols = [row[1] for row in result.fetchall()]
                if col not in cols:
                    print(f"[migration] Adding column '{col}' to table '{table}'")
                    conn.execute(text(sql))
                    conn.commit()
            except Exception as e:
                print(f"[migration] Skipped {table}.{col}: {e}")

@app.on_event("startup")
def on_startup():
    dev_mode = os.environ.get("DEV_MODE", "true").lower() == "true"
    if not dev_mode:
        secret = os.environ.get("JWT_SECRET", "")
        if not secret or secret == "super-secret-default-key":
            raise RuntimeError("JWT_SECRET must be set to a secure value when DEV_MODE=false")
    create_db_and_tables()
    run_migrations()
    seed_tenants_and_admins()

# Register game routes
from app.game_routes import router as game_router
app.include_router(game_router, prefix="/api")

# Register stats routes
from app.stats_routes import router as stats_router
app.include_router(stats_router, prefix="/api")

@app.get("/api/config")
def read_config():
    key = os.environ.get("ANTHROPIC_API_KEY")
    is_valid = bool(key and key.strip() and "your_anthropic_api" not in key)
    google_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    return {
        "photo_ingestion_enabled": is_valid,
        "google_client_id": google_id
    }

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Skipper API is running"}

@app.post("/api/teams/", response_model=Team)
def create_team(team: Team, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    current_user = session.get(User, current_user.id)
    session.add(team)
    session.commit()
    session.refresh(team)
    
    from app.models import UserTeamLink
    link = UserTeamLink(user_id=current_user.id, team_id=team.id)
    session.add(link)
    session.commit()
    session.refresh(team)
    return team

@app.get("/api/teams/", response_model=List[Team])
def read_teams(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    current_user = session.get(User, current_user.id)
    return current_user.teams

@app.post("/api/players/", response_model=Player)
def create_player(player_data: PlayerCreate, session: Session = Depends(get_session), active_team: Team = Depends(get_active_team)):
    player = Player(**player_data.model_dump(), team_id=active_team.id)
    session.add(player)
    session.commit()
    session.refresh(player)
    return player

@app.get("/api/players/", response_model=List[Player])
def read_players(session: Session = Depends(get_session), active_team: Team = Depends(get_active_team)):
    players = session.exec(select(Player).where(Player.team_id == active_team.id)).all()
    return players

@app.put("/api/players/{player_id}", response_model=Player)
def update_player(player_id: int, player_update: PlayerUpdate, session: Session = Depends(get_session), active_team: Team = Depends(get_active_team)):
    db_player = session.exec(select(Player).where(Player.id == player_id, Player.team_id == active_team.id)).first()
    if not db_player:
        raise HTTPException(status_code=404, detail="Player not found on this team")
    
    player_data = player_update.model_dump(exclude_unset=True)
    for key, value in player_data.items():
        setattr(db_player, key, value)
        
    session.add(db_player)
    session.commit()
    session.refresh(db_player)
    return db_player

@app.delete("/api/players/{player_id}")
def delete_player(player_id: int, session: Session = Depends(get_session), active_team: Team = Depends(get_active_team)):
    db_player = session.exec(select(Player).where(Player.id == player_id, Player.team_id == active_team.id)).first()
    if not db_player:
        raise HTTPException(status_code=404, detail="Player not found on this team")
        
    session.delete(db_player)
    session.commit()
    return {"ok": True}

class PositionScoreUpdate(BaseModel):
    score: int
    is_forbidden: bool

@app.get("/api/position-scores/", response_model=List[PositionScore])
def read_position_scores(session: Session = Depends(get_session), active_team: Team = Depends(get_active_team)):
    scores = session.exec(
        select(PositionScore).join(Player).where(Player.team_id == active_team.id)
    ).all()
    return scores

@app.put("/api/position-scores/{player_id}/{position}", response_model=PositionScore)
def update_position_score(player_id: int, position: int, score_update: PositionScoreUpdate, session: Session = Depends(get_session), active_team: Team = Depends(get_active_team)):
    player = session.exec(select(Player).where(Player.id == player_id, Player.team_id == active_team.id)).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found on this team")

    db_score = session.exec(select(PositionScore).where(PositionScore.player_id == player_id, PositionScore.position == position)).first()
    if not db_score:
        db_score = PositionScore(player_id=player_id, position=position, score=score_update.score, is_forbidden=score_update.is_forbidden)
        session.add(db_score)
    else:
        db_score.score = score_update.score
        db_score.is_forbidden = score_update.is_forbidden
        session.add(db_score)
    
    session.commit()
    session.refresh(db_score)
    return db_score

class GoogleLoginRequest(BaseModel):
    credential: str

@app.post("/api/auth/google")
def google_login(request: GoogleLoginRequest, session: Session = Depends(get_session)):
    idinfo = verify_google_token(request.credential)
    email = idinfo.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Invalid Google token payload: email missing")
        
    email_lower = email.strip().lower()
    user = session.exec(select(User).where(User.email == email_lower)).first()
    is_dev = os.environ.get("DEV_MODE", "true").lower() == "true"
    
    if not user:
        if is_dev:
            print(f"DEV MODE: Automatically creating user for '{email_lower}' via Google")
            user = User(email=email_lower, is_active=True)
            session.add(user)
            session.commit()
            session.refresh(user)
            
            # Automatically link newly created dev user to all existing teams
            from app.models import UserTeamLink
            teams = session.exec(select(Team)).all()
            for t in teams:
                link = UserTeamLink(user_id=user.id, team_id=t.id)
                session.add(link)
            session.commit()
            session.refresh(user)
        else:
            print(f"DEBUG LOGIN: Google email '{email_lower}' not found in database.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Your email is not authorized to access this app."
            )
            
    # Valid user, generate JWT
    access_token = create_access_token(data={"sub": user.email, "user_id": user.id})
    return {"access_token": access_token, "token_type": "bearer"}



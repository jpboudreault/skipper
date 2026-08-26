from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select
from app.models import Team, Player, PositionScore, User, PlayerUpdate, PlayerCreate
from app.db import engine, get_session, create_db_and_tables
from typing import List
from pydantic import BaseModel
import os
from app.auth import verify_google_token, verify_microsoft_token, login_user_by_email, get_current_user, get_active_team
from app.i18n.errors import raise_api_error

import json
import logging
from fastapi.responses import JSONResponse
from app.i18n import parse_locale, localize_detail, translate

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("skipper")

def seed_tenants_and_admins():
    config_path = os.path.join(os.path.dirname(__file__), "tenants.json")
    if not os.path.exists(config_path):
        logger.info("Tenants config not found at %s, skipping multi-tenant seed.", config_path)
        return

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            tenants = json.load(f)
    except Exception as e:
        logger.error("Failed to read tenants config: %s", e)
        return

    with Session(engine) as session:
        from app.models import UserTeamLink
        for tenant in tenants:
            # Check if team already exists by name and season
            team = session.exec(
                select(Team).where(Team.name == tenant["name"], Team.season == tenant["season"])
            ).first()
            
            pitch_rules_str = (
                json.dumps(tenant.get("pitch_count_rules") or {})
                if "pitch_count_rules" in tenant
                else None
            )
            integration_config = (
                dict(tenant.get("integration_config") or {})
                if "integration_config" in tenant
                else None
            )
            if tenant.get("standings_points"):
                if integration_config is None:
                    integration_config = {}
                integration_config["standings_points"] = tenant["standings_points"]
            integration_config_str = (
                json.dumps(integration_config) if integration_config else None
            )
            
            if not team:
                logger.info("Seeding team: %s for season %s", tenant['name'], tenant['season'])
                team = Team(
                    name=tenant["name"],
                    season=tenant["season"],
                    innings_per_game=tenant.get("innings_per_game", 6),
                    max_pitcher_innings_per_game=tenant.get("max_pitcher_innings_per_game", 2),
                    max_pitcher_innings_per_7_days=tenant.get("max_pitcher_innings_per_7_days", 4),
                    late_inning_weight=tenant.get("late_inning_weight", 1.5),
                    language=tenant.get("language", "fr"),
                    pitch_count_rules_json=pitch_rules_str or "{}",
                    division=tenant.get("division"),
                    classe=tenant.get("classe"),
                    default_league=tenant.get("default_league"),
                    lineup_print_version=tenant.get("lineup_print_version", "baseball_quebec"),
                    scoresheet_version=tenant.get("scoresheet_version", "baseball_quebec"),
                    integration_version=tenant.get("integration_version"),
                    integration_config_json=integration_config_str,
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
                if pitch_rules_str is not None:
                    team.pitch_count_rules_json = pitch_rules_str
                team.division = tenant.get("division", team.division)
                team.classe = tenant.get("classe", team.classe)
                team.default_league = tenant.get("default_league", team.default_league)
                team.lineup_print_version = tenant.get("lineup_print_version", team.lineup_print_version)
                team.scoresheet_version = tenant.get("scoresheet_version", team.scoresheet_version)
                if "integration_version" in tenant:
                    team.integration_version = tenant.get("integration_version")
                if integration_config is not None:
                    team.integration_config_json = integration_config_str
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
                    logger.info("Seeding admin user: %s", email)
                    user = User(email=email, is_active=True)
                    session.add(user)
                    session.commit()
                    session.refresh(user)

                # Link user to team if not already linked
                link = session.exec(
                    select(UserTeamLink).where(UserTeamLink.user_id == user.id, UserTeamLink.team_id == team.id)
                ).first()
                if not link:
                    logger.info("Linking user %s to team %s", email, team.name)
                    new_link = UserTeamLink(user_id=user.id, team_id=team.id)
                    session.add(new_link)
                    session.commit()

app = FastAPI(title="Skipper API")

# CORS origins are configurable via CORS_ALLOW_ORIGINS (comma-separated). The API
# authenticates with bearer tokens (not cookies), so when origins are wide open ("*")
# we must keep allow_credentials=False to stay spec-compliant.
_cors_origins_env = os.environ.get("CORS_ALLOW_ORIGINS", "*").strip()
if _cors_origins_env == "*":
    _allow_origins = ["*"]
    _allow_credentials = False
else:
    _allow_origins = [o.strip() for o in _cors_origins_env.split(",") if o.strip()]
    _allow_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(
        "Unhandled 500 on %s %s: %s",
        request.method,
        request.url.path,
        f"{type(exc).__name__}: {exc}",
        exc_info=exc,
    )
    locale = parse_locale(request.headers.get("accept-language"))
    return JSONResponse(
        status_code=500,
        content={"detail": translate("internal_server_error", locale=locale)}
    )

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 500:
        logger.error(
            "HTTP 500 on %s %s: %s", request.method, request.url.path, exc.detail
        )
    locale = parse_locale(request.headers.get("accept-language"))
    detail = localize_detail(exc.detail, locale)
    return JSONResponse(status_code=exc.status_code, content={"detail": detail})

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
            ("game", "external_source", "ALTER TABLE game ADD COLUMN external_source TEXT"),
            ("game", "external_game_id", "ALTER TABLE game ADD COLUMN external_game_id TEXT"),
            ("team", "integration_version", "ALTER TABLE team ADD COLUMN integration_version TEXT"),
            ("team", "integration_config_json", "ALTER TABLE team ADD COLUMN integration_config_json TEXT"),
            ("availability", "injury_inning", "ALTER TABLE availability ADD COLUMN injury_inning INTEGER"),
            # Audit timestamps (nullable for pre-existing rows; SQLite disallows CURRENT_TIMESTAMP defaults on ADD COLUMN)
            ("player", "created_at", "ALTER TABLE player ADD COLUMN created_at TIMESTAMP"),
            ("player", "updated_at", "ALTER TABLE player ADD COLUMN updated_at TIMESTAMP"),
            ("game", "created_at", "ALTER TABLE game ADD COLUMN created_at TIMESTAMP"),
            ("game", "updated_at", "ALTER TABLE game ADD COLUMN updated_at TIMESTAMP"),
            (
                "team",
                "compete_score_tolerance_pct",
                "ALTER TABLE team ADD COLUMN compete_score_tolerance_pct REAL NOT NULL DEFAULT 15.0",
            ),
        ]
        for table, col, sql in migrations:
            try:
                # Check if column exists
                result = conn.execute(text(f"PRAGMA table_info({table})"))
                cols = [row[1] for row in result.fetchall()]
                if col not in cols:
                    logger.info("[migration] Adding column '%s' to table '%s'", col, table)
                    conn.execute(text(sql))
                    conn.commit()
            except Exception as e:
                logger.warning("[migration] Skipped %s.%s: %s", table, col, e)

        # One-time: legacy win-focused "compete" games become "optimal"
        try:
            conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS _schema_migration "
                    "(name TEXT PRIMARY KEY, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
                )
            )
            conn.commit()
            row = conn.execute(
                text("SELECT 1 FROM _schema_migration WHERE name = 'game_mode_compete_to_optimal'")
            ).fetchone()
            if row is None:
                logger.info("[migration] Renaming legacy game mode compete -> optimal")
                conn.execute(text("UPDATE game SET mode = 'optimal' WHERE mode = 'compete'"))
                conn.execute(
                    text(
                        "INSERT INTO _schema_migration (name) VALUES ('game_mode_compete_to_optimal')"
                    )
                )
                conn.commit()
        except Exception as e:
            logger.warning("[migration] Skipped game_mode_compete_to_optimal: %s", e)

@app.on_event("startup")
def on_startup():
    dev_mode = os.environ.get("DEV_MODE", "false").lower() == "true"
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
    microsoft_id = os.environ.get("MICROSOFT_CLIENT_ID", "")
    return {
        "photo_ingestion_enabled": is_valid,
        "google_client_id": google_id,
        "microsoft_client_id": microsoft_id,
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
        raise_api_error(404, "player_not_found", player_id=player_id)
    
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
        raise_api_error(404, "player_not_found", player_id=player_id)
        
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
        raise_api_error(404, "player_not_found", player_id=player_id)

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

class MicrosoftLoginRequest(BaseModel):
    id_token: str

@app.post("/api/auth/google")
def google_login(request: GoogleLoginRequest, session: Session = Depends(get_session)):
    idinfo = verify_google_token(request.credential)
    email = idinfo.get("email")
    if not email:
        raise_api_error(400, "google_email_missing")
    return login_user_by_email(email, "Google", session)

@app.post("/api/auth/microsoft")
def microsoft_login(request: MicrosoftLoginRequest, session: Session = Depends(get_session)):
    payload = verify_microsoft_token(request.id_token)
    email = payload.get("email") or payload.get("preferred_username")
    if not email:
        raise_api_error(400, "microsoft_email_missing")
    return login_user_by_email(email, "Microsoft", session)



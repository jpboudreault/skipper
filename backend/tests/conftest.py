import pytest
import pytest_asyncio
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine, Session
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db import get_session
from app.auth import get_current_user
from app.models import User
import os

# Use an in-memory SQLite database for testing
sqlite_url = "sqlite://"
engine = create_engine(
    sqlite_url,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

from fastapi import Depends
from sqlmodel import select

def override_get_session():
    with Session(engine) as session:
        yield session

def override_get_current_user(session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.id == 1)).first()
    if not user:
        user = User(id=1, email="test@example.com", is_active=True)
        session.add(user)
        session.commit()
        session.refresh(user)
    
    # Auto-link the user to all teams in the database for seamless testing
    from app.models import Team, UserTeamLink
    teams = session.exec(select(Team)).all()
    for team in teams:
        link = session.exec(select(UserTeamLink).where(UserTeamLink.user_id == user.id, UserTeamLink.team_id == team.id)).first()
        if not link:
            new_link = UserTeamLink(user_id=user.id, team_id=team.id)
            session.add(new_link)
    session.commit()
    session.refresh(user)
    return user

@pytest.fixture(name="session")
def session_fixture():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        # Seed a default team with id=1 so that basic single-team tests have a team ready
        from app.models import Team
        default_team = Team(
            id=1,
            name="Default Team",
            season="2026",
            innings_per_game=6,
            max_pitcher_innings_per_game=2,
            pitch_count_rules_json="{}"
        )
        session.add(default_team)
        session.commit()
        yield session
    SQLModel.metadata.drop_all(engine)

class PrefixedAsyncClient(AsyncClient):
    async def request(self, method, url, *args, **kwargs):
        url_str = str(url)
        # Automatically prepend /api to relative backend test requests
        if url_str.startswith("/") and not url_str.startswith("/api") and url_str != "/":
            url = f"/api{url_str}"
        return await super().request(method, url, *args, **kwargs)

@pytest_asyncio.fixture(name="client")
async def client_fixture(session):
    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_user] = override_get_current_user
    async with PrefixedAsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()

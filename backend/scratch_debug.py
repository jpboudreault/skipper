import asyncio
from httpx import AsyncClient, ASGITransport
from fastapi import Depends
from app.main import app
from app.db import get_session
from app.auth import get_current_user
from app.models import User, Team, UserTeamLink
from sqlmodel import Session, select, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

async def main():
    # Set up memory db
    sqlite_url = "sqlite://"
    engine = create_engine(
        sqlite_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    
    def override_get_session():
        with Session(engine) as session:
            yield session

    def override_get_current_user(session: Session = Depends(override_get_session)):
        user = session.exec(select(User).where(User.id == 1)).first()
        if not user:
            user = User(id=1, email="test@example.com", is_active=True)
            session.add(user)
            session.commit()
            session.refresh(user)
        return user

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_user] = override_get_current_user
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create a team
        res = await client.post("/teams/", json={
            "name": "Test Team", "season": "2025", "innings_per_game": 5,
            "max_pitcher_innings_per_game": 3, "max_pitcher_innings_per_7_days": 4,
            "late_inning_weight": 1.5, "language": "en", "pitch_count_rules_json": "{}"
        })
        print("POST STATUS:", res.status_code)
        print("POST BODY:", res.text)

        # Get teams
        res2 = await client.get("/teams/")
        print("GET STATUS:", res2.status_code)
        print("GET BODY:", res2.text)

if __name__ == "__main__":
    asyncio.run(main())



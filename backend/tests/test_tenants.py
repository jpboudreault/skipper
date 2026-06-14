import pytest
from httpx import AsyncClient
from sqlmodel import Session, select
from app.main import app
from app.auth import get_current_user
from app.models import User, Team, UserTeamLink

@pytest.mark.asyncio
async def test_tenant_isolation(client: AsyncClient, session: Session):
    # 1. Create two teams
    team_a = Team(
        name="Team Alpha",
        season="2026",
        innings_per_game=6,
        max_pitcher_innings_per_game=2,
        pitch_count_rules_json="{}"
    )
    team_b = Team(
        name="Team Beta",
        season="2026",
        innings_per_game=7,
        max_pitcher_innings_per_game=3,
        pitch_count_rules_json="{}"
    )
    session.add(team_a)
    session.add(team_b)
    session.commit()
    session.refresh(team_a)
    session.refresh(team_b)

    # Create a user linked only to Team Alpha
    user_alpha = User(email="coach_alpha@example.com", is_active=True)
    session.add(user_alpha)
    session.commit()
    session.refresh(user_alpha)

    link = UserTeamLink(user_id=user_alpha.id, team_id=team_a.id)
    session.add(link)
    session.commit()

    # Override get_current_user to return coach_alpha
    def override_coach_alpha():
        # Retrieve user inside the session context of active request/test
        return session.exec(select(User).where(User.id == user_alpha.id)).first()

    app.dependency_overrides[get_current_user] = override_coach_alpha

    try:
        # A. Fetch teams list - should only return Team Alpha
        res = await client.get("/teams/")
        assert res.status_code == 200
        teams = res.json()
        assert len(teams) == 1
        assert teams[0]["name"] == "Team Alpha"

        # B. Make a request with no header - should fallback to Team Alpha (authorized)
        # Create a player on Team Alpha
        player_res = await client.post("/players/", json={
            "first_name": "Johnny",
            "last_name": "Alpha",
            "jersey": 10,
            "active": True
        })
        assert player_res.status_code == 200
        player = player_res.json()
        assert player["team_id"] == team_a.id

        # C. Make a request passing Team Alpha ID explicitly in the header - should succeed
        player_res_2 = await client.post("/players/", json={
            "first_name": "Sammy",
            "last_name": "Alpha",
            "jersey": 11,
            "active": True
        }, headers={"X-Active-Team-ID": str(team_a.id)})
        assert player_res_2.status_code == 200

        # D. Make a request passing Team Beta ID (unauthorized) - should be 403 Forbidden
        bad_player_res = await client.post("/players/", json={
            "first_name": "Imposter",
            "last_name": "Beta",
            "jersey": 99,
            "active": True
        }, headers={"X-Active-Team-ID": str(team_b.id)})
        assert bad_player_res.status_code == 403
        assert bad_player_res.json()["detail"] == "Not authorized for this team"

    finally:
        # Clean up dependency override so other tests are unaffected
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]

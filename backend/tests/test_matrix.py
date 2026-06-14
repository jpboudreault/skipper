import pytest
from httpx import AsyncClient
from app.models import Team, Player

@pytest.mark.asyncio
async def test_update_and_get_position_scores(client: AsyncClient, session):
    # Setup: Create a team and a player
    team_response = await client.post("/teams/", json={
        "name": "Test Team",
        "season": "2025",
        "innings_per_game": 7,
        "max_pitcher_innings_per_game": 3,
        "max_pitcher_innings_per_7_days": 4,
        "late_inning_weight": 1.5,
        "language": "en",
        "pitch_count_rules_json": "{}"
    })
    team_data = team_response.json()
    team_id = team_data["id"]
    
    player_response = await client.post("/players/", json={
        "first_name": "John",
        "last_name": "Doe",
        "jersey": 10,
        "active": True
    })
    player_data = player_response.json()
    player_id = player_data["id"]
    
    # 1. Initially, there should be no position scores
    get_res = await client.get("/position-scores/")
    assert get_res.status_code == 200
    assert len(get_res.json()) == 0

    # 2. Update a position score (upsert/create)
    # Position 1 = Pitcher, Score = 8, not forbidden
    put_res = await client.put(f"/position-scores/{player_id}/1", json={
        "score": 8,
        "is_forbidden": False
    })
    assert put_res.status_code == 200
    put_data = put_res.json()
    assert put_data["player_id"] == player_id
    assert put_data["position"] == 1
    assert put_data["score"] == 8
    assert put_data["is_forbidden"] is False

    # 3. Verify it appears in GET
    get_res2 = await client.get("/position-scores/")
    assert len(get_res2.json()) == 1
    assert get_res2.json()[0]["score"] == 8

    # 4. Update the same position score (upsert/update)
    put_res2 = await client.put(f"/position-scores/{player_id}/1", json={
        "score": 5,
        "is_forbidden": True
    })
    assert put_res2.status_code == 200
    assert put_res2.json()["score"] == 5
    assert put_res2.json()["is_forbidden"] is True

    # 5. Verify it was updated, not duplicated
    get_res3 = await client.get("/position-scores/")
    assert len(get_res3.json()) == 1
    assert get_res3.json()[0]["score"] == 5
    assert get_res3.json()[0]["is_forbidden"] is True

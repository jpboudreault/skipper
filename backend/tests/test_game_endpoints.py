"""HTTP tests for previously-uncovered game endpoints: pitching CRUD, injury,
pitcher-status, and the public /config endpoint."""
import pytest


async def _make_player(client, jersey=7, **kwargs):
    body = {"first_name": "P", "last_name": str(jersey), "jersey": jersey, "active": True}
    body.update(kwargs)
    res = await client.post("/players/", json=body)
    assert res.status_code == 200
    return res.json()


async def _make_game(client, date="2026-06-01", game_type="season"):
    res = await client.post("/games/", json={"date": date, "mode": "compete", "game_type": game_type})
    assert res.status_code == 200
    return res.json()


@pytest.mark.asyncio
async def test_pitching_crud(client, session):
    player = await _make_player(client, jersey=11)
    game = await _make_game(client)

    put_res = await client.put(f"/games/{game['id']}/pitching", json=[{
        "player_id": player["id"],
        "inning_entered": 1,
        "inning_exited": 3,
        "ip_outs": 6,
        "runs_allowed": 1,
        "k": 4,
        "bb": 1,
        "hbp": 0,
        "pitch_count": 35,
    }])
    assert put_res.status_code == 200

    get_res = await client.get(f"/games/{game['id']}/pitching")
    assert get_res.status_code == 200
    apps = get_res.json()
    assert len(apps) == 1
    assert apps[0]["ip_outs"] == 6
    assert apps[0]["pitch_count"] == 35


@pytest.mark.asyncio
async def test_pitching_rejects_unknown_player(client, session):
    game = await _make_game(client)
    res = await client.put(f"/games/{game['id']}/pitching", json=[{
        "player_id": 99999,
        "inning_entered": 1,
        "inning_exited": 2,
        "ip_outs": 3,
    }])
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_injury_endpoint_sets_inning(client, session):
    player = await _make_player(client, jersey=12)
    game = await _make_game(client)

    res = await client.post(f"/games/{game['id']}/injury", json={
        "player_id": player["id"],
        "injury_inning": 3,
    })
    assert res.status_code == 200

    avail_res = await client.get(f"/games/{game['id']}/availability")
    avail = next(a for a in avail_res.json() if a["player_id"] == player["id"])
    assert avail["injury_inning"] == 3


@pytest.mark.asyncio
async def test_pitcher_status_endpoint(client, session):
    player = await _make_player(client, jersey=13)
    game = await _make_game(client)

    res = await client.get(f"/games/{game['id']}/pitcher-status")
    assert res.status_code == 200
    statuses = res.json()
    entry = next(s for s in statuses if s["player_id"] == player["id"])
    assert entry["eligible"] is True
    assert "pitches_today" in entry
    assert "rest_until" in entry


@pytest.mark.asyncio
async def test_config_endpoint_public(client):
    res = await client.get("/config")
    assert res.status_code == 200
    data = res.json()
    assert "photo_ingestion_enabled" in data
    assert "google_client_id" in data
    assert "microsoft_client_id" in data

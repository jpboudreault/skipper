import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_game_crud(client: AsyncClient, session):
    # Create a team first
    team_res = await client.post("/teams/", json={
        "name": "Test Team", "season": "2025", "innings_per_game": 5,
        "max_pitcher_innings_per_game": 3, "max_pitcher_innings_per_7_days": 4,
        "late_inning_weight": 1.5, "language": "en", "pitch_count_rules_json": "{}"
    })
    team = team_res.json()
    
    # Create a game
    game_res = await client.post("/games/", json={
        "date": "2026-06-01",
        "opponent": "Rival Team", "venue": "Home Field",
        "home_away": "H", "mode": "compete"
    })
    assert game_res.status_code == 200
    game = game_res.json()
    assert game["opponent"] == "Rival Team"
    assert game["mode"] == "compete"

    # List games
    list_res = await client.get("/games/")
    assert len(list_res.json()) == 1

    # Get single game
    get_res = await client.get(f"/games/{game['id']}")
    assert get_res.status_code == 200

    # Update game
    put_res = await client.put(f"/games/{game['id']}", json={
        "date": "2026-06-01",
        "opponent": "Updated Rival", "venue": "Away Field",
        "home_away": "A", "mode": "develop"
    })
    assert put_res.status_code == 200
    assert put_res.json()["opponent"] == "Updated Rival"
    assert put_res.json()["mode"] == "develop"

    # Delete game
    del_res = await client.delete(f"/games/{game['id']}")
    assert del_res.status_code == 200
    list_res2 = await client.get("/games/")
    assert len(list_res2.json()) == 0


@pytest.mark.asyncio
async def test_availability(client: AsyncClient, session):
    # Setup
    team_res = await client.post("/teams/", json={
        "name": "T", "season": "2025", "innings_per_game": 5,
        "max_pitcher_innings_per_game": 3, "max_pitcher_innings_per_7_days": 4,
        "pitch_count_rules_json": "{}"
    })
    team = team_res.json()
    
    player_res = await client.post("/players/", json={
        "first_name": "Jane", "last_name": "Doe", "jersey": 5, "active": True
    })
    player = player_res.json()

    substitute_res = await client.post("/players/", json={
        "first_name": "Sub", "last_name": "Player", "jersey": 6, "active": True, "is_substitute": True
    })
    sub_player = substitute_res.json()

    game_res = await client.post("/games/", json={
        "date": "2026-06-01", "mode": "compete"
    })
    game = game_res.json()

    # Verify auto-seeding of availability
    get_res = await client.get(f"/games/{game['id']}/availability")
    avails = get_res.json()
    assert len(avails) == 2
    player_avail = next(a for a in avails if a["player_id"] == player["id"])
    sub_avail = next(a for a in avails if a["player_id"] == sub_player["id"])
    assert player_avail["status"] == "available"
    assert sub_avail["status"] == "absent"

    # Set availability
    avail_res = await client.put(f"/games/{game['id']}/availability", json=[
        {"player_id": player["id"], "status": "absent"}
    ])
    assert avail_res.status_code == 200

    # Get availability
    get_res = await client.get(f"/games/{game['id']}/availability")
    avails = get_res.json()
    player_avail = next(a for a in avails if a["player_id"] == player["id"])
    assert player_avail["status"] == "absent"


@pytest.mark.asyncio
async def test_batting_crud(client: AsyncClient, session):
    # Setup
    team_res = await client.post("/teams/", json={
        "name": "T", "season": "2025", "innings_per_game": 5,
        "max_pitcher_innings_per_game": 3, "max_pitcher_innings_per_7_days": 4,
        "pitch_count_rules_json": "{}"
    })
    team = team_res.json()

    player_res = await client.post("/players/", json={
        "first_name": "A", "last_name": "B", "jersey": 1, "active": True
    })
    player = player_res.json()

    game_res = await client.post("/games/", json={
        "date": "2026-06-01", "mode": "compete"
    })
    game = game_res.json()

    # Save batting line
    bat_res = await client.put(f"/games/{game['id']}/batting", json=[{
        "player_id": player["id"],
        "singles": 2, "doubles": 1, "hr": 0, "bb": 1,
        "rbi": 3, "r": 2, "sb": 1
    }])
    assert bat_res.status_code == 200

    # Get batting
    get_res = await client.get(f"/games/{game['id']}/batting")
    lines = get_res.json()
    assert len(lines) == 1
    assert lines[0]["singles"] == 2
    assert lines[0]["rbi"] == 3


@pytest.mark.asyncio
async def test_batting_update_preserves_existing_order_when_omitted(client: AsyncClient, session):
    team_res = await client.post("/teams/", json={
        "name": "T", "season": "2025", "innings_per_game": 5,
        "max_pitcher_innings_per_game": 3, "max_pitcher_innings_per_7_days": 4,
        "pitch_count_rules_json": "{}"
    })
    team = team_res.json()

    player_res = await client.post("/players/", json={
        "first_name": "A", "last_name": "B", "jersey": 1, "active": True
    })
    player = player_res.json()

    game_res = await client.post("/games/", json={
        "date": "2026-06-01", "mode": "compete"
    })
    game = game_res.json()

    order_res = await client.put(f"/games/{game['id']}/batting", json=[{
        "player_id": player["id"],
        "batting_order": 4,
        "singles": 1
    }])
    assert order_res.status_code == 200

    stats_res = await client.put(f"/games/{game['id']}/batting", json=[{
        "player_id": player["id"],
        "singles": 2,
        "doubles": 1,
        "hr": 0,
        "bb": 1,
        "rbi": 3,
        "r": 2,
        "sb": 1
    }])
    assert stats_res.status_code == 200

    get_res = await client.get(f"/games/{game['id']}/batting")
    line = get_res.json()[0]
    assert line["batting_order"] == 4
    assert line["singles"] == 2
    assert line["doubles"] == 1


@pytest.mark.asyncio
async def test_batting_ingest(client: AsyncClient, session, monkeypatch):
    # Setup team and player and game
    team_res = await client.post("/teams/", json={
        "name": "Test Team", "season": "2025", "innings_per_game": 5,
        "max_pitcher_innings_per_game": 3, "max_pitcher_innings_per_7_days": 4,
        "pitch_count_rules_json": "{}"
    })
    team = team_res.json()
    
    player_res = await client.post("/players/", json={
        "first_name": "John", "last_name": "Smith", "jersey": 24, "active": True
    })
    player = player_res.json()
    
    game_res = await client.post("/games/", json={
        "date": "2026-06-01", "mode": "compete"
    })
    game = game_res.json()
    
    # 1. Test when ANTHROPIC_API_KEY is not set
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    
    # Send a request with a fake image
    files = {"file": ("test.png", b"fake_bytes", "image/png")}
    ingest_res = await client.post(f"/games/{game['id']}/batting/ingest", files=files)
    assert ingest_res.status_code == 503
    assert "not configured" in ingest_res.json()["detail"]
    
    # 2. Test invalid file type
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake_key")
    files_txt = {"file": ("test.txt", b"some text", "text/plain")}
    ingest_res_txt = await client.post(f"/games/{game['id']}/batting/ingest", files=files_txt)
    assert ingest_res_txt.status_code == 400
    assert "Invalid file type" in ingest_res_txt.json()["detail"]
    
    # 3. Test successful parsing using mocked parse_scoresheet
    async def mock_parse_scoresheet(image_bytes, content_type, players, scoresheet_version=None):
        return [{
            "player_id": player["id"],
            "jersey": 24,
            "name": "John Smith",
            "confidence": 0.95,
            "matched": True,
            "singles": 1,
            "doubles": 1,
            "triples": 0,
            "hr": 0,
            "bb": 1,
            "bbi": 0,
            "hbp": 0,
            "sac": 0,
            "intf": 0,
            "kd": 0,
            "ke": 0,
            "outs_not_k": 1,
            "fc": 0,
            "roe": 0,
            "rbi": 2,
            "r": 1,
            "sb": 0
        }]
    
    monkeypatch.setattr("app.vision.parse_scoresheet", mock_parse_scoresheet)
    
    files_ok = {"file": ("test.png", b"fake_png_bytes", "image/png")}
    ingest_res_ok = await client.post(f"/games/{game['id']}/batting/ingest", files=files_ok)
    assert ingest_res_ok.status_code == 200
    data = ingest_res_ok.json()
    assert "parsed" in data
    assert data["player_count"] == 1
    assert data["parsed"][0]["singles"] == 1
    assert data["parsed"][0]["rbi"] == 2


@pytest.mark.asyncio
async def test_solve_filtering_unavailable_and_coaches(client: AsyncClient, session):
    # 1. Create a team
    team_res = await client.post("/teams/", json={
        "name": "Aces", "season": "2026", "innings_per_game": 5,
        "max_pitcher_innings_per_game": 3, "max_pitcher_innings_per_7_days": 4,
        "pitch_count_rules_json": "{}"
    })
    team = team_res.json()

    # 2. Create players: 8 regular, 2 substitutes, 1 coach
    player_ids = []
    # 8 regular players
    for i in range(8):
        p_res = await client.post("/players/", json={
            "first_name": f"Regular{i}", "last_name": "Player", "jersey": 10 + i, "active": True
        })
        player_ids.append(p_res.json()["id"])
    
    # 2 substitute players (seeded absent by default)
    sub_ids = []
    for i in range(2):
        p_res = await client.post("/players/", json={
            "first_name": f"Sub{i}", "last_name": "Player", "jersey": 20 + i, "active": True, "is_substitute": True
        })
        sub_ids.append(p_res.json()["id"])

    # 1 coach player
    coach_res = await client.post("/players/", json={
        "first_name": "Chef", "last_name": "Coach", "jersey": 99, "active": True, "is_coach": True
    })
    coach_id = coach_res.json()["id"]

    # 3. Create a game (triggers auto-seeding)
    game_res = await client.post("/games/", json={
        "date": "2026-06-01", "mode": "compete"
    })
    game = game_res.json()

    # 4. Verify that the coach was NOT seeded for availability
    get_avail_res = await client.get(f"/games/{game['id']}/availability")
    avails = get_avail_res.json()
    # 8 regulars + 2 substitutes = 10 seeded availability records (excluding coach)
    assert len(avails) == 10
    assert not any(a["player_id"] == coach_id for a in avails)

    # 5. Try solving when we only have 7 available (8 regulars - 1 absent, substitutes are absent by default)
    # Set 1 regular as absent
    await client.put(f"/games/{game['id']}/availability", json=[
        {"player_id": player_ids[0], "status": "absent"}
    ])
    
    # Try solve, should fail because 7 < 9
    solve_fail_res = await client.post(f"/games/{game['id']}/solve")
    assert solve_fail_res.status_code == 400
    assert "Need at least 9 available players" in solve_fail_res.json()["detail"]

    # 6. Mark substitutes as available, so we have 9 available players (7 regulars + 2 substitutes)
    await client.put(f"/games/{game['id']}/availability", json=[
        {"player_id": sub_ids[0], "status": "available"},
        {"player_id": sub_ids[1], "status": "available"}
    ])

    # Pre-populate a lingering lineup cell for the absent regular player to check cleanup
    # We set player_ids[0] (absent regular player) to a locked bench position (0) or field position
    # Let's verify that the solver deletes this cell
    await client.put(f"/games/{game['id']}/lineup", json=[
        {"inning": 1, "player_id": player_ids[0], "position": 0, "locked": True}
    ])

    # 7. Solve lineup, should succeed
    solve_res = await client.post(f"/games/{game['id']}/solve")
    assert solve_res.status_code == 200

    # 8. Fetch the lineup and verify absent and coach players have no assignments
    get_lineup_res = await client.get(f"/games/{game['id']}/lineup")
    lineup_cells = get_lineup_res.json()
    
    # No cells should exist for player_ids[0] (the absent regular) or the coach
    assert not any(c["player_id"] == player_ids[0] for c in lineup_cells)
    assert not any(c["player_id"] == coach_id for c in lineup_cells)

    # Make sure we have 9 fielders assigned per inning and no duplicate positions
    for inn in range(1, 6):
        inn_cells = [c for c in lineup_cells if c["inning"] == inn]
        assigned_fielders = [c for c in inn_cells if c["position"] > 0]
        benched_fielders = [c for c in inn_cells if c["position"] == 0]
        
        # 9 fielders
        assert len(assigned_fielders) == 9
        # 0 benched (since we have exactly 9 available players)
        assert len(benched_fielders) == 0
        # No duplicates
        positions = [c["position"] for c in assigned_fielders]
        assert len(set(positions)) == 9


@pytest.mark.asyncio
async def test_solve_lock_validations(client: AsyncClient, session):
    # 1. Create a team
    team_res = await client.post("/teams/", json={
        "name": "Validation Team", "season": "2026", "innings_per_game": 5,
        "max_pitcher_innings_per_game": 2, "max_pitcher_innings_per_7_days": 4,
        "pitch_count_rules_json": "{}"
    })
    team = team_res.json()

    # Create 9 players
    player_ids = []
    for i in range(9):
        p_res = await client.post("/players/", json={
            "first_name": f"P{i}", "last_name": "Player", "jersey": 10 + i, "active": True
        })
        player_ids.append(p_res.json()["id"])

    # Create a game
    game_res = await client.post("/games/", json={
        "date": "2026-06-01", "mode": "compete"
    })
    game = game_res.json()

    # A. Test duplicate positions (e.g. P0 and P1 locked to Pitcher in inning 1)
    await client.put(f"/games/{game['id']}/lineup", json=[
        {"inning": 1, "player_id": player_ids[0], "position": 1, "locked": True},
        {"inning": 1, "player_id": player_ids[1], "position": 1, "locked": True}
    ])
    solve_res = await client.post(f"/games/{game['id']}/solve")
    assert solve_res.status_code == 400
    assert "Multiple players locked to the same position" in solve_res.json()["detail"]

    # C. Test Pitcher Innings Game Cap (e.g. P0 locked to Pitcher in 3 innings, with cap of 2)
    await client.put(f"/games/{game['id']}/lineup", json=[
        {"inning": 1, "player_id": player_ids[0], "position": 1, "locked": True},
        {"inning": 2, "player_id": player_ids[0], "position": 1, "locked": True},
        {"inning": 3, "player_id": player_ids[0], "position": 1, "locked": True}
    ])
    solve_res = await client.post(f"/games/{game['id']}/solve")
    assert solve_res.status_code == 400
    assert "exceeds the game limit of 2" in solve_res.json()["detail"]

    # D. Test Pitcher Re-entry (e.g. P0 locked to Pitcher in Inning 1 and 3, but Catcher in Inning 2)
    await client.put(f"/games/{game['id']}/lineup", json=[
        {"inning": 1, "player_id": player_ids[0], "position": 1, "locked": True},
        {"inning": 2, "player_id": player_ids[0], "position": 2, "locked": True},
        {"inning": 3, "player_id": player_ids[0], "position": 1, "locked": True}
    ])
    solve_res = await client.post(f"/games/{game['id']}/solve")
    assert solve_res.status_code == 400
    assert "Pitcher Re-entry violation" in solve_res.json()["detail"]




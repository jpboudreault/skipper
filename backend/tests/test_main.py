import pytest
from datetime import date
import json
from sqlmodel import select
from app.models import (
    Availability,
    BattingLine,
    Game,
    Lineup,
    LineupSnapshot,
    PitchingAppearance,
    Player,
    PositionScore,
)

@pytest.mark.asyncio
async def test_read_root(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "Skipper API is running"}

@pytest.mark.asyncio
async def test_create_player(client):
    player_data = {
        "first_name": "Test",
        "last_name": "Player",
        "jersey": 99,
        "active": True
    }
    response = await client.post("/players/", json=player_data)
    assert response.status_code == 200
    data = response.json()
    assert data["first_name"] == "Test"
    assert data["jersey"] == 99
    assert "id" in data

@pytest.mark.asyncio
async def test_read_players(client, session):
    # Add a player manually
    p = Player(first_name="Alice", last_name="Smith", jersey=1, team_id=1)
    session.add(p)
    session.commit()

    response = await client.get("/players/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["first_name"] == "Alice"

@pytest.mark.asyncio
async def test_update_player(client, session):
    p = Player(first_name="Alice", last_name="Smith", jersey=1, team_id=1)
    session.add(p)
    session.commit()
    session.refresh(p)

    update_data = {"first_name": "Bob"}
    response = await client.put(f"/players/{p.id}", json=update_data)
    assert response.status_code == 200
    assert response.json()["first_name"] == "Bob"

@pytest.mark.asyncio
async def test_delete_player(client, session):
    p = Player(first_name="Alice", last_name="Smith", jersey=1, team_id=1)
    session.add(p)
    session.commit()
    session.refresh(p)

    response = await client.delete(f"/players/{p.id}")
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    
    # Verify it's gone
    get_res = await client.get("/players/")
    assert len(get_res.json()) == 0

@pytest.mark.asyncio
async def test_delete_player_removes_dependent_rows(client, session):
    player = Player(first_name="Alice", last_name="Smith", jersey=1, team_id=1)
    teammate = Player(first_name="Bob", last_name="Jones", jersey=2, team_id=1)
    game = Game(date=date(2026, 7, 19), team_id=1)
    session.add_all([player, teammate, game])
    session.commit()
    session.refresh(player)
    session.refresh(teammate)
    session.refresh(game)

    session.add_all([
        PositionScore(player_id=player.id, position=1, score=7),
        Availability(game_id=game.id, player_id=player.id, status="available"),
        BattingLine(game_id=game.id, player_id=player.id, singles=1),
        PitchingAppearance(
            game_id=game.id,
            player_id=player.id,
            inning_entered=1,
            inning_exited=2,
            ip_outs=3,
        ),
        Lineup(game_id=game.id, inning=1, player_id=player.id, position=1),
        Lineup(game_id=game.id, inning=1, player_id=teammate.id, position=2),
        LineupSnapshot(
            game_id=game.id,
            label="before-delete",
            cells_json=json.dumps([
                {"inning": 1, "player_id": player.id, "position": 1, "locked": True},
                {"inning": 1, "player_id": teammate.id, "position": 2, "locked": False},
            ]),
        ),
    ])
    session.commit()

    response = await client.delete(f"/players/{player.id}")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    session.expire_all()
    assert session.get(Player, player.id) is None
    assert session.exec(
        select(PositionScore).where(PositionScore.player_id == player.id)
    ).all() == []
    assert session.exec(
        select(Availability).where(Availability.player_id == player.id)
    ).all() == []
    assert session.exec(
        select(BattingLine).where(BattingLine.player_id == player.id)
    ).all() == []
    assert session.exec(
        select(PitchingAppearance).where(PitchingAppearance.player_id == player.id)
    ).all() == []
    assert session.exec(select(Lineup).where(Lineup.player_id == player.id)).all() == []
    remaining_lineup = session.exec(
        select(Lineup).where(Lineup.player_id == teammate.id)
    ).all()
    assert len(remaining_lineup) == 1

    snapshot = session.exec(
        select(LineupSnapshot).where(LineupSnapshot.game_id == game.id)
    ).one()
    cells = json.loads(snapshot.cells_json)
    assert cells == [
        {"inning": 1, "player_id": teammate.id, "position": 2, "locked": False},
    ]

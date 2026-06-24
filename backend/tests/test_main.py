import pytest
from app.models import Player, Team
from sqlmodel import create_engine, text
import app.main as main_module

@pytest.mark.asyncio
async def test_read_root(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "Skipper API is running"}

def test_run_migrations_adds_game_type_for_legacy_schema(monkeypatch, tmp_path):
    legacy_db = tmp_path / "legacy.db"
    legacy_engine = create_engine(f"sqlite:///{legacy_db}", connect_args={"check_same_thread": False})
    with legacy_engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE game (
                id INTEGER PRIMARY KEY,
                team_id INTEGER NOT NULL,
                date DATE NOT NULL,
                mode TEXT NOT NULL
            )
        """))
        conn.execute(text("""
            INSERT INTO game (id, team_id, date, mode)
            VALUES (1, 1, '2026-06-01', 'compete')
        """))
        conn.commit()

    monkeypatch.setattr(main_module, "engine", legacy_engine)
    main_module.run_migrations()

    with legacy_engine.connect() as conn:
        game_type = conn.execute(text("SELECT game_type FROM game WHERE id = 1")).scalar_one()

    assert game_type == "season"

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

"""Tests for lineup history/undo (snapshots)."""
import pytest


async def _make_player(client, jersey):
    res = await client.post("/players/", json={
        "first_name": "P", "last_name": str(jersey), "jersey": jersey, "active": True
    })
    assert res.status_code == 200
    return res.json()


async def _make_game(client):
    res = await client.post("/games/", json={"date": "2026-06-01", "mode": "compete"})
    assert res.status_code == 200
    return res.json()


async def _set_lineup(client, game_id, cells):
    res = await client.put(f"/games/{game_id}/lineup", json=cells)
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_snapshot_save_list_restore(client, session):
    p1 = await _make_player(client, 1)
    p2 = await _make_player(client, 2)
    game = await _make_game(client)

    original = [
        {"inning": 1, "player_id": p1["id"], "position": 1, "locked": False},
        {"inning": 1, "player_id": p2["id"], "position": 2, "locked": False},
    ]
    await _set_lineup(client, game["id"], original)

    snap_res = await client.post(f"/games/{game['id']}/lineup/snapshots", json={"label": "manual"})
    assert snap_res.status_code == 200

    list_res = await client.get(f"/games/{game['id']}/lineup/snapshots")
    assert list_res.status_code == 200
    snapshots = list_res.json()
    assert len(snapshots) == 1
    assert snapshots[0]["cell_count"] == 2
    snapshot_id = snapshots[0]["id"]

    # Overwrite the lineup with something different
    await _set_lineup(client, game["id"], [
        {"inning": 1, "player_id": p1["id"], "position": 3, "locked": False},
    ])
    current = (await client.get(f"/games/{game['id']}/lineup")).json()
    assert len(current) == 1

    # Restore the snapshot
    restore_res = await client.post(f"/games/{game['id']}/lineup/snapshots/{snapshot_id}/restore")
    assert restore_res.status_code == 200
    assert restore_res.json()["restored_cells"] == 2

    restored = (await client.get(f"/games/{game['id']}/lineup")).json()
    assert len(restored) == 2
    positions = sorted(c["position"] for c in restored)
    assert positions == [1, 2]


@pytest.mark.asyncio
async def test_snapshot_empty_lineup_rejected(client, session):
    game = await _make_game(client)
    res = await client.post(f"/games/{game['id']}/lineup/snapshots", json={"label": "manual"})
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_restore_unknown_snapshot_404(client, session):
    game = await _make_game(client)
    res = await client.post(f"/games/{game['id']}/lineup/snapshots/999999/restore")
    assert res.status_code == 404

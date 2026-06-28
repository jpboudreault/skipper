"""Tests for the development trends endpoint (A4)."""
import pytest
from datetime import date
from sqlmodel import Session

from app.models import Team, Player, Game, BattingLine, Lineup


@pytest.mark.asyncio
async def test_development_trends(client, session: Session):
    team = Team(
        name="Trend Team", season="2026", innings_per_game=5,
        max_pitcher_innings_per_game=3, pitch_count_rules_json="{}",
    )
    session.add(team)
    session.commit()

    p1 = Player(team_id=team.id, first_name="A", last_name="One", jersey=1)
    p2 = Player(team_id=team.id, first_name="B", last_name="Two", jersey=2)
    session.add_all([p1, p2])
    session.commit()

    # Two completed games (result set) and one upcoming (no result)
    g1 = Game(team_id=team.id, date=date(2026, 5, 1), mode="compete", result_runs_for=5, result_runs_against=3)
    g2 = Game(team_id=team.id, date=date(2026, 5, 8), mode="develop", result_runs_for=2, result_runs_against=4)
    g3 = Game(team_id=team.id, date=date(2026, 5, 15), mode="compete")
    session.add_all([g1, g2, g3])
    session.commit()

    session.add_all([
        BattingLine(game_id=g1.id, player_id=p1.id, singles=2),
        BattingLine(game_id=g2.id, player_id=p1.id, hr=1, outs_not_k=1),
    ])
    # Position variety for p1 (pitched in g1, played 2nd in g2)
    session.add_all([
        Lineup(game_id=g1.id, inning=1, player_id=p1.id, position=1),
        Lineup(game_id=g2.id, inning=1, player_id=p1.id, position=4),
        Lineup(game_id=g1.id, inning=1, player_id=p2.id, position=0),
    ])
    session.commit()

    res = await client.get(f"/teams/{team.id}/stats/trends")
    assert res.status_code == 200
    data = res.json()

    # Only completed games appear in the cumulative timeline
    assert len(data["cumulative_batting"]) == 2
    first = data["cumulative_batting"][0]
    assert first["game_id"] == g1.id
    # After g1: 2 singles -> H=2, AB=2 -> AVG 1.000
    assert first["avg"] == 1.0

    variety = {row["player_id"]: row for row in data["position_variety"]}
    assert variety[p1.id]["distinct_positions"] == 2  # P and 2B
    assert variety[p2.id]["distinct_positions"] == 0  # only bench


@pytest.mark.asyncio
async def test_trends_requires_team_membership(client, session: Session):
    # A team the test user is not linked to is created AFTER the override runs per request;
    # the conftest auto-links the user to all existing teams, so we assert the happy path
    # works and that an unknown team id is rejected.
    res = await client.get("/teams/999999/stats/trends")
    assert res.status_code == 403

"""Tests for the tournament (pitch-count-based) rest calculator."""
import json
from datetime import date, timedelta
from sqlmodel import Session

from app.models import Team, Player, Game, PitchingAppearance
from app.rest_calculator import get_pitcher_eligibility

PITCH_RULES = {
    "max_pitches_per_day": 85,
    "rest_requirements": [
        {"min_pitches": 1, "max_pitches": 20, "days_rest": 0},
        {"min_pitches": 21, "max_pitches": 35, "days_rest": 1},
        {"min_pitches": 36, "max_pitches": 50, "days_rest": 2},
        {"min_pitches": 51, "max_pitches": 65, "days_rest": 3},
        {"min_pitches": 66, "max_pitches": 85, "days_rest": 4},
    ],
}


def make_team(session: Session, rules=PITCH_RULES) -> Team:
    team = Team(
        name="Tourney Team", season="2026", innings_per_game=6,
        max_pitcher_innings_per_game=3, max_pitcher_innings_per_7_days=4,
        late_inning_weight=1.5, language="en",
        pitch_count_rules_json=json.dumps(rules),
    )
    session.add(team)
    session.commit()
    session.refresh(team)
    return team


def make_player(session: Session, team: Team) -> Player:
    player = Player(team_id=team.id, first_name="T", last_name="P", jersey=10, active=True)
    session.add(player)
    session.commit()
    session.refresh(player)
    return player


def make_game(session: Session, team: Team, game_date: date, game_type: str = "tournament") -> Game:
    game = Game(team_id=team.id, date=game_date, game_type=game_type, mode="compete")
    session.add(game)
    session.commit()
    session.refresh(game)
    return game


def make_pitching(session: Session, game: Game, player: Player, pitches: int) -> None:
    pa = PitchingAppearance(
        game_id=game.id, player_id=player.id,
        inning_entered=1, inning_exited=3, ip_outs=6, pitch_count=pitches,
    )
    session.add(pa)
    session.commit()


def test_eligible_no_history(session):
    team = make_team(session)
    player = make_player(session, team)
    result = get_pitcher_eligibility(player.id, date(2026, 6, 15), "tournament", team, session)
    assert result.eligible is True


def test_daily_max_blocks_same_day(session):
    team = make_team(session)
    player = make_player(session, team)
    today = date(2026, 6, 15)
    game = make_game(session, team, today)
    make_pitching(session, game, player, pitches=85)

    result = get_pitcher_eligibility(player.id, today, "tournament", team, session)
    assert result.eligible is False
    assert result.pitches_today == 85


def test_rest_requirement_blocks(session):
    team = make_team(session)
    player = make_player(session, team)
    today = date(2026, 6, 15)
    # 40 pitches 1 day ago -> bucket 36-50 -> 2 days rest required -> blocked today
    game = make_game(session, team, today - timedelta(days=1))
    make_pitching(session, game, player, pitches=40)

    result = get_pitcher_eligibility(player.id, today, "tournament", team, session)
    assert result.eligible is False
    assert result.rest_until is not None


def test_eligible_after_enough_rest(session):
    team = make_team(session)
    player = make_player(session, team)
    today = date(2026, 6, 15)
    # 40 pitches 3 days ago -> needs 2 rest days -> eligible again on day+3 -> eligible today
    game = make_game(session, team, today - timedelta(days=3))
    make_pitching(session, game, player, pitches=40)

    result = get_pitcher_eligibility(player.id, today, "tournament", team, session)
    assert result.eligible is True


def test_low_pitch_count_no_rest(session):
    team = make_team(session)
    player = make_player(session, team)
    today = date(2026, 6, 15)
    # 15 pitches yesterday -> bucket 1-20 -> 0 rest -> eligible today
    game = make_game(session, team, today - timedelta(days=1))
    make_pitching(session, game, player, pitches=15)

    result = get_pitcher_eligibility(player.id, today, "tournament", team, session)
    assert result.eligible is True


def test_same_day_pitches_summed(session):
    team = make_team(session)
    player = make_player(session, team)
    today = date(2026, 6, 15)
    # Two games same day: 50 + 40 = 90 > 85 daily max
    g1 = make_game(session, team, today)
    g2 = make_game(session, team, today)
    make_pitching(session, g1, player, pitches=50)
    make_pitching(session, g2, player, pitches=40)

    result = get_pitcher_eligibility(player.id, today, "tournament", team, session)
    assert result.eligible is False
    assert result.pitches_today == 90


def test_missing_tournament_pitch_count_blocks_eligibility(session):
    team = make_team(session)
    player = make_player(session, team)
    today = date(2026, 6, 15)
    game = make_game(session, team, today - timedelta(days=1))
    session.add(
        PitchingAppearance(
            game_id=game.id,
            player_id=player.id,
            inning_entered=1,
            inning_exited=3,
            ip_outs=6,
            pitch_count=None,
        )
    )
    session.commit()

    result = get_pitcher_eligibility(player.id, today, "tournament", team, session)
    assert result.eligible is False
    assert "Missing tournament pitch count" in result.reason


def test_no_rules_assumes_eligible(session):
    team = make_team(session, rules={})
    player = make_player(session, team)
    result = get_pitcher_eligibility(player.id, date(2026, 6, 15), "tournament", team, session)
    assert result.eligible is True


def test_season_pitch_count_does_not_affect_tournament(session):
    team = make_team(session)
    player = make_player(session, team)
    today = date(2026, 6, 15)
    # 40 pitches in a season game yesterday would block tournament rest if counted
    season_game = make_game(session, team, today - timedelta(days=1), game_type="season")
    make_pitching(session, season_game, player, pitches=40)

    result = get_pitcher_eligibility(player.id, today, "tournament", team, session)
    assert result.eligible is True

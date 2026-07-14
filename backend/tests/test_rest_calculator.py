"""Tests for the innings-based rest calculator."""
from datetime import date, timedelta
from sqlmodel import Session
from app.models import Team, Player, Game, PitchingAppearance
from app.rest_calculator import get_pitcher_eligibility


def make_team(session: Session) -> Team:
    team = Team(
        name="Test Team", season="2026", innings_per_game=5,
        max_pitcher_innings_per_game=3, max_pitcher_innings_per_7_days=4,
        late_inning_weight=1.5, language="en", pitch_count_rules_json="{}"
    )
    session.add(team)
    session.commit()
    session.refresh(team)
    return team


def make_player(session: Session, team: Team) -> Player:
    player = Player(team_id=team.id, first_name="Test", last_name="Player", jersey=10, active=True)
    session.add(player)
    session.commit()
    session.refresh(player)
    return player


def make_game(session: Session, team: Team, game_date: date, game_type: str = "season") -> Game:
    game = Game(team_id=team.id, date=game_date, game_type=game_type, mode="compete")
    session.add(game)
    session.commit()
    session.refresh(game)
    return game


def make_pitching(session: Session, game: Game, player: Player, ip_outs: int) -> None:
    pa = PitchingAppearance(
        game_id=game.id, player_id=player.id,
        inning_entered=1, inning_exited=3, ip_outs=ip_outs,
    )
    session.add(pa)
    session.commit()


def test_eligible_no_history(session):
    team = make_team(session)
    player = make_player(session, team)
    today = date(2026, 6, 15)

    result = get_pitcher_eligibility(player.id, today, "season", team, session)
    assert result.eligible is True
    assert result.innings_last_7_days == 0
    assert result.remaining_today == 3
    assert result.remaining_7_days == 4


def test_ineligible_daily_cap(session):
    team = make_team(session)
    player = make_player(session, team)
    today = date(2026, 6, 15)

    # Player pitched 3 innings today (= max)
    game = make_game(session, team, today)
    make_pitching(session, game, player, ip_outs=9)  # 3 full innings

    result = get_pitcher_eligibility(player.id, today, "season", team, session)
    assert result.eligible is False
    assert "today" in result.reason.lower()


def test_ineligible_7_day_cap(session):
    team = make_team(session)
    player = make_player(session, team)
    today = date(2026, 6, 15)

    # Player pitched 2 innings 3 days ago and 2 innings yesterday = 4 total (= max)
    game1 = make_game(session, team, today - timedelta(days=3))
    make_pitching(session, game1, player, ip_outs=6)  # 2 innings

    game2 = make_game(session, team, today - timedelta(days=1))
    make_pitching(session, game2, player, ip_outs=6)  # 2 innings

    result = get_pitcher_eligibility(player.id, today, "season", team, session)
    assert result.eligible is False
    assert "7 days" in result.reason.lower() or "7-day" in result.reason.lower()
    assert result.innings_last_7_days == 4


def test_eligible_with_partial_usage(session):
    team = make_team(session)
    player = make_player(session, team)
    today = date(2026, 6, 15)

    # Player pitched 1 inning yesterday
    game = make_game(session, team, today - timedelta(days=1))
    make_pitching(session, game, player, ip_outs=3)  # 1 inning

    result = get_pitcher_eligibility(player.id, today, "season", team, session)
    assert result.eligible is True
    assert result.innings_last_7_days == 1
    assert result.remaining_today == 3  # haven't pitched today
    assert result.remaining_7_days == 3  # 4 - 1 = 3


def test_old_games_outside_window_not_counted(session):
    team = make_team(session)
    player = make_player(session, team)
    today = date(2026, 6, 15)

    # Player pitched 3 innings 8 days ago (outside 7-day window)
    game = make_game(session, team, today - timedelta(days=8))
    make_pitching(session, game, player, ip_outs=9)

    result = get_pitcher_eligibility(player.id, today, "season", team, session)
    assert result.eligible is True
    assert result.innings_last_7_days == 0


def test_exclude_game_id(session):
    team = make_team(session)
    player = make_player(session, team)
    today = date(2026, 6, 15)

    # Player has 3 innings in a game today
    game = make_game(session, team, today)
    make_pitching(session, game, player, ip_outs=9)

    # Without exclusion: ineligible
    result1 = get_pitcher_eligibility(player.id, today, "season", team, session)
    assert result1.eligible is False

    # With exclusion (we're re-solving this game): eligible
    result2 = get_pitcher_eligibility(player.id, today, "season", team, session, exclude_game_id=game.id)
    assert result2.eligible is True


def test_tournament_innings_do_not_affect_season_limits(session):
    team = make_team(session)
    player = make_player(session, team)
    today = date(2026, 6, 15)

    tournament_game = make_game(session, team, today - timedelta(days=1), game_type="tournament")
    make_pitching(session, tournament_game, player, ip_outs=12)

    result = get_pitcher_eligibility(player.id, today, "season", team, session)
    assert result.eligible is True
    assert result.innings_last_7_days == 0
    assert result.remaining_7_days == team.max_pitcher_innings_per_7_days

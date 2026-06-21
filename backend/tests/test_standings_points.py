"""Tests for league standings point configuration."""

from app.standings_points import (
    DEFAULT_STANDINGS_POINTS,
    points_from_record,
    resolve_standings_points,
    win_pct,
)


def test_resolve_standings_points_defaults():
    assert resolve_standings_points({}) == DEFAULT_STANDINGS_POINTS
    assert resolve_standings_points(None) == DEFAULT_STANDINGS_POINTS


def test_resolve_standings_points_from_config():
    config = {"standings_points": {"win": 3, "draw": 1, "loss": 0}}
    assert resolve_standings_points(config) == {"win": 3, "draw": 1, "loss": 0}


def test_points_from_record_and_win_pct():
    pts = {"win": 2, "draw": 1, "loss": 0}
    assert points_from_record(1, 0, 1, pts) == 3
    assert win_pct(3, 2, pts) == 0.75

    custom = {"win": 3, "draw": 1, "loss": 0}
    assert points_from_record(1, 0, 1, custom) == 4
    assert win_pct(4, 2, custom) == round(4 / 6, 3)

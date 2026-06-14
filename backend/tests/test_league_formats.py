"""Tests for league format registry."""

import pytest

from app.league_formats import get_scoresheet_prompt, list_scoresheet_versions


def test_baseball_quebec_is_registered():
    assert "baseball_quebec" in list_scoresheet_versions()


def test_default_scoresheet_prompt():
    prompt = get_scoresheet_prompt(None, [{"jersey": 10, "first_name": "Jean", "last_name": "Dupont"}])
    assert "Baseball Québec" in prompt
    assert "#10 Jean Dupont" in prompt


def test_unknown_scoresheet_version_raises():
    with pytest.raises(ValueError, match="Unknown scoresheet version"):
        get_scoresheet_prompt("unknown_league", [])

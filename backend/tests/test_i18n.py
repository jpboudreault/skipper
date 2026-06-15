from app.i18n import get_locked_locale, parse_locale, translate


def test_parse_locale_french():
    assert parse_locale("fr-CA,fr;q=0.9,en;q=0.8") == "fr"


def test_parse_locale_english():
    assert parse_locale("en-US") == "en"


def test_parse_locale_default():
    assert parse_locale(None) == "en"
    assert parse_locale("de-DE") == "en"


def test_translate_pitcher_cap_fr():
    msg = translate(
        "pitcher_game_cap",
        {"player_name": "Smith", "count": 3, "max": 2},
        "fr",
    )
    assert "Smith" in msg
    assert "3" in msg


def test_translate_fallback_to_en():
    msg = translate("invalid_token", locale="fr")
    assert msg == "Jeton invalide"


def test_translate_position_id_fr():
    msg = translate(
        "duplicate_position_lock",
        {"inning": 1, "position_id": 1, "players": "Dupont"},
        "fr",
    )
    assert "Lanceur" in msg


def test_get_locked_locale(monkeypatch):
    monkeypatch.delenv("SKIPPER_LOCALE", raising=False)
    assert get_locked_locale() is None

    monkeypatch.setenv("SKIPPER_LOCALE", "fr")
    assert get_locked_locale() == "fr"

    monkeypatch.setenv("SKIPPER_LOCALE", "invalid")
    assert get_locked_locale() is None


def test_parse_locale_respects_lock(monkeypatch):
    monkeypatch.setenv("SKIPPER_LOCALE", "en")
    assert parse_locale("fr-CA,fr;q=0.9") == "en"

    monkeypatch.setenv("SKIPPER_LOCALE", "fr")
    assert parse_locale("en-US") == "fr"

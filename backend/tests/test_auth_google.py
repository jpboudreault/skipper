import pytest
from unittest.mock import patch
from sqlmodel import select

from app.models import User


@pytest.mark.asyncio
async def test_google_login_known_user(client, session):
    user = User(email="coach@gmail.com", is_active=True)
    session.add(user)
    session.commit()

    with patch("app.main.verify_google_token") as mock_verify:
        mock_verify.return_value = {"email": "coach@gmail.com"}
        res = await client.post("/auth/google", json={"credential": "fake-token"})

    assert res.status_code == 200
    data = res.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]


@pytest.mark.asyncio
async def test_google_login_unauthorized_production(client, session, monkeypatch):
    monkeypatch.setenv("DEV_MODE", "false")

    with patch("app.main.verify_google_token") as mock_verify:
        mock_verify.return_value = {"email": "stranger@gmail.com"}
        res = await client.post("/auth/google", json={"credential": "fake-token"})

    assert res.status_code == 401
    assert "not authorized" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_google_login_dev_auto_create(client, session, monkeypatch):
    monkeypatch.setenv("DEV_MODE", "true")

    with patch("app.main.verify_google_token") as mock_verify:
        mock_verify.return_value = {"email": "newcoach@gmail.com"}
        res = await client.post("/auth/google", json={"credential": "fake-token"})

    assert res.status_code == 200
    user = session.exec(select(User).where(User.email == "newcoach@gmail.com")).first()
    assert user is not None


@pytest.mark.asyncio
async def test_google_login_missing_email(client):
    with patch("app.main.verify_google_token") as mock_verify:
        mock_verify.return_value = {"sub": "abc123"}
        res = await client.post("/auth/google", json={"credential": "fake-token"})

    assert res.status_code == 400
    assert "email" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_google_login_default_dev_mode_is_safe(client, session, monkeypatch):
    """With DEV_MODE unset, unknown users must be rejected (fail-closed)."""
    monkeypatch.delenv("DEV_MODE", raising=False)

    with patch("app.main.verify_google_token") as mock_verify:
        mock_verify.return_value = {"email": "unseeded@gmail.com"}
        res = await client.post("/auth/google", json={"credential": "fake-token"})

    assert res.status_code == 401

import pytest
from unittest.mock import patch
from sqlmodel import select

from app.models import User


@pytest.mark.asyncio
async def test_microsoft_login_known_user(client, session):
    user = User(email="coach@outlook.com", is_active=True)
    session.add(user)
    session.commit()

    with patch("app.main.verify_microsoft_token") as mock_verify:
        mock_verify.return_value = {"email": "coach@outlook.com"}
        res = await client.post(
            "/auth/microsoft",
            json={"id_token": "fake-token"},
        )

    assert res.status_code == 200
    data = res.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]


@pytest.mark.asyncio
async def test_microsoft_login_preferred_username(client, session):
    user = User(email="coach@hotmail.com", is_active=True)
    session.add(user)
    session.commit()

    with patch("app.main.verify_microsoft_token") as mock_verify:
        mock_verify.return_value = {"preferred_username": "coach@hotmail.com"}
        res = await client.post(
            "/auth/microsoft",
            json={"id_token": "fake-token"},
        )

    assert res.status_code == 200
    assert res.json()["access_token"]


@pytest.mark.asyncio
async def test_microsoft_login_unauthorized_production(client, session, monkeypatch):
    monkeypatch.setenv("DEV_MODE", "false")

    with patch("app.main.verify_microsoft_token") as mock_verify:
        mock_verify.return_value = {"email": "unknown@outlook.com"}
        res = await client.post(
            "/auth/microsoft",
            json={"id_token": "fake-token"},
        )

    assert res.status_code == 401
    assert "not authorized" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_microsoft_login_dev_auto_create(client, session, monkeypatch):
    monkeypatch.setenv("DEV_MODE", "true")

    with patch("app.main.verify_microsoft_token") as mock_verify:
        mock_verify.return_value = {"email": "newuser@live.com"}
        res = await client.post(
            "/auth/microsoft",
            json={"id_token": "fake-token"},
        )

    assert res.status_code == 200
    user = session.exec(select(User).where(User.email == "newuser@live.com")).first()
    assert user is not None


@pytest.mark.asyncio
async def test_microsoft_login_missing_email(client):
    with patch("app.main.verify_microsoft_token") as mock_verify:
        mock_verify.return_value = {"sub": "abc123"}
        res = await client.post(
            "/auth/microsoft",
            json={"id_token": "fake-token"},
        )

    assert res.status_code == 400
    assert "email" in res.json()["detail"].lower()

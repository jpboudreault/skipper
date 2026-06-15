import os
from datetime import datetime, timedelta
import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel import Session
from app.db import get_session
from app.models import User, Team
from typing import Optional
from google.oauth2 import id_token
from google.auth.transport import requests
from app.i18n.errors import raise_api_error

load_dotenv()

JWT_SECRET = os.environ.get("JWT_SECRET", "super-secret-default-key")
ALGORITHM = "HS256"
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")

def verify_google_token(token: str) -> dict:
    """
    Verifies a Google ID token (JWT) securely on the server side.
    Returns the decoded token payload if valid, otherwise raises HTTPException.
    """
    if not GOOGLE_CLIENT_ID:
        raise_api_error(500, "google_client_id_not_configured")
    try:
        # Verify the ID token using Google's public certificates
        idinfo = id_token.verify_oauth2_token(token, requests.Request(), GOOGLE_CLIENT_ID)
        
        # Verify issuer is Google
        if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
            raise ValueError('Wrong issuer.')
            
        return idinfo
    except ValueError as e:
        raise_api_error(401, "invalid_google_token", reason=str(e))
    except Exception as e:
        raise_api_error(401, "google_token_verification_failed", reason=str(e))

def create_access_token(data: dict, expires_delta: timedelta = timedelta(days=30)):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)
    return encoded_jwt

# Security dependency for protecting routes
security = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: Session = Depends(get_session)
) -> User:
    """Decode and validate JWT token from the Authorization header."""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        user_id: int = payload.get("user_id")
        if email is None or user_id is None:
            raise_api_error(401, "invalid_token")
        user = session.get(User, user_id)
        if not user or not user.is_active:
            raise_api_error(401, "invalid_user")
        return user
    except jwt.ExpiredSignatureError:
        raise_api_error(401, "token_expired")
    except jwt.InvalidTokenError:
        raise_api_error(401, "invalid_token")

def get_active_team(
    x_active_team_id: Optional[int] = Header(None, alias="X-Active-Team-ID"),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
) -> Team:
    """Gets the active team from the X-Active-Team-ID header, validating access."""
    # Ensure current_user is bound to the active session
    current_user = session.get(User, current_user.id)
    if not current_user:
        raise_api_error(401, "invalid_user_session")
        
    if not x_active_team_id:
        if not current_user.teams:
            raise_api_error(403, "user_not_associated_with_team")
        return current_user.teams[0]

    team = session.get(Team, x_active_team_id)
    if not team or current_user not in team.admins:
        raise_api_error(403, "not_authorized_for_team")
        
    return team

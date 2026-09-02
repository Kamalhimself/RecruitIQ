"""
RecruitIQ - Authentication & Security Module
Handles Google Workspace SSO ID Token Verification, JWT generation,
and FastAPI dependencies for recruiter authentication.
"""

import os
import time
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

import jwt
from fastapi import HTTPException, Security, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

JWT_SECRET = os.getenv("JWT_SECRET", "recruitiq-dev-secret-key-replace-in-production-9002")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "12"))
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

security_bearer = HTTPBearer(auto_error=False)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Generate a signed JWT access token for an authenticated recruiter."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(hours=JWT_EXPIRATION_HOURS))
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def verify_google_id_token(id_token_str: str) -> Dict[str, Any]:
    """Verify Google OAuth2 ID Token from Google Identity Services."""
    from google.oauth2 import id_token
    from google.auth.transport import requests as google_requests

    try:
        # If GOOGLE_CLIENT_ID is set, verify against it; otherwise verify signature without audience check
        audience = GOOGLE_CLIENT_ID if GOOGLE_CLIENT_ID else None
        id_info = id_token.verify_oauth2_token(
            id_token_str,
            google_requests.Request(),
            audience=audience
        )
        return id_info
    except Exception as exc:
        logger.warning("Google token verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Google authentication failed: {str(exc)}",
        )


async def get_current_recruiter(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer)
) -> Dict[str, Any]:
    """
    FastAPI dependency: Enforce authentication for protected routes.
    Rejects unauthenticated requests with 401 Unauthorized.
    """
    # In development mode, allow bypassing only if explicitly enabled
    dev_bypass = os.getenv("AUTH_DEV_BYPASS", "false").lower() == "true"
    if not credentials:
        if dev_bypass:
            return {
                "recruiter_id": 1,
                "email": "kamaleswar@velansys.com",
                "name": "Kamaleswar Sivashanmugam (Dev)",
                "role": "admin",
            }
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = decode_access_token(token)
    return payload

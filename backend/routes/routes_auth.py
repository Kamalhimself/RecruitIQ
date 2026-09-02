"""
RecruitIQ - Authentication Routes
Endpoints for Google Workspace SSO, JWT token generation, and user profile.
"""

import os
import logging
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import sessionmaker

from backend.database.setup_db import get_engine
from backend.database.models import Recruiter
from backend.services.auth import (
    verify_google_id_token,
    create_access_token,
    get_current_recruiter,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])

engine = get_engine()
Session = sessionmaker(bind=engine)


class GoogleAuthRequest(BaseModel):
    credential: str  # Google ID token string


class DevLoginRequest(BaseModel):
    email: Optional[str] = "kamaleswar@velansys.com"
    name: Optional[str] = "Kamaleswar Sivashanmugam"


@router.post("/google")
def google_sso_login(payload: GoogleAuthRequest):
    """
    Authenticate a user via Google Workspace OAuth2 ID token.
    Links or creates a Recruiter record and returns a session JWT.
    """
    id_info = verify_google_id_token(payload.credential)

    email = id_info.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Google account email is missing.")

    if not id_info.get("email_verified", False):
        raise HTTPException(status_code=400, detail="Google email is not verified.")

    name = id_info.get("name", email.split("@")[0])
    picture = id_info.get("picture")

    # Domain restriction check if configured
    allowed_domains_str = os.getenv("ALLOWED_AUTH_DOMAINS", "")
    if allowed_domains_str:
        allowed_domains = [d.strip().lower() for d in allowed_domains_str.split(",") if d.strip()]
        user_domain = email.split("@")[-1].lower()
        if user_domain not in allowed_domains:
            raise HTTPException(
                status_code=403,
                detail=f"Access restricted to authorized domains ({', '.join(allowed_domains)})."
            )

    session = Session()
    try:
        recruiter = session.query(Recruiter).filter_by(email=email).first()
        if not recruiter:
            recruiter = Recruiter(
                full_name=name,
                email=email,
                is_active=True,
            )
            session.add(recruiter)
            session.commit()
            session.refresh(recruiter)

        token_data = {
            "recruiter_id": recruiter.recruiter_id,
            "email": recruiter.email,
            "name": recruiter.full_name,
            "picture": picture,
            "role": "admin" if "velansys.com" in email else "recruiter",
        }
        access_token = create_access_token(token_data)

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": token_data,
        }
    finally:
        session.close()


@router.post("/dev-login")
def dev_login(payload: Optional[DevLoginRequest] = None):
    """
    Local development login bypass.
    Allowed only in non-production environments.
    """
    is_prod = os.getenv("ENVIRONMENT") == "production"
    if is_prod:
        raise HTTPException(status_code=403, detail="Dev login is disabled in production.")

    email = (payload and payload.email) or "kamaleswar@velansys.com"
    name = (payload and payload.name) or "Kamaleswar Sivashanmugam"

    session = Session()
    try:
        recruiter = session.query(Recruiter).filter_by(email=email).first()
        if not recruiter:
            recruiter = Recruiter(full_name=name, email=email, is_active=True)
            session.add(recruiter)
            session.commit()
            session.refresh(recruiter)

        recruiter_id = recruiter.recruiter_id
    finally:
        session.close()

    token_data = {
        "recruiter_id": recruiter_id,
        "email": email,
        "name": name,
        "role": "admin",
    }
    access_token = create_access_token(token_data)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": token_data,
    }


@router.get("/me")
def get_authenticated_user_profile(user: dict = Depends(get_current_recruiter)):
    """Return the profile of the currently logged-in recruiter."""
    return user

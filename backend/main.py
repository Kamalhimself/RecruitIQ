"""
RecruitIQ - Main FastAPI application
Enterprise Candidate-to-JD Matching and Recruitment Automation Engine
"""
import os
import logging
from dotenv import load_dotenv
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.routes.routes_auth import router as auth_router
from backend.routes.routes_jd import router as jd_router, client_router
from backend.routes.routes_candidate import router as candidate_router
from backend.routes.routes_matching import router as matching_router
from backend.routes.routes_workflow import router as workflow_router

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("recruitiq")

app = FastAPI(
    title="RecruitIQ",
    version="2.2.0",
    description="Enterprise Candidate-to-JD Matching and Recruitment Automation Engine",
)

# -----------------------------------------------------------------------------
# Hardened CORS Configuration
# -----------------------------------------------------------------------------
DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "https://recruitiq.co.uk",
    "https://www.recruitiq.co.uk",
    "https://recruit.velansys.com",
    "https://velansysai.web.app",
    "https://velansysai.firebaseapp.com",
]

cors_origins_env = os.getenv("CORS_ORIGINS", "")
if cors_origins_env:
    extra_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]
    allowed_origins = list(set(DEFAULT_ALLOWED_ORIGINS + extra_origins))
else:
    allowed_origins = DEFAULT_ALLOWED_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


# -----------------------------------------------------------------------------
# Global Exception Handler (Prevents Internal DB / Stack Trace Leakage)
# -----------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled server exception on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal server error occurred. Our operations team has been notified.",
            "path": request.url.path,
        },
    )


# -----------------------------------------------------------------------------
# Route Registration
# -----------------------------------------------------------------------------
app.include_router(auth_router)
app.include_router(client_router)
app.include_router(jd_router)
app.include_router(candidate_router)
app.include_router(matching_router)
app.include_router(workflow_router)


# -----------------------------------------------------------------------------
# Health & Readiness Probes (for Cloud Run / AWS / Docker)
# -----------------------------------------------------------------------------
@app.get("/health", tags=["health"])
@app.get("/", tags=["health"])
def health_check():
    """Liveness probe: returns 200 if container is running."""
    return {"status": "healthy", "app": "RecruitIQ", "version": "2.2.0"}


@app.get("/ready", tags=["health"])
def readiness_check():
    """Readiness probe: validates database connectivity."""
    try:
        from backend.database.setup_db import get_engine
        from sqlalchemy import text
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1;"))
        return {"status": "ready", "database": "connected"}
    except Exception as exc:
        logger.error("Readiness check failed: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "database": "disconnected"}
        )

"""
RecruitIQ - Main FastAPI application
"""
import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routes.routes_jd import router as jd_router, client_router
from backend.routes.routes_candidate import router as candidate_router
from backend.routes.routes_matching import router as matching_router
from backend.routes.routes_workflow import router as workflow_router

load_dotenv()

app = FastAPI(
    title="RecruitIQ",
    version="2.1.0",
    description="Enterprise Candidate-to-JD Matching and Recruitment Automation Engine",
)

cors_origins_env = os.getenv("CORS_ORIGINS", "*")
allowed_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()] if cors_origins_env != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(client_router)
app.include_router(jd_router)
app.include_router(candidate_router)
app.include_router(matching_router)
app.include_router(workflow_router)


@app.get("/health", tags=["health"])
@app.get("/", tags=["health"])
def health_check():
    return {"status": "healthy", "app": "RecruitIQ", "version": "2.1.0"}

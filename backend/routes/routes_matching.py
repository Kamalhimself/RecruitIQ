from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel
from sqlalchemy.orm import sessionmaker

from backend.services.matching_engine import SemanticIndex, score_candidate
from backend.database.models import Candidate, CandidateJDMapping, JobDescription, MappingStatus
from backend.database.setup_db import get_engine

router = APIRouter(prefix="/matching", tags=["matching"])
Session = sessionmaker(bind=get_engine())


class RunMatchingRequest(BaseModel):
    candidate_codes: Optional[List[str]] = None
    candidate_ids: Optional[List[str]] = None
    shortlist_threshold: Optional[float] = 70.0
    w_skills: Optional[float] = 50.0
    w_experience: Optional[float] = 50.0
    w_notice: Optional[float] = 0.0
    w_location: Optional[float] = 0.0


@router.post("/jds/{jd_id}/run")
def run_matching(
    jd_id: int,
    payload: Optional[RunMatchingRequest] = Body(None),
    shortlist_threshold: float = Query(70, ge=0, le=100),
    w_skills: float = Query(50.0, ge=0, le=100),
    w_experience: float = Query(50.0, ge=0, le=100),
    w_notice: float = Query(0.0, ge=0, le=100),
    w_location: float = Query(0.0, ge=0, le=100),
    candidate_code: Optional[str] = Query(None, description="Optional single candidate code to match")
):
    """Score the full talent pool or specifically selected candidate CVs against one open JD and persist the ranked mappings."""
    session = Session()
    try:
        jd = session.get(JobDescription, jd_id)
        if not jd:
            raise HTTPException(404, f"JD {jd_id} was not found")

        # Resolve weights and threshold from payload if passed
        if payload:
            if payload.shortlist_threshold is not None:
                shortlist_threshold = payload.shortlist_threshold
            if payload.w_skills is not None:
                w_skills = payload.w_skills
            if payload.w_experience is not None:
                w_experience = payload.w_experience
            if payload.w_notice is not None:
                w_notice = payload.w_notice
            if payload.w_location is not None:
                w_location = payload.w_location

        all_candidates = session.query(Candidate).all()
        if not all_candidates:
            return {"jd_id": jd_id, "matched": 0, "results": []}

        # Filter target candidates to score
        target_candidates = all_candidates
        if payload and payload.candidate_codes:
            target_codes = set(payload.candidate_codes)
            target_candidates = [c for c in all_candidates if c.candidate_code in target_codes]
        elif payload and payload.candidate_ids:
            target_ids = set(payload.candidate_ids)
            target_candidates = [c for c in all_candidates if str(c.candidate_id) in target_ids]
        elif candidate_code:
            target_candidates = [c for c in all_candidates if c.candidate_code == candidate_code]

        if not target_candidates:
            raise HTTPException(404, "No matching candidates found for the specified selection.")

        index = SemanticIndex()
        index.index_candidates(all_candidates)
        relevance = index.relevance_for(jd, target_candidates)

        results = []
        for candidate in target_candidates:
            score = score_candidate(
                candidate, jd, relevance.get(str(candidate.candidate_id), 0.0),
                w_skills=w_skills, w_experience=w_experience,
                w_notice=w_notice, w_location=w_location
            )
            mapping = session.query(CandidateJDMapping).filter_by(
                candidate_id=candidate.candidate_id, jd_id=jd_id
            ).first()
            if not mapping:
                mapping = CandidateJDMapping(
                    candidate_id=candidate.candidate_id, jd_id=jd_id,
                    is_direct_applicant=False, status=MappingStatus.new,
                )
                session.add(mapping)
            mapping.match_score = score.total
            mapping.skills_score = score.skills
            mapping.experience_score = score.experience
            mapping.notice_period_score = score.notice_period
            mapping.location_score = score.location
            mapping.match_explanation = score.explanation
            if score.total >= shortlist_threshold and mapping.status == MappingStatus.new:
                mapping.status = MappingStatus.shortlisted
            results.append({
                "candidate_code": candidate.candidate_code,
                "full_name": candidate.full_name,
                "email": candidate.email,
                "phone": candidate.phone,
                "current_location": candidate.current_location,
                "total_experience": float(candidate.total_experience) if candidate.total_experience is not None else None,
                "match_score": score.total,
                "status": mapping.status.value,
                "explanation": score.explanation,
                "is_eligible": score.is_eligible,
                "skills_score": score.skills,
                "experience_score": score.experience,
                "notice_period_score": score.notice_period,
                "location_score": score.location,
                "breakdown": score.breakdown,
                "audit": score.audit,
            })
        session.commit()
        return {
            "jd_id": jd_id,
            "matched": len(results),
            "results": sorted(results, key=lambda r: r["match_score"], reverse=True)
        }
    except RuntimeError as exc:
        session.rollback()
        raise HTTPException(503, str(exc)) from exc
    except HTTPException:
        session.rollback()
        raise
    except Exception as exc:
        session.rollback()
        raise HTTPException(500, str(exc)) from exc
    finally:
        session.close()


@router.get("/jds/{jd_id}")
def get_matches(jd_id: int, limit: int = Query(50, ge=1, le=200)):
    session = Session()
    try:
        mappings = session.query(CandidateJDMapping).join(Candidate).filter(
            CandidateJDMapping.jd_id == jd_id
        ).order_by(CandidateJDMapping.match_score.desc().nullslast()).limit(limit).all()
        return [{
            "mapping_id": m.mapping_id,
            "candidate_code": m.candidate.candidate_code,
            "full_name": m.candidate.full_name,
            "email": m.candidate.email,
            "phone": m.candidate.phone,
            "current_location": m.candidate.current_location,
            "total_experience": float(m.candidate.total_experience) if m.candidate.total_experience is not None else None,
            "match_score": float(m.match_score) if m.match_score is not None else None,
            "skills_score": float(m.skills_score) if m.skills_score is not None else None,
            "experience_score": float(m.experience_score) if m.experience_score is not None else None,
            "notice_period_score": float(m.notice_period_score) if m.notice_period_score is not None else None,
            "location_score": float(m.location_score) if m.location_score is not None else None,
            "status": m.status.value,
            "explanation": m.match_explanation,
        } for m in mappings]
    finally:
        session.close()

import json
from uuid import UUID
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from celery.result import AsyncResult
from app.core.database import get_db
from app.models.job_description import JobDescription
from app.models.candidate import Candidate
from app.models.match_result import MatchResult
from app.schemas.match_result import MatchResultOut, MatchDetailOut
from app.core.tasks import run_matching_for_jd, run_bulk_matching, redis_client

router = APIRouter()

@router.post("/trigger/{jd_id}")
def trigger_matching(jd_id: UUID, db: Session = Depends(get_db)):
    try:
        jd = db.query(JobDescription).filter(JobDescription.id == jd_id).first()
        if not jd:
            raise HTTPException(status_code=404, detail="Job description not found")
            
        task = run_matching_for_jd.delay(str(jd_id))
        return {"job_id": task.id, "message": "Matching job triggered"}
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.error(f"Error triggering match: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/status/{job_id}")
def get_match_status(job_id: str):
    val = redis_client.get(f"task:{job_id}")
    if val:
        return json.loads(val)
        
    # Fallback to pure Celery check
    task_result = AsyncResult(job_id)
    return {
        "status": task_result.status,
        "progress": "Unknown",
        "result_count": 0
    }

@router.get("/{jd_id}", response_model=List[MatchResultOut])
def get_matches_for_jd(
    jd_id: UUID, 
    limit: int = Query(20, ge=1, le=100), 
    min_score: float = Query(0.0, ge=0.0, le=1.0),
    db: Session = Depends(get_db)
):
    try:
        matches = (
            db.query(MatchResult)
            .filter(MatchResult.jd_id == jd_id, MatchResult.total_score >= min_score)
            .order_by(MatchResult.total_score.desc())
            .limit(limit)
            .all()
        )
        if not matches:
            # Check if JD exists
            jd = db.query(JobDescription).filter(JobDescription.id == jd_id).first()
            if not jd:
                raise HTTPException(status_code=404, detail="Job description not found")
        
        return matches
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.error(f"Error fetching matches: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{jd_id}/{candidate_id}")
def get_match_explanation(jd_id: UUID, candidate_id: UUID, db: Session = Depends(get_db)):
    try:
        match = (
            db.query(MatchResult)
            .filter(MatchResult.jd_id == jd_id, MatchResult.candidate_id == candidate_id)
            .first()
        )
        if not match:
            raise HTTPException(status_code=404, detail="Match not found")
            
        return match.explanation_detail
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.error(f"Error fetching explanation: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


import json
import redis
from celery import Celery, group
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.matcher import HybridMatcher
from app.models.job_description import JobDescription
from app.models.candidate import Candidate
from app.models.match_result import MatchResult
from app.core import ai_parser
import logging
import time

logger = logging.getLogger(__name__)

# Setup Celery
celery_app = Celery(
    "matching_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.core.tasks"]
)

celery_app.conf.update(
    result_backend=settings.REDIS_URL,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_ignore_result=False,
)

# Setup Redis Client for status tracking
redis_client = redis.StrictRedis.from_url(settings.REDIS_URL, decode_responses=True)

matcher = None

def get_matcher():
    global matcher
    if matcher is None:
        matcher = HybridMatcher()
    return matcher

def update_task_status(job_id: str, status: str, progress: str, result_count: int):
    # Store in Redis with 1 hour expiration
    redis_client.setex(
        f"task:{job_id}",
        3600,
        json.dumps({
            "status": status,
            "progress": progress,
            "result_count": result_count
        })
    )

@celery_app.task(bind=True, max_retries=3, default_retry_delay=5)
def embed_and_store_jd(self, jd_id: str):
    db: Session = SessionLocal()
    try:
        jd = db.query(JobDescription).filter(JobDescription.id == UUID(jd_id)).first()
        if not jd:
            return
        
        m = get_matcher()
        desc = jd.description or ""
        
        # --- AI Parsing Extension ---
        try:
            logger.info(f"Task {self.request.id}: Attempting AI parsing for JD {jd_id}")
            ai_data = ai_parser.extract_skills_and_summary(desc)
            if ai_data:
                # Overwrite heuristics with AI validated skills
                if ai_data.get("extracted_skills"):
                    # SQLAlchemy requires reassigning the list to trigger array update natively
                    jd.required_skills = ai_data["extracted_skills"]
                if ai_data.get("summary"):
                    jd.ai_summary = ai_data["summary"]
                logger.info(f"Task {self.request.id}: AI Parsing successful for JD {jd_id}")
            else:
                logger.warning(f"Task {self.request.id}: AI Parsing returned None. Proceeding with fallback values.")
        except Exception as e:
            logger.error(f"Task {self.request.id}: AI Parsing encountered non-blocking error: {e}. Proceeding with fallback values.")
        # --- End AI Parsing Extension ---
        
        embedding = m.embed_text(desc).tolist()
        jd.embedding = embedding
        
        db.commit()
    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc, countdown=5)
    finally:
        db.close()

@celery_app.task(bind=True, max_retries=3, default_retry_delay=5)
def embed_and_store_candidate(self, candidate_id: str):
    db: Session = SessionLocal()
    try:
        cand = db.query(Candidate).filter(Candidate.id == UUID(candidate_id)).first()
        if not cand:
            return
        
        m = get_matcher()
        desc = cand.resume_text or ""
        embedding = m.embed_text(desc).tolist()
        cand.embedding = embedding
        
        db.commit()
    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc, countdown=5)
    finally:
        db.close()

@celery_app.task(bind=True, max_retries=3, default_retry_delay=5)
def run_matching_for_jd(self, jd_id: str):
    job_id = self.request.id
    db: Session = SessionLocal()
    start_time = time.time()
    try:
        update_task_status(job_id, "running", "0/0", 0)
        logger.info(f"Match triggered. Task ID: {job_id} | JD ID: {jd_id}")
        
        jd = db.query(JobDescription).filter(JobDescription.id == UUID(jd_id)).first()
        if not jd:
            logger.error(f"Failed Match Trigger: JD {jd_id} not found natively")
            update_task_status(job_id, "failed", "0/0", 0)
            return
            
        candidates = db.query(Candidate).all()
        total_cands = len(candidates)
        logger.info(f"Loaded {total_cands} candidates. Starting vector logic...")
        
        m = get_matcher()
        results = []
        flags_raised = 0
        
        for i, cand in enumerate(candidates):
            # Compute match
            match = m.match_candidate_to_jd(jd, cand)
            if match.explanation_detail and match.explanation_detail.get('flags'):
                flags_raised += len(match.explanation_detail['flags'])
            results.append(match)
            
            # Log progress every 100
            if (i + 1) % 100 == 0:
                logger.info(f"Task {job_id} Progression: processed {i + 1} / {total_cands}")
                update_task_status(job_id, "running", f"{i + 1}/{total_cands}", len(results))

        # Clear existing old matches for this JD (upsert behavior requested: replace)
        if results:
            db.query(MatchResult).filter(MatchResult.jd_id == UUID(jd_id)).delete()
            # Save to DB
            db.add_all(results)
            db.commit()
        
        elapsed_time_ms = (time.time() - start_time) * 1000
        logger.info(f"Match task {job_id} Completed! Time taken: {elapsed_time_ms:.2f}ms | Tracked {flags_raised} warning flags natively.")
        update_task_status(job_id, "complete", f"{total_cands}/{total_cands}", len(results))
        return [str(r.id) for r in results]

    except Exception as exc:
        db.rollback()
        logger.exception(f"Unexpected fatal error inside match loop {job_id}")
        update_task_status(job_id, "failed", "error", 0)
        raise self.retry(exc=exc, countdown=5)
    finally:
        db.close()

@celery_app.task(bind=True)
def run_bulk_matching(self, jd_ids: list[str]):
    # Uses Chord/Group for parallelism
    job = group(run_matching_for_jd.s(jd_id) for jd_id in jd_ids)
    result = job.apply_async()
    return result.id


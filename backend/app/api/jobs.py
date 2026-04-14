import io
import pandas as pd
from uuid import UUID
from typing import List, Union
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.job_description import JobDescription
from app.schemas.job_description import JobDescriptionCreate, JobDescriptionOut
from app.core.tasks import embed_and_store_jd

router = APIRouter()

@router.post("", response_model=JobDescriptionOut)
def create_job(job_in: JobDescriptionCreate, db: Session = Depends(get_db)):
    try:
        job_obj = JobDescription(**job_in.model_dump())
        db.add(job_obj)
        db.commit()
        db.refresh(job_obj)
        
        # Trigger embedding generation
        embed_and_store_jd.delay(str(job_obj.id))
        
        return job_obj
    except Exception as e:
        import logging
        logging.error(f"Error creating job: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while creating job")

@router.post("/bulk", response_model=List[JobDescriptionOut])
async def create_jobs_bulk(jobs_in: Union[List[JobDescriptionCreate], None] = None, file: UploadFile = File(None), db: Session = Depends(get_db)):
    try:
        created_jobs = []
        
        if jobs_in:
            for job_in in jobs_in:
                job_obj = JobDescription(**job_in.model_dump())
                db.add(job_obj)
                created_jobs.append(job_obj)
                
        if file:
            if not file.filename.endswith('.csv'):
                raise HTTPException(status_code=400, detail="Only CSV files are supported")
            contents = await file.read()
            try:
                df = pd.read_csv(io.StringIO(contents.decode('utf-8')))
            except Exception as e:
                raise HTTPException(status_code=400, detail="Error reading CSV file")
                
            # Map columns flexibly
            col_map = {c.lower().replace(' ', '_'): c for c in df.columns}
            if 'title' not in col_map and 'job_title' not in col_map:
                raise HTTPException(status_code=422, detail="Missing required column 'title'")
            if 'description' not in col_map and 'job_description' not in col_map:
                raise HTTPException(status_code=422, detail="Missing required column 'description'")
                
            title_col = col_map.get('title') or col_map.get('job_title')
            desc_col = col_map.get('description') or col_map.get('job_description')
                
            for index, row in df.iterrows():
                title = row.get(title_col)
                if pd.isna(title):
                    continue
                    
                req_skills = []
                req_col = col_map.get('required_skills')
                if req_col and pd.notna(row.get(req_col)):
                    req_skills = [s.strip() for s in str(row.get(req_col)).split(',')]
                
                pref_skills = []
                pref_col = col_map.get('preferred_skills')
                if pref_col and pd.notna(row.get(pref_col)):
                    pref_skills = [s.strip() for s in str(row.get(pref_col)).split(',')]
                    
                yoe_min_col = col_map.get('experience_years_min', 'experience_years_min')
                yoe_max_col = col_map.get('experience_years_max', 'experience_years_max')
                
                job_data = {
                    "title": title,
                    "company": str(row.get(col_map.get('company', 'company'))) if pd.notna(row.get(col_map.get('company', 'company'))) else None,
                    "description": str(row.get(desc_col)) if pd.notna(row.get(desc_col)) else "",
                    "required_skills": req_skills,
                    "preferred_skills": pref_skills,
                    "experience_years_min": int(row.get(yoe_min_col)) if pd.notna(row.get(yoe_min_col)) else None,
                    "experience_years_max": int(row.get(yoe_max_col)) if pd.notna(row.get(yoe_max_col)) else None,
                    "seniority_level": str(row.get(col_map.get('seniority_level', 'seniority_level'))) if pd.notna(row.get(col_map.get('seniority_level', 'seniority_level'))) else None
                }
                
                job_obj = JobDescription(**job_data)
                db.add(job_obj)
                created_jobs.append(job_obj)
                
        if not created_jobs:
            raise HTTPException(status_code=400, detail="No valid jobs provided")
            
        db.commit()
        for job in created_jobs:
            db.refresh(job)
            embed_and_store_jd.delay(str(job.id))
            
        return created_jobs
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.error(f"Error bulk uploading jobs: {e}")
        raise HTTPException(status_code=500, detail="Internal server error processing bulk upload")

@router.get("", response_model=List[JobDescriptionOut])
def list_jobs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    try:
        jobs = db.query(JobDescription).offset(skip).limit(limit).all()
        return jobs
    except Exception as e:
        import logging
        logging.error(f"Error listing jobs: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while listing jobs")

@router.get("/{jd_id}", response_model=JobDescriptionOut)
def get_job(jd_id: UUID, db: Session = Depends(get_db)):
    try:
        job = db.query(JobDescription).filter(JobDescription.id == jd_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job description not found")
        return job
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.error(f"Error fetching job: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while fetching job")

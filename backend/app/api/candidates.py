import io
import pandas as pd
from uuid import UUID
from typing import List, Union
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.candidate import Candidate
from app.schemas.candidate import CandidateCreate, CandidateOut
from app.core.tasks import embed_and_store_candidate

router = APIRouter()

@router.post("", response_model=CandidateOut)
def create_candidate(candidate_in: CandidateCreate, db: Session = Depends(get_db)):
    try:
        # Check email duplicate
        existing = db.query(Candidate).filter(Candidate.email == candidate_in.email).first()
        if existing:
            raise HTTPException(status_code=409, detail="Email already registered")
            
        cand_obj = Candidate(**candidate_in.model_dump())
        db.add(cand_obj)
        db.commit()
        db.refresh(cand_obj)
        
        embed_and_store_candidate.delay(str(cand_obj.id))
        
        return cand_obj
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.error(f"Error creating candidate: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while creating candidate")

@router.post("/bulk", response_model=List[CandidateOut])
async def create_candidates_bulk(candidates_in: Union[List[CandidateCreate], None] = None, file: UploadFile = File(None), db: Session = Depends(get_db)):
    created_cands = []
    
    if candidates_in:
        for cand_in in candidates_in:
            existing = db.query(Candidate).filter(Candidate.email == cand_in.email).first()
            if not existing:
                cand_obj = Candidate(**cand_in.model_dump())
                db.add(cand_obj)
                created_cands.append(cand_obj)
            
    if file:
        if not file.filename.endswith('.csv'):
            raise HTTPException(status_code=400, detail="Only CSV files are supported")
        contents = await file.read()
        try:
            df = pd.read_csv(io.StringIO(contents.decode('utf-8')))
            col_map = {c.lower().replace(' ', '_'): c for c in df.columns}
            
            if 'name' not in col_map and 'full_name' not in col_map:
                raise HTTPException(status_code=422, detail="Missing required column 'name'")
            if 'email' not in col_map:
                raise HTTPException(status_code=422, detail="Missing required column 'email'")
            if 'resume_text' not in col_map and 'resume' not in col_map:
                raise HTTPException(status_code=422, detail="Missing required column 'resume_text'")
                
            name_col = col_map.get('name') or col_map.get('full_name')
            email_col = col_map.get('email')
            resume_col = col_map.get('resume_text') or col_map.get('resume')
            
            for _, row in df.iterrows():
                email = str(row[email_col]).strip()
                existing = db.query(Candidate).filter(Candidate.email == email).first()
                if existing:
                    continue # Skip duplicates in bulk upload
                    
                cand_data = {
                    "name": row[name_col],
                    "email": email,
                    "resume_text": row[resume_col],
                    "current_role": row.get(col_map.get('current_role', 'current_role')),
                    "years_of_experience": row.get(col_map.get('years_of_experience', 'years_of_experience'))
                }
                
                skills_col = col_map.get('skills')
                if skills_col and pd.notna(row[skills_col]):
                    cand_data["skills"] = [s.strip() for s in str(row[skills_col]).split(',')]

                # Fill NaNs
                cand_data = {k: (v if pd.notna(v) else None) for k, v in cand_data.items()}
                
                try:
                    if cand_data.get("years_of_experience") is not None:
                        cand_data["years_of_experience"] = float(cand_data["years_of_experience"])
                except ValueError:
                    cand_data["years_of_experience"] = None
                    
                cand_obj = Candidate(**cand_data)
                db.add(cand_obj)
                created_cands.append(cand_obj)
                
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error parsing CSV: {str(e)}")

    if not created_cands:
        import logging
        logging.getLogger("fastapi").warning("No valid candidates processed")
        
    db.commit()
    for c in created_cands:
        db.refresh(c)
        embed_and_store_candidate.delay(str(c.id))
        
    return created_cands

@router.get("", response_model=List[CandidateOut])
def list_candidates(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    try:
        candidates = db.query(Candidate).offset(skip).limit(limit).all()
        return candidates
    except Exception as e:
        import logging
        logging.error(f"Error listing candidates: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{candidate_id}", response_model=CandidateOut)
def get_candidate(candidate_id: UUID, db: Session = Depends(get_db)):
    try:
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")
        return candidate
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.error(f"Error fetching candidate: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


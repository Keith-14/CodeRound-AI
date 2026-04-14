from uuid import UUID
from typing import List, Any, Dict
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class MatchDetailOut(BaseModel):
    model_config = ConfigDict(extra="allow")

class MatchResultOut(BaseModel):
    id: UUID
    jd_id: UUID
    candidate_id: UUID
    total_score: float
    semantic_score: float
    skill_score: float
    experience_score: float
    recency_score: float
    matched_skills: List[str]
    missing_skills: List[str]
    explanation_summary: str
    explanation_detail: Dict[str, Any]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


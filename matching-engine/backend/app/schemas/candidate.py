from uuid import UUID
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class CandidateCreate(BaseModel):
    name: str
    email: str
    resume_text: str
    skills: List[str] = []
    years_of_experience: Optional[float] = None
    current_role: Optional[str] = None

class CandidateOut(CandidateCreate):
    id: UUID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

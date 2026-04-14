from uuid import UUID
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class JobDescriptionCreate(BaseModel):
    title: str
    company: Optional[str] = None
    description: str
    required_skills: List[str] = []
    preferred_skills: List[str] = []
    experience_years_min: Optional[int] = None
    experience_years_max: Optional[int] = None
    seniority_level: Optional[str] = None

class JobDescriptionOut(JobDescriptionCreate):
    id: UUID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

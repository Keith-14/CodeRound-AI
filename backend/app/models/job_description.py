import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from pgvector.sqlalchemy import Vector
from app.core.database import Base

class JobDescription(Base):
    __tablename__ = "job_descriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    title = Column(String, nullable=False)
    company = Column(String, nullable=True)
    description = Column(String, nullable=False)
    required_skills = Column(ARRAY(String), default=list)
    preferred_skills = Column(ARRAY(String), default=list)
    experience_years_min = Column(Integer, nullable=True)
    experience_years_max = Column(Integer, nullable=True)
    seniority_level = Column(String, nullable=True)
    ai_summary = Column(String, nullable=True)
    embedding = Column(Vector(384), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


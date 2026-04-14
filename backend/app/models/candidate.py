import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, Float, String, DateTime
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from pgvector.sqlalchemy import Vector
from app.core.database import Base

class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    resume_text = Column(String, nullable=False)
    skills = Column(ARRAY(String), default=list)
    years_of_experience = Column(Float, nullable=True)
    current_role = Column(String, nullable=True)
    embedding = Column(Vector(384), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


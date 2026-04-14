from sqlalchemy import Column, Integer, String, Text, ForeignKey
from pgvector.sqlalchemy import Vector
from .base import Base

class Candidate(Base):
    __tablename__ = "candidates"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    resume_text = Column(Text)
    embedding = Column(Vector(384))  # for all-MiniLM-L6-v2 (384 dimensions)

class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(Text)
    embedding = Column(Vector(384))

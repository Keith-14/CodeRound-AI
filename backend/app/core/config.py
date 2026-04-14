import os
import logging
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

SUPPORTED_MODELS = {
    "all-MiniLM-L6-v2": 384,
    "paraphrase-MiniLM-L6-v2": 384,
    "all-mpnet-base-v2": 768
}

class Settings(BaseSettings):
    PROJECT_NAME: str = "Job-Candidate Matching Engine"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/matching_engine")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    MODEL_NAME: str = os.getenv("MODEL_NAME", "all-MiniLM-L6-v2")
    WEIGHT_SEMANTIC: float = float(os.getenv("WEIGHT_SEMANTIC", "0.45"))
    WEIGHT_SKILL: float = float(os.getenv("WEIGHT_SKILL", "0.30"))
    WEIGHT_EXPERIENCE: float = float(os.getenv("WEIGHT_EXPERIENCE", "0.15"))
    WEIGHT_RECENCY: float = float(os.getenv("WEIGHT_RECENCY", "0.10"))
    
    class Config:
        env_file = ".env"

settings = Settings()

# Startup Guard
if settings.MODEL_NAME not in SUPPORTED_MODELS:
    raise ValueError(f"Model {settings.MODEL_NAME} is not in SUPPORTED_MODELS. Must be one of {list(SUPPORTED_MODELS.keys())}")

resolved_dim = SUPPORTED_MODELS[settings.MODEL_NAME]
if resolved_dim != 384:
    raise RuntimeError(
        f"Embedding Dimension mismatch! Expected 384 (pgvector setup), but model {settings.MODEL_NAME} is {resolved_dim} dims. "
        "You must run an Alembic migration and truncate the existing embedding columns before switching models."
    )
else:
    logger.warning("Embedding model locked to all-MiniLM-L6-v2 (384 dims). Changing MODEL_NAME requires a schema migration.")



from fastapi import APIRouter
from . import jobs, candidates, match

api_router = APIRouter()
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(candidates.router, prefix="/candidates", tags=["candidates"])
api_router.include_router(match.router, prefix="/match", tags=["match"])


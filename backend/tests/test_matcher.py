import pytest
from unittest.mock import MagicMock
from app.core.matcher import HybridMatcher
from app.models.candidate import Candidate
from app.models.job_description import JobDescription
import numpy as np

@pytest.fixture(scope="module")
def matcher():
    return HybridMatcher()

def test_empty_profile_handling(matcher):
    jd = MagicMock(spec=JobDescription)
    jd.id = "jd-123"
    jd.description = "We need an amazing Python engineer who knows Django and React. Minimum 5 years."
    jd.required_skills = ["python", "django"]
    jd.preferred_skills = ["react"]
    jd.experience_years_min = 5
    jd.experience_years_max = None
    jd.embedding = np.ones(384)

    cand = MagicMock(spec=Candidate)
    cand.id = "cand-123"
    # Provide absolutely empty profile
    cand.resume_text = "   "
    cand.skills = []
    cand.years_of_experience = None

    result = matcher.match_candidate_to_jd(jd, cand)
    
    assert result.total_score == 0.0
    assert "empty profile" in result.explanation_detail["flags"]

def test_vague_jd_handling(matcher):
    jd = MagicMock(spec=JobDescription)
    jd.id = "jd-123"
    # Less than 50 words
    jd.description = "Short JD here."
    jd.required_skills = ["python"]
    jd.preferred_skills = []
    jd.experience_years_min = 2
    jd.experience_years_max = None
    jd.embedding = np.ones(384)

    cand = MagicMock(spec=Candidate)
    cand.id = "cand-123"
    cand.resume_text = "I am a skilled Python developer. " * 20 # > 50 words
    cand.skills = ["python"]
    cand.years_of_experience = 3
    cand.embedding = np.ones(384)

    result = matcher.match_candidate_to_jd(jd, cand)
    
    assert "vague JD" in result.explanation_detail["flags"]

def test_no_skills_overlap_behavior(matcher):
    jd = MagicMock(spec=JobDescription)
    jd.id = "jd-123"
    jd.description = "Valid JD text taking up plenty of space here... " * 15
    jd.required_skills = ["docker"]
    jd.preferred_skills = []
    jd.experience_years_min = None
    jd.experience_years_max = None
    jd.embedding = np.ones(384)

    cand = MagicMock(spec=Candidate)
    cand.id = "cand-123"
    cand.resume_text = "Experienced person here... " * 15
    # No skills at all
    cand.skills = []
    cand.years_of_experience = 5
    cand.embedding = np.ones(384)

    result = matcher.match_candidate_to_jd(jd, cand)
    
    # skill score should be zero due to no overlap boundary mapping
    assert result.skill_score == 0.0
    assert "no skills" in result.explanation_detail["flags"]

def test_missing_experience_neutrality(matcher):
    jd = MagicMock(spec=JobDescription)
    jd.id = "jd-123"
    jd.description = "Valid JD... " * 15
    jd.required_skills = ["java"]
    jd.preferred_skills = []
    jd.experience_years_min = 5
    jd.experience_years_max = None
    jd.embedding = np.ones(384)

    cand = MagicMock(spec=Candidate)
    cand.id = "cand-123"
    cand.resume_text = "Has Java... " * 15
    cand.skills = ["java"]
    # Missing explicit YOE metric
    cand.years_of_experience = None
    cand.embedding = np.ones(384)

    result = matcher.match_candidate_to_jd(jd, cand)
    
    # Should fallback to neutral 0.5 without dropping to zero strictly
    assert result.experience_score == 0.5

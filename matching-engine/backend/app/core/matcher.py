import re
import time
import logging
import numpy as np
import spacy
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
from app.models import JobDescription, Candidate, MatchResult
from app.core.config import settings

logger = logging.getLogger(__name__)

# 100+ Common Technical Skills
TECH_SKILLS_DB = {
    "python", "fastapi", "react", "docker", "kubernetes", "postgresql", "redis", "aws", "gcp", "typescript", "node.js",
    "javascript", "java", "c++", "c#", "go", "rust", "ruby", "php", "django", "flask", "spring", "express", "vue",
    "angular", "svelte", "html", "css", "sass", "less", "tailwind", "bootstrap", "sql", "nosql", "mongodb", "cassandra",
    "elasticsearch", "mysql", "mariadb", "sqlite", "oracle", "azure", "heroku", "digitalocean", "terraform", "ansible",
    "chef", "puppet", "jenkins", "gitlab", "github", "bitbucket", "ci/cd", "linux", "unix", "bash", "shell", "powershell",
    "git", "svn", "mercurial", "agile", "scrum", "kanban", "jira", "trello", "confluence", "machine learning", "deep learning",
    "artificial intelligence", "data science", "nlp", "computer vision", "tensorflow", "pytorch", "keras", "scikit-learn",
    "pandas", "numpy", "matplotlib", "seaborn", "hadoop", "spark", "kafka", "rabbitmq", "celery", "graphql", "rest", "soap",
    "grpc", "microservices", "serverless", "lambda", "blockchain", "solidity", "web3", "smart contracts", "cybersecurity",
    "penetration testing", "cryptography", "oauth", "jwt", "saml", "tcp/ip", "dns", "http", "https", "websocket",
    "webpack", "babel", "vite", "npm", "yarn", "go-lang", "objective-c", "swift", "kotlin", "scala", "clojure", "elixir",
    "erlang", "haskell", "lua", "perl", "r", "pytest", "jest", "cypress"
}

class HybridMatcher:
    def __init__(self):
        # 1. EMBEDDING SERVICE
        logger.info(f"Loading SentenceTransformer model for embeddings: {settings.MODEL_NAME}")
        self.encoder = SentenceTransformer(settings.MODEL_NAME)
        logger.info("Loading SpaCy en_core_web_sm model...")
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            import spacy.cli
            spacy.cli.download("en_core_web_sm")
            self.nlp = spacy.load("en_core_web_sm")

    def embed_text(self, text: str) -> np.ndarray:
        try:
            if not text or not text.strip():
                return np.zeros(384)
            return self.encoder.encode(text)
        except Exception as e:
            logger.error(f"Embedding failure: {e}")
            return np.zeros(384)

    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        try:
            return [self.encoder.encode(t) if (t and t.strip()) else np.zeros(384) for t in texts]
        except Exception as e:
            logger.error(f"Batch embedding failure: {e}")
            return [np.zeros(384)] * len(texts)

    # 2. SKILL EXTRACTOR
    def extract_skills(self, text: str) -> List[str]:
        doc = self.nlp(text)
        lower_text = text.lower()
        extracted = set()

        # SpaCy-assisted parsing + strict keyword matching
        for skill in TECH_SKILLS_DB:
            # Quick bounding check
            if skill in lower_text:
                # To prevent sub-word matching (like 'go' in 'good'), we can use regex
                # Example regex: \bgo\b
                # We compile dynamically for exact token matching
                pattern = r"\b" + re.escape(skill) + r"\b"
                if re.search(pattern, lower_text):
                    extracted.add(skill)
        
        return list(extracted)

    # 3. EXPERIENCE PARSER
    def parse_years_experience(self, text: str) -> Optional[float]:
        # Matches patterns like "5 years", "3.5+ years", "2-4 years"
        # Search for ranges like 2-4 years first
        range_pattern = r'(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*years?'
        range_match = re.search(range_pattern, text, re.IGNORECASE)
        if range_match:
            return float(range_match.group(2))  # Take the higher bound optimistically

        # General number matching
        pattern = r'(\d+(?:\.\d+)?)\s*(?:\+|-\s*\d+(?:\.\d+)?)?\s*years?'
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            return max([float(m) for m in matches])
        return None

    def parse_seniority(self, text: str) -> Optional[str]:
        lower_t = text.lower()
        if "lead" in lower_t or "principal" in lower_t:
            return "lead"
        if "senior" in lower_t or "snr" in lower_t:
            return "senior"
        if "mid" in lower_t or "mid-level" in lower_t or "intermediate" in lower_t:
            return "mid"
        if "junior" in lower_t or "jnr" in lower_t or "entry" in lower_t or "intern" in lower_t:
            return "junior"
        return None

    # 4. SCORING METHODS
    def semantic_similarity(self, jd_embedding, candidate_embedding) -> float:
        if jd_embedding is None or candidate_embedding is None:
            return 0.0
        # Cosine similarity calculation
        jd_norm = np.linalg.norm(jd_embedding)
        cd_norm = np.linalg.norm(candidate_embedding)
        if jd_norm == 0 or cd_norm == 0:
            return 0.0
        return float(np.dot(jd_embedding, candidate_embedding) / (jd_norm * cd_norm))

    def skill_overlap_score(self, jd_required: List[str], jd_preferred: List[str], candidate_skills: List[str]) -> float:
        jd_req_set = set([s.lower() for s in (jd_required or [])])
        jd_pref_set = set([s.lower() for s in (jd_preferred or [])])
        cand_set = set([s.lower() for s in (candidate_skills or [])])

        max_score = len(jd_req_set) * 2 + len(jd_pref_set)
        if max_score == 0:
            # If no skills asked, they implicitly match 100%
            return 1.0 

        req_matched = len(jd_req_set.intersection(cand_set))
        pref_matched = len(jd_pref_set.intersection(cand_set))

        score = (req_matched * 2 + pref_matched) / max_score
        return min(1.0, float(score))

    def experience_match_score(self, jd_min_years: Optional[int], jd_max_years: Optional[int], candidate_years: Optional[float]) -> float:
        if candidate_years is None:
            return 0.5  # Neutral fallback default
        
        if jd_min_years is None and jd_max_years is None:
            return 1.0
            
        jd_min = jd_min_years or 0
        min_score = 1.0
        if candidate_years < jd_min:
            # Score decays based on how far below
            if jd_min == 0:
                min_score = 1.0
            else:
                min_score = max(0.0, candidate_years / jd_min)
        
        max_score = 1.0
        if jd_max_years is not None and candidate_years > jd_max_years:
            # Decay slightly for being overqualified (e.g., 5% per year)
            diff = candidate_years - jd_max_years
            max_score = max(0.0, 1.0 - (diff * 0.05))

        return min(min_score, max_score)

    def compute_total_score(self, semantic: float, skill: float, experience: float, recency: float = 1.0) -> float:
        # Formula uses environment configured weights
        return float(
            (settings.WEIGHT_SEMANTIC * semantic) + 
            (settings.WEIGHT_SKILL * skill) + 
            (settings.WEIGHT_EXPERIENCE * experience) + 
            (settings.WEIGHT_RECENCY * recency)
        )

    # 5. EXPLANATION GENERATOR
    def generate_explanation(self, jd: JobDescription, candidate: Candidate, scores: Dict[str, float], matched_skills: List[str], missing_skills: List[str], candidate_years: Optional[float], flags: set) -> Dict[str, Any]:
        req_count = len(jd.required_skills) if jd.required_skills else 0
        match_count = len(matched_skills)
        exp_score = scores.get('experience', 0)
        
        if exp_score >= 0.8:
            exp_assessment = "meets or exceeds requirement"
        elif exp_score >= 0.5:
            exp_assessment = "partially meets requirement or no strict requirement"
        else:
            exp_assessment = "is below requirement"

        yoe_str = f"{candidate_years} years" if candidate_years is not None else "an unknown amount"
        
        total_score = scores.get('total', 0)
        adjective = "strong" if total_score > 0.7 else "moderate" if total_score > 0.4 else "weak"
        
        summary = (f"Candidate {candidate.name} is a {adjective} match. "
                   f"They bring {match_count} of {req_count} required skills and {yoe_str} of experience. "
                   f"Their profile {exp_assessment}.")

        return {
            "summary": summary,
            "score_breakdown": {
                "semantic": scores.get('semantic', 0),
                "skill": scores.get('skill', 0),
                "experience": exp_score,
                "recency": scores.get('recency', 1.0)
            },
            "matched_skills": list(matched_skills),
            "missing_skills": list(missing_skills),
            "experience_assessment": exp_assessment,
            "flags": list(flags)
        }

    # 6. MAIN MATCH METHOD
    def match_candidate_to_jd(self, jd: JobDescription, candidate: Candidate) -> MatchResult:
        flags = set()
        
        jd_desc = jd.description or ""
        cd_desc = candidate.resume_text or ""
        
        # Word counts for edge cases
        jd_words = len(jd_desc.split())
        cd_words = len(cd_desc.split())

        # Hard failure: empty profile
        if not cd_desc.strip():
            flags.add("empty profile")
            total_score = 0.0
            return MatchResult(
                jd_id=jd.id,
                candidate_id=candidate.id,
                total_score=0.0,
                semantic_score=0.0,
                skill_score=0.0,
                experience_score=0.0,
                recency_score=0.0,
                matched_skills=[],
                missing_skills=[],
                explanation_summary="Profile is completely empty.",
                explanation_detail={"flags": list(flags)}
            )
        
        # Vague JD check
        if jd_words < 50:
            flags.add("vague JD")

        # Thin profile check
        is_thin = False
        if cd_words < 50:
            flags.add("thin profile")
            is_thin = True

        # Parse inputs if missing
        cand_skills = candidate.skills
        if not cand_skills and cd_desc:
            cand_skills = self.extract_skills(cd_desc)
            
        cand_years = candidate.years_of_experience
        if cand_years is None and cd_desc:
            cand_years = self.parse_years_experience(cd_desc)
            
        # Convert to embeddings if not present
        jd_emb = np.array(jd.embedding) if getattr(jd, 'embedding', None) is not None else self.embed_text(jd_desc)
        cd_emb = np.array(candidate.embedding) if getattr(candidate, 'embedding', None) is not None else self.embed_text(cd_desc)

        semantic_score = self.semantic_similarity(jd_emb, cd_emb)
        if is_thin:
            semantic_score *= 0.7 # Reduce semantic weight by 30% for thin profiles
            
        jd_req_set = set([s.lower() for s in (jd.required_skills or [])])
        cand_set = set([s.lower() for s in (cand_skills or [])])
        
        # Skill constraint
        if not jd_req_set or not cand_set:
            skill_score = 0.0
            flags.add("no skills")
            matched_set = set()
            missing_set = jd_req_set
        else:
            skill_score = self.skill_overlap_score(jd.required_skills, jd.preferred_skills, cand_skills)
            matched_set = jd_req_set.intersection(cand_set)
            missing_set = jd_req_set - cand_set
        
        if missing_set and "no skills" not in flags:
            flags.add("missing skills")

        exp_score = self.experience_match_score(jd.experience_years_min, jd.experience_years_max, cand_years)
        
        rec_score = 1.0 # Set static neutral/positive recency score since parsing not strictly defined
        
        total_score = self.compute_total_score(semantic_score, skill_score, exp_score, rec_score)

        scores = {
            "total": total_score,
            "semantic": semantic_score,
            "skill": skill_score,
            "experience": exp_score,
            "recency": rec_score
        }

        explanation = self.generate_explanation(
            jd=jd,
            candidate=candidate,
            scores=scores,
            matched_skills=list(matched_set),
            missing_skills=list(missing_set),
            candidate_years=cand_years,
            flags=flags
        )

        return MatchResult(
            jd_id=jd.id,
            candidate_id=candidate.id,
            total_score=total_score,
            semantic_score=semantic_score,
            skill_score=skill_score,
            experience_score=exp_score,
            recency_score=rec_score,
            matched_skills=list(matched_set),
            missing_skills=list(missing_set),
            explanation_summary=explanation["summary"],
            explanation_detail=explanation
        )

    # 7. BULK MATCH METHOD
    def rank_candidates_for_jd(self, jd: JobDescription, candidates: List[Candidate]) -> List[MatchResult]:
        results = [self.match_candidate_to_jd(jd, cand) for cand in candidates]
        results.sort(key=lambda x: x.total_score, reverse=True)
        return results

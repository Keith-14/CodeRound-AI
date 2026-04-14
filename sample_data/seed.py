import os
import re
import json
import time
import requests
import pandas as pd
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env'))

try:
    from google import genai as _genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    print("[warn] google-genai not installed — falling back to Skills Required line parsing")

API_URL = os.environ.get("API_URL", "http://localhost:8000/api/v1")

# ---------------------------------------------------------------------------
# Candidate Parsing
# ---------------------------------------------------------------------------

def clean_text_enums(text: str) -> str:
    if pd.isna(text) or not text:
        return ""
    return re.sub(r'\b\w+\.\w+\b', '', str(text))


def clean_json_punctuation(text: str) -> str:
    if pd.isna(text) or not text:
        return ""
    text = re.sub(r'[{}\[\]"\'\n]', ' ', str(text))
    return re.sub(r'\s+', ' ', text).strip()


def parse_candidates(csv_path: str) -> List[Dict[str, Any]]:
    df = pd.read_csv(csv_path)
    candidates = []

    for _, row in df.iterrows():
        name = str(row.get('full_name', row.get('name', 'Unknown')))
        if pd.isna(name) or name == 'nan':
            continue

        email = name.lower().replace(" ", ".") + "@candidate.com"

        skills_set = set()
        for col in ['parsed_skills', 'programming_languages', 'backend_frameworks', 'frontend_technologies']:
            val = row.get(col)
            if pd.notna(val) and str(val).strip():
                for s in str(val).split(','):
                    cleaned = s.strip().lower()
                    if cleaned:
                        skills_set.add(cleaned)

        summary = clean_text_enums(row.get('parsed_summary', ''))
        work_exp = clean_text_enums(clean_json_punctuation(row.get('parsed_work_experience', '')))
        resume_text = f"{summary}\n\nWork Experience:\n{work_exp}".strip()

        yoe = None
        yoe_raw = row.get('years_of_experience')
        if pd.notna(yoe_raw):
            try:
                yoe_val = float(yoe_raw)
                if yoe_val > 0:
                    yoe = yoe_val
            except ValueError:
                pass

        current_role = row.get('current_title')
        current_role = None if pd.isna(current_role) else str(current_role)

        candidates.append({
            "name": name,
            "email": email,
            "resume_text": resume_text,
            "skills": list(skills_set),
            "years_of_experience": yoe,
            "current_role": current_role,
        })

    return candidates


# ---------------------------------------------------------------------------
# JD Skill Extraction
# ---------------------------------------------------------------------------

# Words that indicate a phrase is a job duty, not a skill name
DUTY_KEYWORDS = [
    "framework", "system", "pipeline", "testing", "monitoring",
    "generation", "application", "management", "strategy", "process",
    "solution", "practice", "methodology", "environment", "integration",
    "deployment", "architecture", "optimization", "analysis", "design",
]

# Known multi-word skills that should NOT be filtered even if they contain duty words
SKILL_WHITELIST = {
    "machine learning", "deep learning", "natural language processing",
    "generative ai", "prompt engineering", "api development",
    "cloud infrastructure", "distributed systems", "vector databases",
    "weights & biases", "mlflow", "scikit-learn", "tensorflow",
    "a/b testing", "ci/cd", "mlops", "nlp", "rag",
}


def is_skill(s: str) -> bool:
    """Return True if the string looks like a real skill, not a job duty."""
    lower = s.lower().strip()
    if lower in SKILL_WHITELIST:
        return True
    if len(s) > 35:
        return False
    if any(kw in lower for kw in DUTY_KEYWORDS):
        return False
    # Reject vague sentences (more than 4 words)
    if len(s.split()) > 4:
        return False
    return True


def extract_skills_with_llm(jd_text: str) -> List[str]:
    """Use Gemini to extract clean technical skill names from a JD with retry + exponential backoff."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or not GENAI_AVAILABLE:
        return []

    max_retries = 3
    base_delay = 1  # seconds

    for attempt in range(max_retries):
        try:
            client = _genai.Client(api_key=api_key)

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=f"""You are a technical recruiter. Extract ONLY concrete technical skills,
tools, programming languages, and frameworks from this job description.

Rules:
- Return ONLY a flat JSON array of short strings (1-4 words max per item)
- Each item must be a specific technology or skill name, NOT a job duty or responsibility
- Good examples: ["Python", "FastAPI", "Docker", "RAG", "PostgreSQL", "PyTorch"]
- Bad examples: ["Build scalable systems", "Experience with APIs", "Team collaboration"]
- Do NOT include soft skills, years of experience, or vague phrases
- Just the JSON array, no markdown, no explanation

Job Description:
{jd_text}"""
            )

            raw = response.text.strip().replace("```json", "").replace("```", "").strip()
            skills = json.loads(raw)

            if isinstance(skills, list):
                extracted = [str(s).strip() for s in skills if str(s).strip()]
                filtered = [s for s in extracted if is_skill(s)]
                return filtered

            return []

        except Exception as e:
            # If last attempt → fallback
            if attempt == max_retries - 1:
                print(f"  [warn] Gemini skill extraction failed after {max_retries} attempts: {e}")
                return []

            # Exponential backoff
            delay = base_delay * (2 ** attempt)
            print(f"  [retry] Gemini failed (attempt {attempt + 1}) — retrying in {delay}s...")
            time.sleep(delay)


# ---------------------------------------------------------------------------
# JD Parsing
# ---------------------------------------------------------------------------

def parse_jobs(txt_path: str) -> List[Dict[str, Any]]:
    with open(txt_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()

    blocks = re.split(r'\n\s*\n\s*\n+', content)
    jobs = []

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        lines = block.split('\n')

        # First non-empty line = title
        title = next((l.strip() for l in lines if l.strip()), "")
        if not title:
            continue

        req_skills_bullets = []
        pref_skills = []
        skills_required_line: List[str] = []
        current_section = "desc"

        for line in lines:
            stripped = line.strip()
            lower = stripped.lower()

            if "core requirements" in lower:
                current_section = "req"
                continue
            elif "preferred qualifications" in lower:
                current_section = "pref"
                continue
            elif lower.startswith("skills required"):
                # This line already has clean comma-separated skill names
                skills_str = stripped.split(":", 1)[-1].strip() if ":" in stripped else ""
                if skills_str:
                    skills_required_line = [s.strip() for s in skills_str.split(",") if s.strip()]
                current_section = "desc"
                continue

            if current_section == "req" and stripped.startswith(("•", "-", "*")):
                req_skills_bullets.append(stripped.lstrip("•-* ").strip())
            elif current_section == "pref" and stripped.startswith(("•", "-", "*")):
                pref_skills.append(stripped.lstrip("•-* ").strip())

        description = block

        # Priority: Gemini → Skills Required line → empty
        llm_skills = extract_skills_with_llm(description)
        if llm_skills:
            print(f"    [llm] Extracted {len(llm_skills)} skills via Gemini for '{title}'")
            final_req_skills = llm_skills
        elif skills_required_line:
            print(f"    [fallback] Using 'Skills Required' line ({len(skills_required_line)} skills) for '{title}'")
            final_req_skills = skills_required_line
        else:
            print(f"    [fallback] Using regex bullets ({len(req_skills_bullets)} items) for '{title}'")
            final_req_skills = req_skills_bullets

        # Deduplicate preserving order
        seen = set()
        deduped = []
        for s in final_req_skills:
            key = s.lower()
            if key not in seen:
                seen.add(key)
                deduped.append(s)

        exp_match = re.search(r'minimum (\d+) years?', description, re.IGNORECASE)
        yoe_min = int(exp_match.group(1)) if exp_match else None

        lower_desc = description.lower()
        seniority = None
        if "lead" in lower_desc or "principal" in lower_desc:
            seniority = "lead"
        elif "senior" in lower_desc:
            seniority = "senior"
        elif "mid" in lower_desc:
            seniority = "mid"
        elif "junior" in lower_desc:
            seniority = "junior"

        jobs.append({
            "title": title,
            "description": description,
            "required_skills": deduped,
            "preferred_skills": pref_skills,
            "experience_years_min": yoe_min,
            "seniority_level": seniority,
        })

    return jobs


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates_path = os.path.join(base_dir, "combined_candidates.csv")
    jobs_path = os.path.join(base_dir, "Job_Descriptions.txt")

    print(f"Connecting to API at {API_URL}")
    print(f"GEMINI_API_KEY present: {bool(os.getenv('GEMINI_API_KEY'))}")
    print(f"GENAI_AVAILABLE: {GENAI_AVAILABLE}\n")

    # 1. Ingest Candidates
    if not os.path.exists(candidates_path):
        print(f"File not found: {candidates_path}")
    else:
        print("--- INGESTING CANDIDATES ---")
        for cand in parse_candidates(candidates_path):
            try:
                res = requests.post(f"{API_URL}/candidates", json=cand)
                if res.status_code in [200, 201]:
                    print(f"  ✓ {cand['name']} — {len(cand['skills'])} skills, {len(cand['resume_text'])} chars resume")
                elif res.status_code == 400 and "already" in res.text.lower():
                    print(f"  - {cand['name']} — Skipped (already exists)")
                else:
                    print(f"  ✗ {cand['name']} — Failed: {res.text}")
            except Exception as e:
                print(f"  ✗ {cand['name']} — Error: {e}")

    # 2. Ingest Jobs
    job_ids = []
    job_titles = {}
    if not os.path.exists(jobs_path):
        print(f"\nFile not found: {jobs_path}")
    else:
        print("\n--- INGESTING JOB DESCRIPTIONS ---")
        for job in parse_jobs(jobs_path):
            try:
                res = requests.post(f"{API_URL}/jobs", json=job)
                if res.status_code in [200, 201]:
                    jd_id = res.json()['id']
                    job_ids.append(jd_id)
                    job_titles[jd_id] = job['title']
                    print(f"  ✓ {job['title']} — {len(job['required_skills'])} required skills: {job['required_skills'][:5]}...")
                else:
                    print(f"  ✗ {job['title']} — Failed: {res.text}")
            except Exception as e:
                print(f"  ✗ {job['title']} — Error: {e}")

    if job_ids:
        print("\nWaiting for Celery to generate embeddings...")
        time.sleep(6)

    # 3. Trigger Matching
    if job_ids:
        print("\n--- TRIGGERING MATCHING AND FETCHING RESULTS ---")
        for jd_id in job_ids:
            try:
                trigger_res = requests.post(f"{API_URL}/match/trigger/{jd_id}")
                if trigger_res.status_code not in [200, 201]:
                    print(f"Failed to trigger match for {job_titles[jd_id]}: {trigger_res.text}")
                    continue

                task_id = trigger_res.json()['job_id']
                print(f"Started matching for {job_titles[jd_id]} (Task ID: {task_id})")

                # Poll until done
                for _ in range(40):
                    status_res = requests.get(f"{API_URL}/match/status/{task_id}")
                    if status_res.status_code == 200:
                        status = status_res.json().get('status', '').lower()
                        if status in ['complete', 'success']:
                            print(f"  ↳ Complete!")
                            break
                        elif status in ['failed', 'failure']:
                            print(f"  ↳ Task Failed.")
                            break
                    time.sleep(3)
                else:
                    print(f"  ↳ Timed out waiting for match.")

                # Fetch top 3
                match_res = requests.get(f"{API_URL}/match/{jd_id}?limit=3")
                if match_res.status_code == 200:
                    print(f"{job_titles[jd_id]} top matches:")
                    for i, match in enumerate(match_res.json()):
                        cand_res = requests.get(f"{API_URL}/candidates/{match['candidate_id']}")
                        c_name = cand_res.json().get('name', 'Unknown') if cand_res.status_code == 200 else "Unknown"
                        print(f"  {i+1}. {c_name} — {match['total_score']:.2f}")

            except Exception as e:
                print(f"Error during matching for {job_titles[jd_id]}: {e}")

    print("\n--- SEEDING COMPLETE ---")


if __name__ == "__main__":
    main()
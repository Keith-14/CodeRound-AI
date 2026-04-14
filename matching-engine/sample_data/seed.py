import os
import re
import time
import requests
import pandas as pd
from typing import List, Dict, Any

API_URL = os.environ.get("API_URL", "http://localhost:8000/api/v1")

def clean_text_enums(text: str) -> str:
    if pd.isna(text) or not text:
        return ""
    text = str(text)
    # Remove strings matching pattern \b\w+\.\w+\b (e.g. LookingFor.FULL_TIME)
    return re.sub(r'\b\w+\.\w+\b', '', text)

def clean_json_punctuation(text: str) -> str:
    if pd.isna(text) or not text:
        return ""
    text = str(text)
    text = re.sub(r'[{}\[\]"\'\n]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def parse_candidates(csv_path: str) -> List[Dict[str, Any]]:
    df = pd.read_csv(csv_path)
    candidates = []

    for _, row in df.iterrows():
        name = str(row.get('full_name', row.get('name', 'Unknown')))
        if pd.isna(name) or name == 'nan':
            continue

        # Email mapping
        email = name.lower().replace(" ", ".") + "@candidate.com"

        # Skills mapping
        skills_set = set()
        skill_cols = ['parsed_skills', 'programming_languages', 'backend_frameworks', 'frontend_technologies']
        for col in skill_cols:
            val = row.get(col)
            if pd.notna(val) and str(val).strip():
                for s in str(val).split(','):
                    cleaned = s.strip().lower()
                    if cleaned:
                        skills_set.add(cleaned)
        
        # Resume Text mapping
        summary = clean_text_enums(row.get('parsed_summary', ''))
        work_exp_raw = row.get('parsed_work_experience', '')
        work_exp = clean_text_enums(clean_json_punctuation(work_exp_raw))
        
        resume_text = f"{summary}\n\nWork Experience:\n{work_exp}".strip()

        # Years of Experience
        yoe_raw = row.get('years_of_experience')
        yoe = None
        if pd.notna(yoe_raw):
            try:
                yoe_val = float(yoe_raw)
                if yoe_val > 0:
                    yoe = yoe_val
            except ValueError:
                pass

        # Current Role
        current_role = row.get('current_title')
        if pd.isna(current_role):
            current_role = None
        else:
            current_role = str(current_role)

        candidates.append({
            "name": name,
            "email": email,
            "resume_text": resume_text,
            "skills": list(skills_set),
            "years_of_experience": yoe,
            "current_role": current_role
        })

    return candidates

def parse_jobs(txt_path: str) -> List[Dict[str, Any]]:
    with open(txt_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split into blocks on 3+ consecutive blank lines
    blocks = re.split(r'\n\s*\n\s*\n+', content)
    jobs = []

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        lines = block.split('\n')
        
        title = ""
        for line in lines:
            if line.strip():
                title = line.strip()
                break

        if not title:
            continue

        req_skills = []
        pref_skills = []
        desc_lines = []
        
        current_section = "desc"

        for line in lines:
            stripped = line.strip()
            desc_lines.append(line)
            lower_line = stripped.lower()

            if "core requirements" in lower_line:
                current_section = "req"
                continue
            elif "preferred qualifications" in lower_line:
                current_section = "pref"
                continue
            elif "skills required:" in lower_line:
                skills_str = lower_line.split("skills required:", 1)[-1].strip()
                req_skills.extend([s.strip() for s in skills_str.split(",") if s.strip()])
                current_section = "desc"
                continue

            if current_section == "req" and stripped.startswith(("•", "-", "*")):
                req_skills.append(stripped.lstrip("•-* ").strip())
            elif current_section == "pref" and stripped.startswith(("•", "-", "*")):
                pref_skills.append(stripped.lstrip("•-* ").strip())

        description = "\n".join(desc_lines)

        # Min Years
        exp_match = re.search(r'minimum (\d+) years', description, re.IGNORECASE)
        yoe_min = int(exp_match.group(1)) if exp_match else None

        # Seniority
        seniority = None
        lower_desc = description.lower()
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
            "required_skills": req_skills,
            "preferred_skills": pref_skills,
            "experience_years_min": yoe_min,
            "seniority_level": seniority
        })

    return jobs

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates_path = os.path.join(base_dir, "combined_candidates.csv")
    jobs_path = os.path.join(base_dir, "Job_Descriptions.txt")

    print(f"Connecting to API at {API_URL}")

    # 1. Ingest Candidates
    if not os.path.exists(candidates_path):
        print(f"File not found: {candidates_path}")
    else:
        print("\n--- INGESTING CANDIDATES ---")
        candidates_data = parse_candidates(candidates_path)
        for cand in candidates_data:
            try:
                res = requests.post(f"{API_URL}/candidates", json=cand)
                if res.status_code in [200, 201]:
                    print(f"  ✓ {cand['name']} — {len(cand['skills'])} skills, {len(cand['resume_text'])} chars resume")
                elif res.status_code == 400 and "Email already registered" in res.text:
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
        jobs_data = parse_jobs(jobs_path)
        for job in jobs_data:
            try:
                res = requests.post(f"{API_URL}/jobs", json=job)
                if res.status_code in [200, 201]:
                    jd_id = res.json()['id']
                    job_ids.append(jd_id)
                    job_titles[jd_id] = job['title']
                    print(f"  ✓ {job['title']} — {len(job['required_skills'])} required skills")
                else:
                    print(f"  ✗ {job['title']} — Failed: {res.text}")
            except Exception as e:
                print(f"  ✗ {job['title']} — Error: {e}")

    # Wait for celery embeddings to settle
    if job_ids:
        print("\nGiving Celery tasks a few seconds to finish generating embeddings...")
        time.sleep(5)

    # 3. Trigger Matches
    if job_ids:
        print("\n--- TRIGGERING MATCHING AND FETCHING RESULTS ---")
        for jd_id in job_ids:
            try:
                trigger_res = requests.post(f"{API_URL}/match/trigger/{jd_id}")
                if trigger_res.status_code in [200, 201]:
                    task_id = trigger_res.json()['job_id']
                    print(f"Started matching for {job_titles[jd_id]} (Task ID: {task_id})")
                    
                    # Poll status
                    while True:
                        status_res = requests.get(f"{API_URL}/match/status/{task_id}")
                        if status_res.status_code == 200:
                            data = status_res.json()
                            status = data.get('status', '').lower()
                            if status in ['complete', 'success']:
                                print(f"  ↳ Complete!")
                                break
                            elif status in ['failed', 'failure']:
                                print(f"  ↳ Task Failed.")
                                break
                            else:
                                time.sleep(3)
                        else:
                            print(f"  ↳ Error polling status.")
                            break
                    
                    # Fetch Matches
                    match_res = requests.get(f"{API_URL}/match/{jd_id}?limit=3")
                    if match_res.status_code == 200:
                        matches = match_res.json()
                        print(f"{job_titles[jd_id]} top matches:")
                        
                        # Pre-fetch candidate names for display
                        # Ideally frontend/CLI should look up, but here we query single candidates
                        for i, match in enumerate(matches):
                            cand_res = requests.get(f"{API_URL}/candidates/{match['candidate_id']}")
                            c_name = "Unknown"
                            if cand_res.status_code == 200:
                                c_name = cand_res.json().get('name', 'Unknown')
                                
                            print(f"  {i+1}. {c_name} — {match['total_score']:.2f}")
                            
                else:
                    print(f"Failed to trigger match for {job_titles[jd_id]}: {trigger_res.text}")
            except Exception as e:
                print(f"Error during matching for {job_titles[jd_id]}: {e}")

    print("\n--- SEEDING COMPLETE ---")

if __name__ == "__main__":
    main()

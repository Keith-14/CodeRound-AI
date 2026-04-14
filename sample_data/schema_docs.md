# Sample Data Schema & Ingestion

This document details the structure of the data expected by the ingestion script (`seed.py`) as well as the transformations applied during the loading process into the matching engine.

## 1. Candidate Data (`combined_candidates.csv`)

The candidate seeder accepts a CSV with flat columns containing partially parsed data (often extracted from an ATS or resume parser).

### Expected Columns
- **`full_name`** or **`name`** *(Required)*: The candidate's full name.
- **`parsed_skills`** *(Optional)*: Comma-separated list of general skills.
- **`programming_languages`** *(Optional)*: Comma-separated list of languages.
- **`backend_frameworks`** *(Optional)*: Comma-separated list of backend stacks.
- **`frontend_technologies`** *(Optional)*: Comma-separated list of frontend stacks.
- **`parsed_summary`** *(Optional)*: Textual bio or summary.
- **`parsed_work_experience`** *(Optional)*: Stringified JSON or text of work history.
- **`years_of_experience`** *(Optional)*: Numeric representation of experience.
- **`current_title`** *(Optional)*: The candidate's current or last held role.

### Applied Transformations
During ingestion via `seed.py`, the following transformations take place:
1. **Email Autogeneration**: An email is generated since ATS outputs often obfuscate them (e.g. `john.doe@candidate.com`).
2. **Skill Unification**: All four skill columns (`parsed_skills`, `programming_languages`, `backend_frameworks`, `frontend_technologies`) are split, deduplicated, stripped of extra whitespaces, and cast to lowercase to create a unified `skills` array.
3. **Structured Resume Construction**: The `parsed_summary` and `parsed_work_experience` are cleanly concatenated into a single readable `resume_text` block.
4. **JSON Decoupling**: Stray JSON syntax (e.g., curly braces `{}`, unescaped quotes `'`) is stripped from the work experience.
5. **Enum Cleaning**: Stray system Enums matching `Word.WORD` (e.g., `LookingFor.FULL_TIME`) are stripped from all text bodies using RegEx (`\b\w+\.\w+\b`) to preserve semantic embedding purity.

### Example Formatting

**CSV Input Example:**
```csv
full_name,current_title,years_of_experience,parsed_skills,programming_languages,backend_frameworks,frontend_technologies,parsed_summary,parsed_work_experience
Isha Thakur,Backend Engineer,5,"Docker,AWS",Python,FastAPI,,Passionate backend dev,"{'company': 'Tech', 'role': 'Backend'}"
```

**Resulting JSON Payload to API:**
```json
{
  "name": "Isha Thakur",
  "email": "isha.thakur@candidate.com",
  "resume_text": "Passionate backend dev\n\nWork Experience:\n company : Tech , role : Backend",
  "skills": ["docker", "aws", "python", "fastapi"],
  "years_of_experience": 5.0,
  "current_role": "Backend Engineer"
}
```

---

## 2. Job Description Data (`Job_Descriptions.txt`)

The Job Description seeder parses a plain text file containing multiple unformatted Job Descriptions stacked sequentially.

### Expected Structure & Sections
- **Block Separation**: Individual JDs must be separated by **3 or more consecutive blank lines**.
- **Job Title**: The very first non-empty line of a block is assumed to be the *Job Title*.
- **Skill Extraction Blocks**:
  - The script scans for the exact phrase `Core Requirements` (case-insensitive). Any bullet points (`-`, `*`, `•`) following it are mapped strictly into `required_skills`.
  - The script scans for the exact phrase `Preferred Qualifications`. Bullet points following it map to `preferred_skills`.
  - The script looks for inline comma definitions via `Skills Required: Python, AWS, Docker` and appends them to `required_skills`.
- **Global Description**: All lines (including the skill sections) are concatenated natively as the bulk text description used for vector embedding.

### Applied Transformations
1. **Min Experience Heuristics**: The script searches the entire text block for the specific regex footprint `Minimum X years` and extracts the integer `X` to map to `experience_years_min`.
2. **Seniority Inference**: The entire unformatted text is scanned for definitive seniority keywords (`lead`, `principal`, `senior`, `mid`, `junior`) which applies a fixed `seniority_level` enumeration mapped independently of the title.

### Example Formatting

**TXT Input Example:**
```text
Senior Python Engineer

We are looking for an expert scaling APIs.
Minimum 5 years of production experience required.

Core Requirements
- Python
- FastAPI
- PostgreSQL

Preferred Qualifications
- Redis
- AWS

Skills Required: Docker, Kubernetes



Data Scientist

We are looking for ML experts...
...
```

**Resulting JSON Payload to API:**
```json
{
  "title": "Senior Python Engineer",
  "description": "We are looking for an expert scaling APIs.\nMinimum 5 years of production experience required.\n\nCore Requirements\n- Python\n- FastAPI\n- PostgreSQL\n\nPreferred Qualifications\n- Redis\n- AWS\n\nSkills Required: Docker, Kubernetes",
  "required_skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "Kubernetes"],
  "preferred_skills": ["Redis", "AWS"],
  "experience_years_min": 5,
  "seniority_level": "senior"
}
```

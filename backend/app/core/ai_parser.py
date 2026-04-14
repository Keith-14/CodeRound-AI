import os
import time
import json
import logging
import concurrent.futures
from typing import Dict, Any, Optional

try:
    from google import genai as _genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

logger = logging.getLogger(__name__)

# Priority order: 3.1 lite preview → 2.5 lite → 2.5 flash (last resort)
CANDIDATE_MODELS = [
    "gemini-3.1-flash-lite-preview",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
]


def extract_skills_and_summary(jd_text: str) -> Optional[Dict[str, Any]]:
    """
    Use Gemini Flash Lite to extract structured skills and a short summary with retries.
    Tries models in priority order. Returns dict with 'extracted_skills' and 'summary',
    or None if all attempts fail (fallback to heuristic values in tasks.py).
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or not GENAI_AVAILABLE:
        logger.warning("Gemini extraction skipped: No API key or google-genai not installed.")
        return None

    max_retries = 3
    base_delay = 1  # seconds

    prompt = f"""You are a technical recruiter. Parse this Job Description.
Return a valid JSON object ONLY, with exactly two keys: "extracted_skills" and "summary".

Rules for "extracted_skills":
- Return a flat JSON array of short strings (1-4 words max per item).
- Each item must be a specific technology or skill name, NOT a job duty.
- Do NOT include soft skills, years of experience, or vague phrases.

Rules for "summary":
- A concise 1-2 sentence overview of the role and its primary objective.

Job Description:
{jd_text}
"""

    client = _genai.Client(api_key=api_key)

    def call_gemini():
        """Try each model in priority order, skipping NOT_FOUND and UNAVAILABLE errors."""
        last_err = None
        for model_id in CANDIDATE_MODELS:
            try:
                logger.info(f"Trying Gemini model: {model_id}")
                return client.models.generate_content(
                    model=model_id,
                    contents=prompt,
                    config={'response_mime_type': 'application/json'}
                )
            except Exception as e:
                err_str = str(e)
                if "NOT_FOUND" in err_str or "404" in err_str or "UNAVAILABLE" in err_str or "503" in err_str:
                    logger.warning(f"Model {model_id} unavailable/not found, trying next...")
                    last_err = e
                    continue
                # Only propagate unknown errors (auth failures, bad requests, etc.)
                raise
        raise Exception(f"All Gemini models failed. Last error: {last_err}")

    for attempt in range(max_retries):
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(call_gemini)
                try:
                    response = future.result(timeout=10)
                except concurrent.futures.TimeoutError as exc:
                    raise Exception("Gemini API call timed out after 10 seconds") from exc

            raw = response.text.strip()
            data = json.loads(raw)
            skills = data.get("extracted_skills", [])
            summary = data.get("summary", "")

            if isinstance(skills, list):
                extracted = [str(s).strip() for s in skills if str(s).strip()]
                logger.info(f"Gemini AI parsing successful: {len(extracted)} skills extracted.")
                return {
                    "extracted_skills": extracted,
                    "summary": summary
                }

            return None

        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Gemini AI parsing failed after {max_retries} attempts. Falling back. Error: {e}")
                return None

            delay = base_delay * (2 ** attempt)
            logger.warning(f"Gemini AI parsing failed (attempt {attempt + 1}/{max_retries}), retrying in {delay}s: {e}")
            time.sleep(delay)

    return None

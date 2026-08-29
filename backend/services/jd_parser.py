"""
RecruitIQ - Week 2
JD text extraction + LLM-based structured parsing (Groq).
"""

import os
import io
import re
import json
from typing import Optional

import fitz  # PyMuPDF
import docx  # python-docx
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

_groq_client: Optional[Groq] = None


def get_groq_client() -> Groq:
    global _groq_client
    if _groq_client is None:
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is not set. Add it to your .env file.")
        _groq_client = Groq(api_key=GROQ_API_KEY)
    return _groq_client


# ------------------------------------------------------------
# Text extraction
# ------------------------------------------------------------

def extract_text_from_pdf(file_bytes: bytes) -> str:
    text_parts = []
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        for page in doc:
            text_parts.append(page.get_text())
    return "\n".join(text_parts).strip()


def extract_text_from_docx(file_bytes: bytes) -> str:
    buf = io.BytesIO(file_bytes)
    d = docx.Document(buf)
    return "\n".join(p.text for p in d.paragraphs).strip()


def extract_text(file_bytes: bytes, filename: str) -> str:
    """Dispatch on file extension. Raises ValueError on unsupported types."""
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext == "pdf":
        return extract_text_from_pdf(file_bytes)
    elif ext == "docx":
        return extract_text_from_docx(file_bytes)
    elif ext in ("txt", "md"):
        return file_bytes.decode("utf-8", errors="ignore").strip()
    else:
        raise ValueError(f"Unsupported file type: .{ext}. Use PDF, DOCX, or TXT.")


# ------------------------------------------------------------
# LLM structured parsing
# ------------------------------------------------------------

JD_EXTRACTION_PROMPT = """You are extracting structured fields from a job description for a recruitment database.

Return ONLY a single JSON object, no markdown fences, no commentary, with exactly these keys:

{{
  "role_title": string,
  "required_skills": [string, ...],
  "nice_to_have_skills": [string, ...],
  "experience_min": number or null,
  "experience_max": number or null,
  "notice_period_days": integer or null,
  "location": string or null
}}

Rules:
- required_skills / nice_to_have_skills: lowercase, short tokens (e.g. "python", "react", "aws"), no duplicates.
- experience_min/max are in years. If JD says "3+ years", set experience_min=3, experience_max=null.
- notice_period_days: convert "immediate" to 0, "1 month" to 30, "30 days" to 30, etc. null if not mentioned.
- location: city name(s) as written, or "Remote" if remote. null if not mentioned.
- If a field genuinely isn't present in the text, use null (or empty list for skills) — never invent values.

Job description text:
---
{jd_text}
---
"""


def _strip_code_fences(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


def parse_jd_with_llm(jd_text: str) -> dict:
    """Calls Groq to extract structured JD fields.

    Raises ValueError if the model doesn't return parseable JSON — the
    caller should surface this (e.g. via /jds/parse preview) rather than
    silently saving a broken record.
    """
    client = get_groq_client()
    prompt = JD_EXTRACTION_PROMPT.format(jd_text=jd_text[:12000])  # guard against huge JDs

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": "You return only valid JSON. No explanations."},
            {"role": "user", "content": prompt},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    cleaned = _strip_code_fences(raw)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM did not return valid JSON: {e}\nRaw response:\n{raw}")

    # defensive defaults / normalization
    parsed["required_skills"] = sorted(set(
        s.lower().strip() for s in (parsed.get("required_skills") or []) if s
    ))
    parsed["nice_to_have_skills"] = sorted(set(
        s.lower().strip() for s in (parsed.get("nice_to_have_skills") or []) if s
    ))
    parsed.setdefault("role_title", "Untitled Role")

    return parsed


if __name__ == "__main__":
    # quick manual test: python jd_parser.py path/to/sample_jd.pdf
    import sys
    if len(sys.argv) != 2:
        print("Usage: python jd_parser.py <path-to-jd-file>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, "rb") as f:
        raw_bytes = f.read()

    text = extract_text(raw_bytes, path)
    print(f"Extracted {len(text)} characters of text.\n")

    result = parse_jd_with_llm(text)
    print(json.dumps(result, indent=2))

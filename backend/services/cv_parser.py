"""
RecruitIQ - Week 3
CV text extraction + spaCy NLP parsing + Groq LLM fallback.

Strategy (mirrors the proposal exactly):
  1. PyMuPDF / python-docx  → raw text
  2. spaCy                  → rule-based extraction of skills, experience, location,
                              notice period (fast, free, no API call)
  3. Groq LLM               → fills in anything spaCy missed or got wrong,
                              and returns the final clean JSON

This hybrid is cheaper than a pure-LLM approach for CV volume while still
handling messy / unstructured resume formats correctly.

Install:
    pip install pymupdf python-docx spacy groq python-dotenv
    python -m spacy download en_core_web_sm
"""

import os
import io
import re
import json
from typing import Optional

import fitz          # PyMuPDF
import docx          # python-docx
import spacy
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

GROQ_API_KEY  = os.getenv("GROQ_API_KEY")
GROQ_MODEL    = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

_groq_client: Optional[Groq]   = None
_nlp:         Optional[object]  = None   # spacy.Language


# ------------------------------------------------------------------ #
#  Lazy singletons                                                     #
# ------------------------------------------------------------------ #

def get_groq_client() -> Groq:
    global _groq_client
    if _groq_client is None:
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is not set in .env")
        _groq_client = Groq(api_key=GROQ_API_KEY)
    return _groq_client


def get_nlp():
    global _nlp
    if _nlp is None:
        try:
            _nlp = spacy.load("en_core_web_sm")
        except OSError:
            raise RuntimeError(
                "spaCy model not found. Run: python -m spacy download en_core_web_sm"
            )
    return _nlp


# ------------------------------------------------------------------ #
#  Text extraction (same pattern as jd_parser.py)                    #
# ------------------------------------------------------------------ #

def extract_text_from_pdf(file_bytes: bytes) -> str:
    parts = []
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        for page in doc:
            parts.append(page.get_text())
    return "\n".join(parts).strip()


def extract_text_from_docx(file_bytes: bytes) -> str:
    buf = io.BytesIO(file_bytes)
    d = docx.Document(buf)
    return "\n".join(p.text for p in d.paragraphs).strip()


def extract_text(file_bytes: bytes, filename: str) -> str:
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext == "pdf":
        return extract_text_from_pdf(file_bytes)
    elif ext == "docx":
        return extract_text_from_docx(file_bytes)
    elif ext in ("txt", "md"):
        return file_bytes.decode("utf-8", errors="ignore").strip()
    else:
        raise ValueError(f"Unsupported file type: .{ext}. Use PDF, DOCX, or TXT.")


# ------------------------------------------------------------------ #
#  spaCy layer — fast rule-based pre-extraction                      #
# ------------------------------------------------------------------ #

# Canonical skill list — extend as needed for your client's domains
SKILL_KEYWORDS = {
    # languages
    "python", "java", "javascript", "typescript", "go", "golang", "rust", "c++",
    "c#", "ruby", "php", "swift", "kotlin", "scala", "r",
    # web / backend
    "django", "flask", "fastapi", "spring", "springboot", "spring boot",
    "nodejs", "node.js", "express", "react", "angular", "vue", "nextjs",
    "graphql", "rest", "grpc",
    # data / ml
    "pandas", "numpy", "scikit-learn", "tensorflow", "pytorch", "keras",
    "spark", "hadoop", "airflow", "dbt", "sql", "nosql",
    # cloud / devops
    "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ansible",
    "jenkins", "github actions", "cicd", "ci/cd", "linux", "bash",
    # databases
    "postgresql", "mysql", "mongodb", "redis", "elasticsearch", "cassandra",
    "sqlite", "oracle", "dynamodb",
    # messaging
    "kafka", "rabbitmq", "sqs",
    # misc
    "microservices", "git", "jira", "agile", "scrum",
}

# Patterns for notice period
_NOTICE_PATTERNS = [
    (r"\bimmediate(ly)?\b",                     0),
    (r"\b(\d+)\s*day[s]?\s*notice\b",           None),   # group 1 = days
    (r"\bnotice\s*period[:\s]+(\d+)\s*day[s]?", None),
    (r"\b(\d+)\s*month[s]?\s*notice\b",         None),   # group 1 = months → *30
    (r"\bnotice[:\s]+(\d+)\s*month[s]?",        None),
]

# Patterns for total experience
_EXP_PATTERNS = [
    r"(\d+(?:\.\d+)?)\s*\+?\s*year[s]?\s+(?:of\s+)?(?:total\s+)?experience",
    r"experience\s+of\s+(\d+(?:\.\d+)?)\s*\+?\s*year[s]?",
    r"(\d+(?:\.\d+)?)\s*yr[s]?\s+(?:of\s+)?experience",
    r"total\s+experience[:\s]+(\d+(?:\.\d+)?)",
    r"(\d+(?:\.\d+)?)\s*years?\s+in\s+(?:the\s+)?(?:industry|field|software|it)",
]


def _extract_skills_spacy(text: str) -> list[str]:
    """Lowercased token / bigram matching against SKILL_KEYWORDS."""
    text_lower = text.lower()
    found = set()
    for skill in SKILL_KEYWORDS:
        # word-boundary match so "go" doesn't hit "going"
        pattern = r"\b" + re.escape(skill) + r"\b"
        if re.search(pattern, text_lower):
            found.add(skill)
    return sorted(found)


def _extract_experience_spacy(text: str) -> Optional[float]:
    text_lower = text.lower()
    for pattern in _EXP_PATTERNS:
        m = re.search(pattern, text_lower)
        if m:
            try:
                return float(m.group(1))
            except (IndexError, ValueError):
                continue
    return None


def _extract_notice_period_spacy(text: str) -> Optional[int]:
    text_lower = text.lower()
    for pattern, fixed_value in _NOTICE_PATTERNS:
        m = re.search(pattern, text_lower)
        if m:
            if fixed_value is not None:          # "immediate"
                return fixed_value
            val_str = m.group(1)
            try:
                val = int(val_str)
            except ValueError:
                continue
            # heuristic: if the matched group came from a "months" pattern, multiply
            if "month" in pattern:
                return val * 30
            return val
    return None


def _extract_location_spacy(text: str) -> Optional[str]:
    """Use spaCy GPE entities — returns the most frequent one (usually city/country)."""
    nlp = get_nlp()
    doc = nlp(text[:5000])   # only first 5k chars, enough for a header section
    gpe_counts: dict[str, int] = {}
    for ent in doc.ents:
        if ent.label_ == "GPE":
            label = ent.text.strip()
            gpe_counts[label] = gpe_counts.get(label, 0) + 1
    if not gpe_counts:
        return None
    return max(gpe_counts, key=gpe_counts.get)


def _extract_name_spacy(text: str) -> Optional[str]:
    """Heuristic: first PERSON entity in the CV, or first non-empty line."""
    nlp = get_nlp()
    doc = nlp(text[:2000])
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            return ent.text.strip()
    # fallback: first non-empty line is usually the candidate's name
    for line in text.splitlines():
        line = line.strip()
        if line and len(line.split()) <= 5:
            return line
    return None


def _extract_email(text: str) -> Optional[str]:
    m = re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text)
    return m.group(0).lower() if m else None


def _extract_phone(text: str) -> Optional[str]:
    m = re.search(r"(\+?\d[\d\s\-]{8,14}\d)", text)
    return m.group(0).strip() if m else None


def spacy_pre_extract(text: str) -> dict:
    """Returns a partial dict — whatever spaCy could find. Gaps will be filled by LLM."""
    return {
        "full_name":         _extract_name_spacy(text),
        "email":             _extract_email(text),
        "phone":             _extract_phone(text),
        "skills":            _extract_skills_spacy(text),
        "total_experience":  _extract_experience_spacy(text),
        "current_location":  _extract_location_spacy(text),
        "notice_period_days": _extract_notice_period_spacy(text),
    }


# ------------------------------------------------------------------ #
#  Groq LLM layer — fills gaps + validates spaCy output              #
# ------------------------------------------------------------------ #

CV_EXTRACTION_PROMPT = """You are extracting structured fields from a candidate's resume/CV for a recruitment database.

You are given:
1. The raw resume text
2. A partial extraction already done by a rules-based system (spaCy) — some fields may already be correct

Your job:
- Fill in any null/missing fields
- Correct any obvious spaCy errors (e.g. wrong name, missed email, wrong experience years)
- Do NOT invent data that isn't in the resume

Return ONLY a single JSON object, no markdown, no commentary, with exactly these keys:

{{
  "full_name": string,
  "email": string or null,
  "phone": string or null,
  "total_experience": number or null,
  "current_location": string or null,
  "notice_period_days": integer or null,
  "skills": [string, ...],
  "parsed_summary": string
}}

Rules:
- total_experience: years as a decimal (e.g. 3.5). If stated as "3+ years", use 3.0. null if unclear.
- notice_period_days: 0 for immediate, 30 for 1 month, etc. null if not mentioned.
- skills: lowercase short tokens — "python", "aws", "docker", "react". No duplicates. Include ALL skills found.
- current_location: city or city+country as written. null if not mentioned.
- parsed_summary: one sentence summarising the candidate's profile for a recruiter (role + years + key skills).

Partial spaCy extraction (use as a starting point, correct if wrong):
{spacy_result}

Resume text:
---
{cv_text}
---
"""


def parse_cv_with_llm(cv_text: str, spacy_result: dict) -> dict:
    client = get_groq_client()

    prompt = CV_EXTRACTION_PROMPT.format(
        spacy_result=json.dumps(spacy_result, indent=2),
        cv_text=cv_text[:12000],
    )

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": "You return only valid JSON. No explanations."},
            {"role": "user", "content": prompt},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content.strip()
    # strip any accidental code fences
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}\nRaw:\n{raw}")

    # normalise skills
    parsed["skills"] = sorted(set(
        s.lower().strip() for s in (parsed.get("skills") or []) if s
    ))
    parsed.setdefault("full_name", "Unknown Candidate")
    parsed.setdefault("parsed_summary", "")

    return parsed


# ------------------------------------------------------------------ #
#  Public entry point                                                  #
# ------------------------------------------------------------------ #

def parse_cv(file_bytes: bytes, filename: str) -> dict:
    """
    Full pipeline: extract text → spaCy pre-extract → Groq LLM fill-in.

    Returns:
        {
            "raw_text": str,
            "spacy_extract": dict,    # intermediate (useful for debugging)
            "parsed": dict            # final structured output
        }
    """
    raw_text     = extract_text(file_bytes, filename)
    spacy_result = spacy_pre_extract(raw_text)
    parsed       = parse_cv_with_llm(raw_text, spacy_result)

    return {
        "raw_text":      raw_text,
        "spacy_extract": spacy_result,
        "parsed":        parsed,
    }


# ------------------------------------------------------------------ #
#  CLI test: python cv_parser.py path/to/resume.pdf                  #
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python cv_parser.py <path-to-resume>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, "rb") as f:
        data = f.read()

    result = parse_cv(data, path)

    print(f"\n--- spaCy pre-extract ---")
    print(json.dumps(result["spacy_extract"], indent=2))

    print(f"\n--- Final LLM parse ---")
    print(json.dumps(result["parsed"], indent=2))

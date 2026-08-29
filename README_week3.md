# RecruitIQ — Week 3 Deliverable
## CV Parser + Candidate Repository

Builds on Week 1 schema and Week 2 JD pipeline. After this week, the system
can ingest resumes from any source channel, parse them into structured records,
upload to Drive, and store in PostgreSQL — ready for the Week 4 matching engine.

---

## 1. Files in this package

| File | Purpose |
|---|---|
| `cv_parser.py` | spaCy NLP pre-extract → Groq LLM fill-in for structured CV parsing |
| `drive_utils_resume.py` | Uploads resumes to Drive `/TalentPool/<year>/<month>/` |
| `routes_candidate.py` | FastAPI router — parse preview + full save + list + fetch |

---

## 2. Install

```bash
pip install spacy
python -m spacy download en_core_web_sm
```

(`pymupdf`, `python-docx`, `groq`, `google-api-python-client` already installed from Week 2.)

---

## 3. New .env variable

```
GOOGLE_DRIVE_TALENT_POOL_FOLDER_ID=<id-of-your-TalentPool-folder>
```

In your RecruitIQ Google Drive root, create a folder called `TalentPool`.
Share it with the same service account email (Editor). Copy its folder ID from the URL.

---

## 4. Wire into main.py

```python
from routes_candidate import router as candidate_router
app.include_router(candidate_router)
```

---

## 5. How the parsing works

```
Resume PDF/DOCX
      │
      ▼
PyMuPDF / python-docx  ──► raw text
      │
      ▼
spaCy en_core_web_sm
  • Skill token matching (80+ keywords)
  • Regex: experience years, notice period
  • GPE entity: current location
  • PERSON entity + first-line heuristic: name
  • Regex: email, phone
      │
      ▼
spaCy result (partial — may have nulls)
      │
      ▼
Groq LLM (llama-3.3-70b)
  • Fills in whatever spaCy missed
  • Corrects obvious errors
  • Adds parsed_summary (one-line recruiter blurb)
      │
      ▼
Final structured JSON → saved to candidates table
```

This is the approach from the proposal: spaCy handles the common structured
parts for free and fast, LLM only runs once per CV to handle ambiguous/unstructured
sections — keeps Groq token spend low.

---

## 6. API Endpoints

### `POST /candidates/parse`
Preview parse — nothing saved, nothing uploaded. Use to sanity-check before committing.

```bash
curl -X POST http://localhost:8000/candidates/parse \
  -F "file=@resume.pdf"
```

Returns:
```json
{
  "raw_text_preview": "...",
  "spacy_extract": { ... },   ← what rules found
  "parsed": { ... }           ← LLM corrected final output
}
```

### `POST /candidates`
Full pipeline. Creates candidate + optional JD mapping.

```bash
curl -X POST http://localhost:8000/candidates \
  -F "file=@resume.pdf" \
  -F "source=linkedin_apply" \
  -F "jd_id=1" \
  -F "source_detail=LinkedIn - JD-2026-0001"
```

`source` values: `linkedin_apply`, `linkedin_dm`, `email`, `naukri`, `manual_upload`, `referral`

`jd_id` is optional — omit if uploading to the talent pool without a specific JD in mind.

Response includes `"duplicate": true` if the email matched an existing candidate
(new mapping is still created for the jd_id if provided).

### `GET /candidates?skill=python&limit=50`
List candidates. Optional `skill` filter uses Postgres array contains.

### `GET /candidates/CAND-00001`
Fetch one candidate with their JD mappings.

---

## 7. Duplicate detection flow

```
Incoming resume
      │
  parse email
      │
  email found? ──No──► create new Candidate row
      │
     Yes
      │
  existing candidate found (email_normalized match)
      │
  skip new Candidate row
      │
  jd_id provided? ──Yes──► create new CandidateJDMapping (if doesn't exist)
      │
  return existing candidate + duplicate: true
```

DB-level unique index on `email_normalized` is the safety net —
even if the app layer check races, Postgres will reject the duplicate insert.

---

## 8. CLI test (no server needed)

```bash
# sanity check parser directly
python cv_parser.py path/to/resume.pdf
```

Prints spaCy intermediate + final LLM parse — good for checking extraction
quality against real CVs before wiring up the routes.

---

## 9. Before calling Week 3 "done"

- [ ] `python -m spacy download en_core_web_sm` runs clean
- [ ] `python cv_parser.py <sample_resume.pdf>` returns sensible JSON
- [ ] `POST /candidates/parse` works via Swagger UI at `/docs`
- [ ] `POST /candidates` saves a row — verify with `SELECT * FROM candidates;`
- [ ] `GOOGLE_DRIVE_TALENT_POOL_FOLDER_ID` set and resume appears in Drive
- [ ] Upload same candidate twice — confirm `duplicate: true` on second attempt
- [ ] `GET /candidates?skill=python` returns only candidates with python in skills array

---

## 10. What Week 4 needs from this

Week 4 (matching engine) reads:
- `candidates.skills` — for keyword pre-filter in Postgres
- `candidates.total_experience`, `notice_period_days`, `current_location` — for scoring
- `candidates.resume_text` — raw text that gets embedded into ChromaDB
- `candidate_jd_mapping` rows with `status='new'` — these are what the matcher picks up

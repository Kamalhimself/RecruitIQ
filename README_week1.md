# RecruitIQ — Week 1 Deliverable
## JD & Candidate Repository Setup

This covers everything in Week 1 of the delivery plan:
- PostgreSQL schema design
- Candidate repository + JD repository tables
- Drive folder structure
- Candidate ID system + duplicate detection

---

## 1. Files in this package

| File | Purpose |
|---|---|
| `schema.sql` | Full PostgreSQL DDL — run this once to create all tables, enums, indexes, triggers |
| `models.py` | SQLAlchemy ORM models matching the schema (drop into your FastAPI app) |
| `setup_db.py` | Connects to Postgres and applies `schema.sql` |
| `seed_data.py` | Inserts sample client/JD/candidates so you can test relationships |

---

## 2. Quick Start

```bash
pip install sqlalchemy psycopg2-binary python-dotenv

# create a .env file with:
# DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/recruitiq

# 1. create the database first (one-time, via psql or pgAdmin)
createdb recruitiq

# 2. apply schema
python setup_db.py

# 3. (optional) load sample data
python seed_data.py
```

---

## 3. Schema Overview

```
clients ──┬──> job_descriptions ──┐
          │                       │
recruiters┘                       ├──> candidate_jd_mapping <──── candidates
                                   │           │
                                   │           └──> email_history
                                   │
                          (JD repo, embeddings, status)
```

**Core tables:**

- **`clients`** — companies that send you JDs
- **`recruiters`** — internal users (for activity tracking, "created_by", "reviewed_by")
- **`job_descriptions`** — the JD repository. Each row = one role. `required_skills` and
  `nice_to_have_skills` are Postgres arrays (GIN-indexed for fast filtering).
- **`candidates`** — the master talent pool. One row per person, regardless of how many JDs
  they're matched against.
- **`candidate_jd_mapping`** — this is the table everything else hangs off. One row per
  (candidate, JD) pair, holding the AI match score breakdown + pipeline status
  (new → shortlisted → screening_sent → ... → client_submitted).
- **`email_history`** — scaffolded now for Module 3, links to `candidate_jd_mapping`.

---

## 4. Candidate ID System

Two ID types per candidate, by design:

1. **`candidate_id`** (UUID) — internal primary key, used for all foreign keys/joins.
   Never shown to recruiters.
2. **`candidate_code`** (e.g. `CAND-00001`) — human-readable, sequential, shown in the
   Streamlit dashboard and Google Sheets tracker. Generated via `generate_candidate_code()`
   (a Postgres function) or in the app layer using the `candidate_code_seq` sequence.

Same pattern for JDs: `jd_id` (internal int) vs `jd_code` (`JD-2026-0001` — year + sequence,
generated via `generate_jd_code()`).

**Why both?** Recruiters and clients need stable, readable references in spreadsheets/emails
(`CAND-00001`), but your app/DB joins should always use the internal IDs — readable codes
should never be reused or renumbered even if a record is deleted.

---

## 5. Duplicate Candidate Detection

Handled at the DB layer with **generated columns**:

- `email_normalized` = `LOWER(TRIM(email))` — auto-computed by Postgres
- `phone_normalized` = digits-only version of phone

A **unique index** on `email_normalized` means inserting a candidate with an email that
already exists will throw a constraint error — catch this in your ingestion pipeline and
treat it as "existing candidate, create new `candidate_jd_mapping` row instead of a new
candidate row."

Recommended flow in your CV parsing pipeline:
```python
existing = session.query(Candidate).filter_by(email_normalized=email.lower().strip()).first()
if existing:
    candidate = existing  # reuse, just create new mapping to this JD
else:
    candidate = Candidate(...)  # new candidate
```

---

## 6. Google Drive Folder Structure

Recommended hierarchy (matches `resume_file_path` / `jd_file_path` columns):

```
/RecruitIQ
  /JobDescriptions
    /2026
      /JD-2026-0001_BackendEngineer_AcmeTech.pdf
      /JD-2026-0002_...
  /TalentPool
    /2026
      /06               <- month received
        /CAND-00001_ArunKumar.pdf
        /CAND-00002_DivyaRaj.pdf
  /Screening
    /JD-2026-0001
      /sent              <- copies of screening emails sent (optional, for audit)
      /replies
```

- `jd_file_path` and `resume_file_path` in the DB store this path so the Streamlit dashboard
  can construct a Drive link without another API call (`https://drive.google.com/file/d/<drive_id>/view`).
- Store the **file ID** separately (`jd_file_drive_id`, `resume_drive_id`) — paths can change
  if folders get reorganized, but the file ID is permanent.
- One candidate can apply to multiple JDs — their resume lives in `/TalentPool` once;
  `candidate_jd_mapping` handles the JD associations, so no duplicate file copies needed.

---

## 7. What's next (Week 2 preview)

Week 2 builds on this directly:
- Google Sheets tracker — read-only view synced from `candidate_jd_mapping` + `candidates` +
  `job_descriptions` (a scheduled script using `gspread` reading from Postgres)
- JD upload & parsing — populate `job_descriptions.raw_text`, then chunk/embed for ChromaDB
- `generate_jd_code()` / `generate_candidate_code()` get wired into your FastAPI upload
  endpoints

---

## 8. Things to double check before you call this "done" for Week 1

- [ ] Postgres instance is reachable (local or cloud — Supabase free tier works great if you
      don't want to manage your own Postgres)
- [ ] `schema.sql` runs clean with no errors
- [ ] `seed_data.py` inserts and you can query `candidate_jd_mapping` joined with both
      `candidates` and `job_descriptions`
- [ ] Decide now: local Postgres vs Supabase/Neon (free managed Postgres) — saves you
      headache later when deploying the FastAPI backend + Streamlit dashboard

# RecruitIQ

End-to-end recruitment automation: JD and CV ingestion, PostgreSQL talent pool, semantic matching, recruiter review, and Gmail screening workflows.

## Setup

1. Create and activate a Python 3.11+ virtual environment.
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and configure PostgreSQL plus the credentials you want to use.
4. Create an empty `recruitiq` PostgreSQL database, then run `python setup_db.py` and (optionally) `python seed_data.py`.
5. Start the API: `uvicorn backend.main:app --reload` and open `http://127.0.0.1:8000/docs`.
6. Start the recruiter UI in another terminal: `cd frontend && npm run dev` and open `http://localhost:5173`.

## Week 4: matching workflow

After candidates and a JD exist, run `POST /matching/jds/{jd_id}/run`. The endpoint indexes candidate profiles in local ChromaDB, retrieves semantically relevant profiles, and writes a transparent 0-100 score to `candidate_jd_mapping`:

| Component | Weight |
| --- | ---: |
| Required skills (keyword + semantic relevance) | 40 |
| Experience | 25 |
| Notice period | 20 |
| Location | 15 |

Retrieve the ranked candidates with `GET /matching/jds/{jd_id}`. A score at or above the `shortlist_threshold` (70 by default) moves a new mapping to `shortlisted`; recruiters still control every email.

## Week 5: communication workflow

Set up Gmail OAuth using `GMAIL_CREDENTIALS_FILE`, complete the browser consent once, and use `POST /workflow/mappings/{mapping_id}/screening-email` to send a recruiter-approved screening email. Every sent message is written to `email_history`. `GET /workflow/follow-ups-due` provides the candidates awaiting a response after 48 hours for a scheduled follow-up job.

Never commit `.env`, `service_account.json`, Gmail OAuth credentials, or `token.json`.

### Google Drive setup (personal account OAuth)

1. In Google Cloud Console, enable the Google Drive API and create an **OAuth client ID** of type **Desktop app**. Download its JSON file as `drive_credentials.json` in the project root.
2. In your personal Google Drive, create a `RecruitIQ` folder and a `TalentPool` folder inside it. Copy each folder ID from its URL into `GOOGLE_DRIVE_JD_ROOT_FOLDER_ID` and `GOOGLE_DRIVE_TALENT_POOL_FOLDER_ID`.
3. Keep `GOOGLE_DRIVE_AUTH_MODE=oauth`, then run `python drive_utils.py` once. A browser opens for consent; the resulting `drive_token.json` is stored locally and ignored by Git.

This uses your personal Drive quota. If your organisation uses Google Workspace Shared Drives instead, set `GOOGLE_DRIVE_AUTH_MODE=service_account`, add the service account as a Content manager, and set `GOOGLE_DRIVE_SHARED_DRIVE_ID`.

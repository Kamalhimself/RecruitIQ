# RecruitIQ — Week 2 Deliverable
## JD Upload & Parsing + Google Sheets Tracker

Builds directly on Week 1's schema. Candidate ID system and duplicate
detection were already shipped in Week 1, so this covers what's actually
left: turning a raw JD file into a structured `job_descriptions` row, and
giving recruiters a live Sheet view of the pipeline.

---

## 1. Files in this package

| File | Purpose |
|---|---|
| `jd_parser.py` | Extracts text from PDF/DOCX, parses structured fields via Groq |
| `drive_utils.py` | Uploads JD files to Google Drive, builds `/JobDescriptions/<year>/` structure |
| `routes_jd.py` | FastAPI router — `POST /jds/parse` (preview) and `POST /jds` (parse + save) |
| `sheets_sync.py` | Syncs the candidate/JD/mapping join into a Google Sheet |
| `.env.example` | New environment variables this package needs |

---

## 2. Install

```bash
pip install pymupdf python-docx groq google-api-python-client google-auth gspread
```

(`fastapi`, `sqlalchemy`, `psycopg2-binary`, `python-dotenv` you already have from Week 1.)

---

## 3. Google Cloud Setup (one-time)

You'll create **one service account** that both Drive and Sheets scripts share.

1. Go to [console.cloud.google.com](https://console.cloud.google.com), create a project
   (e.g. "RecruitIQ") or reuse an existing one.
2. **APIs & Services → Library** — search for and enable both:
   - Google Drive API
   - Google Sheets API
3. **APIs & Services → Credentials → Create Credentials → Service Account.**
   Name it something like `recruitiq-bot`. No project-level IAM role is needed —
   access is granted later by sharing specific files/folders with it.
4. Open the new service account → **Keys** tab → **Add Key → Create New Key → JSON.**
   Download it, rename to `service_account.json`, place it in your project root.
   **Add it to `.gitignore` immediately** — this key has write access to whatever you share with it.
5. Copy the service account's email — looks like
   `recruitiq-bot@your-project.iam.gserviceaccount.com`. You'll need it in steps 6 and 8.
6. In **your own Google Drive**, create a folder called `RecruitIQ`. Right-click → **Share**
   → paste the service account email → give it **Editor** access.
   (Service accounts have no storage quota of their own — this is why you share *your* folder with it.)
7. Open that folder, copy its ID from the URL:
   `https://drive.google.com/drive/folders/`**`<THIS_PART>`** → set as
   `GOOGLE_DRIVE_JD_ROOT_FOLDER_ID` in `.env`.
8. Create a new Google Sheet (e.g. "RecruitIQ Tracker"). Share it with the same
   service account email, **Editor** access.
9. Copy the Sheet ID from its URL:
   `https://docs.google.com/spreadsheets/d/`**`<THIS_PART>`**`/edit` → set as
   `GOOGLE_SHEET_ID` in `.env`.
10. Get a Groq API key from [console.groq.com/keys](https://console.groq.com/keys) →
    set as `GROQ_API_KEY` in `.env`.

Copy `.env.example` into your existing `.env` and fill in the four new values
(`GROQ_API_KEY`, `GOOGLE_SERVICE_ACCOUNT_FILE`, `GOOGLE_DRIVE_JD_ROOT_FOLDER_ID`, `GOOGLE_SHEET_ID`).

---

## 4. Wire the router into your FastAPI app

```python
# main.py (wherever your FastAPI() app is)
from routes_jd import router as jd_router
app.include_router(jd_router)
```

---

## 5. Testing

**Step 1 — sanity-check parsing without touching the DB:**
```bash
python jd_parser.py path/to/sample_jd.pdf
```
or via the API: `POST /jds/parse` (multipart, just `file`) — returns the raw text
preview + parsed JSON so you can eyeball the LLM's extraction quality before saving anything.

**Step 2 — full save:**
```
POST /jds
  file: <jd.pdf>
  client_id: 1   # from your Week 1 seed data — check with SELECT client_id FROM clients;
```
Returns the saved `jd_code`, parsed fields, and Drive link.
If Drive isn't configured yet, the JD still saves — `jd_file_drive_id`/`jd_file_path`
just come back null, so you're not blocked on Drive setup to test parsing.

**Step 3 — Sheets sync:**
```bash
python sheets_sync.py
```
Check your Sheet — you should see the candidates/JDs from `seed_data.py`
(plus anything new from Step 2 once it has mappings) flattened into the `Tracker` tab.

---

## 6. Notes / design decisions

- **LLM extraction is a single call per JD**, not the hybrid spaCy+LLM approach used
  for CVs in Module 2 — JD volume is low enough (per the proposal: 2-3 active JDs today,
  10+ target) that one clean LLM pass is simpler and accurate enough.
- **`/jds/parse` exists separately from `/jds`** so you (or a recruiter later, via the
  Week 5 dashboard) can review the extraction before it's committed — the LLM can
  misread an experience range or miss a skill, and that's cheaper to catch as a preview
  than as a bad DB row.
- **Sheets sync is a full overwrite**, not incremental — simplest correct thing for now.
  Worth revisiting if the candidate pool gets large enough that a full Sheets API write
  becomes slow (a `gspread` batch_update with diffing would be the next step).
- **Drive upload failures don't block JD creation** — if credentials aren't set up yet,
  `create_jd` still saves the parsed JD with null file fields rather than failing the
  whole request. Useful while you're getting Drive set up in parallel with testing parsing.

---

## 7. Before calling Week 2 "done"

- [ ] `service_account.json` in place, `.gitignore`'d
- [ ] Drive folder + Sheet both shared with the service account email
- [ ] `python jd_parser.py <sample.pdf>` returns sane JSON for a real JD
- [ ] `POST /jds` saves a row and (once Drive's hooked up) the file shows up in
      `/RecruitIQ/JobDescriptions/2026/`
- [ ] `python sheets_sync.py` populates the Tracker tab correctly
- [ ] Decide: do you want `sheets_sync.py` triggered automatically after every JD/mapping
      change, or is a manual/scheduled run fine for now? (Affects whether Week 3-4 work
      needs to call `sync()` directly or just leave it as a standalone script.)

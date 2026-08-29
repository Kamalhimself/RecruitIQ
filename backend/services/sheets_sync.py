"""
RecruitIQ - Week 2
Syncs candidate_jd_mapping + candidates + job_descriptions + recruiters into
a Google Sheet for recruiter-friendly, read-only viewing.

Run manually for now:
    python sheets_sync.py

(A scheduled version — cron or APScheduler — can wrap `sync()` later once
the pipeline is stable; the sync logic itself won't need to change.)

Setup:
1. Same service account as drive_utils.py — it needs Sheets + Drive scope.
2. Create a Google Sheet, share it with the service account's email as Editor.
3. Put the Sheet's ID (from its URL) in GOOGLE_SHEET_ID in .env.
"""

import os
import datetime
from decimal import Decimal
from uuid import UUID

import gspread
from dotenv import load_dotenv
from google.oauth2 import service_account
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from backend.database.setup_db import get_engine

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "./service_account.json")
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
WORKSHEET_NAME = "Tracker"

HEADERS = [
    "Candidate Code", "Candidate Name", "Email", "Phone",
    "JD Code", "Role", "Client",
    "Match Score", "Status",
    "Experience (yrs)", "Notice Period (days)", "Location",
    "Resume Path", "Reviewed By", "Last Updated",
]

QUERY = text("""
    SELECT
        c.candidate_code, c.full_name, c.email, c.phone,
        jd.jd_code, jd.role_title, cl.client_name,
        m.match_score, m.status,
        c.total_experience, c.notice_period_days, c.current_location,
        c.resume_file_path,
        r.full_name AS reviewed_by_name,
        m.updated_at
    FROM candidate_jd_mapping m
    JOIN candidates c ON c.candidate_id = m.candidate_id
    JOIN job_descriptions jd ON jd.jd_id = m.jd_id
    JOIN clients cl ON cl.client_id = jd.client_id
    LEFT JOIN recruiters r ON r.recruiter_id = m.reviewed_by
    ORDER BY m.match_score DESC NULLS LAST
""")


def to_cell(value):
    """Coerce DB types (Decimal, UUID, enum, datetime) into plain values
    gspread can write to a Sheets cell."""
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime.datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    if hasattr(value, "value"):  # enum members (e.g. MappingStatus.shortlisted)
        return value.value
    return value


def fetch_rows() -> list:
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        result = session.execute(QUERY)
        return [[to_cell(v) for v in row] for row in result]
    finally:
        session.close()


def get_worksheet():
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        raise RuntimeError(
            f"Service account file not found at {SERVICE_ACCOUNT_FILE}. "
            "See README Google Cloud Setup section."
        )
    if not SHEET_ID:
        raise RuntimeError("GOOGLE_SHEET_ID is not set in .env")

    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)
    try:
        ws = sh.worksheet(WORKSHEET_NAME)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=WORKSHEET_NAME, rows=1000, cols=len(HEADERS))
    return ws


def sync():
    rows = fetch_rows()
    ws = get_worksheet()
    ws.clear()
    ws.update(values=[HEADERS] + rows, range_name="A1")
    ws.format("A1:O1", {"textFormat": {"bold": True}})
    print(f"Synced {len(rows)} rows to the '{WORKSHEET_NAME}' tab.")


if __name__ == "__main__":
    sync()

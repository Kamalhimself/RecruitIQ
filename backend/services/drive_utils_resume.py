"""
RecruitIQ - Week 3
Extends drive_utils.py with resume upload support.

Adds upload_resume_file() which puts resumes into:
    /RecruitIQ/TalentPool/<year>/<month>/

Uses the same Google Drive OAuth client (or optional service account) as
drive_utils.py.

New .env variable needed:
    GOOGLE_DRIVE_TALENT_POOL_FOLDER_ID=<folder-id-of-your-TalentPool-folder>

Create /RecruitIQ/TalentPool in the signed-in Google Drive and copy its folder ID
into .env.
"""

import io
import os
import datetime

from dotenv import load_dotenv
from googleapiclient.http import MediaIoBaseUpload

from backend.services.drive_utils import _shared_drive_options, get_drive_service, get_or_create_folder

load_dotenv()

TALENT_POOL_ROOT_FOLDER_ID = os.getenv("GOOGLE_DRIVE_TALENT_POOL_FOLDER_ID")


def upload_resume_file(
    file_bytes: bytes,
    filename: str,
    candidate_code: str,
    mime_type: str = "application/pdf",
) -> dict:
    """
    Uploads a resume to /RecruitIQ/TalentPool/<year>/<month>/<filename>

    filename convention (built in routes_candidate.py):
        CAND-00001_JohnDoe.pdf

    Returns:
        {
            "drive_id": str,
            "web_link": str,
            "path": str   # e.g. /TalentPool/2026/07/CAND-00001_JohnDoe.pdf
        }
    """
    if not TALENT_POOL_ROOT_FOLDER_ID:
        raise RuntimeError(
            "GOOGLE_DRIVE_TALENT_POOL_FOLDER_ID is not set in .env. "
            "Create the TalentPool folder in Drive and set the folder ID."
        )

    service = get_drive_service()

    now        = datetime.datetime.now()
    year_str   = str(now.year)
    month_str  = now.strftime("%m")   # zero-padded: 01, 07, 12 etc.

    year_folder  = get_or_create_folder(year_str,  TALENT_POOL_ROOT_FOLDER_ID)
    month_folder = get_or_create_folder(month_str, year_folder)

    media    = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=False)
    metadata = {"name": filename, "parents": [month_folder]}

    uploaded = service.files().create(
        body=metadata, media_body=media, fields="id, webViewLink", **_shared_drive_options()
    ).execute()

    return {
        "drive_id": uploaded["id"],
        "web_link": uploaded.get("webViewLink"),
        "path":     f"/TalentPool/{year_str}/{month_str}/{filename}",
    }

"""
RecruitIQ - Week 2
Google Drive upload helper for JD files.

By default this uses OAuth, so files are created in the recruiter's own Google
Drive and use that account's quota. Shared Drive service-account support remains
available through GOOGLE_DRIVE_AUTH_MODE=service_account.
"""

import os
import io

from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/drive"]

SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "./service_account.json")
AUTH_MODE = os.getenv("GOOGLE_DRIVE_AUTH_MODE", "oauth").strip().lower()
OAUTH_CREDENTIALS_FILE = os.getenv("GOOGLE_DRIVE_CREDENTIALS_FILE", "drive_credentials.json")
OAUTH_TOKEN_FILE = os.getenv("GOOGLE_DRIVE_TOKEN_FILE", "drive_token.json")
ROOT_FOLDER_ID = os.getenv("GOOGLE_DRIVE_JD_ROOT_FOLDER_ID")
SHARED_DRIVE_ID = os.getenv("GOOGLE_DRIVE_SHARED_DRIVE_ID")

_drive_service = None


def _shared_drive_options(include_search_scope: bool = False) -> dict:
    """Options required by Drive API calls targeting a Google Shared Drive."""
    options = {"supportsAllDrives": True}
    if include_search_scope and SHARED_DRIVE_ID:
        options.update({
            "includeItemsFromAllDrives": True,
            "corpora": "drive",
            "driveId": SHARED_DRIVE_ID,
        })
    return options


def _oauth_credentials():
    """Load or create a user OAuth token for personal Google Drive uploads."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    credentials = None
    if os.path.exists(OAUTH_TOKEN_FILE):
        credentials = Credentials.from_authorized_user_file(OAUTH_TOKEN_FILE, SCOPES)
    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
    if not credentials or not credentials.valid:
        if not os.path.exists(OAUTH_CREDENTIALS_FILE):
            raise RuntimeError(
                f"Google OAuth client file not found at {OAUTH_CREDENTIALS_FILE}. "
                "Create a Desktop OAuth client in Google Cloud Console, download its JSON "
                "file there, then run: python drive_utils.py"
            )
        credentials = InstalledAppFlow.from_client_secrets_file(
            OAUTH_CREDENTIALS_FILE, SCOPES
        ).run_local_server(port=0)
        with open(OAUTH_TOKEN_FILE, "w") as token_file:
            token_file.write(credentials.to_json())
    return credentials


def get_drive_service():
    global _drive_service
    if _drive_service is None:
        if AUTH_MODE == "oauth":
            creds = _oauth_credentials()
        elif AUTH_MODE == "service_account":
            if not os.path.exists(SERVICE_ACCOUNT_FILE):
                raise RuntimeError(f"Service account file not found at {SERVICE_ACCOUNT_FILE}.")
            creds = service_account.Credentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE, scopes=SCOPES
            )
        else:
            raise RuntimeError(
                "GOOGLE_DRIVE_AUTH_MODE must be 'oauth' or 'service_account'."
            )
        _drive_service = build("drive", "v3", credentials=creds)
    return _drive_service


def get_or_create_folder(name: str, parent_id: str) -> str:
    """Returns the folder ID for `name` under `parent_id`, creating it if it
    doesn't exist yet. Used to build /JobDescriptions/<year>/ on the fly."""
    service = get_drive_service()
    safe_name = name.replace("'", "\\'")
    query = (
        f"name = '{safe_name}' and '{parent_id}' in parents "
        "and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    )
    results = service.files().list(
        q=query, fields="files(id, name)", **_shared_drive_options(include_search_scope=True)
    ).execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]

    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    folder = service.files().create(
        body=metadata, fields="id", **_shared_drive_options()
    ).execute()
    return folder["id"]


def upload_jd_file(file_bytes: bytes, filename: str, year: str, mime_type: str = "application/pdf") -> dict:
    """Uploads a JD file to /RecruitIQ/JobDescriptions/<year>/ (matching the
    Week 1 README's folder convention) and returns drive_id + web_link + path."""

    if not ROOT_FOLDER_ID:
        raise RuntimeError("GOOGLE_DRIVE_JD_ROOT_FOLDER_ID is not set in .env")

    service = get_drive_service()

    jd_root = get_or_create_folder("JobDescriptions", ROOT_FOLDER_ID)
    year_folder = get_or_create_folder(year, jd_root)

    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=False)
    metadata = {"name": filename, "parents": [year_folder]}

    uploaded = service.files().create(
        body=metadata, media_body=media, fields="id, webViewLink", **_shared_drive_options()
    ).execute()

    return {
        "drive_id": uploaded["id"],
        "web_link": uploaded.get("webViewLink"),
        "path": f"/JobDescriptions/{year}/{filename}",
    }


if __name__ == "__main__":
    # One-time local OAuth setup. A browser opens to let the Drive owner consent.
    account = get_drive_service().about().get(fields="user(emailAddress)").execute()
    print(f"Google Drive connected as {account['user']['emailAddress']}")

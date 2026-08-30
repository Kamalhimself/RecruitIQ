"""Gmail OAuth sender for recruiter-approved screening and follow-up messages."""

from __future__ import annotations

import base64
import os
from email.message import EmailMessage

from dotenv import load_dotenv

load_dotenv()

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def get_gmail_service():
    """Return an authenticated Gmail API client, creating an OAuth token if needed."""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError("Gmail support is not installed. Run: pip install -r requirements.txt") from exc

    credentials_file = os.getenv("GMAIL_CREDENTIALS_FILE", "credentials.json")
    token_file = os.getenv("GMAIL_TOKEN_FILE", "token.json")
    credentials = None
    if os.path.exists(token_file):
        try:
            credentials = Credentials.from_authorized_user_file(token_file, GMAIL_SCOPES)
        except Exception:
            credentials = None

    if credentials and credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
        except Exception:
            credentials = None
            if os.path.exists(token_file):
                try:
                    os.remove(token_file)
                except OSError:
                    pass
    if not credentials or not credentials.valid:
        if not os.path.exists(credentials_file):
            raise RuntimeError(
                f"Gmail OAuth credentials not found at {credentials_file}. "
                "Download an OAuth desktop-app credential from Google Cloud first."
            )
        credentials = InstalledAppFlow.from_client_secrets_file(credentials_file, GMAIL_SCOPES).run_local_server(port=0)
        with open(token_file, "w") as token:
            token.write(credentials.to_json())
    return build("gmail", "v1", credentials=credentials)


def send_email(to: str, subject: str, body: str) -> str:
    sender = os.getenv("GMAIL_SENDER_EMAIL")
    if not sender:
        raise RuntimeError("GMAIL_SENDER_EMAIL is not configured")
    message = EmailMessage()
    message["To"] = to
    message["From"] = sender
    message["Subject"] = subject
    message.set_content(body)
    payload = base64.urlsafe_b64encode(message.as_bytes()).decode()
    sent = get_gmail_service().users().messages().send(userId="me", body={"raw": payload}).execute()
    return sent["id"]


def screening_email(candidate_name: str, role_title: str, questions: list[str] | None = None) -> tuple[str, str]:
    questions = questions or [
        "What is your current notice period and earliest available joining date?",
        "What is your current and expected CTC?",
        "Are you comfortable with the role location and work arrangement?",
        "Please share a brief example of your most relevant recent project.",
    ]
    numbered_questions = "\n".join(f"{i}. {question}" for i, question in enumerate(questions, 1))
    subject = f"Next step: {role_title} opportunity"
    body = (
        f"Hi {candidate_name},\n\n"
        f"Thank you for your interest in the {role_title} opportunity. To proceed, please reply to this email with answers to the questions below:\n\n"
        f"{numbered_questions}\n\n"
        "Regards,\nRecruitment Team"
    )
    return subject, body

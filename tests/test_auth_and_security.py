import os
import unittest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.auth import create_access_token, decode_access_token
from backend.services.upload_validator import validate_uploaded_file, MAX_FILE_SIZE_BYTES
from fastapi import HTTPException, UploadFile
import io

client = TestClient(app)


class TestAuthAndSecurity(unittest.TestCase):

    def test_health_and_readiness_endpoints(self):
        """Verify liveness and readiness endpoints return 200."""
        res = client.get("/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "healthy")

        res_root = client.get("/")
        self.assertEqual(res_root.status_code, 200)

    def test_unauthenticated_request_rejected(self):
        """Verify protected candidate routes reject unauthenticated requests with 401."""
        res = client.get("/candidates")
        self.assertEqual(res.status_code, 401)
        self.assertIn("Authentication required", res.json()["detail"])

    def test_jwt_token_creation_and_decoding(self):
        """Verify JWT access tokens encode and decode correctly."""
        token = create_access_token({"email": "kamaleswar@velansys.com", "role": "admin"})
        self.assertIsInstance(token, str)

        payload = decode_access_token(token)
        self.assertEqual(payload["email"], "kamaleswar@velansys.com")
        self.assertEqual(payload["role"], "admin")
        self.assertIn("exp", payload)

    def test_authenticated_request_accepted(self):
        """Verify authenticated request with Bearer token passes."""
        token = create_access_token({"email": "kamaleswar@velansys.com", "role": "admin", "recruiter_id": 1})
        res = client.get("/candidates", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res.status_code, 200)

    def test_upload_validator_rejects_empty_file(self):
        """Verify validator rejects empty or tiny corrupted files."""
        fake_file = UploadFile(filename="resume.pdf", file=io.BytesIO(b""))
        with self.assertRaises(HTTPException) as ctx:
            validate_uploaded_file(fake_file, b"", entity_name="Resume")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_upload_validator_rejects_invalid_extension(self):
        """Verify validator rejects unauthorized executable/script extensions."""
        fake_file = UploadFile(filename="malicious.exe", file=io.BytesIO(b"MZ12345678901234567890"))
        with self.assertRaises(HTTPException) as ctx:
            validate_uploaded_file(fake_file, b"MZ12345678901234567890", entity_name="Resume")
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Unsupported file format", ctx.exception.detail)

    def test_upload_validator_rejects_mismatched_magic_bytes(self):
        """Verify validator catches file renamed to .pdf that is not actually a PDF."""
        fake_file = UploadFile(filename="spoofed.pdf", file=io.BytesIO(b"NOT_A_REAL_PDF_HEADER_BYTES"))
        with self.assertRaises(HTTPException) as ctx:
            validate_uploaded_file(fake_file, b"NOT_A_REAL_PDF_HEADER_BYTES", entity_name="Resume")
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("signature", ctx.exception.detail)

    def test_upload_validator_accepts_valid_pdf(self):
        """Verify validator accepts valid PDF content."""
        valid_pdf_bytes = b"%PDF-1.4 header bytes valid document"
        fake_file = UploadFile(filename="candidate_cv.pdf", file=io.BytesIO(valid_pdf_bytes))
        # Should not raise
        validate_uploaded_file(fake_file, valid_pdf_bytes, entity_name="Resume")


if __name__ == "__main__":
    unittest.main()

import hashlib
import hmac
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services import webhook_auth  # noqa: E402

SECRET = "whsec_test"
BODY = b'{"job_id": "job-1", "status": "failed"}'


def _signature(body: bytes, secret: str = SECRET) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def test_accepts_valid_signature():
    assert webhook_auth.is_valid_signature(BODY, _signature(BODY), SECRET)


def test_rejects_missing_signature():
    assert not webhook_auth.is_valid_signature(BODY, None, SECRET)
    assert not webhook_auth.is_valid_signature(BODY, "", SECRET)


def test_rejects_signature_from_wrong_secret():
    assert not webhook_auth.is_valid_signature(BODY, _signature(BODY, "other"), SECRET)


def test_rejects_signature_for_tampered_body():
    tampered = b'{"job_id": "job-2", "status": "failed"}'
    assert not webhook_auth.is_valid_signature(tampered, _signature(BODY), SECRET)

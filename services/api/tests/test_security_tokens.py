import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    import jwt

    from app.core import security
    from app.core.config import settings
except Exception as exc:  # noqa: BLE001 - service deps are not installed everywhere
    pytest.skip(f"api dependencies unavailable: {exc}", allow_module_level=True)


def _token(payload: dict, secret: str, algorithm: str = "HS256") -> str:
    token = jwt.encode(payload, secret, algorithm=algorithm)
    return token.decode("utf-8") if isinstance(token, bytes) else token


def _claims(**overrides) -> dict:
    payload = {
        "sub": "11111111-1111-1111-1111-111111111111",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    payload.update(overrides)
    return payload


def test_accepts_token_signed_with_service_secret():
    token = _token(_claims(), settings.jwt_secret, settings.jwt_algorithm)
    assert security.decode_access_token(token)["sub"] == _claims()["sub"]


def test_rejects_token_signed_with_other_secret():
    token = _token(_claims(is_admin=True), "attacker-secret")
    with pytest.raises(jwt.InvalidSignatureError):
        security.decode_access_token(token)


def test_rejects_unsigned_token():
    token = _token(_claims(is_admin=True), "", algorithm="none")
    with pytest.raises(jwt.InvalidTokenError):
        security.decode_access_token(token)


def test_rejects_expired_token():
    token = _token(
        _claims(exp=datetime.now(timezone.utc) - timedelta(minutes=1)),
        settings.jwt_secret,
        settings.jwt_algorithm,
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        security.decode_access_token(token)


def test_rejects_token_without_expiry():
    token = _token({"sub": "abc"}, settings.jwt_secret, settings.jwt_algorithm)
    with pytest.raises(jwt.MissingRequiredClaimError):
        security.decode_access_token(token)


def test_rejects_token_without_subject():
    token = _token(
        {"exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        settings.jwt_secret,
        settings.jwt_algorithm,
    )
    with pytest.raises(jwt.InvalidTokenError):
        security.decode_access_token(token)

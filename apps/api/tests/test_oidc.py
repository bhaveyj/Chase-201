import time

import pytest
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import generate_key

from chase201.auth import validate_google_token
from chase201.config import Settings, get_settings


@pytest.fixture(scope="module")
def signing_key():
    return generate_key("RSA", 2048, {"kid": "test-google-key"})


def signed_token(key, **changes):
    claims = {
        "iss": "https://accounts.google.com",
        "sub": "subject-201",
        "aud": "test-client",
        "exp": int(time.time()) + 300,
        "iat": int(time.time()),
        "nonce": "expected-nonce",
    }
    claims.update(changes)
    return {
        "id_token": jwt.encode(
            {"alg": "RS256", "kid": "test-google-key"},
            claims,
            key,
            algorithms=["RS256"],
        )
    }


def test_google_signature_and_claims(signing_key, monkeypatch):
    monkeypatch.setattr(get_settings(), "google_client_id", "test-client")
    keys = {"keys": [signing_key.as_dict(is_private=False)]}
    claims = validate_google_token(signed_token(signing_key), keys, "expected-nonce")
    assert claims["sub"] == "subject-201"


@pytest.mark.parametrize(
    "changes",
    [
        {"iss": "https://attacker.test"},
        {"aud": "another-client"},
        {"nonce": "wrong-nonce"},
        {"exp": 1},
        {"sub": ""},
        {"azp": "another-client"},
    ],
)
def test_rejects_invalid_google_claims(signing_key, monkeypatch, changes):
    monkeypatch.setattr(get_settings(), "google_client_id", "test-client")
    with pytest.raises(JoseError):
        validate_google_token(
            signed_token(signing_key, **changes),
            {"keys": [signing_key.as_dict(is_private=False)]},
            "expected-nonce",
        )


def test_rejects_bad_signature(signing_key, monkeypatch):
    monkeypatch.setattr(get_settings(), "google_client_id", "test-client")
    wrong_key = generate_key("RSA", 2048, {"kid": "test-google-key"})
    with pytest.raises(JoseError):
        validate_google_token(
            signed_token(wrong_key),
            {"keys": [signing_key.as_dict(is_private=False)]},
            "expected-nonce",
        )


def test_production_configuration_rejects_unsafe_defaults():
    with pytest.raises(ValueError):
        Settings(environment="production")
    with pytest.raises(ValueError):
        Settings(cors_origins=["*"])


def test_configuration_rejects_ambiguous_or_incomplete_deployments():
    with pytest.raises(ValueError):
        Settings(environment="prod")
    with pytest.raises(ValueError):
        Settings(google_client_id="client-without-secret")
    with pytest.raises(ValueError):
        Settings(frontend_url="https://play.example.com/path")

    production = {
        "environment": "production",
        "database_url": "postgresql+asyncpg://app:secret@db.internal/app",
        "secret_key": "a-unique-production-secret-with-32-characters",
        "frontend_url": "https://play.example.com",
        "api_url": "https://api.example.com",
        "cors_origins": ["https://play.example.com"],
        "catalog_version": "approved-2026-01",
    }
    with pytest.raises(ValueError):
        Settings(**production)
    settings = Settings(
        **production,
        google_client_id="google-client",
        google_client_secret="google-secret",
    )
    assert settings.secure_cookies

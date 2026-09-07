import time

import pytest
from authlib.jose import JsonWebKey, JsonWebToken
from authlib.jose.errors import JoseError
from joserfc.errors import JoseError as RFCError

from chase201.auth import validate_google_token
from chase201.config import Settings, get_settings


@pytest.fixture(scope="module")
def signing_key():
    return JsonWebKey.generate_key("RSA", 2048, {"kid": "test-google-key"}, is_private=True)


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
        "id_token": JsonWebToken(["RS256"])
        .encode({"alg": "RS256", "kid": "test-google-key"}, claims, key)
        .decode()
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
    with pytest.raises((JoseError, RFCError)):
        validate_google_token(
            signed_token(signing_key, **changes),
            {"keys": [signing_key.as_dict(is_private=False)]},
            "expected-nonce",
        )


def test_rejects_bad_signature(signing_key, monkeypatch):
    monkeypatch.setattr(get_settings(), "google_client_id", "test-client")
    wrong_key = JsonWebKey.generate_key("RSA", 2048, {"kid": "test-google-key"}, is_private=True)
    with pytest.raises((JoseError, RFCError)):
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

from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import jwt
import requests
from jwt import PyJWKClient

from app.core.config import settings


def generate_pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("utf-8")
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("utf-8")).digest()
    ).rstrip(b"=").decode("utf-8")
    return verifier, challenge


def build_auth_url(state: str, nonce: str, challenge: str) -> str:
    query = urlencode(
        {
            "response_type": "code",
            "client_id": settings.hpr_oauth_client_id,
            "redirect_uri": settings.hpr_oauth_redirect_uri,
            "scope": settings.hpr_oauth_scopes,
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    return f"{settings.hpr_oauth_auth_url}?{query}"


def exchange_code_for_token(code: str, verifier: str) -> dict[str, Any]:
    response = requests.post(
        settings.hpr_oauth_token_url,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.hpr_oauth_redirect_uri,
            "client_id": settings.hpr_oauth_client_id,
            "client_secret": settings.hpr_oauth_client_secret,
            "code_verifier": verifier,
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def validate_id_token(id_token: str) -> dict[str, Any]:
    jwks_client = PyJWKClient(settings.hpr_oauth_jwks_url)
    signing_key = jwks_client.get_signing_key_from_jwt(id_token)
    decode_kwargs: dict[str, Any] = {
        "key": signing_key.key,
        "algorithms": ["RS256"],
        "audience": settings.hpr_oauth_client_id,
        "leeway": settings.hpr_oauth_clock_skew_seconds,
        "options": {"verify_exp": True},
    }
    if settings.hpr_oauth_issuer:
        decode_kwargs["issuer"] = settings.hpr_oauth_issuer
    payload = jwt.decode(id_token, **decode_kwargs)
    if settings.hpr_oauth_issuer and payload.get("iss") != settings.hpr_oauth_issuer:
        raise ValueError("INVALID_ISSUER")
    return payload


def create_oauth_state(state: str, nonce: str, verifier: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "type": "hpr_oauth_state",
        "state": state,
        "nonce": nonce,
        "verifier": verifier,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.hpr_oauth_state_ttl_seconds)).timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_oauth_state(token: str) -> dict[str, Any]:
    payload = jwt.decode(
        token,
        settings.secret_key,
        algorithms=["HS256"],
        leeway=settings.hpr_oauth_clock_skew_seconds,
    )
    if payload.get("type") != "hpr_oauth_state":
        raise ValueError("INVALID_STATE_TOKEN")
    return payload

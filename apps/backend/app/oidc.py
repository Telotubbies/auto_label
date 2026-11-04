"""OIDC bearer-token boundary (optional — disabled unless OIDC_ISSUER is set).

Config (env vars):
    OIDC_ISSUER     issuer URL, e.g. https://keycloak.local/realms/labeldesk
                    or https://accounts.google.com
    OIDC_CLIENT_ID  expected `aud` claim (audience check skipped if unset)

Flow: main.user() calls verify_oidc() first; a valid RS256 id/access token
auto-provisions a local user (id = "oidc:" + sub, role "annotator").
The issuer's .well-known/openid-configuration is fetched once and the
jwks_uri / JWK client is cached for 10 minutes.

Dev IdP: a commented-out `keycloak` service template lives at the bottom
of docker-compose.labeldesk.yml — uncomment to run a local realm.

If PyJWT is not installed, verify_oidc() logs once and returns None so
local-JWT auth keeps working unchanged.
"""
import json
import logging
import os
import time
import urllib.request

log = logging.getLogger("auto_label.oidc")

try:
    import jwt
    _HAS_JWT = True
except ImportError:  # pragma: no cover — PyJWT missing -> OIDC disabled
    jwt = None
    _HAS_JWT = False
    log.warning("PyJWT not installed — OIDC verification disabled")

ISSUER = os.environ.get("OIDC_ISSUER", "").rstrip("/")
CLIENT_ID = os.environ.get("OIDC_CLIENT_ID", "")
_CACHE_TTL = 600  # seconds
_cache = {"ts": 0.0, "jwks_client": None}


def _jwks_client():
    """Fetch discovery doc -> cached jwt.PyJWKClient (10 min TTL)."""
    now = time.time()
    if _cache["jwks_client"] and now - _cache["ts"] < _CACHE_TTL:
        return _cache["jwks_client"]
    try:
        with urllib.request.urlopen(
            f"{ISSUER}/.well-known/openid-configuration", timeout=5
        ) as r:
            cfg = json.loads(r.read())
        _cache["jwks_client"] = jwt.PyJWKClient(cfg["jwks_uri"])
    except Exception as e:
        log.warning("OIDC discovery failed for %s: %s", ISSUER, e)
        _cache["jwks_client"] = None
    _cache["ts"] = now  # cache failures too — don't hammer a down IdP
    return _cache["jwks_client"]


def verify_oidc(token: str) -> dict | None:
    """Verify an RS256 OIDC bearer token -> claims dict, or None.

    Returns None when OIDC is disabled (no OIDC_ISSUER), PyJWT is missing,
    the token isn't RS256 (local tokens are HS256 — fast path), or any
    signature/iss/aud/exp check fails.
    """
    if not ISSUER or not _HAS_JWT:
        return None
    try:
        if jwt.get_unverified_header(token).get("alg") != "RS256":
            return None  # local HS256 token — skip JWKS work entirely
    except Exception:
        return None
    client = _jwks_client()
    if not client:
        return None
    try:
        key = client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            key.key,
            algorithms=["RS256"],
            issuer=ISSUER,
            audience=CLIENT_ID or None,
            options={
                "verify_aud": bool(CLIENT_ID),
                "require": ["exp", "iss", "sub"],
            },
        )
    except Exception as e:
        log.debug("OIDC token rejected: %s", e)
        return None

"""Password hashing (scrypt, memory-hard) and token helpers. Standard library only."""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets

_N, _R, _P, _DKLEN = 2 ** 15, 8, 1, 64
_MAXMEM = 128 * 1024 * 1024


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=_DKLEN, maxmem=_MAXMEM)
    return f"scrypt${_N}${_R}${_P}${_b64(salt)}${_b64(dk)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt_b64, dk_b64 = stored.split("$")
        if algo != "scrypt":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(dk_b64)
        dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=int(n), r=int(r), p=int(p),
                            dklen=len(expected), maxmem=_MAXMEM)
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False


def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def check_password_policy(password: str, policy: dict) -> list[str]:
    """Return a list of human readable problems (empty = OK)."""
    problems: list[str] = []
    min_len = int(policy.get("min_length", 8))
    if len(password) < min_len:
        problems.append(f"at least {min_len} characters")
    if policy.get("require_upper", True) and not re.search(r"[A-Z]", password):
        problems.append("an uppercase letter")
    if policy.get("require_lower", True) and not re.search(r"[a-z]", password):
        problems.append("a lowercase letter")
    if policy.get("require_digit", True) and not re.search(r"\d", password):
        problems.append("a digit")
    if policy.get("require_symbol", False) and not re.search(r"[^A-Za-z0-9]", password):
        problems.append("a symbol")
    return problems

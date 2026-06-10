from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

MIN_PEOPLE_DATA_PASSWORD_LENGTH = 12
_ALGORITHM = "pbkdf2_sha256"
_ITERATIONS = 260_000
_SALT_BYTES = 16


def validate_people_data_password(password: str) -> None:
    if len(password) < MIN_PEOPLE_DATA_PASSWORD_LENGTH:
        raise ValueError(
            f"Password must be at least {MIN_PEOPLE_DATA_PASSWORD_LENGTH} characters long"
        )


def hash_password(plain: str) -> str:
    validate_people_data_password(plain)
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, _ITERATIONS)
    return "$".join(
        [
            _ALGORITHM,
            str(_ITERATIONS),
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(digest).decode("ascii"),
        ]
    )


def verify_password(plain: str, stored: str) -> bool:
    try:
        algorithm, iterations_raw, salt_raw, digest_raw = stored.split("$", 3)
        if algorithm != _ALGORITHM:
            return False
        iterations = int(iterations_raw)
        salt = base64.b64decode(salt_raw.encode("ascii"), validate=True)
        expected = base64.b64decode(digest_raw.encode("ascii"), validate=True)
    except (ValueError, TypeError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)

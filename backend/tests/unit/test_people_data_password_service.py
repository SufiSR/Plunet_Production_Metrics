from __future__ import annotations

import pytest

from app.services.people_data_password_service import hash_password, verify_password


def test_people_data_password_hash_verifies_and_rejects_wrong_password() -> None:
    stored = hash_password("people-secret-123")

    assert verify_password("people-secret-123", stored) is True
    assert verify_password("wrong-secret-123", stored) is False


def test_people_data_password_requires_minimum_length() -> None:
    with pytest.raises(ValueError):
        hash_password("short")

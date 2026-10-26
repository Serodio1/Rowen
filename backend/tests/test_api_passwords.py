"""Tests for how the web API keeps and checks passwords."""

import threading
import time

import pytest

from rowen.api import passwords
from rowen.api.passwords import AT_ONCE, check_password, hash_password


def test_a_hash_is_argon2id_with_owasps_settings() -> None:
    password_hash = hash_password("dragon123")

    assert password_hash.startswith("$argon2id$v=19$m=19456,t=2,p=1$")
    assert "dragon123" not in password_hash


def test_the_same_password_gets_another_hash_each_time() -> None:
    # Each hash has a salt of its own.
    assert hash_password("dragon123") != hash_password("dragon123")


def test_a_password_matches_only_its_own_hash() -> None:
    password_hash = hash_password("dragon123")

    assert check_password(password_hash, "dragon123")
    assert not check_password(password_hash, "dragon124")
    assert not check_password(hash_password("dragon124"), "dragon123")


def test_a_password_typed_in_another_unicode_form_still_matches() -> None:
    # "é" as one character (NFC), as most keyboards type it, and as "e" and
    # a combining accent (NFD), as some devices do: the same password.
    composed = "caf\u00e9 dragon"
    decomposed = "cafe\u0301 dragon"
    assert composed != decomposed

    assert check_password(hash_password(composed), decomposed)
    assert check_password(hash_password(decomposed), composed)


def test_with_no_account_no_password_matches() -> None:
    assert not check_password(None, "there is no account with this username")
    assert not check_password(None, "dragon123")


class SlowHasher:
    """Stands in for Argon2: counts how many hashes are worked out at once."""

    def __init__(self) -> None:
        self.now = 0
        self.most = 0
        self.checked: list[str] = []
        self._lock = threading.Lock()

    def _work(self) -> None:
        with self._lock:
            self.now += 1
            self.most = max(self.most, self.now)
        time.sleep(0.02)
        with self._lock:
            self.now -= 1

    def hash(self, password: str) -> str:
        self._work()
        return "hash"

    def verify(self, password_hash: str, password: str) -> bool:
        self.checked.append(password_hash)
        self._work()
        return True


def test_at_most_a_few_hashes_are_worked_out_at_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hasher = SlowHasher()
    monkeypatch.setattr(passwords, "_HASHER", hasher)
    threads = [
        threading.Thread(target=hash_password, args=("dragon123",)) for _ in range(6)
    ] + [
        threading.Thread(target=check_password, args=("hash", "dragon123"))
        for _ in range(6)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert hasher.most == AT_ONCE


def test_with_no_account_a_hash_is_still_checked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # So it takes as long as with a wrong password.
    hasher = SlowHasher()
    monkeypatch.setattr(passwords, "_HASHER", hasher)

    assert not check_password(None, "dragon123")
    assert hasher.checked == [passwords._NO_ACCOUNT]

"""Password hashes: how an account's password is kept and checked (ADR 0014).

The server never keeps a password, only its hash: a value worked out from it
that can't be turned back into the password. To check a password, the server
works out the hash again and compares. Each hash has a random salt of its own,
so the same password gives another hash each time, and two players with the
same password can't be told apart.

The hash is Argon2id, which is slow and takes memory on purpose: whoever steals
the hashes must spend as much for each password they try. The settings are the
smallest OWASP recommends (19 MiB, 2 passes, 1 thread), and they are written in
each hash, so a hash made with other settings can still be checked. A hash
takes about 30 ms of CPU.

A password is first put in one Unicode form (NFKC), as NIST advises: an "é"
can be typed as one character or as "e" and an accent, depending on the
keyboard or the device, and both must be the same password.

At most ``AT_ONCE`` hashes are worked out at the same time: the server
handles up to 40 requests at once, and 40 hashes would take 760 MiB, more than
the API's 512 MiB (``deploy/cloud-run.yaml``). The others wait their turn.
"""

import threading
import unicodedata

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

AT_ONCE = 4

_HASHER = PasswordHasher(time_cost=2, memory_cost=19 * 1024, parallelism=1)
_TURNS = threading.BoundedSemaphore(AT_ONCE)

# Checked against when there is no account with the username given, so that
# logging in takes as long as with a wrong password: otherwise, how quickly
# the server answers would tell which usernames have an account.
_NO_ACCOUNT = _HASHER.hash("there is no account with this username")


def hash_password(password: str) -> str:
    """Return the hash of a password, to keep in its place."""
    with _TURNS:
        return _HASHER.hash(_normalized(password))


def check_password(password_hash: str | None, password: str) -> bool:
    """Return whether a password is the one a hash was made from.

    ``password_hash`` is None when there is no account with the username
    given: then the password is checked against another hash, which takes as
    long, and the answer is always False.
    """
    with _TURNS:
        try:
            _HASHER.verify(password_hash or _NO_ACCOUNT, _normalized(password))
        except VerifyMismatchError:
            return False
    return password_hash is not None


def _normalized(password: str) -> str:
    """Return a password in Unicode's NFKC form, the one its hash is made from."""
    return unicodedata.normalize("NFKC", password)

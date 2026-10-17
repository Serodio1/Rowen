"""Where the web API keeps its matches: in memory, for now.

A ``MatchStore`` maps the id of each match to its state and its version
(below). The id is a random UUID (version 4): 122 random bits from the
operating system, so nobody can guess the id of a match that isn't theirs.
Whoever has the id can see the match and play it, so the id is all the player
needs.

Anyone can start a match, so the store holds at most ``max_matches`` of them:
otherwise, starting matches without end would fill the server's memory. When
it is full, a new match pushes out the one left unused the longest.

The web server handles requests in threads, so two of them can use the store
at the same time. A lock lets one thread in at a time: without it, one thread
could push out a match while another is reading it.

Each match has a version number, which goes up by one each time its state
is replaced. A move says which version of the match it was chosen from, and
``replace`` keeps a new state only if the match is still at that version. So
a move chosen from an old view is never played: not when another request
played first, while this one was being played (the AI takes a while to think,
and the lock isn't held meanwhile), nor when it reaches the server late,
after the browser gave up on it and the player played again.

PostgreSQL takes its place later in this milestone, behind the same methods,
so the endpoints don't change. There, ``replace`` will be an ``UPDATE ...
WHERE id = :id AND version = :version``.
"""

import threading
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from uuid import UUID

from rowen.engine.public import GameState

# A match takes about 10 KB, so a full store takes about 10 MB.
MAX_MATCHES = 1000

# The version of a new match.
FIRST_VERSION = 1


@dataclass(frozen=True)
class StoredMatch:
    """A match as the store keeps it: its id, its state and its version."""

    id: UUID
    state: GameState
    version: int


class MatchStore:
    """The matches being played, each under its id."""

    def __init__(self, max_matches: int = MAX_MATCHES) -> None:
        """Make an empty store.

        Args:
            max_matches: How many matches it holds at most.
        """
        self._max_matches = max_matches
        # From the match left unused the longest to the one used last.
        self._matches: OrderedDict[UUID, StoredMatch] = OrderedDict()
        self._lock = threading.Lock()

    def create(self, state: GameState) -> StoredMatch:
        """Keep a new match, at its first version, and return it.

        If the store is full, the match left unused the longest is lost.
        """
        match = StoredMatch(id=uuid.uuid4(), state=state, version=FIRST_VERSION)
        with self._lock:
            self._matches[match.id] = match
            if len(self._matches) > self._max_matches:
                self._matches.popitem(last=False)
        return match

    def get(self, match_id: UUID) -> StoredMatch | None:
        """Return a match, or None if there is no match with that id.

        The match counts as used, so it is the last to be pushed out.
        """
        with self._lock:
            match = self._matches.get(match_id)
            if match is not None:
                self._matches.move_to_end(match_id)
            return match

    def replace(
        self, match_id: UUID, version: int, state: GameState
    ) -> StoredMatch | None:
        """Replace the state of a match, but only if it is still at ``version``.

        Return the match as it is now kept, at the next version, or None if it
        wasn't replaced: the match is at another version, or it was pushed out.

        The match counts as used, so it is the last to be pushed out.
        """
        with self._lock:
            old = self._matches.get(match_id)
            if old is None or old.version != version:
                return None
            new = StoredMatch(id=match_id, state=state, version=version + 1)
            self._matches[match_id] = new
            self._matches.move_to_end(match_id)
            return new

"""Where the web API keeps its matches: in memory, for now.

A ``MatchStore`` maps the id of each match to its state. The id is a random
UUID (version 4): 122 random bits from the operating system, so nobody can
guess the id of a match that isn't theirs. Whoever has the id can see the
match, so the id is all the player needs.

Anyone can start a match, so the store holds at most ``max_matches`` of them:
otherwise, starting matches without end would fill the server's memory. When
it is full, a new match pushes out the one left unused the longest.

The web server handles requests in threads, so two of them can use the store
at the same time. A lock lets one thread in at a time: without it, one thread
could push out a match while another is reading it.

Two requests can also play the same match at once, as after a double click:
each gets the match, plays its action and keeps the result. The lock isn't
held while they play, since the AI takes a while to think, so ``replace``
keeps a result only if the match is still the one its request started from.
The other request finds the match changed and is turned down, instead of
undoing the first one's action without a word.

PostgreSQL takes its place later in this milestone, behind the same methods,
so the endpoints don't change.
"""

import threading
import uuid
from collections import OrderedDict
from uuid import UUID

from rowen.engine.public import GameState

# A match takes about 10 KB, so a full store takes about 10 MB.
MAX_MATCHES = 1000


class MatchStore:
    """The matches being played, each under its id."""

    def __init__(self, max_matches: int = MAX_MATCHES) -> None:
        """Make an empty store.

        Args:
            max_matches: How many matches it holds at most.
        """
        self._max_matches = max_matches
        # From the match left unused the longest to the one used last.
        self._matches: OrderedDict[UUID, GameState] = OrderedDict()
        self._lock = threading.Lock()

    def create(self, state: GameState) -> UUID:
        """Keep a new match and return its id.

        If the store is full, the match left unused the longest is lost.
        """
        match_id = uuid.uuid4()
        with self._lock:
            self._matches[match_id] = state
            if len(self._matches) > self._max_matches:
                self._matches.popitem(last=False)
        return match_id

    def get(self, match_id: UUID) -> GameState | None:
        """Return the state of a match, or None if there is no match with that id.

        The match counts as used, so it is the last to be pushed out.
        """
        with self._lock:
            state = self._matches.get(match_id)
            if state is not None:
                self._matches.move_to_end(match_id)
            return state

    def replace(self, match_id: UUID, old: GameState, new: GameState) -> bool:
        """Replace the state of a match, but only if it is still ``old``.

        Return whether it was replaced. It wasn't if another request replaced
        it first, or if it was pushed out. ``old`` is the state ``get``
        returned: the very same object, not just an equal one.

        The match counts as used, so it is the last to be pushed out.
        """
        with self._lock:
            if self._matches.get(match_id) is not old:
                return False
            self._matches[match_id] = new
            self._matches.move_to_end(match_id)
            return True

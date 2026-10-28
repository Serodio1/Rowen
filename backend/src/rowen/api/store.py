"""Where the web API keeps its matches: in memory, or in PostgreSQL.

``MatchStore`` is what the API needs from a store, and there are two:
``MemoryMatchStore``, here, which keeps the matches in the server's memory,
and ``PostgresMatchStore`` (``rowen.api.database``), which keeps them in a
database, so they survive a restart. The same tests run against both
(``tests/test_api_store.py``).

A match is kept as what it takes to play it again: the ids of the two decks,
the seed, and every action played so far, the player's and the AI's, in
order. When the player plays a deck they built, the match also keeps a copy
of it, its name and how many copies of each card (``DeckCopy``): the deck
itself may change or go, but the match must always play again the same way
(ADR 0017). It also keeps the level of the AI the player chose, at which
the AI plays its moves to come. The engine is deterministic, so the same
decks, seed and actions always make the same state (ADR 0003): the API plays
the actions again to get it, in a millisecond or two. The store never sees a
state.

A store maps the id of each match to that record and its version (below). The
id is a random UUID (version 4): 122 random bits from the operating system, so
nobody can guess the id of a match that isn't theirs. A guest's match has no
owner: whoever has the id can see it and play it, so the id is all the player
needs. A match started by a player who is logged in has their account as its
owner, and only they may see it (the API checks that, not the store).

When a match is over, the store also keeps its result: whether the player won,
lost or drew, each round's totals and when it ended. The API works it out and
gives it with the last actions (``add_actions``). With the results, a store
lists an owner's matches, newest first, a page at a time (``list_matches``),
and counts their wins, losses and draws with each deck (``stats``).

Anyone can start a match, so the store in memory holds at most
``max_matches`` of them: otherwise, starting matches without end would fill
the server's memory. When it is full, a new match pushes out the one left
unused the longest.

The web server handles requests in threads, so two of them can use the store
at the same time. In memory, a lock lets one thread in at a time: without it,
one thread could push out a match while another is reading it.

Each match has a version number, which goes up by one each time actions are
added to it. A move says which version of the match it was chosen from, and
``add_actions`` adds its actions only if the match is still at that version.
So a move chosen from an old view is never played: not when another request
played first, while this one was being played (the AI takes a while to think,
and nothing is locked meanwhile), nor when it reaches the server late, after
the browser gave up on it and the player played again. In PostgreSQL this is
an ``UPDATE ... WHERE id = :id AND version = :version``.
"""

import threading
import uuid
from collections import Counter, OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

from rowen.engine.public import Action

# A whole match, of up to about 40 actions, takes at most about 15 KB, so a
# full store takes at most about 15 MB.
MAX_MATCHES = 1000

# The version of a new match.
FIRST_VERSION = 1


# How a match ended, for the player (not the AI).
type Outcome = Literal["won", "lost", "drawn"]

# How well the AI plays: easy is the baseline AI, normal and hard the Monte
# Carlo AI, with more samples for hard (ADR 0018).
type Level = Literal["easy", "normal", "hard"]


@dataclass(frozen=True)
class MatchResult:
    """How a match ended.

    Attributes:
        outcome: Whether the player won, lost or drew.
        rounds: Each round's totals, in order: the player's and then the AI's.
        ended_at: When the last action was played.
    """

    outcome: Outcome
    rounds: tuple[tuple[int, int], ...]
    ended_at: datetime


@dataclass(frozen=True)
class DeckCopy:
    """A copy of a deck a player built, kept with a match they play with it.

    Attributes:
        name: The deck's name when the match started.
        copies: How many copies of each card, by the card's id.
    """

    name: str
    copies: Mapping[str, int]


@dataclass(frozen=True)
class StoredMatch:
    """A match as the store keeps it: what it takes to play it again.

    Attributes:
        id: The match's id.
        decks: The ids of the decks, the player's and then the AI's. For a
            deck the player built, the id of its faction's own deck.
        seed: The seed the match started with. It is never sent to a player.
        actions: Every action played since the match started, in order.
        version: Goes up by one each time actions are added.
        owner: The id of the account that started it, or None for a guest.
        created_at: When it started.
        result: How it ended, or None while it goes on.
        built: A copy of the deck the player built, or None if they play
            their faction's own.
        level: The level of the AI.
    """

    id: UUID
    decks: tuple[str, str]
    seed: int
    actions: tuple[Action, ...]
    version: int
    owner: UUID | None
    created_at: datetime
    result: MatchResult | None
    built: DeckCopy | None = None
    level: Level = "easy"


@dataclass(frozen=True)
class MatchSummary:
    """A match in the list of an owner's matches: no seed, no actions.

    Attributes:
        id: The match's id.
        decks: The ids of the decks, the player's and then the AI's.
        created_at: When it started.
        result: How it ended, or None while it goes on.
        deck_name: The name of the deck the player built, or None if they
            played their faction's own.
        level: The level of the AI.
    """

    id: UUID
    decks: tuple[str, str]
    created_at: datetime
    result: MatchResult | None
    deck_name: str | None = None
    level: Level = "easy"


@dataclass(frozen=True)
class DeckStats:
    """How an owner's matches with one of the decks ended, counted.

    Matches that go on don't count.

    Attributes:
        deck: The id of the deck the player played.
        won: How many of them the player won.
        lost: How many they lost.
        drawn: How many were draws.
    """

    deck: str
    won: int
    lost: int
    drawn: int


class MatchStore(Protocol):
    """What the API needs from a store: what each store does."""

    def create(
        self,
        decks: tuple[str, str],
        seed: int,
        actions: tuple[Action, ...],
        *,
        owner: UUID | None,
        now: datetime,
        built: DeckCopy | None = None,
        level: Level = "easy",
    ) -> StoredMatch:
        """Keep a new match, at its first version, and return it.

        ``actions`` are those played before the match is kept: the AI's
        first moves, if it starts. ``owner`` is the account of the player who
        starts it, if they are logged in, ``now`` when it starts,
        ``built`` a copy of the deck the player built, if they play one, and
        ``level`` the level of the AI.
        """
        ...

    def get(self, match_id: UUID) -> StoredMatch | None:
        """Return a match, or None if there is no match with that id."""
        ...

    def add_actions(
        self,
        match_id: UUID,
        version: int,
        actions: tuple[Action, ...],
        result: MatchResult | None = None,
    ) -> StoredMatch | None:
        """Add actions to a match, but only if it is still at ``version``.

        ``result`` is how the match ended, if these actions end it.

        Return the match as it is now kept, at the next version, or None if
        nothing was added: the match is at another version, or there is no
        match with that id.
        """
        ...

    def list_matches(
        self, owner: UUID, limit: int, before: UUID | None = None
    ) -> tuple[MatchSummary, ...]:
        """Return up to ``limit`` of an owner's matches, the newest first.

        With ``before``, the id of one of the owner's matches, only those
        older than it: the next page, after a page that ended with it. If it
        is no match of the owner's, none.

        Two matches that started at the same time come in the order of their
        ids, so each one is on exactly one page.
        """
        ...

    def stats(self, owner: UUID) -> tuple[DeckStats, ...]:
        """Return how an owner's matches ended with each deck they played.

        One record for each deck with a match that ended, in the order of
        the decks' ids.
        """
        ...


class MemoryMatchStore:
    """The matches being played, each under its id, in the server's memory."""

    def __init__(self, max_matches: int = MAX_MATCHES) -> None:
        """Make an empty store.

        Args:
            max_matches: How many matches it holds at most.
        """
        self._max_matches = max_matches
        # From the match left unused the longest to the one used last.
        self._matches: OrderedDict[UUID, StoredMatch] = OrderedDict()
        self._lock = threading.Lock()

    def create(
        self,
        decks: tuple[str, str],
        seed: int,
        actions: tuple[Action, ...],
        *,
        owner: UUID | None,
        now: datetime,
        built: DeckCopy | None = None,
        level: Level = "easy",
    ) -> StoredMatch:
        """Keep a new match, at its first version, and return it.

        ``actions`` are those played before the match is kept: the AI's
        first moves, if it starts. If the store is full, the match left
        unused the longest is lost, even if it has an owner.
        """
        match = StoredMatch(
            id=uuid.uuid4(),
            decks=decks,
            seed=seed,
            actions=actions,
            version=FIRST_VERSION,
            owner=owner,
            created_at=now,
            result=None,
            built=None
            if built is None
            else DeckCopy(name=built.name, copies=dict(built.copies)),
            level=level,
        )
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

    def add_actions(
        self,
        match_id: UUID,
        version: int,
        actions: tuple[Action, ...],
        result: MatchResult | None = None,
    ) -> StoredMatch | None:
        """Add actions to a match, but only if it is still at ``version``.

        ``result`` is how the match ended, if these actions end it.

        Return the match as it is now kept, at the next version, or None if
        nothing was added: the match is at another version, or it was pushed
        out.

        The match counts as used, so it is the last to be pushed out.
        """
        with self._lock:
            old = self._matches.get(match_id)
            if old is None or old.version != version:
                return None
            new = replace(
                old,
                actions=old.actions + actions,
                version=version + 1,
                result=old.result if result is None else result,
            )
            self._matches[match_id] = new
            self._matches.move_to_end(match_id)
            return new

    def list_matches(
        self, owner: UUID, limit: int, before: UUID | None = None
    ) -> tuple[MatchSummary, ...]:
        """Return up to ``limit`` of an owner's matches, the newest first.

        With ``before``, only those older than that match of the owner's.
        Listing a match doesn't count as using it.
        """
        with self._lock:
            owned = [match for match in self._matches.values() if match.owner == owner]
        owned.sort(key=_order, reverse=True)
        if before is not None:
            cursor = next((match for match in owned if match.id == before), None)
            if cursor is None:
                return ()
            owned = [match for match in owned if _order(match) < _order(cursor)]
        return tuple(
            MatchSummary(
                id=match.id,
                decks=match.decks,
                created_at=match.created_at,
                result=match.result,
                deck_name=None if match.built is None else match.built.name,
                level=match.level,
            )
            for match in owned[:limit]
        )

    def stats(self, owner: UUID) -> tuple[DeckStats, ...]:
        """Return how an owner's matches ended with each deck they played."""
        with self._lock:
            ended = [
                (match.decks[0], match.result.outcome)
                for match in self._matches.values()
                if match.owner == owner and match.result is not None
            ]
        counts = Counter(ended)
        return tuple(
            DeckStats(
                deck=deck,
                won=counts[deck, "won"],
                lost=counts[deck, "lost"],
                drawn=counts[deck, "drawn"],
            )
            for deck in sorted({deck for deck, _ in ended})
        )


def _order(match: StoredMatch) -> tuple[datetime, UUID]:
    """Return what orders matches in a list: when they started, then the id."""
    return match.created_at, match.id

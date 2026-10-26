"""Where the web API keeps the decks players build: in memory, or in PostgreSQL.

As with the matches (``rowen.api.store``), ``DeckStore`` is what the API needs
from a store, and there are two: ``MemoryDeckStore``, here, and
``PostgresDeckStore`` (``rowen.api.database``). The same tests run against
both (``tests/test_api_player_decks.py``).

A deck a player builds belongs to their account. It is kept as the player
chose it: its name, the faction whose cards it holds (the id of the faction's
own deck, such as ``"humans"``) and how many copies of each card, by the
card's id. The store doesn't check the choice: the API does, through the
engine (``build_deck``), before it keeps or changes a deck.

A player may keep up to ``MAX_DECKS`` decks. The store checks it as it adds
one, so that two requests at the same time can't both add the tenth.
"""

import threading
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Protocol
from uuid import UUID

# How many decks a player may keep.
MAX_DECKS = 10


@dataclass(frozen=True)
class StoredDeck:
    """A deck a player built, as the store keeps it.

    Attributes:
        id: The deck's id.
        owner: The id of the account it belongs to.
        name: The name the player gave it.
        faction: The id of the faction's own deck, whose cards it holds.
        copies: How many copies of each card, by the card's id.
        created_at: When it was made: the decks are listed in this order.
    """

    id: UUID
    owner: UUID
    name: str
    faction: str
    copies: Mapping[str, int]
    created_at: datetime


class DeckStore(Protocol):
    """What the API needs from a store of decks: what each store does."""

    def create_deck(
        self,
        owner: UUID,
        name: str,
        faction: str,
        copies: Mapping[str, int],
        now: datetime,
    ) -> StoredDeck | None:
        """Keep a new deck of an owner's and return it.

        Return None, and keep nothing, if the owner already has
        ``MAX_DECKS`` decks.
        """
        ...

    def list_decks(self, owner: UUID) -> tuple[StoredDeck, ...]:
        """Return an owner's decks, the oldest first.

        Two decks made at the same time come in the order of their ids.
        """
        ...

    def get_deck(self, owner: UUID, deck_id: UUID) -> StoredDeck | None:
        """Return a deck of an owner's, or None if they have no such deck."""
        ...

    def replace_deck(
        self,
        owner: UUID,
        deck_id: UUID,
        name: str,
        faction: str,
        copies: Mapping[str, int],
    ) -> StoredDeck | None:
        """Give a deck of an owner's a new name, faction and copies.

        Return the deck as it is now kept, or None if the owner has no such
        deck.
        """
        ...

    def delete_deck(self, owner: UUID, deck_id: UUID) -> bool:
        """Delete a deck of an owner's; return whether there was one."""
        ...


class MemoryDeckStore:
    """The decks players built, in the server's memory.

    As in ``MemoryMatchStore``, a lock lets one thread in at a time. Its decks
    are lost when the server stops, as its accounts are.
    """

    def __init__(self) -> None:
        """Make an empty store."""
        # Each deck under its id.
        self._decks: dict[UUID, StoredDeck] = {}
        self._lock = threading.Lock()

    def create_deck(
        self,
        owner: UUID,
        name: str,
        faction: str,
        copies: Mapping[str, int],
        now: datetime,
    ) -> StoredDeck | None:
        """Keep a new deck of an owner's, unless they have ``MAX_DECKS``."""
        deck = StoredDeck(
            id=uuid.uuid4(),
            owner=owner,
            name=name,
            faction=faction,
            copies=dict(copies),
            created_at=now,
        )
        with self._lock:
            owned = sum(1 for kept in self._decks.values() if kept.owner == owner)
            if owned >= MAX_DECKS:
                return None
            self._decks[deck.id] = deck
        return deck

    def list_decks(self, owner: UUID) -> tuple[StoredDeck, ...]:
        """Return an owner's decks, the oldest first."""
        with self._lock:
            owned = [deck for deck in self._decks.values() if deck.owner == owner]
        return tuple(sorted(owned, key=lambda deck: (deck.created_at, deck.id)))

    def get_deck(self, owner: UUID, deck_id: UUID) -> StoredDeck | None:
        """Return a deck of an owner's, or None if they have no such deck."""
        with self._lock:
            deck = self._decks.get(deck_id)
        return deck if deck is not None and deck.owner == owner else None

    def replace_deck(
        self,
        owner: UUID,
        deck_id: UUID,
        name: str,
        faction: str,
        copies: Mapping[str, int],
    ) -> StoredDeck | None:
        """Give a deck of an owner's a new name, faction and copies."""
        with self._lock:
            old = self._decks.get(deck_id)
            if old is None or old.owner != owner:
                return None
            new = replace(old, name=name, faction=faction, copies=dict(copies))
            self._decks[deck_id] = new
            return new

    def delete_deck(self, owner: UUID, deck_id: UUID) -> bool:
        """Delete a deck of an owner's; return whether there was one."""
        with self._lock:
            deck = self._decks.get(deck_id)
            if deck is None or deck.owner != owner:
                return False
            del self._decks[deck_id]
            return True

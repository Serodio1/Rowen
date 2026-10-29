"""Decks: the cards a player brings to a match."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from rowen.engine.cards import Card, SpecialCard, UnitCard

# Deck limits (rules, section 12).
MIN_UNITS = 22
MAX_SPECIALS = 10

# The most copies of one card a deck a player builds may have (rules, section
# 12): a Legend only one, and a Bond or Muster unit as many as its faction's
# own deck has, if that is more, so the player can still have the whole group.
MAX_COPIES = 3


class Passive(StrEnum):
    """A leader's passive: a rule of its own that works by itself, with no
    action, at the end of each round that doesn't end the match (rules,
    section 12). ``rowen.engine.passives`` carries each one out.
    """

    # After winning a round, draw a card (not on a tie).
    DRAW_ON_ROUND_WIN = "draw_on_round_win"
    # After each round, one random unit stays on the board.
    KEEP_A_UNIT = "keep_a_unit"


@dataclass(frozen=True, kw_only=True)
class Leader:
    """A deck's leader: who leads the faction, and the passive they bring
    (rules, section 12). Each faction has one, and a deck a player builds has
    its faction's.

    Attributes:
        id: Unique identifier, lowercase with hyphens (``"humans-leader"``);
            the page finds the leader's art by it.
        name: The name shown to the player (``"The Commander"``).
        passive: The rule the leader brings.
    """

    id: str
    name: str
    passive: Passive


@dataclass(frozen=True, kw_only=True)
class Deck:
    """A deck of cards, before it is shuffled for a match.

    Each faction has a deck of its own, named after it (rules, section 12),
    and a player may build others from its cards (``build_deck``). Creating a
    deck checks its limits, so an invalid deck can never exist in the program.

    Attributes:
        id: Unique identifier, lowercase with hyphens (``"humans"``).
        name: The name shown to the player (``"Humans"``).
        cards: Every card in the deck, one entry per copy.
        leader: The deck's leader, if it has one. A deck a player builds has
            its faction's.
    """

    id: str
    name: str
    cards: tuple[Card, ...]
    leader: Leader | None = None

    def __post_init__(self) -> None:
        units = sum(isinstance(card, UnitCard) for card in self.cards)
        specials = len(self.cards) - units
        if units < MIN_UNITS:
            raise ValueError(
                f"{self.id}: a deck needs at least {MIN_UNITS} units, got {units}"
            )
        if specials > MAX_SPECIALS:
            raise ValueError(
                f"{self.id}: a deck can't have more than {MAX_SPECIALS} "
                f"special cards, got {specials}"
            )

        # Copies of a card share its id, so one id must always mean one card.
        cards_by_id: dict[str, Card] = {}
        for card in self.cards:
            if card.id in cards_by_id and cards_by_id[card.id] != card:
                raise ValueError(f"{self.id}: two different cards use the id {card.id}")
            cards_by_id[card.id] = card


def max_copies(card: Card, faction: Deck) -> int:
    """Return the most copies of a card a deck built from a faction may have.

    Args:
        card: One of the cards of ``choices(faction, ...)``.
        faction: The faction's own deck, whose cards a player builds from.
    """
    if isinstance(card, UnitCard):
        if card.legend:
            return 1
        if card.group is not None:
            return max(MAX_COPIES, faction.cards.count(card))
    return MAX_COPIES


def choices(faction: Deck, specials: Mapping[str, SpecialCard]) -> tuple[Card, ...]:
    """Return the cards a deck built from a faction may hold, one of each.

    They are the faction's units, in the order of its own deck, and then every
    special card, which is neutral.

    Args:
        faction: The faction's own deck.
        specials: Every special card, by id.
    """
    units = {card.id: card for card in faction.cards if isinstance(card, UnitCard)}
    return (*units.values(), *specials.values())


def build_deck(
    *,
    id: str,
    name: str,
    faction: Deck,
    specials: Mapping[str, SpecialCard],
    copies: Mapping[str, int],
) -> Deck:
    """Build the deck a player chose from a faction's cards.

    The cards come in the order of ``choices``, whatever the order of
    ``copies``: the same choice is always the same deck, and so is shuffled
    the same way by the same seed (ADR 0003).

    Args:
        id: The deck's id.
        name: The deck's name, as the player gave it.
        faction: The faction's own deck, whose cards the player builds from.
        specials: Every special card, by id.
        copies: How many copies of each card the player chose, by the card's
            id. A card that isn't chosen is left out.

    Raises:
        ValueError: If a card isn't one of the faction's choices, if it has
            fewer than 1 copy or more than ``max_copies``, or if the deck
            breaks the deck limits. The message says which.
    """
    available = choices(faction, specials)
    known = {card.id for card in available}
    unknown = sorted(copies.keys() - known)
    if unknown:
        raise ValueError(f"{id}: {faction.name} has no card {unknown[0]}")

    cards: list[Card] = []
    for card in available:
        if card.id not in copies:
            continue
        count = copies[card.id]
        most = max_copies(card, faction)
        # bool is a kind of int in Python, so True would count as 1 copy.
        if type(count) is not int or not 1 <= count <= most:
            raise ValueError(
                f"{id}: {card.id} can have 1 to {most} copies, got {count}"
            )
        cards += [card] * count
    return Deck(id=id, name=name, cards=tuple(cards), leader=faction.leader)

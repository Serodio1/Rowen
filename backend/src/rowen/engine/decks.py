"""Decks: the cards a player brings to a match."""

from dataclasses import dataclass

from rowen.engine.cards import Card, UnitCard

# Deck limits (rules, section 12).
MIN_UNITS = 22
MAX_SPECIALS = 10


@dataclass(frozen=True, kw_only=True)
class Deck:
    """A deck of cards, before it is shuffled for a match.

    In the MVP each faction has one preconstructed deck (rules, section 12), so
    a deck is named after its faction. Creating a deck checks its limits, so an
    invalid deck can never exist in the program.

    Attributes:
        id: Unique identifier, lowercase with hyphens (``"humans"``).
        name: The name shown to the player (``"Humans"``).
        cards: Every card in the deck, one entry per copy.
    """

    id: str
    name: str
    cards: tuple[Card, ...]

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

"""The flow of a match, from its setup onwards."""

from rowen.engine.cards import Card
from rowen.engine.decks import Deck
from rowen.engine.rng import Rng
from rowen.engine.state import GameState, PlayerState

# Cards each player draws at the start of the match (rules, section 3).
HAND_SIZE = 10


def start_match(decks: tuple[Deck, Deck], seed: int) -> GameState:
    """Set up a match: shuffle both decks, flip a coin and deal 10 cards each.

    This is the rules, section 3, steps 1 to 3; the redraw (step 4) is not
    part of it yet. The same decks and seed always give the same match.

    Args:
        decks: The deck of each player: player 0 plays ``decks[0]``.
        seed: Where all the randomness of the match comes from.
    """
    rng = Rng(seed=seed)
    cards_0, rng = rng.shuffled(decks[0].cards)
    cards_1, rng = rng.shuffled(decks[1].cards)
    first_player, rng = rng.coin_flip()
    return GameState(
        players=(_deal(cards_0), _deal(cards_1)),
        current=first_player,
        rng=rng,
    )


def _deal(cards: tuple[Card, ...]) -> PlayerState:
    """Return a player who has drawn their hand from these shuffled cards."""
    return PlayerState(hand=cards[:HAND_SIZE], deck=cards[HAND_SIZE:])

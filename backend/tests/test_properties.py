"""Property-based tests: invariants that hold in every match.

The other tests check the cases we thought of. Here Hypothesis picks the decks,
the seed and, at every turn, one of the legal actions, and looks for a match
that breaks one of the invariants below. When it finds one, it shrinks it to
the simplest match that still fails and shows that one.

Hypothesis plays 100 matches each time the tests run, different ones every
time, and keeps any that failed in the .hypothesis folder, to try them first
the next time.
"""

from collections import Counter

from hypothesis import given, settings
from hypothesis import strategies as st

from rowen.data import load_deck
from rowen.engine.cards import Card
from rowen.engine.decks import Deck
from rowen.engine.events import CardRedrawn, CardsDrawn, Event
from rowen.engine.game import apply, legal_actions, match_over, start_match
from rowen.engine.scoring import player_total
from rowen.engine.state import GameState
from rowen.engine.view import player_events, player_view

DECKS = (load_deck("humans"), load_deck("robots"))

# A match ends long before this: almost every action uses up a card from a
# hand or a deck, and there are 66 of them.
MAX_ACTIONS = 1000

MAX_ROUNDS = 3


# A whole match can take longer than Hypothesis's default deadline of 200 ms
# on a slow machine, which would fail the test for no real reason.
@settings(deadline=None)
@given(
    first=st.sampled_from(DECKS),
    second=st.sampled_from(DECKS),
    seed=st.integers(),
    data=st.data(),
)
def test_invariants_hold_after_every_action(
    first: Deck, second: Deck, seed: int, data: st.DataObject
) -> None:
    decks = (first, second)
    state = start_match(decks, seed=seed)
    check_state(state, decks)

    for _ in range(MAX_ACTIONS):
        actions = legal_actions(state)
        # The match never gets stuck: until it is over, there is something
        # to do, and every action offered can be carried out.
        assert bool(actions) != match_over(state)
        if not actions:
            break
        for action in actions:
            apply(state, action)

        new_state, events = apply(state, data.draw(st.sampled_from(actions)))
        check_state(new_state, decks)
        check_progress(state, new_state)
        check_events(events)
        state = new_state

    # Every match ends.
    assert match_over(state)


def check_state(state: GameState, decks: tuple[Deck, Deck]) -> None:
    """Check the invariants of one state."""
    check_cards(state, decks)
    check_scores(state)
    check_views(state)
    check_legends(state)


def check_cards(state: GameState, decks: tuple[Deck, Deck]) -> None:
    """No card is ever lost or duplicated.

    Every card of both decks is in a hand, a deck, a discard pile, the weather
    area or on the board. A Spy changes sides, so both players' cards are
    counted together.
    """
    cards: Counter[Card] = Counter()
    for player in state.players:
        cards.update(player.hand + player.deck + player.discard + player.weather)
        for row in player.rows.values():
            cards.update(row.units + row.scarecrows)
            if row.horn is not None:
                cards[row.horn] += 1
    assert cards == Counter(decks[0].cards + decks[1].cards)


def check_scores(state: GameState) -> None:
    """Each total is the sum of the strengths on that side of the board."""
    sides = player_view(state, 0).players
    for index, side in enumerate(sides):
        strengths = [unit.strength for row in side.rows.values() for unit in row.units]
        assert all(strength >= 0 for strength in strengths)
        assert sum(row.score for row in side.rows.values()) == side.total
        assert sum(strengths) == side.total == player_total(state, index)


def check_views(state: GameState) -> None:
    """A view shows a player their own hand, and only counts of the rest."""
    for player in (0, 1):
        view = player_view(state, player)
        assert view.hand == state.players[player].hand
        for index, side in enumerate(view.players):
            assert side.hand_size == len(state.players[index].hand)
            assert side.deck_size == len(state.players[index].deck)
        assert "Rng" not in repr(view)


def check_legends(state: GameState) -> None:
    """A Legend on the board always has its base strength."""
    for side in player_view(state, 0).players:
        for row in side.rows.values():
            for unit in row.units:
                if unit.card.legend:
                    assert unit.strength == unit.card.strength


def check_progress(before: GameState, after: GameState) -> None:
    """Lives never go up, and rounds only go forward, up to the third."""
    for old, new in zip(before.players, after.players, strict=True):
        assert 0 <= new.lives <= old.lives
    assert before.round <= after.round <= MAX_ROUNDS


def check_events(events: tuple[Event, ...]) -> None:
    """A player only sees the cards they drew or swapped themselves."""
    for player in (0, 1):
        seen = player_events(events, player)
        assert len(seen) == len(events)
        for event in seen:
            if isinstance(event, CardsDrawn | CardRedrawn):
                assert event.player == player

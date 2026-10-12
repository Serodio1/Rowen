"""Tests for the engine's public face: all a client needs to play a match.

These tests import nothing else from the engine, as a client may not. So if
they can play a match to the end, the public module offers enough.
"""

import pytest

from rowen.data import deck_ids, load_deck
from rowen.engine.public import (
    IllegalActionError,
    MatchEnded,
    Pass,
    apply,
    player_events,
    player_view,
    start_match,
)

DECKS = tuple(load_deck(deck_id) for deck_id in deck_ids())

# Far more actions than a match takes: a match still going after them is stuck.
MAX_ACTIONS = 1000


@pytest.mark.parametrize("seed", range(4))
def test_a_match_can_be_played_to_the_end_through_the_public_module(
    seed: int,
) -> None:
    # Each player plays the first legal action in their own view.
    state = start_match((DECKS[0], DECKS[1]), seed=seed)
    views = (player_view(state, 0), player_view(state, 1))
    actions = 0
    while not views[0].match_over:
        # The legal actions come in the view of the player whose turn it is.
        current = views[0].current
        assert views[current].legal_actions
        assert not views[1 - current].legal_actions

        state, events = apply(state, views[current].legal_actions[0])
        views = (player_view(state, 0), player_view(state, 1))
        actions += 1
        assert actions < MAX_ACTIONS, "the match never ends"

    assert views[1].match_over
    assert views[1].winner == views[0].winner
    # Both players see the match end, and who won.
    for player in (0, 1):
        assert player_events(events, player)[-1] == MatchEnded(winner=views[0].winner)


def test_a_client_can_catch_an_illegal_action() -> None:
    state = start_match((DECKS[0], DECKS[1]), seed=0)

    # Nobody can pass before round 1, during the redraw.
    with pytest.raises(IllegalActionError):
        apply(state, Pass())

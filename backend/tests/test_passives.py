"""Tests for the leaders and the passives they bring (rules, section 12)."""

from collections import Counter
from dataclasses import replace

import pytest
from cards import KNIGHT, SCOUT, SNIPER

from rowen.data import load_deck, load_specials
from rowen.engine.actions import Pass
from rowen.engine.cards import Ability, Card, Row, UnitCard
from rowen.engine.decks import Leader, Passive, build_deck
from rowen.engine.events import CardsDrawn, Event, MatchEnded, RoundEnded, UnitKept
from rowen.engine.game import apply, start_match
from rowen.engine.parsing import parse_deck
from rowen.engine.rng import Rng
from rowen.engine.state import GameState, PlayerState, RowState
from rowen.engine.texts import PASSIVE_TEXTS
from rowen.engine.view import OpponentDrew, player_events, player_view

DRAW, KEEP = Passive.DRAW_ON_ROUND_WIN, Passive.KEEP_A_UNIT

HERO = UnitCard(id="hero", name="Hero", rows=(Row.MELEE,), strength=10, legend=True)
INFILTRATOR = UnitCard(
    id="infiltrator",
    name="Infiltrator",
    rows=(Row.MELEE,),
    strength=4,
    ability=Ability.SPY,
)


def player(
    *board: UnitCard,
    passive: Passive | None = None,
    deck: tuple[Card, ...] = (),
    lives: int = 2,
) -> PlayerState:
    """Return a player with these units on the board, each in its first row,
    and a leader with the passive, if one is given.

    They hold a Knight, so they don't pass by themselves when the next round
    starts.
    """
    rows = {
        row: RowState(units=tuple(unit for unit in board if unit.rows[0] == row))
        for row in Row
    }
    return PlayerState(
        deck=deck,
        hand=(KNIGHT,),
        rows=rows,
        lives=lives,
        leader=None if passive is None else Leader(id="l", name="L", passive=passive),
    )


def end_round(
    first: PlayerState, second: PlayerState, *, seed: int = 7
) -> tuple[GameState, tuple[Event, ...]]:
    """Have player 0 pass after player 1 has, which ends round 1."""
    state = GameState(
        players=(first, replace(second, passed=True)),
        current=0,
        round_starter=0,
        rng=Rng(seed=seed),
    )
    return apply(state, Pass())


def after_round(events: tuple[Event, ...]) -> tuple[Event, ...]:
    """Return the events after the end of the round."""
    index = next(i for i, event in enumerate(events) if isinstance(event, RoundEnded))
    return events[index + 1 :]


def cards_of(player: PlayerState) -> Counter[str]:
    """Return every card a player has, wherever it is, by id."""
    rows = [unit.id for row in player.rows.values() for unit in row.units]
    return Counter(
        [*rows, *(card.id for card in (*player.hand, *player.deck, *player.discard))]
    )


# Every faction has a leader, and every passive a text

HUMANS_LEADER = Leader(id="humans-leader", name="The Commander", passive=DRAW)
ROBOTS_LEADER = Leader(id="robots-leader", name="The Overseer", passive=KEEP)


def test_each_faction_has_its_leader() -> None:
    assert load_deck("humans").leader == HUMANS_LEADER
    assert load_deck("robots").leader == ROBOTS_LEADER


def test_every_passive_has_a_text() -> None:
    assert set(PASSIVE_TEXTS) == set(Passive)


# A deck's data, as in its JSON file, without a leader.
SCOUTS = {
    "id": "scouts",
    "name": "Scouts",
    "units": [
        {"id": "scout", "name": "Scout", "rows": ["melee"], "strength": 3, "copies": 22}
    ],
    "specials": {},
}


def test_a_deck_without_a_leader_has_none() -> None:
    assert parse_deck(SCOUTS, load_specials()).leader is None


@pytest.mark.parametrize(
    ("leader", "error"),
    [
        pytest.param({"id": "x", "name": "X", "passive": "fly"}, "fly", id="passive"),
        pytest.param({"id": "x", "name": "X"}, "missing fields: passive", id="field"),
    ],
)
def test_a_leader_with_bad_data_is_an_error(leader: object, error: str) -> None:
    with pytest.raises(ValueError, match=f"leader: .*{error}"):
        parse_deck({**SCOUTS, "leader": leader}, load_specials())


def test_a_built_deck_has_its_factions_leader() -> None:
    robots = load_deck("robots")
    copies = Counter(card.id for card in robots.cards)
    deck = build_deck(
        id="mine",
        name="Mine",
        faction=robots,
        specials=load_specials(),
        copies=copies,
    )
    assert deck.leader == ROBOTS_LEADER


def test_each_player_starts_with_their_decks_leader() -> None:
    state = start_match((load_deck("humans"), load_deck("robots")), seed=1)

    leaders = [HUMANS_LEADER, ROBOTS_LEADER]
    assert [player.leader for player in state.players] == leaders
    assert [side.leader for side in player_view(state, 0).players] == leaders


# Humans: draw 2 cards after winning a round


def test_the_winner_draws_the_first_2_cards_of_their_deck() -> None:
    state, events = end_round(
        player(SNIPER, passive=DRAW, deck=(SCOUT, KNIGHT, SNIPER)), player(KNIGHT)
    )

    humans = state.players[0]
    assert humans.hand == (KNIGHT, SCOUT, KNIGHT)
    assert humans.deck == (SNIPER,)
    assert after_round(events) == (CardsDrawn(player=0, cards=("scout", "knight")),)


def test_a_deck_with_1_card_left_gives_that_one() -> None:
    state, events = end_round(
        player(SNIPER, passive=DRAW, deck=(SCOUT,)), player(KNIGHT)
    )

    assert state.players[0].hand == (KNIGHT, SCOUT)
    assert state.players[0].deck == ()
    assert after_round(events) == (CardsDrawn(player=0, cards=("scout",)),)


@pytest.mark.parametrize(
    ("board", "deck"),
    [
        pytest.param((SCOUT,), (SCOUT,), id="lost"),
        pytest.param((KNIGHT,), (SCOUT,), id="tie"),
        pytest.param((SNIPER,), (), id="empty deck"),
    ],
)
def test_no_card_is_drawn_without_a_win_or_a_card_to_draw(
    board: tuple[UnitCard, ...], deck: tuple[Card, ...]
) -> None:
    state, events = end_round(player(*board, passive=DRAW, deck=deck), player(KNIGHT))

    assert state.players[0].hand == (KNIGHT,)
    assert not any(isinstance(event, CardsDrawn) for event in events)


def test_no_card_is_drawn_once_the_match_is_over() -> None:
    state, events = end_round(
        player(SNIPER, passive=DRAW, deck=(SCOUT,)), player(KNIGHT, lives=1)
    )

    assert isinstance(events[-1], MatchEnded)
    assert state.players[0].hand == (KNIGHT,)


def test_the_opponent_sees_only_how_many_cards_were_drawn() -> None:
    _, events = end_round(
        player(SNIPER, passive=DRAW, deck=(SCOUT, KNIGHT)), player(KNIGHT)
    )

    assert player_events(after_round(events), 1) == (OpponentDrew(player=0, count=2),)


# Robots: one random unit stays on the board


def test_one_unit_stays_in_its_row_and_the_rest_go_to_the_discard_pile() -> None:
    before = player(KNIGHT, SNIPER, passive=KEEP)
    state, events = end_round(before, player(KNIGHT))

    robots = state.players[0]
    kept = [(row, unit) for row in Row for unit in robots.rows[row].units]
    assert len(kept) == 1
    ((row, unit),) = kept
    assert unit in (KNIGHT, SNIPER)
    assert row == unit.rows[0]
    assert robots.discard == tuple(card for card in (KNIGHT, SNIPER) if card != unit)
    assert after_round(events) == (UnitKept(player=0, card=unit.id, row=row),)
    # No card is lost or made: the unit isn't in the discard pile too.
    assert cards_of(robots) == cards_of(before)


def test_the_unit_kept_is_chosen_by_the_seed() -> None:
    board = (KNIGHT, SNIPER, SCOUT)
    kept = {
        after_round(
            end_round(player(*board, passive=KEEP), player(KNIGHT), seed=seed)[1]
        )
        for seed in range(20)
    }
    # The same seed always keeps the same unit, and other seeds keep others.
    assert end_round(player(*board, passive=KEEP), player(KNIGHT), seed=3) == (
        end_round(player(*board, passive=KEEP), player(KNIGHT), seed=3)
    )
    assert len(kept) == 3


def test_keeping_a_unit_uses_the_matchs_randomness_once() -> None:
    # So the next random choice of the match isn't the same one again.
    state, _ = end_round(player(KNIGHT, passive=KEEP), player(SNIPER))
    without, _ = end_round(player(KNIGHT), player(SNIPER))

    assert state.rng.uses == without.rng.uses + 1


@pytest.mark.parametrize(
    "board",
    [
        pytest.param((), id="no unit"),
        pytest.param((HERO,), id="a legend"),
        pytest.param((INFILTRATOR,), id="the opponent's spy"),
    ],
)
def test_no_unit_stays_without_one_that_may(board: tuple[UnitCard, ...]) -> None:
    state, events = end_round(player(*board, passive=KEEP), player(SNIPER, SNIPER))

    assert all(not row.units for row in state.players[0].rows.values())
    assert not any(isinstance(event, UnitKept) for event in events)


def test_a_unit_stays_after_a_tie_too() -> None:
    state, events = end_round(player(KNIGHT, passive=KEEP), player(KNIGHT))

    assert RoundEnded(scores=(5, 5), winner=None) in events
    assert state.players[0].rows[Row.MELEE].units == (KNIGHT,)


def test_no_unit_stays_once_the_match_is_over() -> None:
    # Player 0 loses the round on their last life.
    _, events = end_round(player(KNIGHT, passive=KEEP, lives=1), player(SNIPER), seed=1)

    assert not any(isinstance(event, UnitKept) for event in events)


def test_the_unit_kept_counts_in_the_next_round() -> None:
    state, _ = end_round(player(SNIPER, passive=KEEP), player(KNIGHT))

    assert player_view(state, 0).players[0].total == 6


def test_a_player_without_a_leader_keeps_nothing_and_draws_nothing() -> None:
    state, events = end_round(player(SNIPER, deck=(SCOUT,)), player(KNIGHT))

    assert state.players[0].hand == (KNIGHT,)
    assert all(not row.units for row in state.players[0].rows.values())
    assert after_round(events) == ()

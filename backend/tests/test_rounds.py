"""Tests for the end of a round and the end of the match."""

from collections import Counter
from dataclasses import replace

import pytest

from rowen.data import load_deck
from rowen.engine.actions import Action, EndRedraw, Pass, PlayUnit
from rowen.engine.cards import Ability, Card, Row, SpecialCard, SpecialKind, UnitCard
from rowen.engine.events import (
    Event,
    MatchEnded,
    PlayerPassed,
    RoundEnded,
    UnitPlayed,
)
from rowen.engine.game import (
    IllegalActionError,
    apply,
    legal_actions,
    match_over,
    match_winner,
    start_match,
)
from rowen.engine.rng import Rng
from rowen.engine.state import (
    STARTING_LIVES,
    GameState,
    PlayerState,
    RowState,
    empty_rows,
)

SNIPER = UnitCard(id="sniper", name="Sniper", rows=(Row.RANGED,), strength=6)
KNIGHT = UnitCard(id="knight", name="Knight", rows=(Row.MELEE,), strength=5)
SCOUT = UnitCard(id="scout", name="Scout", rows=(Row.MELEE,), strength=3)
INFILTRATOR = UnitCard(
    id="infiltrator",
    name="Infiltrator",
    rows=(Row.MELEE,),
    strength=4,
    ability=Ability.SPY,
)
WAR_HORN = SpecialCard(id="war-horn", name="War Horn", kind=SpecialKind.WAR_HORN)
HOARFROST = SpecialCard(id="hoarfrost", name="Hoarfrost", kind=SpecialKind.HOARFROST)


def player(
    *board: UnitCard,
    hand: tuple[Card, ...] = (KNIGHT,),
    lives: int = STARTING_LIVES,
) -> PlayerState:
    """Return a player with these units on the board, each in its first row.

    By default they hold a Knight, so they don't pass by themselves when the
    next round starts.
    """
    rows = {
        row: RowState(units=tuple(unit for unit in board if unit.rows[0] == row))
        for row in Row
    }
    return PlayerState(deck=(), hand=hand, rows=rows, lives=lives)


def make_state(
    first: PlayerState,
    second: PlayerState,
    *,
    current: int = 0,
    round_starter: int = 0,
) -> GameState:
    """Build a match in round 1 with these two players."""
    return GameState(
        players=(first, second),
        current=current,
        round_starter=round_starter,
        rng=Rng(seed=7),
    )


def end_round(
    first: PlayerState, second: PlayerState, *, round_starter: int = 0
) -> tuple[GameState, tuple[Event, ...]]:
    """Have player 0 pass after player 1 has, which ends the round."""
    state = make_state(first, replace(second, passed=True), round_starter=round_starter)
    return apply(state, Pass())


def lives(state: GameState) -> tuple[int, int]:
    return (state.players[0].lives, state.players[1].lives)


# The result of the round


@pytest.mark.parametrize(
    ("board_0", "board_1", "scores", "winner", "lives_left"),
    [
        pytest.param((SNIPER,), (KNIGHT,), (6, 5), 0, (2, 1), id="player 0 wins"),
        pytest.param((KNIGHT,), (SNIPER,), (5, 6), 1, (1, 2), id="player 1 wins"),
        pytest.param((KNIGHT,), (KNIGHT,), (5, 5), None, (1, 1), id="tie"),
    ],
)
def test_loser_of_the_round_loses_a_life_or_both_on_a_tie(
    board_0: tuple[UnitCard, ...],
    board_1: tuple[UnitCard, ...],
    scores: tuple[int, int],
    winner: int | None,
    lives_left: tuple[int, int],
) -> None:
    state, events = end_round(player(*board_0), player(*board_1))

    assert events == (PlayerPassed(player=0), RoundEnded(scores=scores, winner=winner))
    assert lives(state) == lives_left


def test_playing_the_last_card_can_end_the_round() -> None:
    # Player 0 has passed. Player 1 plays their last card, so they pass too.
    first = replace(player(), passed=True)
    state = make_state(first, player(hand=(SNIPER,)), current=1)

    state, events = apply(state, PlayUnit(card="sniper", row=Row.RANGED))

    assert events[:3] == (
        UnitPlayed(player=1, card="sniper", row=Row.RANGED),
        PlayerPassed(player=1),
        RoundEnded(scores=(0, 6), winner=1),
    )
    assert lives(state) == (1, 2)


# Clearing the board


def test_cards_on_the_board_go_to_the_discard_pile_of_their_side() -> None:
    # The Infiltrator is a Spy that player 1 played on player 0's side, so it
    # goes to player 0's discard pile (rules, D4).
    first = PlayerState(
        deck=(),
        hand=(KNIGHT,),
        rows={
            Row.MELEE: RowState(units=(KNIGHT, INFILTRATOR)),
            Row.RANGED: RowState(units=(SNIPER,), horn=WAR_HORN),
            Row.SIEGE: RowState(),
        },
        discard=(SCOUT,),
    )

    state, _ = end_round(first, player(SCOUT))

    assert state.players[0].rows == empty_rows()
    assert state.players[0].discard == (SCOUT, KNIGHT, INFILTRATOR, SNIPER, WAR_HORN)
    assert state.players[1].rows == empty_rows()
    assert state.players[1].discard == (SCOUT,)


def test_weather_goes_to_the_discard_pile_of_the_player_who_played_it() -> None:
    second = replace(player(), weather=(HOARFROST,))

    state, _ = end_round(player(), second)

    assert state.players[1].weather == ()
    assert state.players[1].discard == (HOARFROST,)
    assert state.players[0].discard == ()


def test_hands_and_decks_carry_over() -> None:
    first = replace(player(SNIPER, hand=(KNIGHT, SCOUT)), deck=(SNIPER,))

    state, _ = end_round(first, player())

    assert state.players[0].hand == (KNIGHT, SCOUT)
    assert state.players[0].deck == (SNIPER,)


# The next round


def test_next_round_starts_with_neither_player_passed() -> None:
    state, _ = end_round(player(SNIPER), player(KNIGHT))

    assert state.round == 2
    assert not state.players[0].passed
    assert not state.players[1].passed


def test_winner_of_the_round_goes_first() -> None:
    # Player 0 went first in this round, but player 1 won it.
    state, _ = end_round(player(KNIGHT), player(SNIPER), round_starter=0)

    assert state.current == state.round_starter == 1


@pytest.mark.parametrize("round_starter", [0, 1])
def test_after_a_tie_the_same_player_goes_first(round_starter: int) -> None:
    state, _ = end_round(player(KNIGHT), player(KNIGHT), round_starter=round_starter)

    assert state.current == state.round_starter == round_starter


def test_player_without_cards_passes_when_the_next_round_starts() -> None:
    # Player 1 wins the round, but has no cards left: player 0 goes first.
    state, events = end_round(player(KNIGHT), player(SNIPER, hand=()))

    assert events == (
        PlayerPassed(player=0),
        RoundEnded(scores=(5, 6), winner=1),
        PlayerPassed(player=1),
    )
    assert state.players[1].passed
    assert state.round_starter == 1
    assert state.current == 0


def test_round_with_no_cards_on_either_side_ends_straight_away() -> None:
    # Player 1 has no cards left. Player 0 plays their last one, which ends
    # round 1. Round 2 starts with no cards on either side, so both players
    # pass and it is a 0-0 tie.
    second = replace(player(hand=()), passed=True)
    state = make_state(player(hand=(SNIPER,)), second)

    state, events = apply(state, PlayUnit(card="sniper", row=Row.RANGED))

    assert events == (
        UnitPlayed(player=0, card="sniper", row=Row.RANGED),
        PlayerPassed(player=0),
        RoundEnded(scores=(6, 0), winner=0),
        PlayerPassed(player=0),
        PlayerPassed(player=1),
        RoundEnded(scores=(0, 0), winner=None),
        MatchEnded(winner=0),
    )
    assert lives(state) == (1, 0)


# The end of the match


@pytest.mark.parametrize(
    ("board_0", "board_1", "lives_before", "winner"),
    [
        pytest.param((SNIPER,), (KNIGHT,), (1, 1), 0, id="player 0 wins"),
        pytest.param((KNIGHT,), (SNIPER,), (1, 1), 1, id="player 1 wins"),
        pytest.param((KNIGHT,), (KNIGHT,), (1, 1), None, id="draw"),
        # The round is a tie, but only player 1 loses their last life.
        pytest.param((KNIGHT,), (KNIGHT,), (2, 1), 0, id="tie with lives to spare"),
    ],
)
def test_match_ends_when_a_player_has_no_lives_left(
    board_0: tuple[UnitCard, ...],
    board_1: tuple[UnitCard, ...],
    lives_before: tuple[int, int],
    winner: int | None,
) -> None:
    state, events = end_round(
        player(*board_0, lives=lives_before[0]),
        player(*board_1, lives=lives_before[1]),
    )

    assert match_over(state)
    assert match_winner(state) == winner
    assert events[-1] == MatchEnded(winner=winner)


def test_match_goes_on_while_both_players_have_lives_left() -> None:
    state, events = end_round(player(SNIPER), player(KNIGHT))

    assert not match_over(state)
    assert not any(isinstance(event, MatchEnded) for event in events)
    with pytest.raises(ValueError, match="isn't over"):
        match_winner(state)


def test_board_stays_as_it_is_when_the_match_ends() -> None:
    state, _ = end_round(player(SNIPER, lives=1), player(KNIGHT, lives=1))

    assert state.round == 1
    assert state.players[0].rows == player(SNIPER).rows
    assert state.players[0].discard == ()


def test_no_action_is_legal_when_the_match_is_over() -> None:
    state, _ = end_round(player(SNIPER, lives=1), player(KNIGHT, lives=1))

    assert legal_actions(state) == ()
    with pytest.raises(IllegalActionError):
        apply(state, Pass())


# A whole match


def choose(actions: tuple[Action, ...], turn: int) -> Action:
    """Pick one of the legal actions, a different one each turn.

    It redraws or ends the redraw as it comes. In a round, it plays a unit,
    but passes every fourth turn, to spread the cards over the rounds, and
    when there is no unit left to play.
    """
    if EndRedraw() in actions:
        return actions[turn % len(actions)]
    plays = [action for action in actions if isinstance(action, PlayUnit)]
    return plays[turn % len(plays)] if plays and turn % 4 != 3 else Pass()


@pytest.mark.parametrize("seed", range(5))
def test_a_match_runs_from_the_first_turn_to_the_end(seed: int) -> None:
    # The "done when" of issues #11 to #13, with the real decks: each turn
    # tries every legal action, then takes one of them.
    decks = (load_deck("humans"), load_deck("robots"))
    state = start_match(decks, seed=seed)
    cards_at_start = [Counter(player.hand + player.deck) for player in state.players]
    events: list[Event] = []

    for turn in range(100):
        actions = legal_actions(state)
        if not actions:
            break
        for action in actions:
            apply(state, action)
        state, new_events = apply(state, choose(actions, turn))
        events.extend(new_events)

    assert match_over(state)
    assert events[-1] == MatchEnded(winner=match_winner(state))
    rounds = [event for event in events if isinstance(event, RoundEnded)]
    assert len(rounds) == state.round <= 3
    # Every card is still in the hand, the deck, on the board or in the
    # discard pile.
    for player, at_start in zip(state.players, cards_at_start, strict=True):
        on_board = [unit for row in player.rows.values() for unit in row.units]
        cards = Counter(player.hand + player.deck + player.discard)
        assert cards + Counter(on_board) == at_start

"""Tests for the baseline AI: what it sees, and the moves it chooses."""

import random

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from rowen.ai.baseline import PASS_LEAD, UNKNOWN, choose_action, imagine
from rowen.data import deck_ids, load_deck
from rowen.engine.actions import (
    Action,
    EndRedraw,
    Pass,
    PlayHorn,
    PlaySpecial,
    PlayUnit,
    Revive,
)
from rowen.engine.cards import Ability, Card, Row, SpecialCard, SpecialKind, UnitCard
from rowen.engine.decks import Deck
from rowen.engine.game import (
    apply,
    legal_actions,
    match_over,
    match_winner,
    start_match,
)
from rowen.engine.rng import Rng
from rowen.engine.state import GameState, PlayerState, RowState
from rowen.engine.view import player_view

SCOUT = UnitCard(id="scout", name="Scout", rows=(Row.MELEE,), strength=3)
KNIGHT = UnitCard(id="knight", name="Knight", rows=(Row.MELEE,), strength=5)
SNIPER = UnitCard(id="sniper", name="Sniper", rows=(Row.RANGED,), strength=6)
CATAPULT = UnitCard(id="catapult", name="Catapult", rows=(Row.SIEGE,), strength=4)
INFORMANT = UnitCard(
    id="informant",
    name="Informant",
    rows=(Row.MELEE,),
    strength=3,
    ability=Ability.SPY,
)
MEDIC = UnitCard(
    id="medic", name="Medic", rows=(Row.SIEGE,), strength=4, ability=Ability.MEDIC
)
HOARFROST = SpecialCard(id="hoarfrost", name="Hoarfrost", kind=SpecialKind.HOARFROST)
WAR_HORN = SpecialCard(id="war-horn", name="War Horn", kind=SpecialKind.WAR_HORN)
SCARECROW = SpecialCard(id="scarecrow", name="Scarecrow", kind=SpecialKind.SCARECROW)

# Every deck in the data files, by id, as in test_properties.py.
DECKS = {deck_id: load_deck(deck_id) for deck_id in deck_ids()}


def player(
    hand: tuple[Card, ...] = (SCOUT,),
    *,
    melee: tuple[UnitCard, ...] = (),
    ranged: tuple[UnitCard, ...] = (),
    siege: tuple[UnitCard, ...] = (),
    deck: tuple[Card, ...] = (),
    discard: tuple[Card, ...] = (),
    weather: tuple[SpecialCard, ...] = (),
    lives: int = 2,
    passed: bool = False,
) -> PlayerState:
    """Return a player with these units on their side of the board.

    By default they hold a Scout, so they don't pass by themselves.
    """
    rows = {
        Row.MELEE: RowState(units=melee),
        Row.RANGED: RowState(units=ranged),
        Row.SIEGE: RowState(units=siege),
    }
    return PlayerState(
        deck=deck,
        hand=hand,
        rows=rows,
        discard=discard,
        weather=weather,
        lives=lives,
        passed=passed,
    )


def soldier(strength: int) -> UnitCard:
    """Return an Agile Soldier, which can go in melee or ranged."""
    return UnitCard(
        id="soldier",
        name="Soldier",
        rows=(Row.MELEE, Row.RANGED),
        strength=strength,
        ability=Ability.AGILE,
    )


def ai_choice(
    ai: PlayerState, opponent: PlayerState | None = None, *, reviving: bool = False
) -> Action:
    """Return the action the AI chooses as player 0, on its turn.

    The AI doesn't look at the round number, so the round is always 1.
    """
    state = GameState(
        players=(ai, player() if opponent is None else opponent),
        current=0,
        round_starter=0,
        reviving=reviving,
        rng=Rng(seed=7),
    )
    return choose_action(player_view(state, 0))


# imagine


def test_imagine_puts_unknown_cards_where_the_view_hides_them() -> None:
    state = GameState(
        players=(
            player((SNIPER, KNIGHT), deck=(SCOUT, SCOUT)),
            player((MEDIC, MEDIC, MEDIC), deck=(KNIGHT,)),
        ),
        current=0,
        round_starter=0,
        rng=Rng(seed=7),
    )

    imagined = imagine(player_view(state, 0))

    assert imagined.players[0].hand == (SNIPER, KNIGHT)
    assert imagined.players[0].deck == (UNKNOWN, UNKNOWN)
    assert imagined.players[1].hand == (UNKNOWN, UNKNOWN, UNKNOWN)
    assert imagined.players[1].deck == (UNKNOWN,)
    assert imagined.rng != state.rng


# Hypothesis plays random matches, as in test_properties.py.
@settings(deadline=None)
@given(
    first=st.sampled_from(sorted(DECKS)),
    second=st.sampled_from(sorted(DECKS)),
    seed=st.integers(),
    data=st.data(),
)
def test_imagine_keeps_everything_the_view_shows(
    first: str, second: str, seed: int, data: st.DataObject
) -> None:
    state = start_match((DECKS[first], DECKS[second]), seed=seed)
    while True:
        # Seen from the imagined match, the view is the same: the same board,
        # scores and legal actions.
        for index in (0, 1):
            view = player_view(state, index)
            assert player_view(imagine(view), index) == view
        if match_over(state):
            break
        state, _ = apply(state, data.draw(st.sampled_from(legal_actions(state))))


# choose_action: when it is called


def test_keeps_the_hand_it_was_dealt() -> None:
    state = start_match((DECKS["humans"], DECKS["robots"]), seed=7)
    assert choose_action(player_view(state, state.current)) == EndRedraw()


def test_cant_choose_when_it_isnt_its_turn() -> None:
    state = start_match((DECKS["humans"], DECKS["robots"]), seed=7)
    view = player_view(state, 1 - state.current)
    with pytest.raises(ValueError, match="it isn't its turn"):
        choose_action(view)


# choose_action: whether to pass


def test_passes_when_the_opponent_has_passed_and_it_is_ahead() -> None:
    ai = player((KNIGHT,), melee=(SCOUT,))
    assert ai_choice(ai, player(passed=True)) == Pass()


@pytest.mark.parametrize("opponent", [(SCOUT,), (KNIGHT,)], ids=["tied", "behind"])
def test_plays_on_when_the_opponent_has_passed_and_it_isnt_ahead(
    opponent: tuple[UnitCard, ...],
) -> None:
    ai = player((KNIGHT,), melee=(SCOUT,))
    assert ai_choice(ai, player(melee=opponent, passed=True)) == PlayUnit(
        card="knight", row=Row.MELEE
    )


@pytest.mark.parametrize(
    ("lead", "action"),
    [
        (PASS_LEAD - 1, PlayUnit(card="knight", row=Row.MELEE)),
        (PASS_LEAD, Pass()),
    ],
)
def test_passes_first_when_ahead_by_the_points_of_two_cards(
    lead: int, action: Action
) -> None:
    ahead = UnitCard(id="ahead", name="Ahead", rows=(Row.SIEGE,), strength=lead)
    assert ai_choice(player((KNIGHT,), siege=(ahead,))) == action


def test_plays_on_when_far_ahead_on_its_last_life() -> None:
    ai = player((KNIGHT,), melee=(KNIGHT, KNIGHT, KNIGHT), lives=1)
    assert ai_choice(ai) == PlayUnit(card="knight", row=Row.MELEE)


def test_passes_when_it_has_no_card_it_can_play() -> None:
    # A Scarecrow needs a unit on the AI's side to swap with.
    assert ai_choice(player((SCARECROW,))) == Pass()


# choose_action: which card to play


def test_plays_the_card_that_scores_most() -> None:
    assert ai_choice(player((SCOUT, SNIPER, KNIGHT))) == PlayUnit(
        card="sniper", row=Row.RANGED
    )


def test_plays_a_spy_for_the_cards_it_draws() -> None:
    # The Knight adds 5 points; the Informant gives 3 to the opponent, but
    # draws 2 cards.
    ai = player((KNIGHT, INFORMANT), deck=(SNIPER, SNIPER))
    assert ai_choice(ai) == PlayUnit(card="informant", row=Row.MELEE)


def test_plays_a_medic_for_the_unit_it_brings_back() -> None:
    ai = player((KNIGHT, MEDIC), discard=(SNIPER,))
    assert ai_choice(ai) == PlayUnit(card="medic", row=Row.SIEGE)


def test_revives_the_unit_that_scores_most() -> None:
    ai = player((), siege=(MEDIC,), discard=(SCOUT, SNIPER, KNIGHT))
    assert ai_choice(ai, reviving=True) == Revive(card="sniper", row=Row.RANGED)


def test_plays_weather_that_hurts_the_opponent_more() -> None:
    ai = player((SCOUT, HOARFROST), siege=(CATAPULT,))
    opponent = player(melee=(KNIGHT, KNIGHT))
    assert ai_choice(ai, opponent) == PlaySpecial(card="hoarfrost")


def test_plays_a_war_horn_on_its_strongest_row() -> None:
    ai = player((WAR_HORN,), melee=(KNIGHT,), ranged=(SNIPER,))
    opponent = player(melee=(KNIGHT,), ranged=(SNIPER,))
    assert ai_choice(ai, opponent) == PlayHorn(card="war-horn", row=Row.RANGED)


def test_plays_an_agile_unit_out_of_the_weather() -> None:
    opponent = player(weather=(HOARFROST,))
    assert ai_choice(player((soldier(4),)), opponent) == PlayUnit(
        card="soldier", row=Row.RANGED
    )


@pytest.mark.parametrize(
    ("lives", "strength"),
    [(2, 5), (2, 4), (1, 5), (1, 4)],
    ids=["round-won", "round-tied", "match-won", "match-drawn"],
)
def test_plays_its_last_card_where_the_round_ends_best(
    lives: int, strength: int
) -> None:
    # The opponent has passed with 4 points. In melee, under Hoarfrost, the
    # Soldier would have 1 point and lose the round; in ranged, it wins the
    # round or ties it. On the last life, the match ends with the round.
    ai = player((soldier(strength),), lives=lives)
    opponent = player(siege=(CATAPULT,), weather=(HOARFROST,), lives=lives, passed=True)
    assert ai_choice(ai, opponent) == PlayUnit(card="soldier", row=Row.RANGED)


# choose_action: whole matches


@settings(deadline=None)
@given(
    first=st.sampled_from(sorted(DECKS)),
    second=st.sampled_from(sorted(DECKS)),
    seed=st.integers(),
    ai=st.sampled_from((0, 1)),
    data=st.data(),
)
def test_always_chooses_a_legal_action(
    first: str, second: str, seed: int, ai: int, data: st.DataObject
) -> None:
    # The AI plays one side; Hypothesis picks the other side's actions.
    state = start_match((DECKS[first], DECKS[second]), seed=seed)
    while not match_over(state):
        view = player_view(state, state.current)
        if state.current == ai:
            action = choose_action(view)
            assert action in view.legal_actions
        else:
            action = data.draw(st.sampled_from(view.legal_actions))
        state, _ = apply(state, action)


def play_against_random(decks: tuple[Deck, Deck], seed: int, ai: int) -> int | None:
    """Play a match between the AI, as player ``ai``, and a random player.

    The random player picks any legal action, with the same chance each.

    Returns:
        The index of the player who won, or ``None`` after a draw.
    """
    state = start_match(decks, seed=seed)
    chance = random.Random(seed)
    while not match_over(state):
        if state.current == ai:
            action = choose_action(player_view(state, ai))
        else:
            action = chance.choice(legal_actions(state))
        state, _ = apply(state, action)
    return match_winner(state)


def test_beats_a_random_player_in_most_matches() -> None:
    # Every pair of decks, with the AI as either player, on 10 seeds. The AI
    # must win at least 4 in 5 of them.
    matches = [
        ((DECKS[first], DECKS[second]), seed, ai)
        for first in sorted(DECKS)
        for second in sorted(DECKS)
        for seed in range(10)
        for ai in (0, 1)
    ]
    wins = sum(play_against_random(*match) == match[2] for match in matches)
    assert wins >= 0.8 * len(matches)

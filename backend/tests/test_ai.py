"""Tests for the baseline AI: what it sees, and the moves it chooses."""

import random
from dataclasses import replace

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
    Redraw,
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
from rowen.engine.scoring import unit_strength
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
PLANE = UnitCard(
    id="plane",
    name="Plane",
    rows=(Row.SIEGE,),
    strength=3,
    ability=Ability.MUSTER,
    group="planes",
)
SERVER = UnitCard(
    id="server",
    name="Server",
    rows=(Row.SIEGE,),
    strength=3,
    ability=Ability.MUSTER,
    group="servers",
)
# A Bond unit that happens to share the Planes' group name.
PILOT = UnitCard(
    id="pilot",
    name="Pilot",
    rows=(Row.SIEGE,),
    strength=2,
    ability=Ability.BOND,
    group="planes",
)
HOARFROST = SpecialCard(id="hoarfrost", name="Hoarfrost", kind=SpecialKind.HOARFROST)
CLEAR_SKIES = SpecialCard(
    id="clear-skies", name="Clear Skies", kind=SpecialKind.CLEAR_SKIES
)
WAR_HORN = SpecialCard(id="war-horn", name="War Horn", kind=SpecialKind.WAR_HORN)
SCARECROW = SpecialCard(id="scarecrow", name="Scarecrow", kind=SpecialKind.SCARECROW)

PLAY_KNIGHT = PlayUnit(card="knight", row=Row.MELEE)
PLAY_SNIPER = PlayUnit(card="sniper", row=Row.RANGED)
PLAY_INFORMANT = PlayUnit(card="informant", row=Row.MELEE)

# Cards for a Spy to draw.
DECK = (SCOUT,) * 10

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


def wall(strength: int) -> UnitCard:
    """Return a siege unit with this strength, to give a side its score."""
    return UnitCard(id="wall", name="Wall", rows=(Row.SIEGE,), strength=strength)


def passed(score: int, *, lives: int = 2) -> PlayerState:
    """Return an opponent who has passed with ``score`` points, cards in hand."""
    return player((SCOUT,) * 3, siege=(wall(score),), lives=lives, passed=True)


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

    The AI's choice doesn't depend on which round it is, so the round is
    always 1.
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


def test_cant_choose_when_it_isnt_its_turn() -> None:
    state = start_match((DECKS["humans"], DECKS["robots"]), seed=7)
    view = player_view(state, 1 - state.current)
    with pytest.raises(ValueError, match="it isn't its turn"):
        choose_action(view)


# choose_action: before round 1


def redraw_choice(hand: tuple[Card, ...], deck: tuple[Card, ...] = DECK) -> Action:
    """Return what the AI, as player 0, chooses before round 1."""
    return ai_choice(replace(player(hand, deck=deck), redraws_left=2))


def test_swaps_a_spare_muster_card() -> None:
    assert redraw_choice((KNIGHT, PLANE, PLANE)) == Redraw(card="plane")


@pytest.mark.parametrize(
    "hand",
    [(KNIGHT, PLANE), (PLANE, SERVER), (PLANE, PILOT)],
    ids=["one-muster-card", "two-groups", "bond-card"],
)
def test_keeps_a_hand_without_a_spare_muster_card(hand: tuple[Card, ...]) -> None:
    assert redraw_choice(hand) == EndRedraw()


def test_swaps_the_spare_muster_card_not_a_bond_card_of_its_group() -> None:
    # The Pilot's group name has two Muster cards, but the Pilot isn't one.
    assert redraw_choice((PILOT, PLANE, PLANE)) == Redraw(card="plane")


def test_keeps_its_hand_when_there_is_no_card_to_draw() -> None:
    assert redraw_choice((PLANE, PLANE), deck=()) == EndRedraw()


# choose_action: whether to pass while the opponent still plays


@pytest.mark.parametrize(
    ("lead", "action"), [(PASS_LEAD - 1, PLAY_KNIGHT), (PASS_LEAD, Pass())]
)
def test_passes_first_when_ahead_by_the_points_of_two_cards(
    lead: int, action: Action
) -> None:
    assert ai_choice(player((KNIGHT,), siege=(wall(lead),))) == action


def test_plays_on_when_far_ahead_on_its_last_life() -> None:
    ai = player((KNIGHT,), melee=(KNIGHT, KNIGHT, KNIGHT), lives=1)
    assert ai_choice(ai) == PLAY_KNIGHT


def test_passes_when_it_has_no_card_it_can_play() -> None:
    # A Scarecrow needs a unit on the AI's side to swap with.
    assert ai_choice(player((SCARECROW,))) == Pass()


# choose_action: which card to play


def test_plays_the_card_that_scores_most() -> None:
    assert ai_choice(player((SCOUT, SNIPER, KNIGHT))) == PLAY_SNIPER


def test_plays_a_spy_for_the_cards_it_draws() -> None:
    # The Knight adds 5 points; the Informant gives 3 to the opponent, but
    # draws 2 cards.
    ai = player((KNIGHT, INFORMANT), deck=(SNIPER, SNIPER))
    assert ai_choice(ai) == PLAY_INFORMANT


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


# choose_action: once the opponent has passed


def test_passes_when_the_opponent_has_passed_and_it_is_ahead() -> None:
    ai = player((KNIGHT,), melee=(SCOUT,))
    assert ai_choice(ai, player(passed=True)) == Pass()


@pytest.mark.parametrize("opponent", [(SCOUT,), (KNIGHT,)], ids=["tied", "behind"])
def test_plays_on_when_the_opponent_has_passed_and_it_isnt_ahead(
    opponent: tuple[UnitCard, ...],
) -> None:
    ai = player((KNIGHT,), melee=(SCOUT,))
    assert ai_choice(ai, player(melee=opponent, passed=True)) == PLAY_KNIGHT


@pytest.mark.parametrize(
    ("needed", "action"), [(1, PLAY_KNIGHT), (2, PLAY_KNIGHT), (3, Pass())]
)
def test_spends_up_to_two_cards_to_win_round_1(needed: int, action: Action) -> None:
    # It takes ``needed`` Knights to beat 5 * needed - 1 points.
    ai = player((KNIGHT,) * 5)
    assert ai_choice(ai, passed(5 * needed - 1)) == action


@pytest.mark.parametrize("lives", [(1, 1), (1, 2), (2, 1)])
def test_spends_any_cards_to_win_a_round_that_decides_the_match(
    lives: tuple[int, int],
) -> None:
    # It takes 4 Knights: more than the AI spends on a round that doesn't
    # decide the match.
    ai = player((KNIGHT,) * 5, lives=lives[0])
    assert ai_choice(ai, passed(19, lives=lives[1])) == PLAY_KNIGHT


def test_gives_up_a_round_it_cant_win() -> None:
    assert ai_choice(player((KNIGHT, SNIPER, SCOUT)), passed(40)) == Pass()


@pytest.mark.parametrize(
    ("deck", "action"),
    [((SCOUT, SCOUT), PLAY_INFORMANT), ((SCOUT,), Pass()), ((), Pass())],
    ids=["draws-2", "draws-1", "draws-0"],
)
def test_plays_a_spy_that_keeps_it_ahead_for_the_cards_it_draws(
    deck: tuple[Card, ...], action: Action
) -> None:
    # 6 against 1, and still ahead after the Informant's 3 points. Drawing one
    # card, the Spy leaves as many cards as passing does: on a tie, it passes.
    ai = player((INFORMANT, KNIGHT), ranged=(SNIPER,), deck=deck)
    assert ai_choice(ai, passed(1)) == action


@pytest.mark.parametrize("lives", [(1, 1), (1, 2), (2, 1)])
def test_chases_with_the_units_it_has_not_the_cards_a_spy_would_draw(
    lives: tuple[int, int],
) -> None:
    # The round decides the match. 9 behind, the Knight and the Sniper win it.
    # The cards the Informant would draw are unknown, with no strength in the
    # imagined match, so after the Informant, the Knight and the Sniper would
    # fall short.
    ai = player((KNIGHT, SNIPER, INFORMANT), deck=DECK, lives=lives[0])
    assert ai_choice(ai, passed(9, lives=lives[1])) in {PLAY_KNIGHT, PLAY_SNIPER}


def test_revives_the_unit_that_wins_the_round() -> None:
    # The Medic (4) is 4 behind. Reviving the Knight wins the round; the
    # Informant would draw 2 cards, but give the opponent 3 more points.
    ai = player((SCOUT,), siege=(MEDIC,), discard=(INFORMANT, KNIGHT), deck=DECK)
    assert ai_choice(ai, passed(8), reviving=True) == Revive(
        card="knight", row=Row.MELEE
    )


def test_plays_a_medic_for_the_unit_that_wins_the_round() -> None:
    # 8 behind: the Medic (4) and the Knight it revives win the round, and the
    # Scout stays in the hand.
    ai = player((MEDIC, SCOUT), discard=(INFORMANT, KNIGHT), deck=DECK)
    assert ai_choice(ai, passed(8)) == PlayUnit(card="medic", row=Row.SIEGE)


def test_chases_with_its_strongest_units() -> None:
    # 10 behind: the Knight and the Sniper win with two cards. With the Scout
    # or the Catapult, it would take three.
    ai = player((SCOUT, SNIPER, KNIGHT, CATAPULT))
    assert ai_choice(ai, passed(10)) in {PLAY_KNIGHT, PLAY_SNIPER}


def test_revives_with_a_second_medic_the_unit_that_wins_the_match() -> None:
    # The round decides the match, 18 behind. The AI plays it to the end: two
    # Medics and the Sniper and the Knight they bring back make 19. Reviving
    # the Informant would draw 2 cards, but give the opponent 3 more points.
    ai = player(
        (MEDIC, MEDIC, SCOUT),
        discard=(INFORMANT, KNIGHT, SNIPER),
        deck=DECK,
        lives=1,
    )
    state = GameState(
        players=(ai, passed(18, lives=1)), current=0, round_starter=0, rng=Rng(seed=7)
    )
    while not match_over(state):
        state, _ = apply(state, choose_action(player_view(state, 0)))
    assert match_winner(state) == 0


def test_plays_a_spy_in_a_round_it_cant_win_for_the_cards_it_draws() -> None:
    # The round is lost. After the Informant, the AI passes at once, with one
    # card more than if it passed now, and keeps the Knight.
    ai = player((INFORMANT, KNIGHT), deck=DECK)
    assert ai_choice(ai, passed(40)) == PLAY_INFORMANT


def test_an_unknown_card_has_no_strength_even_under_weather() -> None:
    # So the cards a Spy draws in the imagined match never help the AI catch up.
    row = RowState(units=(UNKNOWN,))
    assert unit_strength(UNKNOWN, row, weathered=True) == 0


def test_wins_the_match_with_the_fewest_cards() -> None:
    # Both ways win the match. Clear Skies, with no weather to clear, would
    # only waste a card.
    ai = player((CLEAR_SKIES, KNIGHT), lives=1)
    opponent = player((), lives=1, passed=True)
    assert ai_choice(ai, opponent) == PLAY_KNIGHT


def test_plays_its_last_card_to_win_a_round_when_the_next_ends_at_once() -> None:
    # After two Scouts, the round is tied, and the third one wins it. Then
    # neither player has a card left, so the last round ends at once in a tie,
    # and the match in a draw. Passing at the tie would lose the match.
    ai = player((SCOUT,) * 3, lives=1)
    opponent = player((), siege=(wall(6),), passed=True)
    assert ai_choice(ai, opponent) == PlayUnit(card="scout", row=Row.MELEE)


@pytest.mark.parametrize(("lives", "action"), [(1, PLAY_KNIGHT), (2, Pass())])
def test_ties_the_round_only_when_a_tie_wins_the_match(
    lives: int, action: Action
) -> None:
    # Two Knights tie the round, and a tie costs both players a life. With 1
    # life left, the opponent then loses the match, so the two cards are worth
    # it. With 2, they aren't.
    ai = player((KNIGHT, KNIGHT))
    assert ai_choice(ai, passed(10, lives=lives)) == action


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

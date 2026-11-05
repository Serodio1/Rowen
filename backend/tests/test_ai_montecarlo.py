"""Tests for the Monte Carlo AI: its guesses, and the moves it chooses."""

from dataclasses import replace

import pytest
from cards import HOARFROST, KNIGHT, SCOUT, WAR_HORN
from hypothesis import given, settings
from hypothesis import strategies as st

from rowen.ai import baseline, montecarlo
from rowen.ai.montecarlo import (
    _next,
    _play_out,
    _rule_of_thumb,
    choose_action,
    guess,
)
from rowen.data import deck_ids, load_deck
from rowen.engine.actions import (
    Action,
    EndRedraw,
    Pass,
    PlayScarecrow,
    PlayUnit,
    Revive,
)
from rowen.engine.cards import Ability, Card, Row, SpecialCard, SpecialKind, UnitCard
from rowen.engine.game import apply, legal_actions, match_over, start_match
from rowen.engine.rng import Rng
from rowen.engine.state import GameState, PlayerState, RowState
from rowen.engine.view import player_view

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
WATCH_MAN = UnitCard(
    id="watch-man",
    name="Watch Man",
    rows=(Row.MELEE,),
    strength=5,
    ability=Ability.WARD,
)

LEGEND_SPY = replace(INFORMANT, id="mole", name="Mole", legend=True)

SCARECROW = SpecialCard(id="scarecrow", name="Scarecrow", kind=SpecialKind.SCARECROW)

# Every deck in the data files, by id, as in test_properties.py.
DECKS = {deck_id: load_deck(deck_id) for deck_id in deck_ids()}


def player(
    hand: tuple[Card, ...] = (),
    *,
    melee: tuple[UnitCard, ...] = (),
    siege: tuple[UnitCard, ...] = (),
    deck: tuple[Card, ...] = (),
    discard: tuple[Card, ...] = (),
    lives: int = 2,
) -> PlayerState:
    """Return a player with these cards."""
    rows = {
        Row.MELEE: RowState(units=melee),
        Row.RANGED: RowState(),
        Row.SIEGE: RowState(units=siege),
    }
    return PlayerState(deck=deck, hand=hand, rows=rows, discard=discard, lives=lives)


def match(ai: PlayerState, opponent: PlayerState) -> GameState:
    """Return a match in round 1 where it is the AI's turn, as player 0."""
    return GameState(
        players=(ai, opponent), current=0, round_starter=0, rng=Rng(seed=7)
    )


def wall(strength: int) -> UnitCard:
    """Return a siege unit with this strength, to give a side its score."""
    return UnitCard(id="wall", name="Wall", rows=(Row.SIEGE,), strength=strength)


# guess


def test_guess_draws_the_hidden_cards_from_the_cards_not_seen() -> None:
    # The AI sees its hand and the board. Its deck list has two more Knights,
    # so those are its deck. Of the opponent's list, the Catapult on the board
    # and the Scout in the discard pile are seen: the hand and deck are the
    # rest, the three Knights, in some order.
    state = match(
        player((SCOUT,), melee=(KNIGHT,), deck=(KNIGHT, KNIGHT)),
        player((KNIGHT, KNIGHT), siege=(CATAPULT,), deck=(KNIGHT,), discard=(SCOUT,)),
    )
    decks = ((SCOUT, KNIGHT, KNIGHT, KNIGHT), (CATAPULT, SCOUT, KNIGHT, KNIGHT, KNIGHT))

    guessed, _ = guess(player_view(state, 0), decks, Rng(seed=1))

    assert guessed.players[0].hand == (SCOUT,)
    assert guessed.players[0].deck == (KNIGHT, KNIGHT)
    assert guessed.players[1].hand == (KNIGHT, KNIGHT)
    assert guessed.players[1].deck == (KNIGHT,)


def test_guess_takes_away_the_special_cards_seen() -> None:
    # The opponent's War Horn, Scarecrow and Hoarfrost are in play, so of
    # their list only the Knight can be in their hand.
    opponent = PlayerState(
        deck=(),
        hand=(KNIGHT,),
        rows={
            Row.MELEE: RowState(horn=WAR_HORN, scarecrows=(SCARECROW,)),
            Row.RANGED: RowState(),
            Row.SIEGE: RowState(),
        },
        weather=(HOARFROST,),
    )
    state = match(player((SCOUT,)), opponent)
    decks = ((SCOUT,), (WAR_HORN, SCARECROW, HOARFROST, KNIGHT))

    guessed, _ = guess(player_view(state, 0), decks, Rng(seed=1))

    assert guessed.players[1].hand == (KNIGHT,)


def test_guess_counts_a_spy_for_the_player_who_played_it() -> None:
    # The Informant on the AI's side is the opponent's: their list has one,
    # so it isn't in their hand. The AI's own Informant isn't seen, so it can
    # be in the AI's deck.
    state = match(
        player(melee=(INFORMANT,), deck=(SCOUT,)),
        player((SCOUT,), deck=()),
    )
    decks = ((INFORMANT,), (INFORMANT, SCOUT))

    guessed, _ = guess(player_view(state, 0), decks, Rng(seed=1))

    assert guessed.players[0].deck == (INFORMANT,)
    assert guessed.players[1].hand == (SCOUT,)


@pytest.mark.parametrize(
    "ai",
    [
        # The AI's Medic revived the opponent's Informant from its discard
        # pile, onto the opponent's side.
        pytest.param(player(), id="revived onto its owner's side"),
        # The AI's Scarecrow took the opponent's Informant back.
        pytest.param(player((INFORMANT,)), id="taken back into the AI's hand"),
    ],
)
def test_guess_counts_a_spy_for_the_player_whose_deck_has_it(
    ai: PlayerState,
) -> None:
    # Only the opponent's list has an Informant, so it is seen, and their
    # hidden card is the Scout, whatever the guess.
    opponent = player((SCOUT,))
    if not ai.hand:
        opponent = player((SCOUT,), melee=(INFORMANT,))
    state = match(ai, opponent)
    decks = ((KNIGHT,), (INFORMANT, SCOUT))

    for seed in range(10):
        guessed, _ = guess(player_view(state, 0), decks, Rng(seed=seed))

        assert guessed.players[1].hand == (SCOUT,)


def test_guess_keeps_its_list_when_a_card_seen_is_not_in_it() -> None:
    # The opponent plays a deck they built, with a Knight the AI's list of
    # their deck doesn't have: the guess still draws from the list.
    state = match(player(), player((SCOUT,), melee=(KNIGHT,)))
    decks = ((), (SCOUT,))

    guessed, _ = guess(player_view(state, 0), decks, Rng(seed=1))

    assert guessed.players[1].hand == (SCOUT,)


def test_guess_fills_the_rest_with_unknown_cards() -> None:
    # The guess of the opponent's deck is wrong: it has fewer cards left than
    # they hold.
    state = match(player((SCOUT,)), player((KNIGHT, KNIGHT, KNIGHT)))

    guessed, _ = guess(player_view(state, 0), ((SCOUT,), (KNIGHT,)), Rng(seed=1))

    assert guessed.players[1].hand == (KNIGHT, baseline.UNKNOWN, baseline.UNKNOWN)


def test_guess_changes_with_the_rng() -> None:
    state = match(player((SCOUT,)), player((SCOUT,), deck=(SCOUT,) * 5))
    decks = ((SCOUT,), (SCOUT, SCOUT, SCOUT, KNIGHT, KNIGHT, KNIGHT))
    view = player_view(state, 0)

    hands = set()
    rng = Rng(seed=1)
    for _ in range(20):
        guessed, rng = guess(view, decks, rng)
        hands.add(guessed.players[1].hand)

    assert hands == {(SCOUT,), (KNIGHT,)}


# Hypothesis plays random matches, as in test_properties.py.
@settings(deadline=None, max_examples=50)
@given(
    first=st.sampled_from(sorted(DECKS)),
    second=st.sampled_from(sorted(DECKS)),
    seed=st.integers(),
    data=st.data(),
)
def test_guess_keeps_everything_the_view_shows(
    first: str, second: str, seed: int, data: st.DataObject
) -> None:
    decks = (DECKS[first].cards, DECKS[second].cards)
    state = start_match((DECKS[first], DECKS[second]), seed=seed)
    while True:
        for index in (0, 1):
            view = player_view(state, index)
            guessed, _ = guess(view, decks, Rng(seed=seed))
            # Seen from the guess, the view is the same: the same board,
            # scores and legal actions.
            assert player_view(guessed, index) == view
            # The guess is the baseline's imagined match with only the hidden
            # cards changed: every other field is kept, even one added later.
            imagined = baseline.imagine(view)
            assert replace(guessed, players=imagined.players) == imagined
            for guessed_player, imagined_player in zip(
                guessed.players, imagined.players, strict=True
            ):
                assert (
                    replace(
                        guessed_player,
                        deck=imagined_player.deck,
                        hand=imagined_player.hand,
                    )
                    == imagined_player
                )
            # With the real deck lists, every guessed card comes from the
            # player's own list. The hand the view shows is left out: a
            # Scarecrow can take back the opponent's Spy.
            other = guessed.players[1 - index]
            guesses = (
                (guessed.players[index].deck, decks[index]),
                ((*other.deck, *other.hand), decks[1 - index]),
            )
            for cards, deck in guesses:
                assert set(cards) <= {*deck, baseline.UNKNOWN}
        if match_over(state):
            break
        state, _ = apply(state, data.draw(st.sampled_from(legal_actions(state))))


# choose_action


def test_needs_a_legal_action_and_a_sample() -> None:
    state = match(player((SCOUT,)), player((SCOUT,)))
    decks = ((SCOUT,), (SCOUT,))
    with pytest.raises(ValueError, match="no legal actions"):
        choose_action(player_view(state, 1), decks=decks, samples=1, seed=0)
    with pytest.raises(ValueError, match="samples"):
        choose_action(player_view(state, 0), decks=decks, samples=0, seed=0)


def test_redraws_as_the_baseline_does() -> None:
    state = start_match((DECKS["humans"], DECKS["robots"]), seed=3)
    view = player_view(state, state.current)
    decks = (DECKS["humans"].cards, DECKS["robots"].cards)

    action = choose_action(view, decks=decks, samples=4, seed=0)

    assert EndRedraw() in view.legal_actions
    assert action == baseline.choose_action(view)


def test_plays_as_the_baseline_once_the_opponent_has_passed() -> None:
    # The opponent plays no more cards this round, so their hidden cards
    # change nothing: the baseline's choice is kept.
    opponent = replace(player((KNIGHT,) * 3, siege=(wall(4),)), passed=True)
    state = match(player((KNIGHT, SCOUT)), opponent)
    view = player_view(state, 0)
    decks = ((KNIGHT, SCOUT), (KNIGHT,) * 3 + (wall(4),))

    action = choose_action(view, decks=decks, samples=4, seed=0)

    assert action == baseline.choose_action(view)


def test_revives_as_the_baseline_does() -> None:
    state = replace(
        match(player(discard=(SCOUT, KNIGHT)), player((SCOUT,))), reviving=True
    )
    view = player_view(state, 0)

    action = choose_action(view, decks=((SCOUT, KNIGHT), (SCOUT,)), samples=4, seed=0)

    assert (
        action == baseline.choose_action(view) == Revive(card="knight", row=Row.MELEE)
    )


def test_passes_with_an_empty_hand() -> None:
    state = match(player(), player((SCOUT,)))

    action = choose_action(
        player_view(state, 0), decks=((), (SCOUT,)), samples=4, seed=0
    )

    assert action == Pass()


def test_plays_on_when_the_opponent_holds_enough_to_catch_up() -> None:
    # The AI leads by 10, which the baseline thinks is enough to pass. But
    # every card the opponent can hold is a Knight: with their three, they
    # would win the round. So the AI plays its Knight instead.
    state = match(
        player((KNIGHT, KNIGHT), siege=(wall(10),)),
        player((KNIGHT,) * 3),
    )
    view = player_view(state, 0)

    assert baseline.choose_action(view) == Pass()
    action = choose_action(
        view, decks=((KNIGHT,) * 2 + (wall(10),), (KNIGHT,) * 3), samples=4, seed=0
    )
    assert action == PlayUnit(card="knight", row=Row.MELEE)


def test_passes_when_the_opponent_holds_too_little() -> None:
    # The same lead, but every card the opponent can hold is a Scout: three
    # of them don't catch up, so the AI keeps its cards.
    state = match(
        player((KNIGHT, KNIGHT), siege=(wall(10),)),
        player((SCOUT,) * 3),
    )
    view = player_view(state, 0)

    action = choose_action(
        view, decks=((KNIGHT,) * 2 + (wall(10),), (SCOUT,) * 3), samples=4, seed=0
    )
    assert action == Pass()


def test_plays_on_when_every_sample_loses_the_match() -> None:
    # The last round: the AI leads by a point with three Scouts, and the
    # opponent holds seven Knights. Every sample loses the match, whatever the
    # AI does. Passing would keep its cards, but they count for nothing once
    # the match is lost: it plays on, as the opponent may still go wrong.
    state = match(
        player((SCOUT,) * 3, siege=(wall(1),), lives=1),
        player((KNIGHT,) * 7, lives=1),
    )
    decks = ((SCOUT,) * 3 + (wall(1),), (KNIGHT,) * 7)

    action = choose_action(player_view(state, 0), decks=decks, samples=4, seed=0)

    assert action == PlayUnit(card="scout", row=Row.MELEE)


@pytest.mark.parametrize(
    ("opponent_passed", "reviving"), [(True, False), (False, True)]
)
def test_leaves_the_choice_to_the_baseline(
    opponent_passed: bool, reviving: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Once the opponent has passed, or after a Medic, the hidden cards change
    # nothing: whatever the baseline chooses is played, without a sample. The
    # baseline is made to choose what no sample could: an action that isn't
    # even legal.
    opponent = replace(player((SCOUT,)), passed=opponent_passed)
    state = replace(
        match(player((KNIGHT,), discard=(SCOUT,)), opponent), reviving=reviving
    )
    view = player_view(state, 0)
    chosen = PlayUnit(card="scout", row=Row.SIEGE)
    monkeypatch.setattr(baseline, "choose_action", lambda _: chosen)

    action = choose_action(view, decks=((KNIGHT, SCOUT), (SCOUT,)), samples=4, seed=0)

    assert action == chosen


def test_adds_up_every_sample() -> None:
    # The last round: the AI leads by 10. The opponent holds three of a
    # Knight and four Scouts: with the Knight, they catch up and win the
    # match, and with three Scouts (9 points) they don't. With seed 1, the
    # first two samples give them the Knight and the last one doesn't: on
    # their own, the last one would pass, to win with a card more.
    state = match(
        player((KNIGHT, KNIGHT), siege=(wall(10),), lives=1),
        player((SCOUT,) * 3, lives=1),
    )
    decks = ((KNIGHT, KNIGHT, wall(10)), (KNIGHT, SCOUT, SCOUT, SCOUT, SCOUT))

    action = choose_action(player_view(state, 0), decks=decks, samples=3, seed=1)

    assert action == PlayUnit(card="knight", row=Row.MELEE)


# The Hard level's rules of thumb


def test_hard_plays_its_rule_of_thumb_before_any_sample() -> None:
    # With an Informant in the hand, the Hard AI plays it; the other levels
    # leave it to the samples, which score a move by its points only.
    state = match(player((KNIGHT, INFORMANT), deck=(SCOUT,)), player((SCOUT,)))
    view = player_view(state, 0)
    decks = ((KNIGHT, INFORMANT, SCOUT), (SCOUT,))

    action = choose_action(view, decks=decks, samples=4, seed=0, hard=True)

    assert action == PlayUnit(card="informant", row=Row.MELEE)
    assert choose_action(view, decks=decks, samples=4, seed=0) != action


def test_hard_revives_a_spy() -> None:
    # The baseline revives the strongest unit, the Knight (as in
    # test_revives_as_the_baseline_does); the Hard AI, the Informant.
    state = replace(
        match(player(discard=(INFORMANT, KNIGHT), deck=(SCOUT,)), player((SCOUT,))),
        reviving=True,
    )
    view = player_view(state, 0)

    action = _rule_of_thumb(view, ((INFORMANT, KNIGHT), (SCOUT,)))

    assert isinstance(action, Revive)
    assert action.card == "informant"
    assert action in view.legal_actions


def test_hard_revives_as_the_baseline_without_a_spy() -> None:
    state = replace(
        match(player(discard=(SCOUT, KNIGHT)), player((SCOUT,))), reviving=True
    )

    assert _rule_of_thumb(player_view(state, 0), ((SCOUT, KNIGHT), (SCOUT,))) is None


def test_hard_takes_back_an_opponents_spy_with_a_scarecrow() -> None:
    # The Informant on the AI's side is the opponent's Spy: back in the AI's
    # hand, it is the AI's to play. The Knight is the stronger unit to take.
    state = match(
        player((SCARECROW,), melee=(KNIGHT, INFORMANT), deck=(SCOUT,)),
        player((SCOUT,)),
    )
    view = player_view(state, 0)

    action = _rule_of_thumb(view, ((SCARECROW, KNIGHT), (INFORMANT, SCOUT)))

    assert action == PlayScarecrow(card="scarecrow", row=Row.MELEE, unit="informant")


def test_hard_plays_a_medic_while_a_spy_is_in_its_discard_pile() -> None:
    state = match(
        player((KNIGHT, MEDIC), discard=(INFORMANT,), deck=(SCOUT,)), player((SCOUT,))
    )
    view = player_view(state, 0)

    action = _rule_of_thumb(view, ((KNIGHT, MEDIC, INFORMANT, SCOUT), (SCOUT,)))

    assert action == PlayUnit(card="medic", row=Row.SIEGE)


@pytest.mark.parametrize("discard", [SCOUT, LEGEND_SPY])
def test_hard_keeps_its_medic_without_a_spy_to_revive(discard: UnitCard) -> None:
    # A Medic can't revive a Legend, even a Spy.
    state = match(player((KNIGHT, MEDIC), discard=(discard,)), player((SCOUT,)))
    decks = ((KNIGHT, MEDIC, discard), (SCOUT,))

    assert _rule_of_thumb(player_view(state, 0), decks) is None


@pytest.mark.parametrize(
    ("deck", "their_melee"),
    [
        # No card left to draw: the Spy would only give the opponent points.
        ((), ()),
        # A Ward unit in the opponent's melee keeps the Informant out.
        ((SCOUT,), (WATCH_MAN,)),
    ],
)
def test_hard_has_no_rule_for_a_spy_that_would_draw_nothing(
    deck: tuple[Card, ...], their_melee: tuple[UnitCard, ...]
) -> None:
    opponent = player((SCOUT,), melee=their_melee)
    decks = ((SCARECROW, MEDIC, INFORMANT, KNIGHT, *deck), (SCOUT, WATCH_MAN))
    in_hand = match(player((KNIGHT, INFORMANT), deck=deck), opponent)
    medic = match(player((MEDIC,), discard=(INFORMANT,), deck=deck), opponent)
    scarecrow = match(
        player((SCARECROW,), melee=(KNIGHT, INFORMANT), deck=deck), opponent
    )
    reviving = replace(
        match(player(discard=(INFORMANT, KNIGHT), deck=deck), opponent),
        reviving=True,
    )

    for state in (in_hand, medic, scarecrow, reviving):
        assert _rule_of_thumb(player_view(state, 0), decks) is None


def test_hard_revives_as_the_baseline_once_the_opponent_passed() -> None:
    # With the opponent passed, a revived Spy would only give them points.
    opponent = replace(player((SCOUT,)), passed=True)
    state = replace(
        match(player(discard=(INFORMANT, KNIGHT), deck=(SCOUT,)), opponent),
        reviving=True,
    )

    assert (
        _rule_of_thumb(player_view(state, 0), ((INFORMANT, KNIGHT), (SCOUT,))) is None
    )


def test_hard_needs_a_medic_to_revive_its_spy() -> None:
    state = match(
        player((KNIGHT,), discard=(INFORMANT,), deck=(SCOUT,)), player((SCOUT,))
    )
    decks = ((KNIGHT, INFORMANT, SCOUT), (SCOUT,))

    assert _rule_of_thumb(player_view(state, 0), decks) is None


def test_hard_plays_a_ward_unit_where_the_opponents_spies_would_go() -> None:
    # The opponent's list has an Informant the AI hasn't seen: a melee Spy.
    state = match(player((KNIGHT, WATCH_MAN)), player((SCOUT,)))
    view = player_view(state, 0)

    action = _rule_of_thumb(view, ((KNIGHT, WATCH_MAN), (SCOUT, INFORMANT)))

    assert action == PlayUnit(card="watch-man", row=Row.MELEE)


@pytest.mark.parametrize(
    ("melee", "discard", "their_deck"),
    [
        # No Spy in the opponent's list.
        ((), (), (SCOUT, KNIGHT)),
        # Their only Spy is seen already: in the AI's discard pile, where an
        # opponent's Spy ends up after the round.
        ((), (INFORMANT,), (SCOUT, INFORMANT)),
        # A Ward unit is in the row already.
        ((WATCH_MAN,), (), (SCOUT, INFORMANT)),
    ],
)
def test_hard_keeps_its_ward_unit_when_no_spy_can_come(
    melee: tuple[UnitCard, ...],
    discard: tuple[Card, ...],
    their_deck: tuple[Card, ...],
) -> None:
    state = match(
        player((KNIGHT, WATCH_MAN), melee=melee, discard=discard), player((SCOUT,))
    )
    decks = ((KNIGHT, WATCH_MAN, *melee), their_deck)

    assert _rule_of_thumb(player_view(state, 0), decks) is None


@pytest.mark.parametrize("before_round_1", [True, False])
def test_hard_has_no_rule_before_round_1_nor_once_the_opponent_passed(
    before_round_1: bool,
) -> None:
    # A Spy then would only give the opponent points.
    opponent = replace(player((SCOUT,)), passed=not before_round_1)
    ai = replace(player((INFORMANT,)), redraws_left=2 if before_round_1 else 0)
    state = match(ai, opponent)
    view = player_view(state, 0)

    assert (EndRedraw() in view.legal_actions) is before_round_1
    assert _rule_of_thumb(view, ((INFORMANT,), (SCOUT, INFORMANT))) is None


# _next: the play-out


@pytest.mark.parametrize(
    ("lead", "lives", "action"),
    [
        (10, 2, Pass()),
        (9, 2, PlayUnit(card="knight", row=Row.MELEE)),
        (10, 1, PlayUnit(card="knight", row=Row.MELEE)),
    ],
)
def test_play_out_passes_ahead_by_10_but_not_on_the_last_life(
    lead: int, lives: int, action: Action
) -> None:
    state = match(player((KNIGHT,), siege=(wall(lead),), lives=lives), player((SCOUT,)))
    assert _next(state) == action


@pytest.mark.parametrize(
    ("ai_hand", "behind", "lives", "their_hand", "action"),
    [
        # 10 behind, a life to spare, as many cards: gives up the round.
        ((KNIGHT,), 10, 2, (SCOUT,), Pass()),
        # With a Spy, plays it first: 2 cards more for the next round.
        (
            (KNIGHT, INFORMANT),
            10,
            2,
            (SCOUT, SCOUT),
            PlayUnit(card="informant", row=Row.MELEE),
        ),
        # 9 behind: plays on.
        ((KNIGHT,), 9, 2, (SCOUT,), PlayUnit(card="knight", row=Row.MELEE)),
        # The last life: plays on.
        ((KNIGHT,), 10, 1, (SCOUT,), PlayUnit(card="knight", row=Row.MELEE)),
        # Fewer cards than the opponent: plays on.
        ((KNIGHT,), 10, 2, (SCOUT, SCOUT), PlayUnit(card="knight", row=Row.MELEE)),
    ],
)
def test_hard_play_out_gives_up_a_round_far_behind(
    ai_hand: tuple[Card, ...],
    behind: int,
    lives: int,
    their_hand: tuple[Card, ...],
    action: Action,
) -> None:
    state = match(
        player(ai_hand, lives=lives), player(their_hand, siege=(wall(behind),))
    )

    assert _next(state, hard=True) == action
    # The other levels play on.
    assert _next(state) == PlayUnit(card="knight", row=Row.MELEE)


@pytest.mark.parametrize("hard", [True, False])
def test_only_hard_gives_up_rounds_in_its_play_outs(
    hard: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    # No rule of thumb applies here: the samples choose, and each play-out
    # plays at the level asked for.
    levels: list[bool] = []

    def spy(state: GameState, *, hard: bool = False) -> Action:
        levels.append(hard)
        return _next(state, hard=hard)

    monkeypatch.setattr(montecarlo, "_next", spy)
    state = match(player((KNIGHT, SCOUT)), player((SCOUT,) * 2))

    choose_action(
        player_view(state, 0),
        decks=((KNIGHT, SCOUT), (SCOUT,) * 2),
        samples=2,
        seed=0,
        hard=hard,
    )

    assert levels
    assert set(levels) == {hard}


def test_play_out_passes_once_ahead_after_the_opponent_passed() -> None:
    # A lead of 1 is enough: the opponent plays no more cards this round.
    opponent = replace(player((SCOUT,)), passed=True)
    state = match(player((KNIGHT,), siege=(wall(1),)), opponent)
    assert _next(state) == Pass()


def test_play_out_goes_on_to_the_end_of_the_match() -> None:
    # Passing wins round 1 by a point, and the match goes on: in round 2, the
    # AI's Knight (5) beats the opponent's Scout (3). So the score is a won
    # match, not the life round 1 won (7).
    opponent = replace(player((SCOUT,)), passed=True)
    state = match(player((KNIGHT,), siege=(wall(1),)), opponent)
    assert _play_out(state, Pass()) == baseline.WIN


def test_the_same_seed_gives_the_same_action() -> None:
    state = start_match((DECKS["humans"], DECKS["robots"]), seed=5)
    while EndRedraw() in legal_actions(state):
        state, _ = apply(state, EndRedraw())
    view = player_view(state, state.current)
    decks = (DECKS["humans"].cards, DECKS["robots"].cards)

    actions = {choose_action(view, decks=decks, samples=2, seed=9) for _ in range(3)}
    assert len(actions) == 1


@settings(deadline=None, max_examples=20)
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
    decks = (DECKS[first].cards, DECKS[second].cards)
    state = start_match((DECKS[first], DECKS[second]), seed=seed)
    while not match_over(state):
        view = player_view(state, state.current)
        if state.current == ai:
            action = choose_action(view, decks=decks, samples=1, seed=seed)
            assert action in view.legal_actions
        else:
            action = data.draw(st.sampled_from(view.legal_actions))
        state, _ = apply(state, action)

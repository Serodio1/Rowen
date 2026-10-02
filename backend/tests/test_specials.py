"""Tests for playing weather, Clear Skies and War Horn (rules, section 8).

How weather and a War Horn change a unit's strength is tested in
test_scoring.py; here, playing the cards and where they go.
"""

from collections.abc import Mapping

import pytest

from rowen.engine.actions import Action, Pass, PlayHorn, PlaySpecial, PlayUnit
from rowen.engine.cards import Ability, Card, Row, SpecialCard, SpecialKind, UnitCard
from rowen.engine.events import (
    HornPlayed,
    PlayerPassed,
    UnitDestroyed,
    WeatherCleared,
    WeatherPlayed,
    WildfirePlayed,
)
from rowen.engine.game import IllegalActionError, apply, legal_actions
from rowen.engine.rng import Rng
from rowen.engine.scoring import player_total
from rowen.engine.state import GameState, PlayerState, RowState

SNIPER = UnitCard(id="sniper", name="Sniper", rows=(Row.RANGED,), strength=6)
KNIGHT = UnitCard(id="knight", name="Knight", rows=(Row.MELEE,), strength=5)
SCOUT = UnitCard(id="scout", name="Scout", rows=(Row.MELEE,), strength=3)
CHAMPION = UnitCard(id="champion", name="Champion", rows=(Row.MELEE,), strength=8)
HUMAN = UnitCard(
    id="human",
    name="Human",
    rows=(Row.MELEE,),
    strength=4,
    ability=Ability.BOND,
    group="humans",
)
PRESIDENT = UnitCard(
    id="president", name="President", rows=(Row.MELEE,), strength=10, legend=True
)
HOARFROST = SpecialCard(id="hoarfrost", name="Hoarfrost", kind=SpecialKind.HOARFROST)
THICK_FOG = SpecialCard(id="thick-fog", name="Thick Fog", kind=SpecialKind.THICK_FOG)
DOWNPOUR = SpecialCard(id="downpour", name="Downpour", kind=SpecialKind.DOWNPOUR)
CLEAR_SKIES = SpecialCard(
    id="clear-skies", name="Clear Skies", kind=SpecialKind.CLEAR_SKIES
)
WAR_HORN = SpecialCard(id="war-horn", name="War Horn", kind=SpecialKind.WAR_HORN)
WILDFIRE = SpecialCard(id="wildfire", name="Wildfire", kind=SpecialKind.WILDFIRE)
SCARECROW = SpecialCard(id="scarecrow", name="Scarecrow", kind=SpecialKind.SCARECROW)

# Each player has a Knight (5) in melee and a Sniper (6) in ranged: 11 in all.
BOARD = {Row.MELEE: (KNIGHT,), Row.RANGED: (SNIPER,), Row.SIEGE: ()}

PLAY_HOARFROST = PlaySpecial(card="hoarfrost")
PLAY_CLEAR_SKIES = PlaySpecial(card="clear-skies")
PLAY_WILDFIRE = PlaySpecial(card="wildfire")


def player(
    hand: tuple[Card, ...] = (KNIGHT,),
    *,
    weather: tuple[SpecialCard, ...] = (),
    horns: tuple[Row, ...] = (),
    board: Mapping[Row, tuple[UnitCard, ...]] = BOARD,
) -> PlayerState:
    """Return a player with ``board`` on their side and War Horns in ``horns``.

    By default they hold a Knight, so they don't pass by themselves.
    """
    rows = {
        row: RowState(units=board[row], horn=WAR_HORN if row in horns else None)
        for row in Row
    }
    return PlayerState(deck=(), hand=hand, rows=rows, weather=weather)


def make_state(
    first: PlayerState, second: PlayerState | None = None, *, current: int = 0
) -> GameState:
    """Build a round 1 where player ``current`` plays next."""
    return GameState(
        players=(first, player() if second is None else second),
        current=current,
        round_starter=current,
        rng=Rng(seed=7),
    )


def totals(state: GameState) -> tuple[int, int]:
    return (player_total(state, 0), player_total(state, 1))


# legal_actions


def test_each_card_in_the_hand_gives_its_plays_in_order() -> None:
    state = make_state(player((HOARFROST, SNIPER, CLEAR_SKIES, WILDFIRE)))

    assert legal_actions(state) == (
        PLAY_HOARFROST,
        PlayUnit(card="sniper", row=Row.RANGED),
        PLAY_CLEAR_SKIES,
        PLAY_WILDFIRE,
        Pass(),
    )


def test_war_horn_can_go_in_any_of_the_players_rows() -> None:
    # The opponent's horn slots are all taken, but they aren't the player's.
    state = make_state(player((WAR_HORN,)), player(horns=tuple(Row)))

    assert legal_actions(state) == (
        PlayHorn(card="war-horn", row=Row.MELEE),
        PlayHorn(card="war-horn", row=Row.RANGED),
        PlayHorn(card="war-horn", row=Row.SIEGE),
        Pass(),
    )


def test_war_horn_cant_go_in_a_horn_slot_already_taken() -> None:
    state = make_state(player((WAR_HORN,), horns=(Row.RANGED,)))

    assert legal_actions(state) == (
        PlayHorn(card="war-horn", row=Row.MELEE),
        PlayHorn(card="war-horn", row=Row.SIEGE),
        Pass(),
    )


def test_war_horn_cant_be_played_when_every_horn_slot_is_taken() -> None:
    state = make_state(player((WAR_HORN,), horns=tuple(Row)))

    assert legal_actions(state) == (Pass(),)


def test_copies_of_a_special_card_give_the_same_actions_once() -> None:
    hand = (HOARFROST, WAR_HORN, HOARFROST, WAR_HORN)
    state = make_state(player(hand, horns=(Row.MELEE, Row.RANGED)))

    assert legal_actions(state) == (
        PLAY_HOARFROST,
        PlayHorn(card="war-horn", row=Row.SIEGE),
        Pass(),
    )


def test_scarecrow_cant_be_played_yet() -> None:
    state = make_state(player((SCARECROW,)))

    assert legal_actions(state) == (Pass(),)


# Weather


@pytest.mark.parametrize(
    ("card", "row"),
    [
        pytest.param(HOARFROST, Row.MELEE, id="hoarfrost"),
        pytest.param(THICK_FOG, Row.RANGED, id="thick fog"),
        pytest.param(DOWNPOUR, Row.SIEGE, id="downpour"),
    ],
)
def test_weather_goes_from_the_hand_to_the_weather_area(
    card: SpecialCard, row: Row
) -> None:
    state = make_state(player((card, KNIGHT)))

    state, events = apply(state, PlaySpecial(card=card.id))

    assert state.players[0].hand == (KNIGHT,)
    assert state.players[0].weather == (card,)
    assert events == (WeatherPlayed(player=0, card=card.id, row=row),)


def test_weather_is_kept_on_the_side_of_the_player_who_played_it() -> None:
    state = make_state(player(), player((HOARFROST, KNIGHT)), current=1)

    state, events = apply(state, PLAY_HOARFROST)

    assert state.players[0].weather == ()
    assert state.players[1].weather == (HOARFROST,)
    assert events == (WeatherPlayed(player=1, card="hoarfrost", row=Row.MELEE),)


def test_weather_sets_its_row_to_1_on_both_sides() -> None:
    state = make_state(player((HOARFROST, KNIGHT)))

    state, _ = apply(state, PLAY_HOARFROST)

    # Both Knights go from 5 to 1. The Snipers, in ranged, keep their 6.
    assert totals(state) == (7, 7)


def test_different_weather_cards_add_up() -> None:
    state = make_state(player((THICK_FOG, KNIGHT)), player(weather=(HOARFROST,)))

    state, _ = apply(state, PlaySpecial(card="thick-fog"))

    assert totals(state) == (2, 2)


def test_second_copy_of_the_same_weather_stays_but_adds_nothing() -> None:
    state = make_state(player((HOARFROST, KNIGHT)), player(weather=(HOARFROST,)))
    assert totals(state) == (7, 7)

    state, _ = apply(state, PLAY_HOARFROST)

    assert state.players[0].weather == (HOARFROST,)
    assert state.players[1].weather == (HOARFROST,)
    assert totals(state) == (7, 7)


# Clear Skies


def test_clear_skies_sends_each_weather_card_to_its_players_discard_pile() -> None:
    first = player(weather=(HOARFROST,))
    second = player((CLEAR_SKIES, KNIGHT), weather=(THICK_FOG, DOWNPOUR))
    state = make_state(first, second, current=1)

    state, events = apply(state, PLAY_CLEAR_SKIES)

    assert state.players[0].weather == state.players[1].weather == ()
    assert state.players[0].discard == (HOARFROST,)
    # The Clear Skies goes last: it is resolved once the weather is cleared.
    assert state.players[1].discard == (THICK_FOG, DOWNPOUR, CLEAR_SKIES)
    assert state.players[1].hand == (KNIGHT,)
    assert events == (WeatherCleared(player=1, card="clear-skies"),)


def test_clear_skies_gives_the_units_their_strength_back() -> None:
    state = make_state(player((CLEAR_SKIES, KNIGHT), weather=(HOARFROST,)))
    assert totals(state) == (7, 7)

    state, _ = apply(state, PLAY_CLEAR_SKIES)

    assert totals(state) == (11, 11)


def test_clear_skies_without_weather_only_goes_to_the_discard_pile() -> None:
    state = make_state(player((CLEAR_SKIES, KNIGHT)))

    state, events = apply(state, PLAY_CLEAR_SKIES)

    assert state.players[0].discard == (CLEAR_SKIES,)
    assert state.players[1].discard == ()
    assert events == (WeatherCleared(player=0, card="clear-skies"),)


# Wildfire


def test_wildfire_destroys_the_strongest_units_on_both_sides() -> None:
    # Each side has a Sniper (6), the strongest unit on the board.
    state = make_state(player((WILDFIRE, KNIGHT)))

    state, events = apply(state, PLAY_WILDFIRE)

    for side in (0, 1):
        assert state.players[side].rows[Row.MELEE].units == (KNIGHT,)
        assert state.players[side].rows[Row.RANGED].units == ()
    # The Wildfire goes last: it is resolved once the units are destroyed.
    assert state.players[0].discard == (SNIPER, WILDFIRE)
    assert state.players[1].discard == (SNIPER,)
    assert state.players[0].hand == (KNIGHT,)
    assert events == (
        WildfirePlayed(player=0, card="wildfire"),
        UnitDestroyed(side=0, row=Row.RANGED, card="sniper"),
        UnitDestroyed(side=1, row=Row.RANGED, card="sniper"),
    )


def test_wildfire_destroys_only_the_strongest_unit() -> None:
    board = {Row.MELEE: (SCOUT, CHAMPION, KNIGHT), Row.RANGED: (), Row.SIEGE: ()}
    state = make_state(player((WILDFIRE, KNIGHT)), player(board=board))

    state, events = apply(state, PLAY_WILDFIRE)

    # The other units keep their places.
    assert state.players[1].rows[Row.MELEE].units == (SCOUT, KNIGHT)
    assert state.players[1].discard == (CHAMPION,)
    assert state.players[0].rows == player().rows
    assert events[1:] == (UnitDestroyed(side=1, row=Row.MELEE, card="champion"),)


def test_wildfire_destroys_every_copy_tied_for_highest() -> None:
    board = {Row.MELEE: (), Row.RANGED: (SNIPER, SNIPER), Row.SIEGE: ()}
    state = make_state(player((WILDFIRE, KNIGHT), board=board))

    state, _ = apply(state, PLAY_WILDFIRE)

    assert state.players[0].rows[Row.RANGED].units == ()
    assert state.players[0].discard == (SNIPER, SNIPER, WILDFIRE)
    assert state.players[1].discard == (SNIPER,)


def test_wildfire_goes_by_current_strength() -> None:
    # Under Thick Fog the Snipers are 1, so the Knights (5) are the strongest.
    state = make_state(player((WILDFIRE, KNIGHT), weather=(THICK_FOG,)))

    state, events = apply(state, PLAY_WILDFIRE)

    assert events[1:] == (
        UnitDestroyed(side=0, row=Row.MELEE, card="knight"),
        UnitDestroyed(side=1, row=Row.MELEE, card="knight"),
    )


def test_wildfire_finds_every_unit_before_destroying_any() -> None:
    # Two Humans with Bond are 4 x 2 = 8 each. Once one is destroyed, the
    # other would only be 4, but it was among the strongest, so it goes too.
    board = {Row.MELEE: (HUMAN, HUMAN), Row.RANGED: (SNIPER,), Row.SIEGE: ()}
    state = make_state(player((WILDFIRE, KNIGHT)), player(board=board))

    state, _ = apply(state, PLAY_WILDFIRE)

    assert state.players[1].rows[Row.MELEE].units == ()
    assert state.players[1].discard == (HUMAN, HUMAN)


def test_wildfire_leaves_legends_out() -> None:
    # The President (10) is the strongest unit, but a Legend (D8), so the
    # Snipers (6) are destroyed.
    board = {Row.MELEE: (PRESIDENT,), Row.RANGED: (SNIPER,), Row.SIEGE: ()}
    state = make_state(player((WILDFIRE, KNIGHT)), player(board=board))

    state, events = apply(state, PLAY_WILDFIRE)

    assert state.players[1].rows[Row.MELEE].units == (PRESIDENT,)
    assert events[1:] == (
        UnitDestroyed(side=0, row=Row.RANGED, card="sniper"),
        UnitDestroyed(side=1, row=Row.RANGED, card="sniper"),
    )


def test_wildfire_with_only_legends_only_goes_to_the_discard_pile() -> None:
    board = {Row.MELEE: (PRESIDENT,), Row.RANGED: (), Row.SIEGE: ()}
    state = make_state(player((WILDFIRE, KNIGHT), board=board), player(board=board))

    state, events = apply(state, PLAY_WILDFIRE)

    assert state.players[0].rows[Row.MELEE].units == (PRESIDENT,)
    assert state.players[1].rows[Row.MELEE].units == (PRESIDENT,)
    assert state.players[0].discard == (WILDFIRE,)
    assert state.players[1].discard == ()
    assert events == (WildfirePlayed(player=0, card="wildfire"),)


def test_wildfire_goes_to_the_discard_pile_of_the_player_who_played_it() -> None:
    state = make_state(player(), player((WILDFIRE, KNIGHT)), current=1)

    state, events = apply(state, PLAY_WILDFIRE)

    assert state.players[0].discard == (SNIPER,)
    assert state.players[1].discard == (SNIPER, WILDFIRE)
    assert events[0] == WildfirePlayed(player=1, card="wildfire")


# War Horn


def test_war_horn_goes_from_the_hand_to_the_rows_horn_slot() -> None:
    state = make_state(player((WAR_HORN, KNIGHT)))

    state, events = apply(state, PlayHorn(card="war-horn", row=Row.MELEE))

    rows = state.players[0].rows
    assert rows[Row.MELEE] == RowState(units=(KNIGHT,), horn=WAR_HORN)
    assert rows[Row.RANGED] == RowState(units=(SNIPER,))
    assert state.players[0].hand == (KNIGHT,)
    assert events == (HornPlayed(player=0, card="war-horn", row=Row.MELEE),)


def test_war_horn_doubles_a_row_on_the_side_of_the_player_who_played_it() -> None:
    state = make_state(player(), player((WAR_HORN, KNIGHT)), current=1)

    state, events = apply(state, PlayHorn(card="war-horn", row=Row.RANGED))

    assert state.players[0].rows[Row.RANGED].horn is None
    assert state.players[1].rows[Row.RANGED].horn == WAR_HORN
    # Only player 1's Sniper doubles, from 6 to 12.
    assert totals(state) == (11, 17)
    assert events == (HornPlayed(player=1, card="war-horn", row=Row.RANGED),)


# The turn


def test_playing_a_special_card_ends_the_turn() -> None:
    state = make_state(player((HOARFROST, KNIGHT)))

    state, _ = apply(state, PLAY_HOARFROST)

    assert state.current == 1


def test_playing_a_copy_keeps_the_others_in_hand() -> None:
    state = make_state(player((HOARFROST, KNIGHT, HOARFROST)))

    state, _ = apply(state, PLAY_HOARFROST)

    assert state.players[0].hand == (KNIGHT, HOARFROST)


def test_playing_the_last_card_in_hand_passes() -> None:
    state = make_state(player((WAR_HORN,)))

    state, events = apply(state, PlayHorn(card="war-horn", row=Row.SIEGE))

    assert state.players[0].passed
    assert events == (
        HornPlayed(player=0, card="war-horn", row=Row.SIEGE),
        PlayerPassed(player=0),
    )


@pytest.mark.parametrize(
    "action",
    [
        pytest.param(PlaySpecial(card="war-horn"), id="war horn without a row"),
        pytest.param(PlayHorn(card="hoarfrost", row=Row.MELEE), id="weather as horn"),
        pytest.param(PlayHorn(card="war-horn", row=Row.RANGED), id="horn slot taken"),
        pytest.param(PlaySpecial(card="thick-fog"), id="card not in hand"),
        pytest.param(PlaySpecial(card="knight"), id="unit as a special card"),
        pytest.param(PlaySpecial(card="scarecrow"), id="not playable yet"),
    ],
)
def test_illegal_action_raises(action: Action) -> None:
    hand = (WAR_HORN, HOARFROST, KNIGHT, SCARECROW)
    state = make_state(player(hand, horns=(Row.RANGED,)))

    with pytest.raises(IllegalActionError, match="illegal action"):
        apply(state, action)

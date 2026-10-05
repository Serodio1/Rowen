"""Tests for how a match looks in the terminal: views, actions and events as text."""

from dataclasses import replace

import pytest

from rowen.ai.baseline import choose_action
from rowen.cli.display import action_text, card_text, event_text, view_text
from rowen.data import load_deck
from rowen.engine.actions import (
    Action,
    EndRedraw,
    Pass,
    PlayHorn,
    PlayScarecrow,
    PlaySpecial,
    PlayUnit,
    Redraw,
    Revive,
)
from rowen.engine.cards import Ability, Card, Row, SpecialCard, SpecialKind, UnitCard
from rowen.engine.events import (
    CardRedrawn,
    CardsDrawn,
    HornPlayed,
    MatchEnded,
    PlayerPassed,
    RedrawEnded,
    RoundEnded,
    ScarecrowPlayed,
    UnitDestroyed,
    UnitMustered,
    UnitPlayed,
    UnitRevived,
    WeatherCleared,
    WeatherPlayed,
    WildfirePlayed,
)
from rowen.engine.game import apply, start_match
from rowen.engine.view import (
    EventView,
    OpponentDrew,
    OpponentRedrew,
    PlayerView,
    RowView,
    SideView,
    UnitView,
    player_events,
    player_view,
)

SNIPER = UnitCard(id="sniper", name="Sniper", rows=(Row.RANGED,), strength=6)
CATAPULT = UnitCard(id="catapult", name="Catapult", rows=(Row.SIEGE,), strength=8)
SOLDIER = UnitCard(
    id="soldier",
    name="Soldier",
    rows=(Row.MELEE, Row.RANGED),
    strength=4,
    ability=Ability.AGILE,
)
PRESIDENT = UnitCard(
    id="president",
    name="President",
    rows=(Row.MELEE,),
    strength=10,
    ability=Ability.INSPIRE,
    legend=True,
)
PRIME_MINISTER = UnitCard(
    id="prime-minister",
    name="Prime Minister",
    rows=(Row.RANGED,),
    strength=7,
    legend=True,
)
SPY = UnitCard(
    id="computer-spy",
    name="Computer Spy",
    rows=(Row.MELEE,),
    strength=2,
    ability=Ability.SPY,
)
DOWNPOUR = SpecialCard(id="downpour", name="Downpour", kind=SpecialKind.DOWNPOUR)
HOARFROST = SpecialCard(id="hoarfrost", name="Hoarfrost", kind=SpecialKind.HOARFROST)
CLEAR_SKIES = SpecialCard(
    id="clear-skies", name="Clear Skies", kind=SpecialKind.CLEAR_SKIES
)
WAR_HORN = SpecialCard(id="war-horn", name="War Horn", kind=SpecialKind.WAR_HORN)
WILDFIRE = SpecialCard(id="wildfire", name="Wildfire", kind=SpecialKind.WILDFIRE)
SCARECROW = SpecialCard(id="scarecrow", name="Scarecrow", kind=SpecialKind.SCARECROW)

CARDS: tuple[Card, ...] = (
    SNIPER,
    CATAPULT,
    SOLDIER,
    PRESIDENT,
    PRIME_MINISTER,
    SPY,
    DOWNPOUR,
    HOARFROST,
    CLEAR_SKIES,
    WAR_HORN,
    WILDFIRE,
    SCARECROW,
)
NAMES = {card.id: card.name for card in CARDS}

EMPTY_ROW = RowView(units=(), horn=None, scarecrows=(), weathered=False, score=0)


def make_view() -> PlayerView:
    """Build the view of player 0 in round 2, on their turn.

    The views here are built by hand, not by the engine: the text must show
    what the view says, whatever the numbers are.
    """
    ai = SideView(
        rows={
            Row.MELEE: EMPTY_ROW,
            Row.RANGED: replace(
                EMPTY_ROW,
                units=(
                    UnitView(card=SNIPER, strength=6),
                    UnitView(card=SNIPER, strength=6),
                ),
                score=12,
            ),
            Row.SIEGE: replace(
                EMPTY_ROW,
                units=(UnitView(card=CATAPULT, strength=1),),
                weathered=True,
                score=1,
            ),
        },
        weather=(DOWNPOUR,),
        discard=(SNIPER,) * 4,
        lives=1,
        passed=True,
        redraws_left=0,
        hand_size=5,
        deck_size=12,
        total=13,
    )
    you = SideView(
        rows={
            Row.MELEE: replace(
                EMPTY_ROW,
                units=(UnitView(card=SOLDIER, strength=8),),
                horn=WAR_HORN,
                scarecrows=(SCARECROW,),
                score=8,
            ),
            Row.RANGED: replace(
                EMPTY_ROW, units=(UnitView(card=SNIPER, strength=6),), score=6
            ),
            Row.SIEGE: replace(
                EMPTY_ROW,
                units=(UnitView(card=CATAPULT, strength=1),),
                weathered=True,
                score=1,
            ),
        },
        weather=(),
        discard=(SNIPER,) * 3,
        lives=2,
        passed=False,
        redraws_left=0,
        hand_size=2,
        deck_size=14,
        total=15,
    )
    return PlayerView(
        player=0,
        hand=(SNIPER, WAR_HORN),
        players=(you, ai),
        current=0,
        round=2,
        reviving=False,
        legal_actions=(),
        match_over=False,
        winner=None,
    )


# The board


def test_the_view_shows_the_board_and_the_hand() -> None:
    assert view_text(make_view()) == "\n".join(
        [
            "Round 2: your turn",
            "AI  lives 1  hand 5  deck 12  discard 4  total 13  passed",
            "  siege    1 | Catapult 1  [weather]",
            "  ranged  12 | Sniper 6, Sniper 6",
            "  melee    0 |",
            "---------------------------------------- weather: Downpour",
            "  melee    8 | Soldier 8, Scarecrow  [War Horn]",
            "  ranged   6 | Sniper 6",
            "  siege    1 | Catapult 1  [weather]",
            "You lives 2  hand 2  deck 14  discard 3  total 15",
            "",
            "Your hand:",
            "  Sniper (6 ranged)",
            "  War Horn (special)",
        ]
    )


def test_the_player_of_the_view_is_at_the_bottom() -> None:
    view = make_view()

    lines = view_text(replace(view, player=1)).splitlines()

    assert lines[1] == "AI  lives 2  hand 2  deck 14  discard 3  total 15"
    assert lines[9] == "You lives 1  hand 5  deck 12  discard 4  total 13  passed"


@pytest.mark.parametrize(
    ("player", "current", "over", "line"),
    [
        (0, 0, False, "Round 2: your turn"),
        (0, 1, False, "Round 2: the AI's turn"),
        (1, 1, False, "Round 2: your turn"),
        (1, 0, False, "Round 2: the AI's turn"),
        (0, 0, True, "Round 2: match over"),
    ],
)
def test_the_first_line_says_whose_turn_it_is(
    player: int, current: int, over: bool, line: str
) -> None:
    view = replace(make_view(), player=player, current=current, match_over=over)

    assert view_text(view).splitlines()[0] == line


def test_swaps_left_show_while_there_are_any() -> None:
    view = make_view()
    you = replace(view.players[0], redraws_left=2)

    text = view_text(replace(view, players=(you, view.players[1])))

    assert "total 15  swaps left 2" in text


@pytest.mark.parametrize(
    ("ai_weather", "your_weather", "line"),
    [
        ((), (), "-" * 40),
        ((DOWNPOUR,), (HOARFROST,), "-" * 40 + " weather: Downpour, Hoarfrost"),
    ],
)
def test_the_middle_line_shows_the_weather_of_both_players(
    ai_weather: tuple[SpecialCard, ...],
    your_weather: tuple[SpecialCard, ...],
    line: str,
) -> None:
    view = make_view()
    you = replace(view.players[0], weather=your_weather)
    ai = replace(view.players[1], weather=ai_weather)

    lines = view_text(replace(view, players=(you, ai))).splitlines()

    assert lines[5] == line


def test_an_empty_hand_says_so() -> None:
    view = replace(make_view(), hand=())

    assert view_text(view).endswith("\n\nYour hand is empty.")


# Cards


@pytest.mark.parametrize(
    ("card", "text"),
    [
        (SNIPER, "Sniper (6 ranged)"),
        (SOLDIER, "Soldier (4 melee/ranged, agile)"),
        (PRIME_MINISTER, "Prime Minister (7 ranged, legend)"),
        (PRESIDENT, "President (10 melee, legend, inspire)"),
        (DOWNPOUR, "Downpour (weather on siege)"),
        (WAR_HORN, "War Horn (special)"),
    ],
)
def test_a_card_shows_what_a_player_needs_to_know(card: Card, text: str) -> None:
    assert card_text(card) == text


# Actions


@pytest.mark.parametrize(
    ("action", "text"),
    [
        (PlayUnit(card="sniper", row=Row.RANGED), "Play Sniper in the ranged row"),
        (PlaySpecial(card="downpour"), "Play Downpour"),
        (PlayHorn(card="war-horn", row=Row.MELEE), "Play War Horn in the melee row"),
        (
            PlayScarecrow(card="scarecrow", row=Row.RANGED, unit="sniper"),
            "Play Scarecrow in the ranged row, taking back Sniper",
        ),
        (Pass(), "Pass"),
        (Revive(card="sniper", row=Row.RANGED), "Revive Sniper in the ranged row"),
        (Redraw(card="downpour"), "Swap Downpour"),
        (EndRedraw(), "Keep this hand"),
    ],
)
def test_an_action_reads_as_a_choice(action: Action, text: str) -> None:
    assert action_text(action, NAMES) == text


# Events, as player 0 sees them


@pytest.mark.parametrize(
    ("event", "text"),
    [
        (
            UnitPlayed(player=0, card="sniper", row=Row.RANGED, side=0),
            "You played Sniper in the ranged row.",
        ),
        (
            UnitPlayed(player=1, card="computer-spy", row=Row.MELEE, side=0),
            "The AI played Computer Spy in your melee row.",
        ),
        (
            UnitPlayed(player=0, card="computer-spy", row=Row.MELEE, side=1),
            "You played Computer Spy in the AI's melee row.",
        ),
        (
            UnitRevived(player=1, card="sniper", row=Row.RANGED, side=1),
            "The AI revived Sniper in the ranged row.",
        ),
        (
            UnitRevived(player=0, card="computer-spy", row=Row.MELEE, side=1),
            "You revived Computer Spy in the AI's melee row.",
        ),
        (
            UnitMustered(player=0, card="catapult", row=Row.SIEGE, from_hand=False),
            "Catapult came from your deck to the siege row.",
        ),
        (
            UnitMustered(player=1, card="catapult", row=Row.SIEGE, from_hand=True),
            "Catapult came from the AI's hand to the siege row.",
        ),
        (
            CardsDrawn(player=0, cards=("sniper", "war-horn")),
            "You drew Sniper, War Horn.",
        ),
        (OpponentDrew(player=1, count=2), "The AI drew 2 cards."),
        (OpponentDrew(player=1, count=1), "The AI drew 1 card."),
        (
            WeatherPlayed(player=1, card="downpour", row=Row.SIEGE),
            "The AI played Downpour: weather on both siege rows.",
        ),
        (
            WeatherCleared(player=0, card="clear-skies"),
            "You played Clear Skies and cleared all weather.",
        ),
        (
            HornPlayed(player=0, card="war-horn", row=Row.MELEE),
            "You played War Horn in the melee row.",
        ),
        (
            ScarecrowPlayed(player=0, card="scarecrow", row=Row.RANGED, unit="sniper"),
            "You played Scarecrow in the ranged row and took back Sniper.",
        ),
        (WildfirePlayed(player=1, card="wildfire"), "The AI played Wildfire."),
        (
            UnitDestroyed(side=0, row=Row.RANGED, card="sniper"),
            "Sniper was destroyed in your ranged row.",
        ),
        (
            UnitDestroyed(side=1, row=Row.SIEGE, card="catapult"),
            "Catapult was destroyed in the AI's siege row.",
        ),
        (PlayerPassed(player=1), "The AI passed."),
        (
            RoundEnded(scores=(23, 19), winner=0),
            "Round over: you 23, the AI 19. You won the round.",
        ),
        (
            RoundEnded(scores=(12, 15), winner=1),
            "Round over: you 12, the AI 15. The AI won the round.",
        ),
        (
            RoundEnded(scores=(10, 10), winner=None),
            "Round over: you 10, the AI 10. It's a tie.",
        ),
        (MatchEnded(winner=0), "Match over. You won the match."),
        (MatchEnded(winner=1), "Match over. The AI won the match."),
        (MatchEnded(winner=None), "Match over. It's a draw."),
        (
            CardRedrawn(player=0, card="downpour", drawn="sniper"),
            "You swapped Downpour for Sniper.",
        ),
        (OpponentRedrew(player=1), "The AI swapped a card."),
        (RedrawEnded(player=0), "You finished swapping."),
    ],
)
def test_an_event_reads_as_one_sentence(event: EventView, text: str) -> None:
    assert event_text(event, 0, NAMES) == text


def test_each_player_reads_an_event_from_their_own_side() -> None:
    played = UnitPlayed(player=1, card="computer-spy", row=Row.MELEE, side=0)
    ended = RoundEnded(scores=(23, 19), winner=0)

    assert event_text(played, 1, NAMES) == (
        "You played Computer Spy in the AI's melee row."
    )
    assert event_text(ended, 1, NAMES) == (
        "Round over: you 19, the AI 23. The AI won the round."
    )


# With the real decks


def test_every_view_action_and_event_of_a_match_has_a_text() -> None:
    decks = (load_deck("humans"), load_deck("robots"))
    names = {card.id: card.name for deck in decks for card in deck.cards}
    state = start_match(decks, seed=7)

    while not player_view(state, 0).match_over:
        # Each player's view, with the legal actions of whoever plays now.
        for player in (0, 1):
            view = player_view(state, player)
            assert view_text(view)
            for action in view.legal_actions:
                assert action_text(action, names)

        action = choose_action(player_view(state, state.current))
        state, events = apply(state, action)
        for player in (0, 1):
            for event in player_events(events, player):
                assert event_text(event, player, names)

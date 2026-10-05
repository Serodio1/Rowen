"""How a match looks in the terminal: the player view, actions and events as text.

The functions here only turn data into text. They read nothing and print
nothing, so they are tested like the engine.

The text comes only from the player view and from the events as the player
may see them, so the AI's hand never shows. And nothing is worked out here:
strengths, scores, the legal actions and who won all come from the engine
(ADR 0002).

Actions and events name cards by id, so the functions that show them take
``names``: the name of every card, by id.
"""

from collections.abc import Mapping

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
from rowen.engine.cards import WEATHER_ROWS, Card, Row, SpecialCard
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
from rowen.engine.view import (
    EventView,
    OpponentDrew,
    OpponentRedrew,
    PlayerView,
    RowView,
    SideView,
)

# The line between the two sides of the board.
MIDDLE = "-" * 40


def view_text(view: PlayerView) -> str:
    """Return the board and the hand, as the player of the view sees them.

    The AI's side is on top and the player's own side at the bottom, so the
    two melee rows meet in the middle, as on a real table.
    """
    you = view.player
    ai = 1 - you
    weather = (*view.players[ai].weather, *view.players[you].weather)
    middle = MIDDLE
    if weather:
        middle += " weather: " + ", ".join(card.name for card in weather)

    lines = [
        _turn_text(view),
        _side_text("AI", view.players[ai]),
        *(_row_text(row, view.players[ai].rows[row]) for row in reversed(Row)),
        middle,
        *(_row_text(row, view.players[you].rows[row]) for row in Row),
        _side_text("You", view.players[you]),
        "",
    ]
    if view.hand:
        lines.append("Your hand:")
        lines.extend(f"  {card_text(card)}" for card in view.hand)
    else:
        lines.append("Your hand is empty.")
    return "\n".join(lines)


def card_text(card: Card) -> str:
    """Return a card with what a player needs to know about it.

    For example ``Soldier (4 melee/ranged, agile)`` or
    ``Downpour (weather on siege)``.
    """
    if isinstance(card, SpecialCard):
        if card.kind in WEATHER_ROWS:
            return f"{card.name} (weather on {WEATHER_ROWS[card.kind]})"
        return f"{card.name} (special)"

    details = [f"{card.strength} {'/'.join(card.rows)}"]
    if card.legend:
        details.append("legend")
    if card.ability is not None:
        details.append(card.ability)
    return f"{card.name} ({', '.join(details)})"


def action_text(action: Action, names: Mapping[str, str]) -> str:
    """Return an action as one of the player's choices.

    For example ``Play Sniper in the ranged row``.

    Every kind of action is named here, so mypy reports a missing return when
    a new kind has no text yet.
    """
    match action:
        case PlayUnit():
            return f"Play {names[action.card]} in the {action.row} row"
        case PlaySpecial():
            return f"Play {names[action.card]}"
        case PlayHorn():
            return f"Play {names[action.card]} in the {action.row} row"
        case PlayScarecrow():
            return (
                f"Play {names[action.card]} in the {action.row} row,"
                f" taking back {names[action.unit]}"
            )
        case Pass():
            return "Pass"
        case Revive():
            return f"Revive {names[action.card]} in the {action.row} row"
        case Redraw():
            return f"Swap {names[action.card]}"
        # The last kind left, so the match never falls through.
        case EndRedraw():  # pragma: no branch
            return "Keep this hand"


def event_text(event: EventView, viewer: int, names: Mapping[str, str]) -> str:
    """Return an event as one sentence for the player ``viewer``.

    The event must be one that ``viewer`` may see, as ``player_events``
    returns it: a ``CardsDrawn`` of the AI would show the cards it drew.

    Every kind of event is named here, so mypy reports a missing return when
    a new kind has no text yet.
    """
    match event:
        case UnitPlayed():
            where = _where(event.row, event.side, event.player, viewer)
            return f"{_who(event.player, viewer)} played {names[event.card]} {where}."
        case UnitRevived():
            where = _where(event.row, event.side, event.player, viewer)
            return f"{_who(event.player, viewer)} revived {names[event.card]} {where}."
        case UnitMustered():
            place = "hand" if event.from_hand else "deck"
            return (
                f"{names[event.card]} came from {_whose(event.player, viewer)}"
                f" {place} to the {event.row} row."
            )
        case CardsDrawn():
            cards = ", ".join(names[card] for card in event.cards)
            return f"{_who(event.player, viewer)} drew {cards}."
        case OpponentDrew():
            cards = "1 card" if event.count == 1 else f"{event.count} cards"
            return f"{_who(event.player, viewer)} drew {cards}."
        case WeatherPlayed():
            return (
                f"{_who(event.player, viewer)} played {names[event.card]}:"
                f" weather on both {event.row} rows."
            )
        case WeatherCleared():
            return (
                f"{_who(event.player, viewer)} played {names[event.card]}"
                " and cleared all weather."
            )
        case HornPlayed():
            return (
                f"{_who(event.player, viewer)} played {names[event.card]}"
                f" in the {event.row} row."
            )
        case ScarecrowPlayed():
            return (
                f"{_who(event.player, viewer)} played {names[event.card]}"
                f" in the {event.row} row and took back {names[event.unit]}."
            )
        case WildfirePlayed():
            return f"{_who(event.player, viewer)} played {names[event.card]}."
        case UnitDestroyed():
            return (
                f"{names[event.card]} was destroyed in"
                f" {_whose(event.side, viewer)} {event.row} row."
            )
        case PlayerPassed():
            return f"{_who(event.player, viewer)} passed."
        case RoundEnded():
            scores = f"you {event.scores[viewer]}, the AI {event.scores[1 - viewer]}"
            if event.winner is None:
                return f"Round over: {scores}. It's a tie."
            return f"Round over: {scores}. {_who(event.winner, viewer)} won the round."
        case MatchEnded():
            if event.winner is None:
                return "Match over. It's a draw."
            return f"Match over. {_who(event.winner, viewer)} won the match."
        case CardRedrawn():
            return (
                f"{_who(event.player, viewer)} swapped {names[event.card]}"
                f" for {names[event.drawn]}."
            )
        case OpponentRedrew():
            return f"{_who(event.player, viewer)} swapped a card."
        # The last kind left, so the match never falls through.
        case RedrawEnded():  # pragma: no branch
            return f"{_who(event.player, viewer)} finished swapping."


def _turn_text(view: PlayerView) -> str:
    """Return the round and whose turn it is."""
    if view.match_over:
        turn = "match over"
    elif view.current == view.player:
        turn = "your turn"
    else:
        turn = "the AI's turn"
    return f"Round {view.round}: {turn}"


def _side_text(label: str, side: SideView) -> str:
    """Return what both players may count of one player, like their lives."""
    text = (
        f"{label:<4}lives {side.lives}  hand {side.hand_size}"
        f"  deck {side.deck_size}  discard {len(side.discard)}  total {side.total}"
    )
    if side.redraws_left > 0:
        text += f"  swaps left {side.redraws_left}"
    if side.passed:
        text += "  passed"
    return text


def _row_text(row: Row, view: RowView) -> str:
    """Return one row: its score, its units with their strength, and the rest.

    For example ``  melee    8 | Sniper 6, Scarecrow  [War Horn]  [weather]``.
    """
    cards = [f"{unit.card.name} {unit.strength}" for unit in view.units]
    cards.extend(scarecrow.name for scarecrow in view.scarecrows)
    text = f"  {row:<6} {view.score:>3} | {', '.join(cards)}"
    if view.horn is not None:
        text += f"  [{view.horn.name}]"
    if view.weathered:
        text += "  [weather]"
    # An empty row would end in a space.
    return text.rstrip()


def _who(player: int, viewer: int) -> str:
    """Return a player as the subject of a sentence: ``You`` or ``The AI``."""
    return "You" if player == viewer else "The AI"


def _whose(player: int, viewer: int) -> str:
    """Return a player as an owner: ``your`` or ``the AI's``."""
    return "your" if player == viewer else "the AI's"


def _where(row: Row, side: int, player: int, viewer: int) -> str:
    """Return the row a unit went in, and whose side it is on when it isn't the
    player's own: a Spy's."""
    if side == player:
        return f"in the {row} row"
    return f"in {_whose(side, viewer)} {row} row"

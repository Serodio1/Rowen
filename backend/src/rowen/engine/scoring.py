"""Strength and score: what the units on the board are worth (rules, section 6).

Strength and score are never stored in the state. They are worked out from the
board every time they are needed, so they can never be out of date.
"""

from rowen.engine.cards import WEATHER_ROWS, Ability, Row, UnitCard
from rowen.engine.state import GameState, RowState


def weathered_rows(state: GameState) -> frozenset[Row]:
    """Return the rows under weather, which are the same on both sides.

    Each weather card is kept on the side of the player who played it, but it
    affects both players. A second copy of the same weather adds nothing.
    """
    return frozenset(
        WEATHER_ROWS[card.kind] for player in state.players for card in player.weather
    )


def unit_strength(unit: UnitCard, row: RowState, *, weathered: bool) -> int:
    """Return the current strength of a unit, in the order of the rules.

    Args:
        unit: One of the units in ``row``.
        row: The row the unit is in, with the units it works with.
        weathered: Whether the row is under weather.
    """
    # Legends are immune to everything below.
    if unit.legend:
        return unit.strength

    # 1 and 2: the base strength, or 1 under weather.
    strength = 1 if weathered else unit.strength

    # 3: Bond. The count includes the unit itself.
    if unit.ability is Ability.BOND:
        strength *= sum(
            other.ability is Ability.BOND and other.group == unit.group
            for other in row.units
        )

    # 4: Inspire, +1 for each other unit with it. The unit is in the row too,
    # so a unit with Inspire doesn't count itself.
    inspiring = sum(other.ability is Ability.INSPIRE for other in row.units)
    if unit.ability is Ability.INSPIRE:
        inspiring -= 1
    strength += inspiring

    # 5: War Horn.
    if row.horn is not None:
        strength *= 2

    return strength


def row_score(row: RowState, *, weathered: bool) -> int:
    """Return a row's score: the sum of its units' current strength."""
    return sum(unit_strength(unit, row, weathered=weathered) for unit in row.units)


def player_total(state: GameState, player: int) -> int:
    """Return a player's total: the sum of their three rows' scores.

    Args:
        state: The match.
        player: The player's index, 0 or 1.
    """
    weather = weathered_rows(state)
    return sum(
        row_score(row_state, weathered=row in weather)
        for row, row_state in state.players[player].rows.items()
    )

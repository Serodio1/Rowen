"""Card definitions: what each card is, independent of any deck or match.

A definition says what a card *is*, for example "the Sniper is a unit with
strength 6 that goes in the ranged row". How many copies of it a deck holds
belongs to the deck, not to the card.
"""

from dataclasses import dataclass
from enum import StrEnum


class Row(StrEnum):
    """A row of the board (rules, section 2)."""

    MELEE = "melee"
    RANGED = "ranged"
    SIEGE = "siege"


class Ability(StrEnum):
    """A unit ability (rules, section 7). A unit has at most one."""

    AGILE = "agile"
    SPY = "spy"
    MEDIC = "medic"
    MUSTER = "muster"
    BOND = "bond"
    INSPIRE = "inspire"


class SpecialKind(StrEnum):
    """The effect of a special card (rules, section 8)."""

    HOARFROST = "hoarfrost"
    THICK_FOG = "thick-fog"
    DOWNPOUR = "downpour"
    CLEAR_SKIES = "clear-skies"
    WAR_HORN = "war-horn"
    WILDFIRE = "wildfire"
    SCARECROW = "scarecrow"


# The rows an Agile unit can be played in.
AGILE_ROWS = (Row.MELEE, Row.RANGED)

# Abilities that need a group: the cards that share it bond or muster together.
GROUP_ABILITIES = frozenset({Ability.BOND, Ability.MUSTER})

# The only abilities a Legend may have (rules, section 7.3, decision D6).
LEGEND_ABILITIES = frozenset({None, Ability.SPY, Ability.MEDIC, Ability.INSPIRE})


@dataclass(frozen=True, kw_only=True)
class UnitCard:
    """A unit card: it is played on a row and has strength.

    Creating a card checks that it follows the rules, so an invalid card can
    never exist in the program.

    Attributes:
        id: Unique identifier, lowercase with hyphens (``"prime-minister"``).
        name: The name shown to the player (``"Prime Minister"``).
        rows: The rows the unit can be played in; only Agile units have two.
        strength: Base strength, before weather and abilities.
        ability: The unit's ability, if it has one.
        group: Bond or Muster group; cards with the same group work together.
        legend: Whether the unit is a Legend, immune to specials and abilities.
    """

    id: str
    name: str
    rows: tuple[Row, ...]
    strength: int
    ability: Ability | None = None
    group: str | None = None
    legend: bool = False

    def __post_init__(self) -> None:
        if self.strength < 0:
            raise ValueError(f"{self.id}: strength can't be negative")

        if self.ability is Ability.AGILE:
            if self.rows != AGILE_ROWS:
                raise ValueError(f"{self.id}: an Agile unit goes in melee or ranged")
        elif len(self.rows) != 1:
            raise ValueError(f"{self.id}: a unit that isn't Agile has exactly one row")

        needs_group = self.ability in GROUP_ABILITIES
        if needs_group and self.group is None:
            raise ValueError(f"{self.id}: a Bond or Muster unit needs a group")
        if not needs_group and self.group is not None:
            raise ValueError(f"{self.id}: only Bond and Muster units have a group")

        if self.legend and self.ability not in LEGEND_ABILITIES:
            raise ValueError(f"{self.id}: a Legend can only have Spy, Medic or Inspire")


@dataclass(frozen=True, kw_only=True)
class SpecialCard:
    """A special card: it has no strength, only an effect.

    Attributes:
        id: Unique identifier, lowercase with hyphens (``"thick-fog"``).
        name: The name shown to the player (``"Thick Fog"``).
        kind: Which effect the card has.
    """

    id: str
    name: str
    kind: SpecialKind


# Any card, unit or special.
type Card = UnitCard | SpecialCard

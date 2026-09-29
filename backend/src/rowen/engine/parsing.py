"""Turn plain data, as read from JSON, into cards and decks.

The functions here receive data that is already in memory (dicts, lists,
strings and numbers) and never read files, so the engine has no I/O (ADR 0003).
Reading the files is the job of ``rowen.data``.

The data comes from outside the program, so nothing about it is trusted: every
field is checked, and an error says what is wrong and where, for example
``units[2]: unknown fields: abilty``.
"""

from collections.abc import Mapping, Set

from rowen.engine.cards import Ability, Row, SpecialCard, SpecialKind, UnitCard
from rowen.engine.decks import Deck

DECK_FIELDS = frozenset({"id", "name", "units", "specials"})
UNIT_FIELDS = frozenset({"id", "name", "rows", "strength", "copies"})
OPTIONAL_UNIT_FIELDS = frozenset({"ability", "group", "legend"})
SPECIAL_FIELDS = frozenset({"id", "name", "kind"})


def parse_specials(data: object) -> dict[str, SpecialCard]:
    """Create the special cards from a list of JSON objects.

    Special cards are neutral: they are defined once and every deck says how
    many copies it has.

    Returns:
        The special cards, by id.
    """
    if not isinstance(data, list):
        raise ValueError(f"expected a list of special cards, got {data!r}")

    specials: dict[str, SpecialCard] = {}
    for index, entry in enumerate(data):
        try:
            fields = _object(entry, required=SPECIAL_FIELDS)
            special = SpecialCard(
                id=_get(fields, "id", str),
                name=_get(fields, "name", str),
                kind=SpecialKind(_get(fields, "kind", str)),
            )
        except ValueError as error:
            raise ValueError(f"[{index}]: {error}") from error
        if special.id in specials:
            raise ValueError(
                f"[{index}]: another special card uses the id {special.id}"
            )
        specials[special.id] = special
    return specials


def parse_deck(data: object, specials: Mapping[str, SpecialCard]) -> Deck:
    """Create a deck from a JSON object.

    Args:
        data: The deck: its units (with the number of copies of each) and the
            number of copies of each special card.
        specials: Every special card, by id, as returned by `parse_specials`.
    """
    fields = _object(data, required=DECK_FIELDS)
    units = _parse_units(_get(fields, "units", list))
    special_cards = _parse_special_copies(_get(fields, "specials", dict), specials)
    return Deck(
        id=_get(fields, "id", str),
        name=_get(fields, "name", str),
        cards=(*units, *special_cards),
    )


def _parse_units(entries: list[object]) -> list[UnitCard]:
    """Create the unit cards of a deck, one per copy."""
    units: list[UnitCard] = []
    for index, entry in enumerate(entries):
        try:
            fields = _object(entry, required=UNIT_FIELDS, optional=OPTIONAL_UNIT_FIELDS)
            unit = UnitCard(
                id=_get(fields, "id", str),
                name=_get(fields, "name", str),
                rows=tuple(Row(row) for row in _get(fields, "rows", list)),
                strength=_get(fields, "strength", int),
                ability=(
                    Ability(_get(fields, "ability", str))
                    if "ability" in fields
                    else None
                ),
                group=_get(fields, "group", str) if "group" in fields else None,
                legend=_get(fields, "legend", bool) if "legend" in fields else False,
            )
            copies = _copies(fields["copies"])
        except ValueError as error:
            raise ValueError(f"units[{index}]: {error}") from error
        units += [unit] * copies
    return units


def _parse_special_copies(
    copies_by_id: dict[str, object], specials: Mapping[str, SpecialCard]
) -> list[SpecialCard]:
    """Create the special cards of a deck, one per copy."""
    cards: list[SpecialCard] = []
    for special_id, copies in copies_by_id.items():
        if special_id not in specials:
            raise ValueError(f"specials: unknown special card {special_id}")
        try:
            cards += [specials[special_id]] * _copies(copies)
        except ValueError as error:
            raise ValueError(f"specials.{special_id}: {error}") from error
    return cards


def _object(
    data: object, *, required: Set[str], optional: Set[str] = frozenset()
) -> dict[str, object]:
    """Check that data is a JSON object with every required field and no others.

    An unknown field is an error, so a typo such as ``"abilty"`` is caught
    instead of being ignored.
    """
    if not isinstance(data, dict):
        raise ValueError(f"expected an object, got {data!r}")
    missing = required - data.keys()
    if missing:
        raise ValueError(f"missing fields: {', '.join(sorted(missing))}")
    unknown = data.keys() - required - optional
    if unknown:
        raise ValueError(f"unknown fields: {', '.join(sorted(unknown))}")
    return data


def _get[T](fields: Mapping[str, object], key: str, kind: type[T]) -> T:
    """Return a field, checking that its value has the expected type."""
    value = fields[key]
    if not isinstance(value, kind):
        raise ValueError(f"{key} must be of type {kind.__name__}, got {value!r}")
    return value


def _copies(value: object) -> int:
    """Check a number of copies: a whole number, at least 1."""
    if not isinstance(value, int) or value < 1:
        raise ValueError(f"copies must be a whole number of at least 1, got {value!r}")
    return value

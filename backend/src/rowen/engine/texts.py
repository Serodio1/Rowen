"""What each card does, in words, for the player (rules, sections 7 and 8).

The texts are here, beside the rules they tell of, so a client shows them
without knowing the rules (ADR 0002): when a rule changes, its text changes
in the same place. A new ability, special card or passive needs its text
here too: ``describe`` and the clients look them up, and a test checks that
every one has one.
"""

from collections.abc import Mapping

from rowen.engine.cards import WEATHER_ROWS, Ability, Card, SpecialKind, UnitCard
from rowen.engine.decks import Passive

# What each ability does (rules, section 7).
ABILITY_TEXTS: Mapping[Ability, str] = {
    Ability.AGILE: "Agile: can be played in the melee or the ranged row.",
    Ability.SPY: (
        "Spy: goes on the opponent's side, where its strength counts for them. "
        "Whoever plays it draws 2 cards."
    ),
    Ability.MEDIC: (
        "Medic: plays at once a unit, not a Legend, from your own discard pile."
    ),
    Ability.MUSTER: (
        "Muster: plays at once every card of its group from your deck and hand."
    ),
    Ability.BOND: (
        "Bond: its strength is multiplied by the number of units in its row "
        "that share its bond."
    ),
    Ability.INSPIRE: "Inspire: gives +1 to every other unit in its row.",
}

# What a Legend is (rules, section 7.3).
LEGEND_TEXT = (
    "Legend: immune to weather, War Horn, Inspire, Wildfire, Scarecrow and Medic."
)

# What each special card does (rules, section 8). A weather card's text
# names the rows it hits, as the rules do (WEATHER_ROWS).
SPECIAL_TEXTS: Mapping[SpecialKind, str] = {
    **{
        kind: (
            f"Weather: every unit in the {row} rows, on both sides, has strength "
            "1, but not a Legend. A second copy changes nothing."
        )
        for kind, row in WEATHER_ROWS.items()
    },
    SpecialKind.CLEAR_SKIES: "Removes every weather card in play.",
    SpecialKind.WAR_HORN: (
        "Goes in the horn slot of one of your rows, and doubles the strength of "
        "its units, but not of a Legend."
    ),
    SpecialKind.WILDFIRE: (
        "Destroys the strongest units on the board, on both sides. Legends are "
        "never destroyed."
    ),
    SpecialKind.SCARECROW: (
        "Takes a unit on your side, not a Legend, back to your hand, and stays "
        "in its place with strength 0."
    ),
}


# What each faction's passive does (rules, section 12).
PASSIVE_TEXTS: Mapping[Passive, str] = {
    Passive.DRAW_ON_ROUND_WIN: "Draws a card after winning a round.",
    Passive.KEEP_A_UNIT: (
        "After each round, one random unit stays on the board, but not a "
        "Legend or a Spy."
    ),
}


def describe(card: Card) -> tuple[str, ...]:
    """Return what the card does, one sentence per thing: none for a unit
    with no ability that isn't a Legend.
    """
    if isinstance(card, UnitCard):
        texts = [LEGEND_TEXT] if card.legend else []
        if card.ability is not None:
            texts.append(ABILITY_TEXTS[card.ability])
        return tuple(texts)
    return (SPECIAL_TEXTS[card.kind],)

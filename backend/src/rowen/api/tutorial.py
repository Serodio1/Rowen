"""The tutorial's script: a short, always identical match, told step by step.

The tutorial is a match recorded once and played back in the page, with no API
calls (ADR 0020). This module holds what is written by hand: the script, which
says what the player does at each step and how the AI answers, and the seed
that makes the engine deal the cards the script needs. Playing the script with
the engine and recording what the player sees comes after, in the generator;
the rules stay in the engine (ADR 0002).

The match is the Humans (the player, index 0) against the Robots (the AI).
"""

from dataclasses import dataclass

from rowen.api import schemas
from rowen.data import load_deck
from rowen.engine.public import (
    Action,
    EndRedraw,
    Pass,
    PlayHorn,
    PlaySpecial,
    PlayUnit,
    Revive,
    Row,
    apply,
    player_view,
    start_match,
)

HUMAN = 0
AI = 1

# What a balloon points at: "rows", "hand", "total", "lives", "leader",
# "discard", "weather", "row:<melee|ranged|siege>" or "card:<card id>". The
# page finds it by a ``data-tutorial`` attribute with the same text.
Target = str

# The first seed, from 0, where the player starts round 1 and holds a Soldier,
# a Sniper, an Informant, Clear Skies and a Medic, and the AI holds Hoarfrost.
# The hands: the player's, after the redraw, are smart-guy, plane, human x2,
# war-horn, informant, medic, clear-skies, sniper and soldier; the AI's are
# war-horn, robot x3, mechanic, hoarfrost, server, machine, drone and
# scarecrow. Changing the cards or the deal means searching for a new seed.
SEED = 59


@dataclass(frozen=True)
class ScriptStep:
    """One step of the tutorial: a balloon, and what happens next.

    Attributes:
        text: What the balloon says.
        target: What the balloon points at.
        action: The action the player is asked to play, or ``None`` on a step
            that only explains and has a Next button.
        ai: The actions the AI plays after it, one after the other.
    """

    text: str
    target: Target
    action: Action | None
    ai: tuple[Action, ...] = ()


SCRIPT: tuple[ScriptStep, ...] = (
    # Round 1.
    ScriptStep(
        "Your rows are at the bottom: melee, ranged and siege. "
        "The AI's are at the top.",
        "rows",
        None,
    ),
    ScriptStep("These are your cards. A unit's number is its strength.", "hand", None),
    ScriptStep(
        "Play the Soldier in your melee row.",
        "card:soldier",
        PlayUnit(card="soldier", row=Row.MELEE),
        (PlayUnit(card="robot", row=Row.MELEE),),
    ),
    ScriptStep(
        "Each row adds up its units. Your total is the sum of your rows.",
        "total",
        None,
    ),
    ScriptStep(
        "Play the Sniper in your ranged row.",
        "card:sniper",
        PlayUnit(card="sniper", row=Row.RANGED),
        (PlayUnit(card="robot", row=Row.MELEE),),
    ),
    # The AI answers with Hoarfrost: the next two steps show what it does.
    ScriptStep(
        "Play the Informant. It goes on the AI's side and gives it 3 points, "
        "but you draw 2 cards.",
        "card:informant",
        PlayUnit(card="informant", row=Row.MELEE),
        (PlaySpecial(card="hoarfrost"),),
    ),
    ScriptStep(
        "Cards are what you play with all match: you don't draw new ones each round.",
        "hand",
        None,
    ),
    ScriptStep(
        "Hoarfrost: every unit in the melee row, on both sides, now has strength 1.",
        "row:melee",
        None,
    ),
    ScriptStep(
        "Play Clear Skies to remove all weather.",
        "card:clear-skies",
        PlaySpecial(card="clear-skies"),
        # A War Horn on its empty siege row adds nothing: the AI can't get
        # past the player's 10 with the cards it holds, so it plays this one.
        (PlayHorn(card="war-horn", row=Row.SIEGE),),
    ),
    ScriptStep(
        "You are ahead. Pass: you play no more cards this round, but the AI still can.",
        "total",
        Pass(),
        (Pass(),),
    ),
    # Round 2: the winner of a round starts the next, so the player does.
    ScriptStep(
        "You won the round: the AI loses a life. Win 2 rounds to win the match.",
        "lives",
        None,
    ),
    ScriptStep(
        "Your leader, The Commander, gives you 1 card for each round you win.",
        "leader",
        None,
    ),
    ScriptStep(
        "Round 2, and you start. Play the Medic. It brings back a unit from "
        "your discard pile.",
        "card:medic",
        PlayUnit(card="medic", row=Row.SIEGE),
    ),
    ScriptStep(
        "Choose the Sniper: it comes back to the board.",
        "discard",
        Revive(card="sniper", row=Row.RANGED),
        (Pass(),),
    ),
    ScriptStep(
        "The AI passed and you are ahead. Pass to win the match.",
        "total",
        Pass(),
    ),
)


class TutorialStep(schemas.Schema):
    """One step as the page gets it: the balloon, and the match as it is then.

    Attributes:
        text: What the balloon says.
        target: What the balloon points at (see ``Target``).
        view: The match after the step's actions, as the player sees it, with
            the legal actions cut down to the asked one.
        moves: The actions played in this step, the player's and the AI's,
            for the page to animate.
    """

    text: str
    target: str
    view: schemas.PlayerView
    moves: tuple[schemas.MovePlayed, ...]


class Tutorial(schemas.Schema):
    """The whole tutorial: what ``tutorial.json`` holds."""

    steps: tuple[TutorialStep, ...]


class ScriptError(ValueError):
    """The script asks for something the engine can't do at that step."""


def generate(script: tuple[ScriptStep, ...] = SCRIPT, seed: int = SEED) -> Tutorial:
    """Play ``script`` with the engine and record what the player sees.

    Both players end their redraw first, so the redraw is not a step. Each
    step records the view before its actions, with the legal actions cut down
    to the asked one, and then the moves: the player's action and the AI's.

    Raises:
        ScriptError: If a step points at a card the player doesn't hold, or
            asks for an action that isn't legal, naming the step (from 1).
    """
    state = start_match((load_deck("humans"), load_deck("robots")), seed)
    state, _ = apply(state, EndRedraw())
    state, _ = apply(state, EndRedraw())
    steps: list[TutorialStep] = []
    for number, step in enumerate(script, start=1):
        view = player_view(state, HUMAN)
        card = step.target.removeprefix("card:")
        if step.target.startswith("card:") and card not in {c.id for c in view.hand}:
            raise ScriptError(f"step {number}: {card} is not in the player's hand")
        shown = schemas.from_view(view)
        asked: tuple[schemas.Action, ...] = ()
        if step.action is not None:
            if step.action not in view.legal_actions:
                raise ScriptError(f"step {number}: {step.action} is not legal")
            asked = (schemas.from_action(step.action),)
        moves: list[schemas.MovePlayed] = []
        for action in (() if step.action is None else (step.action,)) + step.ai:
            state, events = apply(state, action)
            moves.append(
                schemas.MovePlayed(
                    events=schemas.from_events(events, HUMAN),
                    view=schemas.from_view(player_view(state, HUMAN)),
                )
            )
        steps.append(
            TutorialStep(
                text=step.text,
                target=step.target,
                view=shown.model_copy(update={"legal_actions": asked}),
                moves=tuple(moves),
            )
        )
    return Tutorial(steps=tuple(steps))

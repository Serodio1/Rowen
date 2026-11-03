"""Variants of the Hard AI's play-outs, measured against the Hard AI of main.

Not for main: a throwaway measuring bench (branch experiment/hard-ai).
VARIANT is a comma list of flags, e.g. "giveup=10,cards".
  giveup[=N]: in a play-out, a player N (10) or more points behind, not on
    their last life, gives up the round (playing a Spy first, if they hold one).
  cards: with giveup, only give up when not behind in cards in the hand.
  spies: in a play-out, a player holding a Spy plays it first, as people do
    (the baseline's board-only score almost never picks one), unless the
    opponent has passed.
"""

import os

from rowen.ai import baseline, montecarlo
from rowen.engine.abilities import on_opponent_side
from rowen.engine.actions import Pass, PlayUnit
from rowen.engine.game import legal_actions

FLAGS = dict(
    (f.split("=") + [""])[:2] for f in os.environ.get("VARIANT", "").split(",") if f
)
ORIGINAL_NEXT = montecarlo._next


def _spy(state, action):
    if not isinstance(action, PlayUnit):
        return False
    hand = state.players[state.current].hand
    card = next(c for c in hand if c.id == action.card)
    return on_opponent_side(card)


def variant_next(state):
    player = state.current
    me, them = state.players[player], state.players[1 - player]
    if "giveup" in FLAGS and not state.reviving and not them.passed and me.lives > 1:
        behind = -baseline.player_lead(state, player)
        cards_ok = "cards" not in FLAGS or len(me.hand) >= len(them.hand)
        if behind >= int(FLAGS["giveup"] or 10) and cards_ok:
            spies = tuple(a for a in legal_actions(state) if _spy(state, a))
            return baseline.best(state, spies) if spies else Pass()
    if "spies" in FLAGS and not state.reviving and not them.passed:
        spies = tuple(a for a in legal_actions(state) if _spy(state, a))
        if spies:
            return baseline.best(state, spies)
    return ORIGINAL_NEXT(state)


def choose(view, level, decks, seed):
    """The arena's choose: "hard" = the variant, "normal" = main's Hard."""
    if level == "easy":
        return baseline.choose_action(view)
    montecarlo._next = variant_next if level == "hard" else ORIGINAL_NEXT
    try:
        return montecarlo.choose_action(
            view, decks=decks, samples=montecarlo.HARD_SAMPLES, seed=seed
        )
    finally:
        montecarlo._next = ORIGINAL_NEXT

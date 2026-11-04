"""Variants of the Hard AI's play-outs, measured against the Hard AI of main.

Not for main: a throwaway measuring bench (branch experiment/hard-ai).
VARIANT is a comma list of flags, e.g. "giveup=10,cards".
  giveup[=N]: in a play-out, a player N (10) or more points behind, not on
    their last life, gives up the round (playing a Spy first, if they hold one).
  cards: with giveup, only give up when not behind in cards in the hand.
  spies: in a play-out, a player holding a Spy plays it first, as people do
    (the baseline's board-only score almost never picks one), unless the
    opponent has passed.
  scare: in a play-out, a player plays a Scarecrow on a Spy on their own
    side (the opponent's), unless the opponent has passed.
  redraw: before round 1, the Hard AI also swaps a Bond card without its
    pair in the hand, then its weakest plain unit (no ability, not a Legend)
    if it is weaker than the average unit left in its deck list.
  ward: the Hard AI plays a Ward unit first (before thinking) while its
    melee row (where every Spy goes) has none, the opponent hasn't passed,
    and the opponent's deck list may still hide a Spy.
"""

import os

from rowen.ai import baseline, montecarlo
from rowen.engine.abilities import on_opponent_side
from rowen.engine.actions import EndRedraw, Pass, PlayScarecrow, PlayUnit, Redraw
from rowen.engine.cards import Ability, Row, UnitCard
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
    if "scare" in FLAGS and not state.reviving and not them.passed:
        scares = tuple(
            a for a in legal_actions(state)
            if isinstance(a, PlayScarecrow) and on_opponent_side(
                next(u for u in me.rows[a.row].units if u.id == a.unit)
            )
        )
        if scares:
            return scares[0]
    if "spies" in FLAGS and not state.reviving and not them.passed:
        spies = tuple(a for a in legal_actions(state) if _spy(state, a))
        if spies:
            return baseline.best(state, spies)
    return ORIGINAL_NEXT(state)


def choose(view, level, decks, seed):
    """The arena's choose: "hard" = the variant, "normal" = main's Hard."""
    if level == "easy":
        return baseline.choose_action(view)
    if level == "hard" and "redraw" in FLAGS and EndRedraw() in view.legal_actions:
        return _redraw(view, decks[view.player])
    if level == "hard" and "ward" in FLAGS:
        ward = _ward(view, decks)
        if ward is not None:
            return ward
    montecarlo._next = variant_next if level == "hard" else ORIGINAL_NEXT
    try:
        return montecarlo.choose_action(
            view, decks=decks, samples=montecarlo.HARD_SAMPLES, seed=seed
        )
    finally:
        montecarlo._next = ORIGINAL_NEXT


def _redraw(view, deck):
    first = baseline._redraw(view)
    if first != EndRedraw():
        return first
    hand = view.hand
    units = [c for c in hand if isinstance(c, UnitCard)]
    lonely = [
        c for c in units
        if c.ability is Ability.BOND
        and sum(o.ability is Ability.BOND and o.group == c.group for o in units) == 1
    ]
    left = list(deck)
    for c in hand:
        if c in left:
            left.remove(c)
    pool = [c.strength for c in left if isinstance(c, UnitCard)]
    average = sum(pool) / len(pool) if pool else 0
    plain = [c for c in units if c.ability is None and not c.legend and c.strength < average]
    for c in sorted(lonely, key=lambda c: c.strength) + sorted(plain, key=lambda c: c.strength):
        if Redraw(card=c.id) in view.legal_actions:
            return Redraw(card=c.id)
    return EndRedraw()


def _ward(view, decks):
    me, them = view.players[view.player], view.players[1 - view.player]
    if view.reviving or them.passed or EndRedraw() in view.legal_actions:
        return None
    if any(u.card.ability is Ability.WARD for u in me.rows[Row.MELEE].units):
        return None
    if not any(montecarlo._spy(c) for c in montecarlo._unseen(view, decks, 1 - view.player)):
        return None
    wards = {c.id for c in view.hand if isinstance(c, UnitCard) and c.ability is Ability.WARD}
    for a in view.legal_actions:
        if isinstance(a, PlayUnit) and a.card in wards and a.row is Row.MELEE:
            return a
    return None

"""The Monte Carlo AI: an opponent that guesses the hidden cards many times.

The baseline AI (``rowen.ai.baseline``) imagines each card it can't see as an
unknown card, with no strength. So it never counts on what the opponent could
play next. This AI guesses instead: it fills the hidden cards with real ones,
at random, from the cards each player could still hold. Each guess is one
whole match it could be playing, a *sample*. In each sample, it tries every
legal action, and both players then play the rest of the match in a quicker
version of the baseline's way (``_next``). The action with the best total
score over all the samples is the one it plays (ADR 0018).

Where the hidden cards change nothing, it plays as the baseline does: before
round 1, once the opponent has passed, and when it revives a unit.

Where do the guessed cards come from? The AI knows its own deck, as any player
does. It doesn't know the opponent's: it guesses they play their faction's own
deck, which anyone can look up. From each list, it takes away the cards it has
already seen of that player, on the board and in the discard piles, and draws
the hidden ones from what is left. A guess can be wrong, for example against
a deck the player built. It is never a peek: the AI only uses its player view,
as a human does.

The randomness comes from a seed, so the same view and seed always give the
same action, which keeps the tests repeatable.

The Hard level plays a little better than its samples alone (ADR 0018, update
of 4 November 2026). In its play-outs, a player far behind gives up the round
when it costs them no cards. And a few rules of thumb, about Spies and Ward
units, come before the samples: a Spy draws 2 cards, which a play-out's
points-only scoring of each move doesn't see.
"""

from collections.abc import Callable
from dataclasses import replace

from rowen.ai import baseline
from rowen.engine.abilities import on_opponent_side
from rowen.engine.actions import (
    Action,
    EndRedraw,
    Pass,
    PlayScarecrow,
    PlayUnit,
    Revive,
)
from rowen.engine.cards import Ability, Card, UnitCard
from rowen.engine.game import apply_legal, legal_actions, match_over
from rowen.engine.rng import Rng
from rowen.engine.state import GameState
from rowen.engine.view import PlayerView, SideView

# The samples for each level of the AI; Easy is the baseline AI. Against the
# baseline, in 400 matches of rowen-arena each, 8 samples won 57% of the
# decisive matches and 16 won 66% (ADR 0018).
NORMAL_SAMPLES = 8
HARD_SAMPLES = 16

# In a Hard play-out, how many points behind a player gives up the round. 5,
# 10 and 15 won as often in rowen-arena (ADR 0018, update of 4 November 2026).
GIVE_UP_BEHIND = 10


def choose_action(
    view: PlayerView,
    *,
    decks: tuple[tuple[Card, ...], tuple[Card, ...]],
    samples: int,
    seed: int,
    hard: bool = False,
) -> Action:
    """Return the AI's next action: one of ``view.legal_actions``.

    Args:
        view: The AI's player view.
        decks: The cards each player's deck held at the start of the match,
            by player index: the AI's own deck, and its guess of the
            opponent's.
        samples: How many guesses of the hidden cards to try. More play
            better and take longer.
        seed: Where the guesses' randomness comes from.
        hard: Whether to play as the Hard level: with its rules of thumb
            (``_rule_of_thumb``) and its way of giving up rounds in the
            play-outs (``_next``).

    Raises:
        ValueError: If the view has no legal actions, or ``samples`` is not
            positive.
    """
    actions = view.legal_actions
    if not actions:
        raise ValueError("the AI has no legal actions: it isn't its turn")
    if samples < 1:
        raise ValueError(f"samples must be at least 1, got {samples}")
    if hard:
        rule = _rule_of_thumb(view, decks)
        if rule is not None:
            return rule

    # The baseline's choice is kept where the hidden cards don't change it.
    # Before round 1, guessing the cards it would draw says little about which
    # to swap. Once the opponent has passed, they play no more cards this
    # round, and the baseline already plays the rest of it in its head
    # (ADR 0006). After a Medic, the unit to revive is in the discard pile,
    # which both players see.
    opponent = view.players[1 - view.player]
    if EndRedraw() in actions or opponent.passed or view.reviving:
        return baseline.choose_action(view)
    if len(actions) == 1:
        return actions[0]

    # Each candidate is a first action and, on Hard, a plan for the rest of
    # the round (ADR 0018, update of 12 November 2026). The legal actions
    # come first, so a plan is played only when it scores strictly better.
    candidates: list[tuple[Action, Plan | None]] = [(a, None) for a in actions]
    if hard:
        imagined = baseline.imagine(view)
        candidates += [(plan(imagined, view.player), plan) for plan in PLANS]
    totals = [0] * len(candidates)
    rng = Rng(seed=seed)
    for _ in range(samples):
        state, rng = guess(view, decks, rng)
        for index, (action, plan) in enumerate(candidates):
            totals[index] += _play_out(state, action, hard=hard, plan=plan)
    # max keeps the first of equal totals, in the order of the candidates.
    best = max(range(len(candidates)), key=lambda index: totals[index])
    return candidates[best][0]


def guess(
    view: PlayerView,
    decks: tuple[tuple[Card, ...], tuple[Card, ...]],
    rng: Rng,
) -> tuple[GameState, Rng]:
    """Return one guess of the whole match from the view, and the ``Rng`` to use next.

    The guess is ``baseline.imagine``, with real cards in place of the unknown
    ones: the opponent's hand, and both decks, in a random order.
    """
    imagined = baseline.imagine(view)
    players = list(imagined.players)
    for index in (0, 1):
        player = players[index]
        hidden = len(player.deck) + (0 if index == view.player else len(player.hand))
        pool = _unseen(view, decks, index)
        cards, rng = rng.shuffled(pool)
        cards = cards[:hidden] + (baseline.UNKNOWN,) * (hidden - len(cards))
        if index == view.player:
            players[index] = replace(player, deck=cards)
        else:
            size = len(player.hand)
            players[index] = replace(player, hand=cards[:size], deck=cards[size:])
    return replace(imagined, players=(players[0], players[1])), rng


def _unseen(
    view: PlayerView, decks: tuple[tuple[Card, ...], tuple[Card, ...]], index: int
) -> tuple[Card, ...]:
    """Return the cards of player ``index``'s deck list that the view doesn't show.

    A player's cards are on their side of the board, in their weather and in
    their discard pile, except their Spies. A Spy is the player's whose deck
    list has it, wherever it is: a Medic can revive the opponent's Spy onto
    its owner's side, and a Scarecrow take it back into a hand. When both
    lists have it, where it is tells: a Spy on a side was played by the other
    player, and one in the hand is the viewer's.
    """
    mine, theirs = view.players[index], view.players[1 - index]
    own, other = decks[index], decks[1 - index]
    seen = [card for card in _cards(mine) if not _spy(card)]
    if index == view.player:
        seen += [card for card in view.hand if not _spy(card)]
    # Each Spy shown, and whose it would be by where it is.
    spies = [(card, 1 - index) for card in _cards(mine) if _spy(card)]
    spies += [(card, index) for card in _cards(theirs) if _spy(card)]
    spies += [(card, view.player) for card in view.hand if _spy(card)]
    seen += [
        card
        for card, by_place in spies
        if card in own and (card not in other or by_place == index)
    ]
    unseen = list(own)
    for card in seen:
        # A card the list doesn't have is a wrong guess: nothing to take away.
        if card in unseen:
            unseen.remove(card)
    return tuple(unseen)


def _cards(side: SideView) -> tuple[Card, ...]:
    """Return every card the view shows on one side: board, weather and discard."""
    cards: list[Card] = []
    for row in side.rows.values():
        cards.extend(unit.card for unit in row.units)
        cards.extend(row.scarecrows)
        if row.horn is not None:
            cards.append(row.horn)
    return (*cards, *side.weather, *side.discard)


def _spy(card: Card) -> bool:
    return isinstance(card, UnitCard) and on_opponent_side(card)


def _drawing_spy(view: PlayerView, card: Card) -> bool:
    """Return whether the card is a Spy that would draw the AI a card if it played it.

    Its deck has a card left, and the opponent has a row the Spy can go in
    without a Ward unit (rules, section 7.4).
    """
    if (
        not isinstance(card, UnitCard)
        or not _spy(card)
        or view.players[view.player].deck_size == 0
    ):
        return False
    rows = view.players[1 - view.player].rows
    return any(
        not any(u.card.ability is Ability.WARD for u in rows[row].units)
        for row in card.rows
    )


def _rule_of_thumb(
    view: PlayerView, decks: tuple[tuple[Card, ...], tuple[Card, ...]]
) -> Action | None:
    """Return the Hard AI's action where a rule of thumb says what to play, or ``None``.

    Each Spy the AI plays draws it 2 cards, and each one it takes away from the
    opponent costs them 2: in rowen-arena, these rules won more often (ADR
    0018, update of 4 November 2026). In this order:

    - After a Medic, revive a Spy.
    - Take an opponent's Spy back from its own side with a Scarecrow: back in
      the AI's hand, the Spy is the AI's to play.
    - Play a Spy from the hand.
    - Play a Medic while the discard pile holds a Spy to revive.
    - Play a Ward unit in a row with none yet where a Spy the opponent may
      still hold could go: it keeps every Spy out of that row.

    A Spy counts only while it would draw the AI a card: its deck has one
    left, and the opponent has a row for the Spy without a Ward unit. Once
    the opponent has passed, no rule applies, revives included: a Spy played
    then only gives them points. (Before round 1, only redraws are legal:
    none applies either.)
    """
    me, opponent = view.players[view.player], view.players[1 - view.player]
    actions = view.legal_actions
    if opponent.passed:
        return None
    if view.reviving:
        spies = {card.id for card in me.discard if _drawing_spy(view, card)}
        return next(
            (a for a in actions if isinstance(a, Revive) and a.card in spies), None
        )
    hand = {card.id: card for card in view.hand}
    units = [a for a in actions if isinstance(a, PlayUnit)]
    for action in actions:
        if isinstance(action, PlayScarecrow):
            unit = next(
                u for u in me.rows[action.row].units if u.card.id == action.unit
            )
            if _drawing_spy(view, unit.card):
                return action
    for unit_action in units:
        if _drawing_spy(view, hand[unit_action.card]):
            return unit_action
    # A Medic can't revive a Legend.
    if any(
        _drawing_spy(view, card) and not card.legend
        for card in me.discard
        if isinstance(card, UnitCard)
    ):
        for unit_action in units:
            card = hand[unit_action.card]
            if isinstance(card, UnitCard) and card.ability is Ability.MEDIC:
                return unit_action
    their_spies = [card for card in _unseen(view, decks, 1 - view.player) if _spy(card)]
    for unit_action in units:
        card, row = hand[unit_action.card], unit_action.row
        if (
            isinstance(card, UnitCard)
            and card.ability is Ability.WARD
            and not any(u.card.ability is Ability.WARD for u in me.rows[row].units)
            and any(row in spy.rows for spy in their_spies if isinstance(spy, UnitCard))
        ):
            return unit_action
    return None


def _play_out(
    state: GameState, action: Action, *, hard: bool = False, plan: Plan | None = None
) -> int:
    """Return the score, for the player whose turn it is, after the action.

    After it, both players play on as ``_next`` says until the match ends. The
    score is the baseline's: who won, and then the cards left. Stopping at the
    end of the round instead won less (ADR 0018).

    With a ``plan``, the player follows it instead on their own turns for the
    rest of this round, while the opponent still plays. After a Medic, the
    unit to revive is chosen as ``_next`` says.
    """
    player, this_round = state.current, state.round
    state, _ = apply_legal(state, action)
    while not match_over(state):
        if (
            plan is not None
            and state.current == player
            and state.round == this_round
            and not state.reviving
            and not state.players[1 - player].passed
        ):
            move = plan(state, player)
        else:
            move = _next(state, hard=hard)
        state, _ = apply_legal(state, move)
    return baseline.score(state, player)


# A plan for the rest of a round: the player's action on each of their turns.
type Plan = Callable[[GameState, int], Action]


def _plays(state: GameState) -> tuple[Action, ...]:
    """Return the current player's legal actions, apart from Pass."""
    return tuple(action for action in legal_actions(state) if action != Pass())


def _minimal(state: GameState, player: int) -> Action:
    """Win the round with the least: pass once ahead, else the weakest play that leads.

    If no play puts the player ahead, they play the best one.
    """
    plays = _plays(state)
    if not plays or baseline.player_lead(state, player) > 0:
        return Pass()
    leading = [a for a in plays if baseline.lead_after(state, a, player) > 0]
    if not leading:
        return baseline.best(state, plays)
    return min(leading, key=lambda action: baseline.lead_after(state, action, player))


def _give_up(state: GameState, player: int) -> Action:
    """Give the round up: play a Spy, which draws cards, else pass."""
    spies = tuple(a for a in legal_actions(state) if _plays_a_spy(state, a))
    return baseline.best(state, spies) if spies else Pass()


def _wait(state: GameState, player: int) -> Action:
    """Wait for the opponent to pass: play the cheapest card, never pass first."""
    plays = _plays(state)
    if not plays:
        return Pass()
    return min(plays, key=lambda action: baseline.lead_after(state, action, player))


PLANS: tuple[Plan, ...] = (_minimal, _give_up, _wait)


def _next(state: GameState, *, hard: bool = False) -> Action:
    """Return the next action in a play-out, for the player whose turn it is.

    They play as the baseline AI does, in a quicker way: on the guessed match
    as it is, with each action scored only by the board right after it. Once
    the opponent has passed, they play on as ``baseline.next_play`` says.
    Before, they pass as ``baseline.passes_first`` says, as the baseline does,
    and otherwise play the best card.

    On the Hard level, a player ``GIVE_UP_BEHIND`` or more points behind,
    with a life to spare and no fewer cards in the hand than the opponent,
    gives up the round: they keep their cards for the next one, as people
    do. They play a Spy first if they hold one, which draws them 2 cards.
    With fewer cards they play on: giving up would hand the opponent the
    round and leave them ahead in cards too.
    """
    player = state.current
    actions = legal_actions(state)
    if state.reviving:
        return baseline.best(state, actions)
    if state.players[1 - player].passed:
        return baseline.next_play(state, player)
    lead = baseline.player_lead(state, player)
    me, opponent = state.players[player], state.players[1 - player]
    if (
        hard
        and -lead >= GIVE_UP_BEHIND
        and me.lives > 1
        and len(me.hand) >= len(opponent.hand)
    ):
        spies = tuple(a for a in actions if _plays_a_spy(state, a))
        return baseline.best(state, spies) if spies else Pass()
    plays = tuple(action for action in actions if action != Pass())
    if not plays or baseline.passes_first(lead, state.players[player].lives):
        return Pass()
    return baseline.best(state, plays)


def _plays_a_spy(state: GameState, action: Action) -> bool:
    """Return whether the action plays a Spy from the current player's hand."""
    if not isinstance(action, PlayUnit):
        return False
    hand = state.players[state.current].hand
    return any(card.id == action.card and _spy(card) for card in hand)

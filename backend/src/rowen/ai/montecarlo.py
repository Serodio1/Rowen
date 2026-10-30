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
"""

from dataclasses import replace

from rowen.ai import baseline
from rowen.engine.abilities import on_opponent_side
from rowen.engine.actions import Action, EndRedraw, Pass
from rowen.engine.cards import Card, UnitCard
from rowen.engine.game import apply_legal, legal_actions, match_over
from rowen.engine.rng import Rng
from rowen.engine.state import GameState
from rowen.engine.view import PlayerView, SideView

# The samples for each level of the AI; Easy is the baseline AI. Against the
# baseline, in 400 matches of rowen-arena each, 8 samples won 57% of the
# decisive matches and 16 won 66% (ADR 0018).
NORMAL_SAMPLES = 8
HARD_SAMPLES = 16


def choose_action(
    view: PlayerView,
    *,
    decks: tuple[tuple[Card, ...], tuple[Card, ...]],
    samples: int,
    seed: int,
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

    Raises:
        ValueError: If the view has no legal actions, or ``samples`` is not
            positive.
    """
    actions = view.legal_actions
    if not actions:
        raise ValueError("the AI has no legal actions: it isn't its turn")
    if samples < 1:
        raise ValueError(f"samples must be at least 1, got {samples}")

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

    totals = dict.fromkeys(actions, 0)
    rng = Rng(seed=seed)
    for _ in range(samples):
        state, rng = guess(view, decks, rng)
        for action in actions:
            totals[action] += _play_out(state, action)
    # max keeps the first of equal totals, in the order of the legal actions.
    return max(actions, key=lambda action: totals[action])


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


def _play_out(state: GameState, action: Action) -> int:
    """Return the score, for the player whose turn it is, after the action.

    After it, both players play on as ``_next`` says until the match ends. The
    score is the baseline's: who won, and then the cards left. Stopping at the
    end of the round instead won less (ADR 0018).
    """
    player = state.current
    state, _ = apply_legal(state, action)
    while not match_over(state):
        state, _ = apply_legal(state, _next(state))
    return baseline.score(state, player)


def _next(state: GameState) -> Action:
    """Return the next action in a play-out, for the player whose turn it is.

    They play as the baseline AI does, in a quicker way: on the guessed match
    as it is, with each action scored only by the board right after it. Once
    the opponent has passed, they play on as ``baseline.next_play`` says.
    Before, they pass as ``baseline.passes_first`` says, as the baseline does,
    and otherwise play the best card.
    """
    player = state.current
    actions = legal_actions(state)
    if state.reviving:
        return baseline.best(state, actions)
    if state.players[1 - player].passed:
        return baseline.next_play(state, player)
    plays = tuple(action for action in actions if action != Pass())
    lead = baseline.player_lead(state, player)
    if not plays or baseline.passes_first(lead, state.players[player].lives):
        return Pass()
    return baseline.best(state, plays)

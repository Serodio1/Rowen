"""The baseline AI: an opponent that tries each move before it plays one.

The AI gets its player view, like a human, so it can't see the opponent's
hand or the order of the decks (rules, section 11). It answers with one of the
view's legal actions.

To choose one, it asks the engine "what if?". It imagines the match from its
view, with an unknown card in place of each card it can't see. There it tries
each legal action with ``apply`` and scores the result: the points, cards and
lives it has more of than the opponent. Then it plays the action with the best
score. The state is never changed, so trying an action leaves the match as it
was (ADR 0003). And the rules stay in the engine: a new card needs no code
here.

The engine tells what an action does, but not what the opponent will do next.
So whether to pass is decided by a rule of thumb instead, in ``_should_pass``.
"""

from rowen.engine.actions import Action, EndRedraw, Pass
from rowen.engine.cards import Row, UnitCard
from rowen.engine.game import apply, legal_actions, match_over, match_winner
from rowen.engine.rng import Rng
from rowen.engine.scoring import player_total
from rowen.engine.state import GameState, PlayerState, RowState
from rowen.engine.view import PlayerView

# A card the AI can't see, in the opponent's hand or in a deck: it knows how
# many there are, but not which. With no ability or group, it never joins a
# Muster, so the AI doesn't count on the units its deck could add.
UNKNOWN = UnitCard(id="unknown", name="Unknown", rows=(Row.SIEGE,), strength=0)

# What a card in the hand is worth, in points: about what a card adds to the
# board. No cards are drawn between rounds, so the cards left are all a player
# has for the rest of the match. Counting them, the AI plays a Spy for the
# cards it draws, and a Medic for the unit it brings back.
CARD_VALUE = 5

# What a life is worth, in points: as much as two cards.
LIFE_VALUE = 2 * CARD_VALUE

# The score of a match won, higher than any other score can be.
WIN = 1_000_000

# The lead at which the AI passes while the opponent still plays: the points
# of two cards. To win the round, the opponent then needs about two more
# cards, and the AI spends none.
PASS_LEAD = 2 * CARD_VALUE


def choose_action(view: PlayerView) -> Action:
    """Return the AI's next action: one of ``view.legal_actions``.

    Raises:
        ValueError: If the view has no legal actions: it isn't the AI's turn,
            or the match is over.
    """
    actions = view.legal_actions
    if not actions:
        raise ValueError("the AI has no legal actions: it isn't its turn")

    # Before round 1, the AI keeps the hand it was dealt.
    if EndRedraw() in actions:
        return EndRedraw()

    # After a Medic, the only actions are the units to revive.
    if view.reviving:
        return _best(imagine(view), actions)

    plays = tuple(action for action in actions if action != Pass())
    if not plays or _should_pass(view):
        return Pass()
    return _best(imagine(view), plays)


def imagine(view: PlayerView) -> GameState:
    """Return the match as the AI imagines it from its view.

    What the view shows is as in the real match, and each card it hides is an
    ``UNKNOWN`` card. So the AI has the same legal actions in the imagined
    match as in the real one, and each changes the board in the same way,
    except that a Muster calls no units from the deck.
    """
    return GameState(
        players=(_imagine_player(view, 0), _imagine_player(view, 1)),
        current=view.current,
        # The view doesn't say who started the round. That only decides who
        # starts the next round after a tie, which changes no score.
        round_starter=view.current,
        round=view.round,
        reviving=view.reviving,
        # Nor does it give the rng, which would tell the order of the decks.
        # Only a redraw uses it, and the AI never tries one.
        rng=Rng(seed=0),
    )


def _imagine_player(view: PlayerView, index: int) -> PlayerState:
    """Return player ``index`` as the AI imagines them from its view."""
    side = view.players[index]
    hand = view.hand if index == view.player else (UNKNOWN,) * side.hand_size
    rows = {
        row: RowState(
            units=tuple(unit.card for unit in row_view.units),
            horn=row_view.horn,
            scarecrows=row_view.scarecrows,
        )
        for row, row_view in side.rows.items()
    }
    return PlayerState(
        deck=(UNKNOWN,) * side.deck_size,
        hand=hand,
        rows=rows,
        weather=side.weather,
        discard=side.discard,
        lives=side.lives,
        passed=side.passed,
        redraws_left=side.redraws_left,
    )


def _should_pass(view: PlayerView) -> bool:
    """Return whether the AI passes instead of playing a card.

    If the opponent has passed, the AI passes as soon as it is ahead: it wins
    the round without spending another card. Otherwise, it passes when it is
    ahead by ``PASS_LEAD`` or more, unless it is on its last life, where
    losing the round would lose the match.
    """
    mine = view.players[view.player]
    theirs = view.players[1 - view.player]
    lead = mine.total - theirs.total
    if theirs.passed:
        return lead > 0
    return lead >= PASS_LEAD and mine.lives > 1


def _best(state: GameState, actions: tuple[Action, ...]) -> Action:
    """Return the action with the best score after it; the first one on a tie."""
    return max(actions, key=lambda action: _value(state, action))


def _value(state: GameState, action: Action) -> int:
    """Return the score, for the player whose turn it is, after the action.

    After a Medic, the same player must choose a unit to revive. Each choice
    is tried as well, and the best one counts: so a Medic scores for the unit
    it brings back, and for the next one too if that is a Medic.
    """
    player = state.current
    state, _ = apply(state, action)
    if state.reviving:
        return max(_value(state, revive) for revive in legal_actions(state))
    return _score(state, player)


def _score(state: GameState, player: int) -> int:
    """Return how well the match is going for ``player``: the higher, the better.

    That is what they have more of than the opponent: points on the board,
    cards in the hand, worth ``CARD_VALUE`` each, and lives, worth
    ``LIFE_VALUE`` each. Once the match is over, only who won counts.
    """
    if match_over(state):
        winner = match_winner(state)
        if winner is None:
            return 0
        return WIN if winner == player else -WIN

    mine, theirs = state.players[player], state.players[1 - player]
    points = player_total(state, player) - player_total(state, 1 - player)
    cards = len(mine.hand) - len(theirs.hand)
    lives = mine.lives - theirs.lives
    return points + CARD_VALUE * cards + LIFE_VALUE * lives

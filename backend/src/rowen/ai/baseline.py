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
So while the opponent still plays, whether to pass is a rule of thumb, in
``_should_pass``. Once the opponent has passed, they take no more turns this
round: the AI then plays the rest of the round in its head, in ``_finish``, to
see whether winning it is worth the cards (ADR 0006).

Before round 1, the AI swaps its spare Muster cards, up to two (``_redraw``).
"""

from rowen.engine.abilities import muster_group
from rowen.engine.actions import Action, EndRedraw, Pass, Redraw
from rowen.engine.cards import Ability, Row, UnitCard
from rowen.engine.events import RoundEnded
from rowen.engine.game import apply, legal_actions, match_over, match_winner
from rowen.engine.rng import Rng
from rowen.engine.scoring import player_total
from rowen.engine.state import GameState, PlayerState, RowState
from rowen.engine.view import PlayerView

# A card the AI can't see, in the opponent's hand or in a deck: it knows how
# many there are, but not which. It has no strength, and as a Legend nothing
# can change that, not even weather. With no ability or group, it never joins
# a Muster, so the AI doesn't count on the units its deck could add.
UNKNOWN = UnitCard(
    id="unknown", name="Unknown", rows=(Row.SIEGE,), strength=0, legend=True
)

# What a card in the hand is worth, in points: about what a card adds to the
# board. No cards are drawn between rounds, so the cards left are all a player
# has for the rest of the match. Counting them, the AI plays a Spy for the
# cards it draws, and a Medic for the unit it brings back.
CARD_VALUE = 5

# What a life is worth, in points. Once the opponent has passed, winning the
# round instead of losing it puts the AI two lives further ahead: it keeps its
# life and the opponent loses one. That is 14 points: more than two cards (10)
# and less than three (15), so the AI spends up to two cards to win round 1.
# Later rounds decide the match, and winning it beats any number of cards.
LIFE_VALUE = 7

# What winning the match adds to a score: more than the rest of any score can
# be.
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

    if EndRedraw() in actions:
        return _redraw(view)

    state = imagine(view)
    plays = tuple(action for action in actions if action != Pass())

    # The opponent takes no more turns this round, so the AI can play the rest
    # of it in its head. Pass is tried first, and max keeps the first of equal
    # scores: when passing scores as well as playing, the AI passes and keeps
    # its cards. After a Medic, the only actions are the units to revive.
    if view.players[1 - view.player].passed:
        candidates = plays if view.reviving else (Pass(), *plays)
        return max(candidates, key=lambda action: _finish(state, action))

    if view.reviving:
        return _best(state, actions)
    if not plays or _should_pass(view):
        return Pass()
    return _best(state, plays)


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


def _redraw(view: PlayerView) -> Action:
    """Return the AI's choice before round 1: swap a spare Muster card, or stop.

    A Muster unit plays its whole group, from the deck and from the hand
    (rules, section 7.2, and D7). So a second card of the group in the hand is
    spare: swapped, it goes back into the deck, still comes along with the
    first one, and the card drawn in its place is one card more.
    """
    for card in view.hand:
        spare = (
            isinstance(card, UnitCard)
            and card.ability is Ability.MUSTER
            and len(muster_group(view.hand, card)) > 1
        )
        # With an empty deck, there is nothing to draw: only EndRedraw is legal.
        if spare and Redraw(card=card.id) in view.legal_actions:
            return Redraw(card=card.id)
    return EndRedraw()


def _should_pass(view: PlayerView) -> bool:
    """Return whether the AI passes first, while the opponent still plays.

    It passes when it is ahead by ``PASS_LEAD`` or more, unless it is on its
    last life, where losing the round would lose the match.
    """
    mine = view.players[view.player]
    theirs = view.players[1 - view.player]
    return mine.total - theirs.total >= PASS_LEAD and mine.lives > 1


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


def _finish(state: GameState, action: Action) -> int:
    """Return the score, for the player whose turn it is, at the end of the round.

    The opponent has passed, so every turn left in the round is the player's.
    After the action, they can pass at once, or play on as ``_next_play`` says
    until the round ends: the better of the two counts. After a Medic, each
    unit they could revive is tried as well, and the best one counts.
    """
    player, this_round = state.current, state.round
    state, _ = apply(state, action)
    if state.reviving:
        return max(_finish(state, revive) for revive in legal_actions(state))
    if not _goes_on(state, this_round):
        return _score(state, player)

    passed, _ = apply(state, Pass())
    while _goes_on(state, this_round):
        state, _ = apply(state, _next_play(state, player))
    return max(_score(passed, player), _score(state, player))


def _goes_on(state: GameState, this_round: int) -> bool:
    """Return whether the round ``this_round`` is still being played.

    When the match ends, the round number stays as it is, so that is checked
    too.
    """
    return state.round == this_round and not match_over(state)


def _next_play(state: GameState, player: int) -> Action:
    """Return the player's next action, in a round the opponent has passed.

    Once ahead, they pass: the round is won. Until then, they play the action
    with the best score among those that bring them closer to winning the
    round, and pass when none does. The cards a Spy would draw never help
    them catch up: in the imagined match, they are unknown cards, with no
    strength. After a Medic, they revive the unit with the best score.
    """
    actions = legal_actions(state)
    if state.reviving:
        return _best(state, actions)
    lead = _lead(state, player)
    if lead > 0:
        return Pass()
    closer = tuple(
        action
        for action in actions
        if action != Pass() and _lead_after(state, action, player) > lead
    )
    if not closer:
        return Pass()
    return _best(state, closer)


def _lead_after(state: GameState, action: Action, player: int) -> int:
    """Return the player's lead once the action is carried out.

    After a Medic, that is before the unit it revives, which is chosen next.
    If the action ends the round, that is the lead the round ended with, as
    the board is cleared after it.
    """
    after, events = apply(state, action)
    for event in events:
        if isinstance(event, RoundEnded):
            return event.scores[player] - event.scores[1 - player]
    return _lead(after, player)


def _lead(state: GameState, player: int) -> int:
    """Return how many points ``player`` is ahead of the opponent, below 0 if behind."""
    return player_total(state, player) - player_total(state, 1 - player)


def _score(state: GameState, player: int) -> int:
    """Return how well the match is going for ``player``: the higher, the better.

    That is what they have more of than the opponent: points on the board,
    cards in the hand, worth ``CARD_VALUE`` each, and lives, worth
    ``LIFE_VALUE`` each. Once the match is over, who won counts above all,
    and the cards only break ties: of two ways to win the match, the AI
    takes the one that spends fewer cards.
    """
    mine, theirs = state.players[player], state.players[1 - player]
    cards = CARD_VALUE * (len(mine.hand) - len(theirs.hand))
    if match_over(state):
        winner = match_winner(state)
        if winner is None:
            return cards
        return (WIN if winner == player else -WIN) + cards

    lives = LIFE_VALUE * (mine.lives - theirs.lives)
    return _lead(state, player) + cards + lives

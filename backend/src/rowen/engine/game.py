"""The flow of a match, from its setup onwards."""

from dataclasses import replace

from rowen.engine.actions import Action, Pass, PlayUnit
from rowen.engine.cards import Card, UnitCard
from rowen.engine.decks import Deck
from rowen.engine.events import (
    Event,
    MatchEnded,
    PlayerPassed,
    RoundEnded,
    UnitPlayed,
)
from rowen.engine.rng import Rng
from rowen.engine.scoring import player_total
from rowen.engine.state import GameState, PlayerState, empty_rows

# Cards each player draws at the start of the match (rules, section 3).
HAND_SIZE = 10


class IllegalActionError(ValueError):
    """Raised by ``apply`` for an action that isn't one of the legal actions."""


def start_match(decks: tuple[Deck, Deck], seed: int) -> GameState:
    """Set up a match: shuffle both decks, flip a coin and deal 10 cards each.

    This is the rules, section 3, steps 1 to 3; the redraw (step 4) is not
    part of it yet. The same decks and seed always give the same match.

    Args:
        decks: The deck of each player: player 0 plays ``decks[0]``.
        seed: Where all the randomness of the match comes from.
    """
    rng = Rng(seed=seed)
    cards_0, rng = rng.shuffled(decks[0].cards)
    cards_1, rng = rng.shuffled(decks[1].cards)
    first_player, rng = rng.coin_flip()
    return GameState(
        players=(_deal(cards_0), _deal(cards_1)),
        current=first_player,
        round_starter=first_player,
        rng=rng,
    )


def legal_actions(state: GameState) -> tuple[Action, ...]:
    """Return every action the player whose turn it is can take.

    That is playing any unit in the hand on any of its rows, or passing
    (rules, sections 4 and 5). Special cards can't be played yet. When the
    match is over, there are none.
    """
    if match_over(state):
        return ()

    hand = state.players[state.current].hand
    # Copies of a card give the same action. A dict keeps one of each, in order.
    plays = dict.fromkeys(
        PlayUnit(card=card.id, row=row)
        for card in hand
        if isinstance(card, UnitCard)
        for row in card.rows
    )
    return (*plays, Pass())


def apply(state: GameState, action: Action) -> tuple[GameState, tuple[Event, ...]]:
    """Carry out an action of the player whose turn it is.

    When the action ends the round, ``apply`` also scores it and starts the
    next one, or ends the match (rules, sections 9 and 10). So a round never
    stays over: in the new state, both players have passed only if the match
    is over.

    Returns:
        The new state and the events: what happened, in order.

    Raises:
        IllegalActionError: If the action isn't in ``legal_actions(state)``.
    """
    if action not in legal_actions(state):
        raise IllegalActionError(f"illegal action: {action}")

    if isinstance(action, Pass):
        state, events = _pass(state)
    else:
        state, events = _play_unit(state, action)

    state, auto_passes = _pass_empty_hands(state)
    state = _turn_to(state, 1 - state.current)
    events += auto_passes

    # Usually this ends one round at most. A new round can end straight away,
    # though, if neither player has a card left to play it.
    while _round_over(state) and not match_over(state):
        state, round_events = _end_round(state)
        events += round_events
    return state, events


def match_over(state: GameState) -> bool:
    """Return whether a player has no lives left (rules, section 10)."""
    return any(player.lives == 0 for player in state.players)


def match_winner(state: GameState) -> int | None:
    """Return the index of the player who won the match, or ``None`` for a draw.

    Raises:
        ValueError: If the match isn't over yet.
    """
    if not match_over(state):
        raise ValueError("the match isn't over yet")
    # The first player with lives left, if there is one. There can't be two.
    return next(
        (index for index, player in enumerate(state.players) if player.lives > 0),
        None,
    )


def _deal(cards: tuple[Card, ...]) -> PlayerState:
    """Return a player who has drawn their hand from these shuffled cards."""
    return PlayerState(hand=cards[:HAND_SIZE], deck=cards[HAND_SIZE:])


def _play_unit(
    state: GameState, action: PlayUnit
) -> tuple[GameState, tuple[Event, ...]]:
    """Move one copy of the unit from the hand to the end of the row."""
    player = state.players[state.current]
    unit = next(
        card
        for card in player.hand
        if isinstance(card, UnitCard) and card.id == action.card
    )
    row = player.rows[action.row]
    player = replace(
        player,
        hand=_without(player.hand, unit),
        rows={**player.rows, action.row: replace(row, units=(*row.units, unit))},
    )
    event = UnitPlayed(player=state.current, card=unit.id, row=action.row)
    return _with_player(state, state.current, player), (event,)


def _pass(state: GameState) -> tuple[GameState, tuple[Event, ...]]:
    """Mark the player whose turn it is as passed."""
    player = replace(state.players[state.current], passed=True)
    event = PlayerPassed(player=state.current)
    return _with_player(state, state.current, player), (event,)


def _pass_empty_hands(state: GameState) -> tuple[GameState, tuple[Event, ...]]:
    """Pass for every player who has no cards left in hand (rules, section 4)."""
    events: list[Event] = []
    for index, player in enumerate(state.players):
        if not player.hand and not player.passed:
            state = _with_player(state, index, replace(player, passed=True))
            events.append(PlayerPassed(player=index))
    return state, tuple(events)


def _turn_to(state: GameState, player: int) -> GameState:
    """Give the turn to ``player``, or to the opponent if ``player`` has passed.

    A player who has passed takes no more turns this round, so the other one
    keeps playing until they pass too (rules, section 4).
    """
    if state.players[player].passed:
        player = 1 - player
    return replace(state, current=player)


def _round_over(state: GameState) -> bool:
    """Return whether both players have passed, which ends the round."""
    return all(player.passed for player in state.players)


def _end_round(state: GameState) -> tuple[GameState, tuple[Event, ...]]:
    """Score the round, then start the next one or end the match.

    The players who didn't win the round lose a life: the loser, or both on a
    tie (rules, section 9). When that ends the match, the board is left as it
    is, to show how the match ended.
    """
    scores = (player_total(state, 0), player_total(state, 1))
    winner = _round_winner(scores)
    for index, player in enumerate(state.players):
        if index != winner:
            state = _with_player(state, index, replace(player, lives=player.lives - 1))
    events: tuple[Event, ...] = (RoundEnded(scores=scores, winner=winner),)

    if match_over(state):
        return state, (*events, MatchEnded(winner=match_winner(state)))

    state, auto_passes = _start_next_round(state, winner)
    return state, events + auto_passes


def _round_winner(scores: tuple[int, int]) -> int | None:
    """Return the index of the player with the higher score, or ``None`` on a tie."""
    if scores[0] == scores[1]:
        return None
    return 0 if scores[0] > scores[1] else 1


def _start_next_round(
    state: GameState, winner: int | None
) -> tuple[GameState, tuple[Event, ...]]:
    """Clear the board and give the first turn of the next round.

    The winner of the round goes first. After a tie, the player who went first
    in it goes first again (rules, section 9).
    """
    starter = state.round_starter if winner is None else winner
    state = replace(
        state,
        players=(_clear_board(state.players[0]), _clear_board(state.players[1])),
        round=state.round + 1,
        round_starter=starter,
    )
    state, auto_passes = _pass_empty_hands(state)
    return _turn_to(state, starter), auto_passes


def _clear_board(player: PlayerState) -> PlayerState:
    """Move the player's cards in play to their discard pile, for a new round.

    That is the cards on their side of the board, even an opponent's Spy, and
    the weather cards they played (rules, section 9). The hand and the deck
    stay as they are: no cards are drawn.
    """
    in_play: list[Card] = []
    for row in player.rows.values():
        in_play.extend(row.units)
        if row.horn is not None:
            in_play.append(row.horn)
    in_play.extend(player.weather)
    return replace(
        player,
        rows=empty_rows(),
        weather=(),
        discard=(*player.discard, *in_play),
        passed=False,
    )


def _with_player(state: GameState, index: int, player: PlayerState) -> GameState:
    """Return the state with player ``index`` replaced by ``player``."""
    if index == 0:
        return replace(state, players=(player, state.players[1]))
    return replace(state, players=(state.players[0], player))


def _without(cards: tuple[Card, ...], card: Card) -> tuple[Card, ...]:
    """Return the cards with one copy of ``card`` taken out."""
    index = cards.index(card)
    return cards[:index] + cards[index + 1 :]

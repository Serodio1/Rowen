"""The flow of a match, from its setup onwards."""

from dataclasses import replace

from rowen.engine.actions import Action, Pass, PlayUnit
from rowen.engine.cards import Card, UnitCard
from rowen.engine.decks import Deck
from rowen.engine.events import Event, PlayerPassed, UnitPlayed
from rowen.engine.rng import Rng
from rowen.engine.state import GameState, PlayerState

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
        rng=rng,
    )


def legal_actions(state: GameState) -> tuple[Action, ...]:
    """Return every action the player whose turn it is can take.

    That is playing any unit in the hand on any of its rows, or passing
    (rules, sections 4 and 5). Special cards can't be played yet. When both
    players have passed, the round is over and there are none.
    """
    if all(player.passed for player in state.players):
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
    return _next_turn(state), events + auto_passes


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


def _next_turn(state: GameState) -> GameState:
    """Give the turn to the opponent, unless they have passed.

    A player who has passed takes no more turns this round, so the other one
    keeps playing until they pass too (rules, section 4).
    """
    opponent = 1 - state.current
    if state.players[opponent].passed:
        return state
    return replace(state, current=opponent)


def _with_player(state: GameState, index: int, player: PlayerState) -> GameState:
    """Return the state with player ``index`` replaced by ``player``."""
    if index == 0:
        return replace(state, players=(player, state.players[1]))
    return replace(state, players=(state.players[0], player))


def _without(cards: tuple[Card, ...], card: Card) -> tuple[Card, ...]:
    """Return the cards with one copy of ``card`` taken out."""
    index = cards.index(card)
    return cards[:index] + cards[index + 1 :]

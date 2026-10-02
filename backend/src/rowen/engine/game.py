"""The flow of a match, from its setup onwards."""

from dataclasses import replace

from rowen.engine import abilities, specials
from rowen.engine.actions import (
    Action,
    EndRedraw,
    Pass,
    PlayHorn,
    PlaySpecial,
    PlayUnit,
    Redraw,
    Revive,
)
from rowen.engine.cards import Card, Row, SpecialCard, SpecialKind, UnitCard
from rowen.engine.decks import Deck
from rowen.engine.events import (
    CardRedrawn,
    Event,
    MatchEnded,
    PlayerPassed,
    RedrawEnded,
    RoundEnded,
    UnitPlayed,
    UnitRevived,
)
from rowen.engine.rng import Rng
from rowen.engine.scoring import player_total
from rowen.engine.state import (
    GameState,
    PlayerState,
    empty_rows,
    with_player,
    with_unit,
)

# Cards each player draws at the start of the match (rules, section 3).
HAND_SIZE = 10

# Cards each player can swap before round 1 (rules, section 3).
MAX_REDRAWS = 2


class IllegalActionError(ValueError):
    """Raised by ``apply`` for an action that isn't one of the legal actions."""


def start_match(decks: tuple[Deck, Deck], seed: int) -> GameState:
    """Set up a match: shuffle both decks, flip a coin and deal 10 cards each.

    This is the rules, section 3, steps 1 to 3. The match then goes on with
    the redraw (step 4), through ``legal_actions`` and ``apply``: the player
    who won the coin flip redraws first, then the other one, and then round 1
    starts. The same decks and seed always give the same match.

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

    Before round 1, that is swapping any card in the hand, if there is a card
    to draw, or ending the redraw (rules, section 3). Then it is playing any
    card in the hand, as ``_plays`` says, or passing (rules, sections 4, 5
    and 8). Right after a Medic, it is only reviving a unit from the discard
    pile on any of its rows (rules, section 7.2). When the match is over,
    there are none.
    """
    if match_over(state):
        return ()

    player = state.players[state.current]
    if state.reviving:
        # Copies of a card give the same action, as below.
        revives = dict.fromkeys(
            Revive(card=unit.id, row=row)
            for unit in abilities.revivable(player)
            for row in unit.rows
        )
        return tuple(revives)
    if _redrawing(state):
        if not player.deck:
            return (EndRedraw(),)
        # Copies of a card give the same action, as below.
        swaps = dict.fromkeys(Redraw(card=card.id) for card in player.hand)
        return (*swaps, EndRedraw())

    # Copies of a card give the same actions. A dict keeps one of each, in order.
    plays = dict.fromkeys(
        action for card in player.hand for action in _plays(player, card)
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

    # The redraw happens before round 1, so none of the round's steps below
    # apply to it.
    if isinstance(action, Redraw):
        return _redraw(state, action)
    if isinstance(action, EndRedraw):
        return _end_redraw(state)

    if isinstance(action, Pass):
        state, events = _pass(state)
    elif isinstance(action, Revive):
        state, events = _revive(state, action)
    elif isinstance(action, PlaySpecial):
        state, events = _play_special(state, action)
    elif isinstance(action, PlayHorn):
        state, events = _play_horn(state, action)
    else:
        state, events = _play_unit(state, action)

    # After a Medic, the turn waits for the player to choose a unit to revive.
    if state.reviving:
        return state, events

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
    """Return a player who has drawn their hand from these shuffled cards.

    They can still swap ``MAX_REDRAWS`` cards before round 1.
    """
    return PlayerState(
        hand=cards[:HAND_SIZE],
        deck=cards[HAND_SIZE:],
        redraws_left=MAX_REDRAWS,
    )


def _plays(player: PlayerState, card: Card) -> tuple[Action, ...]:
    """Return the ways to play a card from the hand, one action per choice.

    A unit goes on any of its rows; a War Horn in any row with an empty horn
    slot; a weather card or Clear Skies needs no choice. Wildfire and
    Scarecrow can't be played yet.
    """
    if isinstance(card, UnitCard):
        return tuple(PlayUnit(card=card.id, row=row) for row in card.rows)
    if card.kind is SpecialKind.WAR_HORN:
        rows = specials.free_horn_rows(player)
        return tuple(PlayHorn(card=card.id, row=row) for row in rows)
    if card.kind in specials.EFFECTS:
        return (PlaySpecial(card=card.id),)
    return ()


def _redrawing(state: GameState) -> bool:
    """Return whether round 1 is waiting for a player to finish redrawing."""
    return any(player.redraws_left > 0 for player in state.players)


def _redraw(state: GameState, action: Redraw) -> tuple[GameState, tuple[Event, ...]]:
    """Swap one copy of the card for the top card of the deck (rules, section 3).

    The new card is drawn first, into the old card's place in the hand. Only
    then does the old card go back into the deck, which is shuffled, so it is
    never drawn straight back. After their last swap, the player is done.
    """
    player = state.players[state.current]
    index = next(i for i, card in enumerate(player.hand) if card.id == action.card)
    card, drawn = player.hand[index], player.deck[0]
    deck, rng = state.rng.shuffled((*player.deck[1:], card))
    player = replace(
        player,
        hand=(*player.hand[:index], drawn, *player.hand[index + 1 :]),
        deck=deck,
        redraws_left=player.redraws_left - 1,
    )
    state = replace(with_player(state, state.current, player), rng=rng)
    events: tuple[Event, ...] = (
        CardRedrawn(player=state.current, card=card.id, drawn=drawn.id),
    )

    if player.redraws_left == 0:
        state, end = _end_redraw(state)
        events += end
    return state, events


def _end_redraw(state: GameState) -> tuple[GameState, tuple[Event, ...]]:
    """End the redraw of the player whose turn it is.

    The other player redraws next, unless they are done too. Then round 1
    starts with the player who won the coin flip.
    """
    player = replace(state.players[state.current], redraws_left=0)
    event = RedrawEnded(player=state.current)
    state = with_player(state, state.current, player)

    opponent = 1 - state.current
    if state.players[opponent].redraws_left > 0:
        return replace(state, current=opponent), (event,)
    return replace(state, current=state.round_starter), (event,)


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
    player = replace(player, hand=_without(player.hand, unit))
    state = with_player(state, state.current, player)

    state, side, ability_events = _put_on_board(state, unit, action.row)
    event = UnitPlayed(player=state.current, card=unit.id, row=action.row, side=side)
    return state, (event, *ability_events)


def _play_special(
    state: GameState, action: PlaySpecial
) -> tuple[GameState, tuple[Event, ...]]:
    """Take one copy of the special card from the hand and carry out its effect.

    The effect puts the card where it goes: the weather area or the discard
    pile.
    """
    state, card = _take_special(state, action.card)
    return specials.play(state, state.current, card)


def _play_horn(
    state: GameState, action: PlayHorn
) -> tuple[GameState, tuple[Event, ...]]:
    """Move one copy of the War Horn from the hand to the row's horn slot."""
    state, card = _take_special(state, action.card)
    return specials.play_horn(state, state.current, card, action.row)


def _take_special(state: GameState, card_id: str) -> tuple[GameState, SpecialCard]:
    """Take one copy of a special card from the hand of the player whose turn it is."""
    player = state.players[state.current]
    card = next(
        card
        for card in player.hand
        if isinstance(card, SpecialCard) and card.id == card_id
    )
    player = replace(player, hand=_without(player.hand, card))
    return with_player(state, state.current, player), card


def _revive(state: GameState, action: Revive) -> tuple[GameState, tuple[Event, ...]]:
    """Move one copy of the unit from the discard pile to the end of the row.

    This is the choice a Medic asks for. As with any unit played, its on-play
    ability takes effect, so a revived Medic asks for another choice.
    """
    player = state.players[state.current]
    unit = next(card for card in abilities.revivable(player) if card.id == action.card)
    player = replace(player, discard=_without(player.discard, unit))
    state = replace(with_player(state, state.current, player), reviving=False)

    state, side, ability_events = _put_on_board(state, unit, action.row)
    event = UnitRevived(player=state.current, card=unit.id, row=action.row, side=side)
    return state, (event, *ability_events)


def _put_on_board(
    state: GameState, unit: UnitCard, row: Row
) -> tuple[GameState, int, tuple[Event, ...]]:
    """Put a unit of the player whose turn it is at the end of the row.

    The row is on the side the unit goes on, which is the opponent's for a
    Spy. Then the unit's on-play ability, if it has one, takes effect.

    Returns:
        The new state, the index of the side the unit went on and the events
        of its ability.
    """
    side = abilities.side(unit, state.current)
    state = with_unit(state, side, row, unit)
    state, events = abilities.on_play(state, state.current, unit)
    return state, side, events


def _pass(state: GameState) -> tuple[GameState, tuple[Event, ...]]:
    """Mark the player whose turn it is as passed."""
    player = replace(state.players[state.current], passed=True)
    event = PlayerPassed(player=state.current)
    return with_player(state, state.current, player), (event,)


def _pass_empty_hands(state: GameState) -> tuple[GameState, tuple[Event, ...]]:
    """Pass for every player who has no cards left in hand (rules, section 4)."""
    events: list[Event] = []
    for index, player in enumerate(state.players):
        if not player.hand and not player.passed:
            state = with_player(state, index, replace(player, passed=True))
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
            state = with_player(state, index, replace(player, lives=player.lives - 1))
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


def _without(cards: tuple[Card, ...], card: Card) -> tuple[Card, ...]:
    """Return the cards with one copy of ``card`` taken out."""
    index = cards.index(card)
    return cards[:index] + cards[index + 1 :]

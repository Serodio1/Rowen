"""The web API: start a match against the AI, and see it as the player may.

The server keeps the state of each match and never sends it: a response holds
only the player's view, so the AI's hand, the order of the decks and the seed
stay on the server (ADR 0002). The human player is player 0 and the AI player
1, as in the CLI. When the AI has a move to make, it makes it before the
server answers, so the player always gets the match on their turn, unless the
match is over.

Endpoints get the match store and the seed of a new match from ``get_store``
and ``new_seed``, through FastAPI's ``Depends``. The tests replace both with
``app.dependency_overrides``: a new store for each test, and seeds they know.

To run the server on your computer, in ``backend``:
``uv run uvicorn rowen.api.app:app --reload --reload-dir src``.
"""

import secrets
from importlib.metadata import version
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Response, status

from rowen.ai.baseline import choose_action
from rowen.api.schemas import Match, NewMatch, from_view
from rowen.api.store import MatchStore
from rowen.data import deck_ids, load_deck
from rowen.engine.public import GameState, apply, player_view, start_match

# The human player is always player 0 and the AI player 1, as in the CLI. The
# coin flip in start_match still decides who starts.
HUMAN = 0
AI = 1

# How many random bits a seed has. Whoever knows the seed can work out the
# AI's hand, and a small seed can be found by trying every one against the
# cards in the player's hand. 2**64 seeds are far too many to try.
SEED_BITS = 64

app = FastAPI(title="Rowen", version=version("rowen"))

# All the server's matches, in the memory of its process. So the server must
# run as a single process, as uvicorn does unless told otherwise: with several
# workers, each would have a store of its own, and a match started in one
# would be unknown to the others.
_store = MatchStore()


def get_store() -> MatchStore:
    """Return where the server keeps its matches."""
    return _store


def new_seed() -> int:
    """Return the seed of a new match: random, and never sent to a player."""
    return secrets.randbits(SEED_BITS)


# What an endpoint asks for to get the store or a seed: FastAPI calls the
# function in Depends and passes the endpoint what it returns.
type Store = Annotated[MatchStore, Depends(get_store)]
type Seed = Annotated[int, Depends(new_seed)]


@app.post("/matches", status_code=status.HTTP_201_CREATED)
def create_match(
    new_match: NewMatch, response: Response, store: Store, seed: Seed
) -> Match:
    """Start a match against the AI, which plays another deck.

    The ``Location`` header of the response holds the address of the match.
    """
    decks = deck_ids()
    if new_match.deck not in decks:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"There is no such deck. The decks are: {', '.join(decks)}.",
        )
    ai_deck = next(deck for deck in decks if deck != new_match.deck)
    state = start_match((load_deck(new_match.deck), load_deck(ai_deck)), seed=seed)
    state = _ai_plays(state)
    match_id = store.create(state)
    response.headers["Location"] = app.url_path_for("get_match", match_id=str(match_id))
    return _match(match_id, state)


@app.get("/matches/{match_id}")
def get_match(match_id: UUID, store: Store) -> Match:
    """Return a match as the player may see it."""
    state = store.get(match_id)
    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="There is no match with this id.",
        )
    return _match(match_id, state)


def _ai_plays(state: GameState) -> GameState:
    """Let the AI play until it is the player's turn or the match is over.

    The AI chooses from its own view, as the player does (ADR 0006).
    """
    view = player_view(state, AI)
    while view.current == AI and not view.match_over:
        state, _ = apply(state, choose_action(view))
        view = player_view(state, AI)
    return state


def _match(match_id: UUID, state: GameState) -> Match:
    """Return a match as the player may see it, ready to send."""
    return Match(id=match_id, view=from_view(player_view(state, HUMAN)))

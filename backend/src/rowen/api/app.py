"""The web API: start a match against the AI, play it, and see it as the player may.

The server keeps the state of each match and never sends it: a response holds
only the player's view, and the events of their action and of the AI's answer
as the player may see them. So the AI's hand, the order of the decks and the
seed stay on the server (ADR 0002). The human player is player 0 and the AI
player 1, as in the CLI. When the AI has a move to make, it makes it before
the server answers, so the player always gets the match on their turn, unless
the match is over.

When the API turns a request down, it always answers with the same shape, an
``Error``: a ``code`` for the browser and a ``message`` for a person. So does
it when a bug on the server makes a request fail.

Endpoints get the match store and the seed of a new match from ``get_store``
and ``new_seed``, through FastAPI's ``Depends``. The tests replace both with
``app.dependency_overrides``: a new store for each test, and seeds they know.

To run the server on your computer, in ``backend``:
``uv run uvicorn rowen.api.app:app --reload --reload-dir src``.
"""

import secrets
from collections.abc import Mapping
from importlib.metadata import version
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from rowen.ai.baseline import choose_action
from rowen.api.schemas import (
    Action,
    Error,
    ErrorCode,
    Match,
    NewMatch,
    Played,
    from_events,
    from_view,
    to_action,
)
from rowen.api.store import MatchStore
from rowen.data import deck_ids, load_deck
from rowen.engine.public import (
    Event,
    GameState,
    apply,
    player_view,
    start_match,
)

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


class ApiError(Exception):
    """A request the API turns down, with the ``Error`` it answers with."""

    def __init__(self, status_code: int, code: ErrorCode, message: str) -> None:
        """Make the error.

        Args:
            status_code: The HTTP status of the response.
            code: What went wrong, for the browser.
            message: What went wrong, in words, for a person.
        """
        super().__init__(message)
        self.status_code = status_code
        self.error = Error(code=code, message=message)


# The errors an endpoint can answer with, for the OpenAPI document.
def _errors(*status_codes: int) -> dict[int | str, dict[str, Any]]:
    return {status_code: {"model": Error} for status_code in status_codes}


@app.post(
    "/matches",
    status_code=status.HTTP_201_CREATED,
    responses=_errors(status.HTTP_422_UNPROCESSABLE_CONTENT),
)
def create_match(
    new_match: NewMatch, response: Response, store: Store, seed: Seed
) -> Match:
    """Start a match against the AI, which plays another deck.

    The ``Location`` header of the response holds the address of the match.
    """
    decks = deck_ids()
    if new_match.deck not in decks:
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "unknown_deck",
            f"There is no such deck. The decks are: {', '.join(decks)}.",
        )
    ai_deck = next(deck for deck in decks if deck != new_match.deck)
    state = start_match((load_deck(new_match.deck), load_deck(ai_deck)), seed=seed)
    state, _ = _ai_plays(state)
    match_id = store.create(state)
    response.headers["Location"] = app.url_path_for("get_match", match_id=str(match_id))
    return Match(id=match_id, view=from_view(player_view(state, HUMAN)))


@app.get(
    "/matches/{match_id}",
    responses=_errors(status.HTTP_404_NOT_FOUND, status.HTTP_422_UNPROCESSABLE_CONTENT),
)
def get_match(match_id: UUID, store: Store) -> Match:
    """Return a match as the player may see it."""
    state = _state(store, match_id)
    return Match(id=match_id, view=from_view(player_view(state, HUMAN)))


@app.post(
    "/matches/{match_id}/actions",
    responses=_errors(
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
def play(match_id: UUID, action: Action, store: Store) -> Played:
    """Play the player's action, and then let the AI answer.

    The action is one of the legal actions in the player's view, sent back as
    it is. If it isn't legal now, the answer is a 409 and the match doesn't
    change. If another request for the same match kept its result while this
    action was played, the answer is a 409 too: get the match again to see
    where it is.
    """
    old = _state(store, match_id)
    played = to_action(action)
    # The engine works out the legal actions of the player's view. When it
    # isn't the player's turn there are none, so the player can never make a
    # move of the AI's.
    if played not in player_view(old, HUMAN).legal_actions:
        raise ApiError(
            status.HTTP_409_CONFLICT,
            "illegal_action",
            "This action isn't legal now: it isn't one of the legal actions in "
            "the view.",
        )
    state, events = apply(old, played)
    state, answer = _ai_plays(state)
    if not store.replace(match_id, old, state):
        raise ApiError(
            status.HTTP_409_CONFLICT,
            "match_changed",
            "The match changed while this action was played. Get it again.",
        )
    return Played(
        id=match_id,
        view=from_view(player_view(state, HUMAN)),
        events=from_events(events + answer, HUMAN),
    )


def _state(store: MatchStore, match_id: UUID) -> GameState:
    """Return the state of a match, or turn the request down if there is none."""
    state = store.get(match_id)
    if state is None:
        raise ApiError(
            status.HTTP_404_NOT_FOUND,
            "match_not_found",
            "There is no match with this id.",
        )
    return state


def _ai_plays(state: GameState) -> tuple[GameState, tuple[Event, ...]]:
    """Let the AI play until it is the player's turn or the match is over.

    Return the new state and the events of the AI's moves, in order. The AI
    chooses from its own view, as the player does (ADR 0006).
    """
    events: tuple[Event, ...] = ()
    view = player_view(state, AI)
    while view.current == AI and not view.match_over:
        state, new_events = apply(state, choose_action(view))
        events += new_events
        view = player_view(state, AI)
    return state, events


@app.exception_handler(ApiError)
def _api_error(request: Request, error: ApiError) -> JSONResponse:
    """Answer a request an endpoint turned down."""
    return _error(error.status_code, error.error)


@app.exception_handler(RequestValidationError)
def _invalid_request(request: Request, error: RequestValidationError) -> JSONResponse:
    """Answer a request that isn't in the shape the endpoint expects.

    FastAPI's own answer sends back each wrong value. Here only where the first
    mistake is and what kind it is are sent: a value could be huge, or nested
    so deep that sending it back fails.
    """
    first = error.errors()[0]
    where = ".".join(str(part) for part in first["loc"])
    return _error(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        Error(
            code="invalid_request",
            message=f"The request isn't valid at {where}: {first['type']}.",
        ),
    )


@app.exception_handler(HTTPException)
def _http_error(request: Request, error: HTTPException) -> JSONResponse:
    """Answer a request that FastAPI itself turned down.

    That is a request for an address or a method the API doesn't have, or one
    whose body can't even be read, such as text that isn't UTF-8.
    """
    match error.status_code:
        case status.HTTP_404_NOT_FOUND:
            found = Error(code="not_found", message="There is nothing at this address.")
        case status.HTTP_405_METHOD_NOT_ALLOWED:
            found = Error(
                code="method_not_allowed",
                message="This address doesn't take this method.",
            )
        case _:
            found = Error(code="invalid_request", message="The request isn't valid.")
    return _error(error.status_code, found, error.headers)


@app.exception_handler(Exception)
def _server_error(request: Request, error: Exception) -> JSONResponse:
    """Answer a request that failed because of a bug on the server.

    The answer says nothing about the error, which could hold the state of the
    match. The error itself still goes to the server's log.
    """
    return _error(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        Error(code="server_error", message="Something went wrong on the server."),
    )


def _error(
    status_code: int, error: Error, headers: Mapping[str, str] | None = None
) -> JSONResponse:
    """Return the response that sends an error."""
    return JSONResponse(
        error.model_dump(mode="json"), status_code=status_code, headers=headers
    )

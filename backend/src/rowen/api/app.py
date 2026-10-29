"""The web API: start a match against the AI, play it, and see it as the player may.

The server keeps each match, as its seed and every action played (``store``),
and never sends it, nor the state they make: a response holds only the
player's view, and the moves just played (the AI's first actions in a new
match, or the player's action and the AI's answer), each with its events and
the view after it, as the player may see them. So the AI's hand, the order of
the decks and the seed stay on the server (ADR 0002). The human player is
player 0 and the AI player 1, as in the CLI. When the AI has a move to make, it
makes it before the server answers, so the player always gets the match on
their turn, unless the match is over.

A player may also make an account and log in (ADR 0014), but needn't: a guest
plays the same way. A player who is logged in may build decks of their own from
a faction's cards, and keep up to 10. A match a player starts while logged in
is theirs: only they may see it and play it, and it is in the list of their
matches, with how it ended, and in their stats. To anybody else, it is a match
that doesn't exist (404), so the answer doesn't even say that the id is right.
A guest's match is anybody's who has its id, as before. Logging in sets a
cookie with the session's token, which the browser sends back with each
request. A request that would change something and comes from a page of another
site is turned down (``Origin``, below), against cross-site request forgery.

When the API turns a request down, it always answers with the same shape, an
``Error``: a ``code`` for the browser and a ``message`` for a person. It does
the same when a bug on the server makes a request fail.

Endpoints get the match store, the account store, the deck store, the seed of
a new match, the seed of the AI's guesses and the time from ``get_store``,
``get_accounts``, ``get_decks``, ``new_seed``, ``new_ai_seed`` and
``get_now``, through FastAPI's ``Depends``. The tests replace them with
``app.dependency_overrides``: new stores for each test, seeds they know, and
a time they choose.

To run the server on your computer, in ``backend``:
``uv run uvicorn rowen.api.app:app --reload --reload-dir src``.
"""

import hashlib
import os
import secrets
from collections.abc import Awaitable, Callable, Iterable, Mapping
from datetime import UTC, datetime, timedelta
from importlib.metadata import version
from typing import Annotated, Any
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import Cookie, Depends, FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.exceptions import HTTPException

from rowen.ai import baseline, montecarlo
from rowen.api.accounts import AccountStore, MemoryAccountStore, StoredAccount
from rowen.api.database import (
    PostgresAccountStore,
    PostgresDeckStore,
    PostgresMatchStore,
    create_engine,
)
from rowen.api.passwords import check_password, hash_password
from rowen.api.player_decks import MAX_DECKS, DeckStore, MemoryDeckStore, StoredDeck
from rowen.api.schemas import (
    Account,
    Choices,
    Credentials,
    DeckChoice,
    Decks,
    DeckStats,
    DeckSummary,
    Error,
    ErrorCode,
    Match,
    Matches,
    MatchSummary,
    Move,
    MovePlayed,
    NewMatch,
    Played,
    PlayerDeck,
    PlayerDecks,
    Result,
    RoundScores,
    Stats,
    from_choices,
    from_events,
    from_view,
    to_action,
)
from rowen.api.schemas import RoundEnded as RoundEndedJson
from rowen.api.store import (
    DeckCopy,
    Level,
    MatchResult,
    MatchStore,
    MemoryMatchStore,
    StoredMatch,
)
from rowen.data import deck_ids, load_deck, load_specials
from rowen.engine.public import (
    Action,
    Card,
    Deck,
    Event,
    GameState,
    PlayerView,
    RoundEnded,
    apply,
    build_deck,
    player_view,
    start_match,
)

# The human player is always player 0 and the AI player 1, as in the CLI. The
# coin flip in start_match still decides who starts.
HUMAN = 0
AI = 1

# How many random bits a seed has. Whoever knows the seed can work out the
# AI's hand, and a small seed can be found by trying every one against the
# cards in the player's hand. 2**63 seeds are far too many to try. 63 and not
# 64, so that a seed fits PostgreSQL's BIGINT, whose largest value is 2**63 - 1.
SEED_BITS = 63

# The cookie with the session's token. The __Host- prefix makes the browser
# take it only if it is Secure, for the whole site (Path=/) and for this
# address alone, not for others under the same domain (no Domain).
SESSION_COOKIE = "__Host-session"

# How long a session lasts after it was last renewed, and how often it is
# renewed: when the page asks who is logged in (GET /session, each time it
# opens), at most once a day, so that not every request writes to the
# database.
SESSION_LENGTH = timedelta(days=30)
RENEW_AFTER = timedelta(days=1)

# How many matches a page of the list of a player's matches holds at most.
PAGE_SIZE = 20


def _operation_id(route: APIRoute) -> str:
    """Name each endpoint in the OpenAPI document after its function.

    FastAPI's default adds the path and the method (``create_match_matches_post``),
    and the frontend's generated types use these names.
    """
    return route.name


app = FastAPI(
    title="Rowen",
    version=version("rowen"),
    generate_unique_id_function=_operation_id,
    # No redirect from /decks/ to /decks: the API's redirects name its own
    # address, which behind nginx is not the browser's, and the page never adds
    # the slash. Such an address is just unknown (404).
    redirect_slashes=False,
    # Only /docs: each docs page runs scripts from a CDN on the game's
    # address, and the README sends people to this one.
    redoc_url=None,
    swagger_ui_oauth2_redirect_url=None,
)


def make_stores(
    environ: Mapping[str, str],
) -> tuple[MatchStore, AccountStore, DeckStore]:
    """Return the stores the server keeps its matches, accounts and decks in.

    In PostgreSQL if ``DATABASE_URL`` gives its address, so they survive a
    restart, as in Docker Compose and online. All share the same
    connections. Otherwise in the memory of the server's process, as when it
    runs on a computer for development. Then the server must run as a single
    process, as uvicorn does unless told otherwise: with several workers,
    each would have stores of its own, and a match started in one would be
    unknown to the others.
    """
    url = environ.get("DATABASE_URL")
    if url:
        engine = create_engine(url)
        return (
            PostgresMatchStore(engine),
            PostgresAccountStore(engine),
            PostgresDeckStore(engine),
        )
    return MemoryMatchStore(), MemoryAccountStore(), MemoryDeckStore()


# All the server's matches, accounts and decks. No connection to the database
# is made until a request needs one.
_store, _accounts, _decks = make_stores(os.environ)


def get_store() -> MatchStore:
    """Return where the server keeps its matches."""
    return _store


def get_accounts() -> AccountStore:
    """Return where the server keeps its accounts and their sessions."""
    return _accounts


def get_decks() -> DeckStore:
    """Return where the server keeps the decks players built."""
    return _decks


def new_seed() -> int:
    """Return the seed of a new match: random, and never sent to a player."""
    return secrets.randbits(SEED_BITS)


def new_ai_seed() -> int:
    """Return the seed of the AI's guesses in a request: random, as for a match.

    The AI's moves are kept with the match, so a match plays again the same
    without it. It is not the match's seed: from that, the AI would know the
    player's hand.
    """
    return secrets.randbits(SEED_BITS)


def get_now() -> datetime:
    """Return the time now, to know when a session expires."""
    return datetime.now(UTC)


# What an endpoint asks for to get a store, a seed or the time: FastAPI calls
# the function in Depends and passes the endpoint what it returns.
type Store = Annotated[MatchStore, Depends(get_store)]
type Accounts = Annotated[AccountStore, Depends(get_accounts)]
type PlayerDeckStore = Annotated[DeckStore, Depends(get_decks)]
type Seed = Annotated[int, Depends(new_seed)]
type AiSeed = Annotated[int, Depends(new_ai_seed)]
type Now = Annotated[datetime, Depends(get_now)]
# The session's token, from its cookie. An endpoint gives it None as its
# default, for when the browser sends none.
type Token = Annotated[str | None, Cookie(alias=SESSION_COOKIE)]


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


# The errors an endpoint answers with on purpose, for the OpenAPI document. A
# bug on the server (500) and a body that can't be read (400) aren't listed: no
# endpoint answers with them on purpose.
def _errors(*status_codes: int) -> dict[int | str, dict[str, Any]]:
    return {status_code: {"model": Error} for status_code in status_codes}


# Methods that only read, which a page of another site may send.
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@app.middleware("http")
async def _same_origin(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Turn down a request that changes something and comes from another site.

    A browser says which site's page sends a request in ``Origin``, and a page
    can't change it. The page and the API have the same address (behind
    nginx, as in development behind Vite), which the browser sends in
    ``Host``, so a request from the game's own page has an ``Origin`` with
    that address. Without the check, a page of another site could, say, log
    the player out with the cookie their browser keeps for the game. The
    cookie's ``SameSite=Lax`` already keeps the browser from sending it then;
    this is a second guard, in case a browser doesn't.

    A request with no ``Origin`` doesn't come from a page, but from a program
    such as curl, which has no cookie of the player's to send: it goes on.
    """
    origin = request.headers.get("origin")
    if (
        request.method not in _SAFE_METHODS
        and origin is not None
        and urlsplit(origin).netloc != request.headers.get("host")
    ):
        return _error(
            status.HTTP_403_FORBIDDEN,
            Error(
                code="forbidden_origin",
                message="This request comes from a page of another site.",
            ),
        )
    return await call_next(request)


@app.get("/decks")
def list_decks() -> Decks:
    """Return the decks the player can choose from to start a match.

    The AI plays another one of them.
    """
    decks = [load_deck(deck_id) for deck_id in deck_ids()]
    return Decks(decks=tuple(DeckSummary(id=deck.id, name=deck.name) for deck in decks))


@app.post(
    "/matches",
    status_code=status.HTTP_201_CREATED,
    responses=_errors(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
def create_match(
    new_match: NewMatch,
    request: Request,
    response: Response,
    store: Store,
    seed: Seed,
    ai_seed: AiSeed,
    accounts: Accounts,
    decks: PlayerDeckStore,
    now: Now,
    token: Token = None,
) -> Played:
    """Start a match against the AI, which plays another faction's own deck.

    The player plays a faction's own deck (``deck``) or, while logged in, one
    they built (``my_deck``): the match keeps a copy of it, so changing or
    deleting the deck later doesn't change the match (ADR 0017).

    ``level`` is how well the AI plays, ``easy`` when the request doesn't say
    (ADR 0018). If the AI starts, it plays until it is the player's turn, and
    its moves come with the match. The ``Location`` header of the response
    holds the address of the match. If the player is logged in, the match is
    theirs.
    """
    player = _logged_in(accounts, token, now)
    if new_match.my_deck is not None:
        if player is None:
            raise _not_logged_in()
        kept = decks.get_deck(player.id, new_match.my_deck)
        if kept is None:
            raise _deck_not_found()
        faction = kept.faction
        built: DeckCopy | None = DeckCopy(name=kept.name, copies=kept.copies)
    # NewMatch has a deck when it has no my_deck.
    elif new_match.deck is not None and new_match.deck in deck_ids():
        faction, built = new_match.deck, None
    else:
        raise _unknown_deck(status.HTTP_422_UNPROCESSABLE_CONTENT)
    try:
        player_deck = _deck(faction, built)
    except ValueError:
        # A deck kept before the rules changed may break them now.
        raise _invalid_deck() from None
    ai_deck = next(deck for deck in deck_ids() if deck != faction)
    state = start_match((player_deck, load_deck(ai_deck)), seed=seed)
    state, actions, moves = _ai_plays(
        state, new_match.level, (faction, ai_deck), ai_seed
    )
    match = store.create(
        (faction, ai_deck),
        seed,
        actions,
        owner=None if player is None else player.id,
        now=now,
        built=built,
        level=new_match.level,
    )
    # url_path_for leaves out root_path, which behind nginx is /api (uvicorn's
    # --root-path in backend/Dockerfile), so it is added here.
    path = app.url_path_for("get_match", match_id=str(match.id))
    response.headers["Location"] = request.scope.get("root_path", "") + path
    return Played(
        id=match.id,
        version=match.version,
        view=from_view(player_view(state, HUMAN)),
        # The AI's first moves never end a round: the player hasn't passed.
        rounds=(),
        moves=moves,
    )


@app.get(
    "/matches/{match_id}",
    responses=_errors(status.HTTP_404_NOT_FOUND, status.HTTP_422_UNPROCESSABLE_CONTENT),
)
def get_match(
    match_id: UUID, store: Store, accounts: Accounts, now: Now, token: Token = None
) -> Match:
    """Return a match as the player may see it."""
    match = _match(store, match_id, _logged_in(accounts, token, now))
    state, rounds = _play_again(match)
    return Match(
        id=match.id,
        version=match.version,
        view=from_view(player_view(state, HUMAN)),
        rounds=rounds,
    )


@app.post(
    "/matches/{match_id}/actions",
    responses=_errors(
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
def play(
    match_id: UUID,
    move: Move,
    store: Store,
    ai_seed: AiSeed,
    accounts: Accounts,
    now: Now,
    token: Token = None,
) -> Played:
    """Play the player's action, and then let the AI answer, at the match's level.

    The action is one of the legal actions in the player's view, sent back as
    it is, with the version of the match that came with that view. If the
    match is at another version, the answer is a 409 and the match doesn't
    change: get it again to see where it is. That is so also when another
    request for the same match is played first, while this one is. If the
    action isn't legal now, the answer is a 409 too.

    If the match ends, the store keeps how it ended with the last actions.
    """
    old = _match(store, match_id, _logged_in(accounts, token, now))
    # Checked first: an action chosen from an old view may also be legal now,
    # and it would be played twice.
    if move.version != old.version:
        raise _match_changed()
    played = to_action(move.action)
    state, rounds = _play_again(old)
    # The engine works out the legal actions of the player's view. When it
    # isn't the player's turn there are none, so the player can never make a
    # move of the AI's.
    if played not in player_view(state, HUMAN).legal_actions:
        raise ApiError(
            status.HTTP_409_CONFLICT,
            "illegal_action",
            "This action isn't legal now: it isn't one of the legal actions in "
            "the view.",
        )
    state, events = apply(state, played)
    first = _move(state, events)
    state, answer, answer_moves = _ai_plays(state, old.level, old.decks, ai_seed)
    actions = (played, *answer)
    moves = (first, *answer_moves)
    rounds += _rounds(moves)
    result = _result(state, rounds, now) if _over(state) else None
    new = store.add_actions(match_id, old.version, actions, result)
    if new is None:
        raise _match_changed()
    return Played(
        id=new.id,
        version=new.version,
        view=from_view(player_view(state, HUMAN)),
        rounds=rounds,
        moves=moves,
    )


@app.get(
    "/matches",
    responses=_errors(
        status.HTTP_401_UNAUTHORIZED, status.HTTP_422_UNPROCESSABLE_CONTENT
    ),
)
def list_matches(
    store: Store,
    accounts: Accounts,
    now: Now,
    token: Token = None,
    before: UUID | None = None,
) -> Matches:
    """Return the matches of the player who is logged in, newest first.

    A page holds up to 20. For the next one, ``before`` is the id of the last
    match of this one. If the player isn't logged in, the answer is a 401.
    """
    player = _player(accounts, token, now)
    # One more than a page, to know whether there are more.
    found = store.list_matches(player.id, PAGE_SIZE + 1, before)
    return Matches(
        matches=tuple(
            MatchSummary(
                id=match.id,
                deck=match.decks[0],
                deck_name=match.deck_name,
                ai_deck=match.decks[1],
                level=match.level,
                started_at=match.created_at,
                result=None if match.result is None else _result_json(match.result),
            )
            for match in found[:PAGE_SIZE]
        ),
        more=len(found) > PAGE_SIZE,
    )


@app.get(
    "/stats",
    responses=_errors(
        status.HTTP_401_UNAUTHORIZED, status.HTTP_422_UNPROCESSABLE_CONTENT
    ),
)
def get_stats(accounts: Accounts, store: Store, now: Now, token: Token = None) -> Stats:
    """Return how the player's matches ended with each deck they played.

    If the player isn't logged in, the answer is a 401.
    """
    player = _player(accounts, token, now)
    return Stats(
        decks=tuple(
            DeckStats(deck=deck.deck, won=deck.won, lost=deck.lost, drawn=deck.drawn)
            for deck in store.stats(player.id)
        )
    )


@app.get(
    "/decks/{deck_id}/choices",
    responses=_errors(status.HTTP_404_NOT_FOUND, status.HTTP_422_UNPROCESSABLE_CONTENT),
)
def get_choices(deck_id: str) -> Choices:
    """Return what a player may put in a deck they build from a faction's cards.

    ``deck_id`` is the id of the faction's own deck, from ``GET /decks``.
    """
    if deck_id not in deck_ids():
        raise _unknown_deck(status.HTTP_404_NOT_FOUND)
    return from_choices(load_deck(deck_id), load_specials())


@app.get(
    "/my-decks",
    responses=_errors(
        status.HTTP_401_UNAUTHORIZED, status.HTTP_422_UNPROCESSABLE_CONTENT
    ),
)
def list_player_decks(
    accounts: Accounts, decks: PlayerDeckStore, now: Now, token: Token = None
) -> PlayerDecks:
    """Return the decks of the player who is logged in, the oldest first.

    If the player isn't logged in, the answer is a 401.
    """
    player = _player(accounts, token, now)
    return PlayerDecks(
        decks=tuple(_player_deck(deck) for deck in decks.list_decks(player.id)),
        most=MAX_DECKS,
    )


@app.post(
    "/my-decks",
    status_code=status.HTTP_201_CREATED,
    responses=_errors(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
def create_player_deck(
    choice: DeckChoice,
    accounts: Accounts,
    decks: PlayerDeckStore,
    now: Now,
    token: Token = None,
) -> PlayerDeck:
    """Build a deck and keep it for the player who is logged in.

    The deck must keep to the rules (``GET /decks/{id}/choices``), and a
    player may keep up to 10 decks (409 when they have 10).
    """
    player = _player(accounts, token, now)
    _check_deck(choice)
    deck = decks.create_deck(player.id, choice.name, choice.deck, choice.copies, now)
    if deck is None:
        raise ApiError(
            status.HTTP_409_CONFLICT,
            "too_many_decks",
            f"A player may keep up to {MAX_DECKS} decks: delete one first.",
        )
    return _player_deck(deck)


@app.put(
    "/my-decks/{deck_id}",
    responses=_errors(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
def replace_player_deck(
    deck_id: UUID,
    choice: DeckChoice,
    accounts: Accounts,
    decks: PlayerDeckStore,
    now: Now,
    token: Token = None,
) -> PlayerDeck:
    """Change a deck of the player's: its name, faction and copies, all at once.

    As when it was built, the deck must keep to the rules.
    """
    player = _player(accounts, token, now)
    _check_deck(choice)
    deck = decks.replace_deck(
        player.id, deck_id, choice.name, choice.deck, choice.copies
    )
    if deck is None:
        raise _deck_not_found()
    return _player_deck(deck)


@app.delete(
    "/my-decks/{deck_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_errors(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
def delete_player_deck(
    deck_id: UUID,
    accounts: Accounts,
    decks: PlayerDeckStore,
    now: Now,
    token: Token = None,
) -> None:
    """Delete a deck of the player's."""
    player = _player(accounts, token, now)
    if not decks.delete_deck(player.id, deck_id):
        raise _deck_not_found()


@app.post(
    "/accounts",
    status_code=status.HTTP_201_CREATED,
    responses=_errors(status.HTTP_409_CONFLICT, status.HTTP_422_UNPROCESSABLE_CONTENT),
)
def register(
    credentials: Credentials,
    response: Response,
    accounts: Accounts,
    now: Now,
    token: Token = None,
) -> Account:
    """Make an account, and log in with it.

    If another account has the username, the answer is a 409.
    """
    account = accounts.create_account(
        credentials.username, hash_password(credentials.password)
    )
    if account is None:
        raise ApiError(
            status.HTTP_409_CONFLICT,
            "username_taken",
            "There is already an account with this username. Choose another.",
        )
    _start_session(account, response, accounts, now, token)
    return Account(username=account.username)


@app.post(
    "/session",
    responses=_errors(
        status.HTTP_401_UNAUTHORIZED, status.HTTP_422_UNPROCESSABLE_CONTENT
    ),
)
def log_in(
    credentials: Credentials,
    response: Response,
    accounts: Accounts,
    now: Now,
    token: Token = None,
) -> Account:
    """Log in with an account's username and password.

    A username with no account and a wrong password get the same answer, a
    401, so it doesn't tell which usernames have an account.
    """
    account = accounts.find_account(credentials.username)
    password_hash = None if account is None else account.password_hash
    # check_password is always False without an account: "account is None" is
    # here for mypy, which can't know it.
    if not check_password(password_hash, credentials.password) or account is None:
        raise ApiError(
            status.HTTP_401_UNAUTHORIZED,
            "wrong_credentials",
            "The username or the password is wrong.",
        )
    _start_session(account, response, accounts, now, token)
    return Account(username=account.username)


@app.get("/session", responses=_errors(status.HTTP_401_UNAUTHORIZED))
def get_session(
    response: Response, accounts: Accounts, now: Now, token: Token = None
) -> Account:
    """Return the account the player is logged in with.

    If the player isn't logged in, or their session expired, the answer is a
    401. Once a day at most, the session is renewed: it then lasts 30 days
    from now, and so does its cookie.
    """
    session = None if token is None else accounts.find_session(_hash_token(token), now)
    if token is None or session is None:
        raise _not_logged_in()
    if session.expires_at - now < SESSION_LENGTH - RENEW_AFTER:
        accounts.renew_session(session.token_hash, now + SESSION_LENGTH)
        _set_cookie(response, token)
    return Account(username=session.account.username)


@app.delete("/session", status_code=status.HTTP_204_NO_CONTENT)
def log_out(response: Response, accounts: Accounts, token: Token = None) -> None:
    """Log out: the session ends, and the browser forgets its cookie.

    The answer is the same if the player wasn't logged in.
    """
    if token is not None:
        accounts.delete_session(_hash_token(token))
    response.delete_cookie(
        SESSION_COOKIE, path="/", secure=True, httponly=True, samesite="lax"
    )


def _check_deck(choice: DeckChoice) -> None:
    """Turn the request down unless the deck keeps to the rules.

    The engine checks it (``build_deck``), as it would to play the deck. The
    message is the same whatever is wrong, since the engine's would name the
    request's cards and counts, and an error never holds a value from the
    request (``Error``): the page knows the rules from ``GET
    /decks/{id}/choices``, so this is only a last guard.
    """
    if choice.deck not in deck_ids():
        raise _unknown_deck(status.HTTP_422_UNPROCESSABLE_CONTENT)
    try:
        build_deck(
            id=choice.deck,
            name=choice.name,
            faction=load_deck(choice.deck),
            specials=load_specials(),
            copies=choice.copies,
        )
    except ValueError:
        raise _invalid_deck() from None


def _invalid_deck() -> ApiError:
    """Return the error for a deck that breaks the rules."""
    return ApiError(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "invalid_deck",
        "This deck breaks the rules: each card must be one the deck may hold, "
        "with 1 copy up to the most it may have, and a deck needs enough units "
        "and not too many special cards (GET /decks/{id}/choices).",
    )


def _deck(faction: str, built: DeckCopy | None) -> Deck:
    """Return the deck a player plays: their faction's own, or one they built.

    Raises:
        ValueError: If the deck they built breaks the rules.
    """
    if built is None:
        return load_deck(faction)
    return build_deck(
        id=faction,
        name=built.name,
        faction=load_deck(faction),
        specials=load_specials(),
        copies=built.copies,
    )


def _player_deck(deck: StoredDeck) -> PlayerDeck:
    """Return a deck a player built as the API sends it."""
    return PlayerDeck(
        id=deck.id, name=deck.name, deck=deck.faction, copies=dict(deck.copies)
    )


def _deck_not_found() -> ApiError:
    """Return the error for a deck the player doesn't have.

    Also for a deck of another player's: the answer doesn't tell that its id
    is right.
    """
    return ApiError(
        status.HTTP_404_NOT_FOUND, "deck_not_found", "The player has no such deck."
    )


def _unknown_deck(status_code: int) -> ApiError:
    """Return the error for a faction's deck that doesn't exist."""
    return ApiError(
        status_code,
        "unknown_deck",
        f"There is no such deck. The decks are: {', '.join(deck_ids())}.",
    )


def _logged_in(
    accounts: AccountStore, token: str | None, now: datetime
) -> StoredAccount | None:
    """Return the account the player is logged in with, or None for a guest."""
    session = None if token is None else accounts.find_session(_hash_token(token), now)
    return None if session is None else session.account


def _player(accounts: AccountStore, token: str | None, now: datetime) -> StoredAccount:
    """Return the account the player is logged in with, or turn the request down."""
    player = _logged_in(accounts, token, now)
    if player is None:
        raise _not_logged_in()
    return player


def _not_logged_in() -> ApiError:
    """Return the error for a request that needs a player who is logged in."""
    return ApiError(
        status.HTTP_401_UNAUTHORIZED,
        "not_logged_in",
        "The player isn't logged in.",
    )


def _start_session(
    account: StoredAccount,
    response: Response,
    accounts: AccountStore,
    now: datetime,
    old_token: str | None,
) -> None:
    """Start a session of an account, and set its cookie in the response.

    The token is 32 random bytes from the operating system (256 bits), so
    nobody can guess one. The store keeps only its hash.

    ``old_token`` is the token of the cookie the browser sent, if any: its
    session ends, since the new cookie takes its place in the browser and
    nobody could use it any more.
    """
    if old_token is not None:
        accounts.delete_session(_hash_token(old_token))
    token = secrets.token_urlsafe(32)
    accounts.create_session(account, _hash_token(token), now + SESSION_LENGTH, now)
    _set_cookie(response, token)


def _hash_token(token: str) -> bytes:
    """Return a session token's SHA-256 hash, which the store keeps.

    The token is random and long, so a fast hash is enough: unlike a
    password, it can't be found by trying likely ones.
    """
    return hashlib.sha256(token.encode()).digest()


def _set_cookie(response: Response, token: str) -> None:
    """Set the cookie with the session's token, for the next 30 days.

    - ``HttpOnly``: the page's JavaScript can't read it, so a script that
      got into the page can't send it elsewhere.
    - ``Secure``: only over HTTPS (or to localhost, in development).
    - ``SameSite=Lax``: the browser doesn't send it with a request that a
      page of another site makes, only when the player follows a link here.
    """
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(SESSION_LENGTH.total_seconds()),
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )


def _match(
    store: MatchStore, match_id: UUID, player: StoredAccount | None
) -> StoredMatch:
    """Return a match the player may see, or turn the request down.

    ``player`` is the account the player is logged in with, or None. A match
    with an owner is only its owner's: to anybody else, the answer is the
    same as when there is no such match, so it doesn't tell that the id is
    right.
    """
    match = store.get(match_id)
    if match is None or (
        match.owner is not None and (player is None or player.id != match.owner)
    ):
        raise ApiError(
            status.HTTP_404_NOT_FOUND,
            "match_not_found",
            "There is no match with this id.",
        )
    return match


def _match_changed() -> ApiError:
    """Return the error for a move chosen from another version of the match."""
    return ApiError(
        status.HTTP_409_CONFLICT,
        "match_changed",
        "The match changed since this action was chosen. Get it again.",
    )


def _play_again(
    match: StoredMatch,
) -> tuple[GameState, tuple[RoundEndedJson, ...]]:
    """Return the state a match's actions make from the start, and each round's end.

    The engine is deterministic, so this is the state they made when they were
    played (ADR 0003). The player's deck is made again from the match's own
    copy, if they built it (ADR 0017), never from the deck as it is now.

    The rounds are those that ended, in order, as the API sends them. The
    state doesn't keep them: they come only in the event that ends a round.
    """
    player_deck, ai_deck = match.decks
    state = start_match(
        (_deck(player_deck, match.built), load_deck(ai_deck)), seed=match.seed
    )
    rounds: tuple[RoundEndedJson, ...] = ()
    for action in match.actions:
        state, events = apply(state, action)
        rounds += tuple(
            RoundEndedJson(type="round_ended", scores=event.scores, winner=event.winner)
            for event in events
            if isinstance(event, RoundEnded)
        )
    return state, rounds


def _rounds(moves: Iterable[MovePlayed]) -> tuple[RoundEndedJson, ...]:
    """Return the end of each round among the events of moves, in order."""
    return tuple(
        event
        for move in moves
        for event in move.events
        if isinstance(event, RoundEndedJson)
    )


def _over(state: GameState) -> bool:
    """Return whether a match is over."""
    return player_view(state, HUMAN).match_over


def _result(
    state: GameState, rounds: tuple[RoundEndedJson, ...], now: datetime
) -> MatchResult:
    """Return how a match ended: ``state`` is the end, ``rounds`` its rounds."""
    winner = player_view(state, HUMAN).winner
    return MatchResult(
        outcome="drawn" if winner is None else "won" if winner == HUMAN else "lost",
        rounds=tuple(round_.scores for round_ in rounds),
        ended_at=now,
    )


def _result_json(result: MatchResult) -> Result:
    """Return how a match ended, as the API sends it."""
    return Result(
        outcome=result.outcome,
        rounds=tuple(RoundScores(player=player, ai=ai) for player, ai in result.rounds),
        ended_at=result.ended_at,
    )


def _ai_plays(
    state: GameState, level: Level, decks: tuple[str, str], seed: int
) -> tuple[GameState, tuple[Action, ...], tuple[MovePlayed, ...]]:
    """Let the AI play at ``level`` until it is the player's turn or the match is over.

    ``decks`` are the match's deck ids, the player's and then the AI's, and
    ``seed`` the seed of the AI's guesses.

    Return the new state, the AI's actions and its moves as the player sees
    them, in order. The AI chooses from its own view, as the player does
    (ADR 0006).
    """
    actions: tuple[Action, ...] = ()
    moves: tuple[MovePlayed, ...] = ()
    view = player_view(state, AI)
    while view.current == AI and not view.match_over:
        # Each decision guesses with a seed of its own.
        action = _ai_choice(view, level, decks, seed + len(actions))
        state, events = apply(state, action)
        actions += (action,)
        moves += (_move(state, events),)
        view = player_view(state, AI)
    return state, actions, moves


def _ai_choice(
    view: PlayerView, level: Level, decks: tuple[str, str], seed: int
) -> Action:
    """Return the AI's next action at ``level``: the baseline's, or the Monte Carlo's.

    The Monte Carlo AI guesses the hidden cards from the AI's own deck and,
    for the player, their faction's own deck, which anyone can look up, even
    when they play one they built (ADR 0018). It gets them by player index.
    """
    if level == "easy":
        return baseline.choose_action(view)
    samples = (
        montecarlo.NORMAL_SAMPLES if level == "normal" else montecarlo.HARD_SAMPLES
    )
    guess: tuple[tuple[Card, ...], tuple[Card, ...]] = (
        load_deck(decks[HUMAN]).cards,
        load_deck(decks[AI]).cards,
    )
    return montecarlo.choose_action(view, decks=guess, samples=samples, seed=seed)


def _move(state: GameState, events: tuple[Event, ...]) -> MovePlayed:
    """Return an action's events and the state after it, as the player sees them."""
    return MovePlayed(
        events=from_events(events, HUMAN),
        view=from_view(player_view(state, HUMAN)),
    )


@app.exception_handler(ApiError)
def _api_error(request: Request, error: ApiError) -> JSONResponse:
    """Answer a request an endpoint turned down."""
    return _error(error.status_code, error.error)


@app.exception_handler(RequestValidationError)
def _invalid_request(request: Request, error: RequestValidationError) -> JSONResponse:
    """Answer a request that isn't in the shape the endpoint expects.

    FastAPI's own answer lists every mistake, each with its wrong value: it can
    be many times bigger than the request, and a value nested too deep makes it
    fail. Here only where the first mistake is and what kind it is are sent.

    A field the request has and shouldn't is named by the request, not by the
    API: only where it is goes back, not its name, so no value the client sent
    is ever sent back. The same for the keys of ``copies``, the card ids the
    client chose: where stops at ``copies``.
    """
    first = error.errors()[0]
    location = first["loc"]
    if first["type"] == "extra_forbidden":
        location = location[:-1]
    if "copies" in location:
        location = location[: location.index("copies") + 1]
    where = ".".join(str(part) for part in location)
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

# ADR 0014: Log players in with Argon2id passwords and sessions kept in PostgreSQL

- **Status:** Accepted
- **Date:** 2026-10-22

## Context

Phase 4 adds accounts, so that later each player's matches and decks can be
kept ([plan](../plan.md)). Guests must still play in a few seconds, with no
account. Five things had to be chosen: what a player logs in with, how the
password is kept, how the server knows who sends a request, how long that
lasts, and how a page of another site is kept from acting for the player
(cross-site request forgery, CSRF).

What matters: the author wants no monthly cost and no personal data to look
after; the API runs as one process with 1 vCPU and 512 MiB
([ADR 0010](0010-deploy-on-cloud-run.md)) and handles up to 40 requests at
once; the page and the API have the same address, behind nginx online and
behind Vite in development ([ADR 0009](0009-docker-images-behind-nginx.md)).

## Decision

- **A username and a password, no email.** A username is 3 to 20 lower-case
  letters, digits, `_` or `-`; a password 8 to 128 characters (NIST SP
  800-63B asks for at least 8). A forgotten password loses the account.
- **Passwords are kept as Argon2id hashes** (`argon2-cffi`), with OWASP's
  smallest settings: 19 MiB, 2 passes, 1 thread, about 30 ms each. At most 4
  hashes are worked out at once (76 MiB), so 40 logins at the same time can't
  use up the API's memory. A username with no account is still checked
  against a hash, so the answer takes as long and is the same as for a wrong
  password. A password is put in Unicode's NFKC form first (added after the
  review of 26/10), so an "é" typed as one character or as "e" and an accent
  is the same password.
- **Sessions are rows of a `sessions` table in PostgreSQL**
  ([ADR 0013](0013-keep-matches-in-postgresql.md)). Logging in makes a
  token of 32 random bytes and sends it in a cookie; the table keeps only its
  SHA-256 hash, the account and when it expires. Logging out deletes the
  row. The API's role, `rowen_app`, may delete sessions (the migration grants
  it), and still no other rows.
- **The cookie** is `__Host-session`: `HttpOnly`, `Secure`, `SameSite=Lax`,
  `Path=/`. A session lasts 30 days after the player was last seen, renewed
  at most once a day (`GET /session`), so not every request writes to the
  database.
- **Two guards against CSRF.** `SameSite=Lax` keeps the browser from sending
  the cookie with a request another site's page makes. And the API turns
  down (403 `forbidden_origin`) any request but `GET`, `HEAD` and `OPTIONS`
  whose `Origin` doesn't name its own address (the `Host` the browser sent,
  which nginx now passes on). A request with no `Origin` comes from a program,
  not a page, and goes on.
- **nginx limits logins:** 5 `POST`s a minute to `/api/session` and
  `/api/accounts` per address (plus 5 at once), on top of the limits of
  [ADR 0011](0011-limit-requests-per-address.md).
- **Guests stay as they are:** their matches have no owner, and making an
  account later doesn't take them over.
- **The endpoints:** `POST /accounts` (make an account and log in),
  `POST /session` (log in), `GET /session` (who is logged in) and
  `DELETE /session` (log out). As with the matches, both a store in memory
  and one in PostgreSQL sit behind one protocol, `AccountStore`, with the same
  tests.

## Alternatives considered

- **An email and a password.** Usual for a product, but resetting a password
  means sending email (a service, and a cost) and keeping personal data, for
  little gain in a portfolio game.
- **Logging in with GitHub (OAuth).** No passwords to keep, but a recruiter
  would need a GitHub account, and the game would depend on another service.
- **A signed token (JWT) in the cookie, with no table.** No database query per
  request, but logging out can't end a token before it expires without
  keeping a table again, and it has more ways to go wrong.
- **bcrypt.** Well known, but it cuts passwords at 72 bytes, and it is easier
  to attack with dedicated hardware than Argon2id, which takes memory.
- **OWASP's larger Argon2id settings (64 MiB, the library's default).** About
  185 ms each here, and four at once would take a quarter of the API's memory.
- **Only `SameSite`, or a CSRF token.** `SameSite` alone leaves it all to the
  browser; a token in each request is more code in the page and the API, and
  isn't needed when the page and the API share one address.

## Consequences

- Logging in is slow on purpose (about 30 ms of CPU) and limited, so guessing
  passwords is slow too: at most about 7,000 a day from one address. Many
  addresses at once (a botnet) can try more, as ADR 0011 already accepts.
- Each request that needs the player reads the database once, and a page
  can't read the cookie, so the page asks `GET /session` who is logged in.
- Making an account says whether a username is taken: that can't be avoided
  when usernames are unique, and the login limit slows down asking.
- In development, the cookie works over `http://localhost`, which browsers
  treat as secure. A test client must use `https://`.
- If the Argon2id settings change, old hashes still work (the settings are in
  each hash); they aren't hashed again with the new ones yet.
- A setup that rewrote the `Host` header between the browser and the API,
  such as a proxy in front of Cloud Run, would turn every page's request
  down: `Host` would have to be passed on there too.

## Update (2026-10-27)

At 5 a minute, one address could make about 7,000 accounts a day, and each
may keep 10 decks: enough to fill the free database within weeks. Making an
account now has a limit of its own too, in nginx: 1 a minute per address
(nginx counts no slower), plus 10 at once, on top of the logins' limit. That
is about 1,400 a day, as much room as the new matches already allow. A
player makes an account once; CI makes 4 in a run.

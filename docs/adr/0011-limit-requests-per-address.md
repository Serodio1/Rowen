# ADR 0011: Limit the API's requests per visitor's address, in nginx

- **Status:** Accepted
- **Date:** 2026-10-16

## Context

The game is public on Cloud Run ([ADR 0010](0010-deploy-on-cloud-run.md)).
Two kinds of abuse matter there:

- **Pushing out everyone's matches.** The API keeps the last 1,000 matches in
  memory (`MAX_MATCHES`), so 1,000 new matches in a row from one visitor
  would end everyone else's.
- **Floods of requests.** Each move makes the AI think. A flood burns CPU, and
  the spending cap on Cloud Run pauses the game when it is reached.

Behind Cloud Run every request reaches nginx from Google's front end, on a
link-local address (`169.254.169.126` when this was written). The front end
adds the visitor's address at the end of `X-Forwarded-For`, after anything the
visitor wrote there: a request sent with `X-Forwarded-For: 203.0.113.9`
arrived as `203.0.113.9,<the visitor's address>`.

## Decision

- **nginx limits requests per address** (`frontend/nginx.conf`), with
  `limit_req`. Each address has a "bucket" that refills at a fixed rate; a
  burst lets a few requests in a row through at once.
  - Every request to `/api/`: 5 a second, burst 20.
  - New matches (`/api/matches`): 10 a minute, burst 5, on top of that. One
    address would need about 100 minutes to push out 1,000 matches.
- **A visitor is an IPv4 address, or an IPv6 block of 64 bits** (a /64: the
  first four groups). One home usually gets a whole /64 and can send each
  request from another address in it, so counting single IPv6 addresses
  would let one visitor through every limit. When nginx writes the address
  with `::` among those four groups, the groups before `::` are used, a
  larger block: never looser than a /64.
- **The address is the last one in `X-Forwarded-For`, only from Google's
  front end** (`set_real_ip_from 169.254.0.0/16`, `real_ip_recursive off`).
  Link-local addresses cannot come from the internet, and the addresses
  before the last are the visitor's own words. In Compose no request comes
  from there, so the address nginx sees is used.
- **Over a limit, 429 with an error like the API's**:
  `{"code": "too_many_requests", "message": "..."}`. The code joins the
  API's `ErrorCode`, so the OpenAPI document and the page's types know it,
  and the page shows the message.
- **Requests over 16 KB get 413** (`client_max_body_size`), before the API
  reads them. The largest move is under 1 KB.

## Alternatives considered

- **Limits in the API** (a FastAPI middleware). The API would need the
  visitor's address from nginx, the limits would live in the memory of the
  one API process, and requests would reach Python before being turned down.
  nginx turns them down first, and its `limit_req` is well tested.
- **One limit on all of `/api/`.** Simpler, but at 5 a second one address
  could still push out 1,000 matches in about 3 minutes.
- **Only a limit on new matches.** Moves, which make the AI think, would have
  no limit.
- **nginx's default answer** (503 with an HTML page). The page would say it
  cannot reach the server, which is wrong.
- **Google Cloud Armor**, Google's own rate limiting. It needs a load
  balancer in front of Cloud Run, which is billed every month.

## Consequences

- One visitor cannot end everyone's matches alone, or flood the API. Many
  addresses at once still can: that is accepted for a portfolio game, and the
  spending cap bounds the cost.
- People behind one address (a school, an office, a mobile network) share its
  limits. 5 requests a second and 10 new matches a minute are far above what
  a player does.
- The limits live in nginx's memory, per instance: with at most one instance
  (ADR 0010) that is one set of buckets. More instances would each count
  apart.
- If Google ever reached nginx from an address outside `169.254.0.0/16`,
  every visitor would share Google's address and its limits. The access log
  shows the address nginx uses, so this would be visible.
- Anything put in front of Cloud Run later (a load balancer, a CDN) adds its
  own address at the end of `X-Forwarded-For`, so it changes which entry is
  the visitor's: this setting has to change with it.
- A request over 16 KB gets nginx's own HTML page, not an error like the
  API's. The page never sends one.
- `too_many_requests` is in the API's `ErrorCode` although only nginx sends
  it. The endpoints in the OpenAPI document do not list a 429: nginx, not
  the API, answers it, for any of them.
- With the visitor's real address, nginx's log lines in Cloud Logging hold
  it. Cloud Run's own request log already did, so little changes.
- CI cannot check the part that only Google's front end exercises
  (`set_real_ip_from`), since in Compose no request comes from there:
  `docs/deploy.md` says how to check it after a deployment.

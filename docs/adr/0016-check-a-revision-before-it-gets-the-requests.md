# ADR 0016: Check a new revision before it gets the requests, built from fixed base images

- **Status:** Accepted
- **Date:** 2026-10-26

## Context

Since [ADR 0012](0012-deploy-from-ci.md), each merge to `main` deploys itself.
`gcloud run services replace` started the new revision and sent it all the
requests as soon as its containers' startup probes passed; the check online
came after. The probes only ask the API for `/decks`, which needs no
database, so a revision that cannot reach PostgreSQL (a wrong secret, a
migration it does not match) passed them and took every visitor's request
until someone went back by hand. ADR 0012 had left this out as more steps
than it was worth before the first deployment could be tried.

The check also does more than ADR 0012 says: since the matches moved to
PostgreSQL ([ADR 0013](0013-keep-matches-in-postgresql.md)), it makes a new
match and reads it back, so that the database is checked too.

Two jobs build the images of each commit: *Docker* builds and tests them,
*Deploy* builds them again and pushes them. The Dockerfiles started from
tags (`python:3.14-slim-trixie`, `node:24-alpine`,
`nginx-unprivileged:1.30-alpine`), which move whenever their makers publish
a new build, so the images online could start from a base no test had run on.

## Decision

- **The new revision starts with no traffic.** `deploy/cloud-run.yaml` names
  it after the commit (`rowen-<short hash>`) and lists the traffic: all of it
  to the revision that answers now (read from the service before deploying),
  none to the new one, which gets the tag `candidate`. A tag gives a revision
  its own address, `https://candidate---<the service's address>`.
- **The check runs against that address**: the page with its
  Content-Security-Policy, the decks through nginx, and a new match read back
  from the database.
- **Only if it passes, the traffic moves** (`gcloud run services
  update-traffic --to-revisions=rowen-<short hash>=100`), and the game's own
  address must still answer. If anything before fails, the job fails and the
  visitors never meet the new revision.
- **The base images are named by digest** as well as tag
  (`python:3.14-slim-trixie@sha256:…`), so both builds of a commit start from
  the same bytes. Taking a new build of a base (for its security fixes) is a
  change to the Dockerfile, in a pull request, that CI tests.

## Alternatives considered

- **A readiness probe that asks the database** (an endpoint running
  `SELECT 1`). A revision with a broken database would never start, but every
  cold start would wait for Neon to wake up (it sleeps after 5 minutes), and
  the probe would only cover what that one query covers.
- **Leaving it as it was**, going back by hand
  (`update-traffic --to-revisions`) after a failed check. Nothing to add, but
  the game is broken online for the time it takes to notice.
- **Passing the tested images from the *Docker* job to the *Deploy* job**
  (as a file between jobs, or through a registry). The images online would be
  the very ones tested, but it moves about a gigabyte between jobs on each
  run, or needs a registry the pull requests can push to.

## Consequences

- A revision that fails the check never gets a visitor's request. The check
  makes one match on the database per deployment, as before.
- The `candidate` tag stays on the newest revision, so its address keeps
  answering; it is the same game as the main address.
- `rowen-deploy` needs no new permission: Cloud Run Developer may already
  update the service's traffic.
- The deployment has one more step, and the file has one more placeholder
  (`SERVING_REVISION`) to fill when deploying by hand (`docs/deploy.md`). The
  very first deployment, with no revision to keep, needs the old `traffic`
  part instead.
- Deploying the same commit again does not make a new revision, as before:
  a revision's name is taken once.
- The base images no longer take security fixes by themselves. Someone has
  to update the digests now and then; nothing in the repository reminds them
  yet.

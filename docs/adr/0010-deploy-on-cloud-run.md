# ADR 0010: Deploy the game on Google Cloud Run, nginx and the API in one service

- **Status:** Accepted
- **Date:** 2026-10-16

## Context

Phase 2 puts the game at a public HTTPS address (#54). Rowen is a portfolio
project: it should cost next to nothing from month to month, and someone who opens the
link should be able to play within seconds. The game already runs as two Docker
images, nginx with the page and the web API ([ADR 0009](0009-docker-images-behind-nginx.md)).
Until the database (#55), matches live in the memory of one API process, so
only one copy of the API may run.

## Decision

- **Google Cloud Run, region `europe-west1`.** Cloud Run runs containers and,
  with request-based billing, bills their CPU and memory only while they start
  and answer requests; its monthly free tier is far above what a portfolio
  game uses. With no requests, it runs no instances.
- **One service, `rowen`, with two containers** (`deploy/cloud-run.yaml`):
  `web` (nginx) receives the requests on port 8080; `api` runs beside it, a
  *sidecar*. The containers of an instance share its network, so nginx passes
  `/api/` on to `127.0.0.1:8000`. nginx starts after the API's startup probe
  passes (`container-dependencies`).
- **At most one instance** (`maxScale: "1"`), since matches are in memory,
  with CPU only during requests (`cpu-throttling`), so idle time is not
  billed.
- **Images built on the developer's computer**, named after the commit, and
  pushed to Artifact Registry in the same region. A cleanup policy keeps the
  last 3 versions of each image, within the store's free 0.5 GB. The steps are
  in [`docs/deploy.md`](../deploy.md); deploying from CI on every merge is
  #56.
- **Its own service account, with no roles**: the game calls no other Google
  service. Cloud Run would otherwise run it as the Compute Engine default
  service account, which has the Editor role on the whole project by default.
- **uvicorn ignores `X-Forwarded-For` and `X-Forwarded-Proto`**
  (`--no-proxy-headers`): it trusts them from 127.0.0.1, which is now nginx,
  and nginx passes on what the browser sent, so a visitor could choose the
  address the API sees.
- **Public through IAM**: `allUsers` gets `roles/run.invoker`.
- **Budgets on the project**: an alert at €1 for all services, and a spending
  cap on Cloud Run at €2 a month at list prices.
- **Compose mirrors Cloud Run**: `web` shares the API's network
  (`network_mode: "service:api"`), so nginx reaches the API on `127.0.0.1`
  there too, and one `nginx.conf` serves both. nginx's redirects name only the
  path (`absolute_redirect off`), since behind Cloud Run its own address
  (http, port 8080) is not the browser's.

## Alternatives considered

- **A virtual machine.** Always on, so no waiting after idle time, and matches
  kept until a restart. But it is billed whether anyone plays or not, and its
  system and Docker have to be installed and patched by hand.
- **Two Cloud Run services**, one per image. nginx would reach the API over
  the internet, with HTTPS and a token for each request, and the API would
  have its own public address and its own cold start.
- **One image with both nginx and the API.** It undoes ADR 0009's two images
  and needs a process manager inside the container.
- **A minimum of one instance** (`minScale: "1"`). No cold start and fewer
  lost matches, but billed all the time.
- **Building with Cloud Build** (`gcloud run deploy --source`). One more API
  and service account to set up, and the images built in the cloud are not
  the ones tried on the computer.
- **Deploying from CI now.** GitHub would need credentials for the project
  (Workload Identity Federation): one more concept in a pull request that
  already brings Cloud Run, so it is a pull request of its own (#56).

## Consequences

- The game has a public address. While the free tier lasts, it costs only a
  few cents a month of outbound data: from Europe, that is billed from the
  first byte.
- The cap counts list prices, before the free tier, and is not instant: about
  15 hours a month of busy instance could reach it while the real bill is
  still €0, and Google would then pause the game until the next month. Far
  more than a portfolio game sees, and the cap can be raised.
- After some idle minutes the instance stops: the next visitor waits for both
  containers to start (a cold start), and the matches in memory are lost, as
  they are with every deployment. Both end with the database (#55), which will
  have to fit the same rule of no monthly cost.
- One instance answers everyone, up to 80 requests at once
  (`containerConcurrency`, set since its default depends on the CPU).
  A visitor can still start enough matches to push out everyone else's
  (`MAX_MATCHES` in the API's store): a limit on requests per address comes in
  the next pull request, once the real `X-Forwarded-For` behind Cloud Run has
  been seen.
- This changes two points of ADR 0009. Compose publishes the page's port on
  the `api` service, the one whose network both containers share. And Compose
  must restart nginx when the API's container is replaced (`restart: true`)
  because nginx lives in that container's network, no longer because it looks
  up the API's address: `docker compose up` for the whole game does it, but
  `docker compose up api` alone leaves nginx in the old network.
- Artifact Registry keeps the last 3 versions of each image, so only the last
  3 deployments can be rolled back to.
- The project ID and the image tag are placeholders in `deploy/cloud-run.yaml`,
  replaced at deploy time, so the file holds no account details.

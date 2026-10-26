# ADR 0012: Deploy from CI on every merge, signed in to Google with no stored key

- **Status:** Accepted; how a new revision gets the requests, and what the
  check online does, changed in [ADR 0016](0016-check-a-revision-before-it-gets-the-requests.md)
- **Date:** 2026-10-17

## Context

The game runs on Cloud Run ([ADR 0010](0010-deploy-on-cloud-run.md)), and
until now each deployment was a block of commands run by hand after a merge
(`docs/deploy.md`), with the images built on the author's computer. A step
that depends on someone remembering it gets forgotten, and the game online
falls behind `main`. This ADR replaces that one point of ADR 0010; the rest of
it stands.

To deploy, a GitHub Actions job must act in the Google Cloud project: push
images to Artifact Registry and update the `rowen` service. Whatever lets it
do that is a way into the project, and the repository is public.

## Decision

- **A `deploy` job in `ci.yml`**, after the `backend`, `frontend` and `docker`
  jobs pass, on `main` only: on every push to `main` (each merge), and from
  the *Run workflow* button to deploy `main` again. It runs the same steps as
  a deployment by hand, with the commit's short hash as the images' tag, then
  checks that the page (with its Content-Security-Policy) and the decks answer
  online. It makes no new match, so it uses up no visitor's limit.
- **No stored key: Workload Identity Federation.** The job asks GitHub for a
  short-lived token (OIDC), signed by GitHub, that names the repository, the
  branch and the environment. Google checks the signature and trades the
  token for an hour of access as the service account `rowen-deploy`
  (`google-github-actions/auth`).
- **Google trusts only this repository and only its `production`
  environment.** The pool admits only tokens with this repository's ID,
  which, unlike its name, a new repository can never take. Only tokens whose
  subject is `repo:Serodio1@91077172/Rowen@1393642354:environment:production`
  (the owner and the repository with their IDs, as GitHub names them for
  repositories created after 15 July 2026) may act as
  `rowen-deploy`, and on GitHub only `main` may run a job in `production`.
  A pull request's run cannot get such a token.
- **`rowen-deploy` may do only what a deployment needs:** Cloud Run Developer
  on the `rowen` service only, Artifact Registry Writer on the `rowen` store
  only, and Service Account User on `rowen-run` only (to run the service as
  it). It cannot create other services, read other stores or change
  permissions.
- **No manual approval** before deploying: the merge is the approval.
- **On `main`, a run never stops halfway.** A new push to `main` waits for the
  run in progress, and a waiting run makes way for a newer one, so the last
  commit is always deployed last. On pull requests a new push still cancels
  the run in progress.
- **If the check online fails, the job fails** and GitHub sends an email. The
  new revision already gets the requests, so going back is by hand
  (`update-traffic --to-revisions`, in `docs/deploy.md`).

## Alternatives considered

- **A service account key** (a JSON file) in a GitHub secret. Simpler to set
  up, but the key never expires by itself: anyone who reads it, from a log
  or a leaked secret, can use it until someone notices and deletes it.
  Google recommends federation instead.
- **Deploying by hand** (as before). Nothing to set up, but the game online
  falls behind `main` whenever the step is forgotten, and it needs Docker on
  the author's computer.
- **A manual approval** on the environment before each deployment. Safer
  against a bad merge, but it is the forgotten step again, and the author is
  the only reviewer.
- **Trying the new revision before it gets the requests** (deploying it with
  no traffic, checking it at its own address, then moving the traffic). The
  game would never be broken online, but it takes more steps and permissions,
  and cannot be tried from where this was written.
- **Deploying from a separate workflow** started when CI finishes
  (`workflow_run`). It runs with the default branch's workflow file and
  needs care to deploy the right commit; a job in the same run gets the
  commit and the order for free.

## Consequences

- A merge to `main` puts the change online in a few minutes, with no step to
  remember, and every deployment is a commit of `main` with nothing on top.
- No secret to keep: nothing in the repository or in GitHub gives access to
  Google by itself. The three values the job needs are GitHub environment
  variables, not secrets.
- The setup is one-off but has many parts (two Google APIs, a pool, a
  provider, an account with three roles, a GitHub environment with a branch
  rule and three variables), in `docs/deploy.md`. CI cannot try it before the
  first merge: the first real test is the first deployment.
- A bad merge goes online, and is caught only by CI before it and by the
  check after it. Going back is a command by hand.
- Each deployment builds the images again on another runner, so the images
  online are not the ones the `docker` job tested, but they are built from
  the same commit with the same Dockerfiles.

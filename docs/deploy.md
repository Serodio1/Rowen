# Deploying to Google Cloud Run

The game runs on [Cloud Run](https://cloud.google.com/run) as one service,
`rowen`, in the `europe-west1` region: nginx with the page and the web API run
side by side in each instance ([ADR 0010](adr/0010-deploy-on-cloud-run.md),
[`deploy/cloud-run.yaml`](../deploy/cloud-run.yaml)). The images are kept in
Artifact Registry, Google's store for images.

**Every merge to `main` deploys itself**: once CI passes on `main`, the
*Deploy* job builds the images, pushes them, starts a new revision of the
service, checks it at its own address and only then sends it the visitors'
requests ([`ci.yml`](../.github/workflows/ci.yml),
[ADR 0012](adr/0012-deploy-from-ci.md),
[ADR 0016](adr/0016-check-a-revision-before-it-gets-the-requests.md)). To deploy `main` again, open
*Actions* → *CI* → *Run workflow* on GitHub and run it on `main`. Deploying
by hand, below, is the fallback.

The commands below are for PowerShell on Windows, run from the repository's
folder, with the [gcloud CLI](https://cloud.google.com/sdk/docs/install)
signed in (`gcloud init`) as the project's owner, and the project chosen as its
default. Docker Desktop must be running to deploy by hand.

## Once per project

In the [Google Cloud console](https://console.cloud.google.com/billing), link
a billing account to the project (the APIs below need one), then, under
*Billing* → *Budgets & alerts*, create two budgets: an alert by email at €1 for
all services, and a spending cap on Cloud Run at €2 a month. The cap counts
list prices, before the free tier, and is not instant: when it is reached,
Google pauses Cloud Run, so the game goes offline until the next month or
until the cap is raised.

Turn on the three Google APIs the deployment uses, and nothing else:

```powershell
gcloud services enable run.googleapis.com artifactregistry.googleapis.com iam.googleapis.com
gcloud services list --enabled    # compute.googleapis.com must not be listed
```

Create the image store, and the policy that keeps only the last 3 versions of
each image (the store is free up to 0.5 GB). Artifact Registry applies the
policy about once a day, so only the last 3 deployments can be rolled back to.
The second command must print `Dry run is disabled.`: the policy really
deletes.

```powershell
gcloud artifacts repositories create rowen --repository-format=docker --location=europe-west1
gcloud artifacts repositories set-cleanup-policies rowen --location=europe-west1 --policy=deploy/cleanup-policy.json --no-dry-run
```

Create the service's own identity, with no roles: the game calls no other
Google service. Google may take a minute to know it everywhere: if the first
deployment says it does not exist, run that deployment again.

```powershell
gcloud iam service-accounts create rowen-run --display-name="Rowen on Cloud Run"
```

Let Docker push to the store, with gcloud's sign-in:

```powershell
gcloud auth configure-docker europe-west1-docker.pkg.dev
```

## Once per project: deploying from CI

CI signs in to Google with no stored key, through *Workload Identity
Federation*: each run of the *Deploy* job gets a token from GitHub, signed by
GitHub, that says which repository and environment it runs for, and Google
trades it for an hour of access as the account `rowen-deploy`. Google only
trusts tokens from this repository (its ID never changes, unlike its name)
and from jobs in the GitHub environment `production`, which only `main` may
use.

Turn on the two APIs that trade the token:

```powershell
gcloud services enable sts.googleapis.com iamcredentials.googleapis.com
```

Create the account CI deploys as, and let it do only what a deployment needs:
update the `rowen` service, push to the `rowen` image store, and run the
service as `rowen-run`. Paste one line at a time: a long line pasted with
others can be cut short. The lines that start with `$` keep a value for the
next ones, so run them all in the same terminal.

```powershell
$project = gcloud config get-value project
$number = gcloud projects describe $project --format="value(projectNumber)"
$deployer = "rowen-deploy@$project.iam.gserviceaccount.com"
$member = "serviceAccount:$deployer"

gcloud iam service-accounts create rowen-deploy --display-name="Rowen's deployments from GitHub"
gcloud run services add-iam-policy-binding rowen --region=europe-west1 --member=$member --role=roles/run.developer
gcloud artifacts repositories add-iam-policy-binding rowen --location=europe-west1 --member=$member --role=roles/artifactregistry.writer
gcloud iam service-accounts add-iam-policy-binding "rowen-run@$project.iam.gserviceaccount.com" --member=$member --role=roles/iam.serviceAccountUser
```

Trust GitHub's tokens from this repository only, then let the jobs in
`production` act as `rowen-deploy`. `1393642354` is the repository's ID and
`91077172` its owner's (`https://api.github.com/repos/Serodio1/Rowen` shows
both). GitHub names a job in a token's subject by these IDs as well as the
names, `repo:Serodio1@91077172/Rowen@1393642354:environment:production`, for
repositories created after 15 July 2026, such as this one; older ones use
`repo:Serodio1/Rowen:environment:production` unless they opt in. A subject
that does not match exactly is turned down with
`Permission 'iam.serviceAccounts.getAccessToken' denied`.

```powershell
gcloud iam workload-identity-pools create github --location=global
$issuer = "https://token.actions.githubusercontent.com"
$mapping = "google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.repository_id=assertion.repository_id"
$condition = "assertion.repository_id=='1393642354'"
gcloud iam workload-identity-pools providers create-oidc rowen --location=global --workload-identity-pool=github --issuer-uri=$issuer --attribute-mapping=$mapping --attribute-condition=$condition
$principal = "principal://iam.googleapis.com/projects/$number/locations/global/workloadIdentityPools/github/subject/repo:Serodio1@91077172/Rowen@1393642354:environment:production"
gcloud iam service-accounts add-iam-policy-binding $deployer --role=roles/iam.workloadIdentityUser --member=$principal

gcloud iam workload-identity-pools providers describe rowen --location=global --workload-identity-pool=github --format="value(name)"
$deployer
$project
```

The last three lines print the values GitHub needs. On GitHub, under the
repository's *Settings* → *Environments*, create the environment
`production`. Under *Deployment branches and tags*, choose *Selected branches
and tags* and add `main`, so no other branch can run a job in it. Under
*Environment variables* (not secrets: none of them gives access), add:

| Name | Value |
|---|---|
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | what `providers describe` printed, `projects/…/providers/rowen` |
| `GCP_SERVICE_ACCOUNT` | `rowen-deploy@<the project's ID>.iam.gserviceaccount.com` |
| `GCP_PROJECT_ID` | the project's ID |

Google may take a few minutes to apply new permissions: if the first
deployment from CI is denied, run it again with *Run workflow*.

## Once per project: the database

The matches are kept in PostgreSQL, on [Neon](https://neon.com)'s free plan,
in Frankfurt, near Cloud Run's `europe-west1`
([ADR 0013](adr/0013-keep-matches-in-postgresql.md)). Two roles use it:

- the database's owner, `neondb_owner`, which CI uses to run the migrations
  (they make and change the tables);
- `rowen_app`, which the API uses: it may only read, add and change rows,
  never change a table. The exceptions are deleting sessions, to log out,
  which the migration that makes the `sessions` table allows
  ([ADR 0014](adr/0014-accounts-with-sessions-in-postgresql.md)), and
  deleting the decks players build, which the migration that makes the
  `player_decks` table allows.

**On Neon** (sign up at <https://neon.com>, with GitHub or an email), create
a project: name `rowen`, Postgres version 18, region *AWS Europe Central 1
(Frankfurt)*. Then open *SQL Editor* and run this first, to get a long random
password for `rowen_app` (64 hexadecimal characters):

```sql
SELECT replace(gen_random_uuid()::text || gen_random_uuid()::text, '-', '');
```

Copy it, then run the rest with the password pasted in place of `PASSWORD`:

```sql
CREATE ROLE rowen_app WITH LOGIN PASSWORD 'PASSWORD';
GRANT CONNECT ON DATABASE neondb TO rowen_app;
GRANT USAGE ON SCHEMA public TO rowen_app;
-- The tables the owner makes later (the migrations) are open to rowen_app.
ALTER DEFAULT PRIVILEGES FOR ROLE neondb_owner IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE ON TABLES TO rowen_app;
```

Under *Connect* (on the project's dashboard), with *Connection pooling*
turned off, copy the address Neon shows for `neondb_owner`. It looks like
`postgresql://neondb_owner:...@ep-....eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require`.
Make the two addresses the game uses from it, changing `sslmode=require` to
`sslmode=verify-full&sslrootcert=/etc/ssl/certs/ca-certificates.crt`, so the
connection also checks that the server is Neon's (the file is where Debian
and Ubuntu keep the certificates they trust):

- **for the migrations**, the owner's, as it is apart from `sslmode`;
- **for the API**, the same with `rowen_app` and its password in place of
  `neondb_owner` and the owner's password.

**In Secret Manager**, keep the API's address, readable by `rowen-run` only.
`Read-Host` asks for it, so it never goes into the terminal's history, and
the file it is written to is deleted at once (with .NET's `File.Delete`:
`Remove-Item` can't find the file when the user's folder has an accented
letter, such as `C:\Users\Serôdio`):

```powershell
gcloud services enable secretmanager.googleapis.com
$project = gcloud config get-value project
$file = "$env:TEMP\rowen-database-url.txt"
Read-Host "The API's address" | Set-Content -NoNewline -Path $file
gcloud secrets create rowen-database-url --replication-policy=automatic --data-file=$file
[System.IO.File]::Delete($file)
gcloud secrets add-iam-policy-binding rowen-database-url --member="serviceAccount:rowen-run@$project.iam.gserviceaccount.com" --role=roles/secretmanager.secretAccessor
```

Cloud Run reads it when an instance starts (`deploy/cloud-run.yaml`). To
change it later, `gcloud secrets versions add rowen-database-url
--data-file=...`, then deploy again.

**On GitHub**, in the environment `production` (*Settings* → *Environments*),
under *Environment secrets* (not variables: this one gives access), add
`MIGRATION_DATABASE_URL` with the address for the migrations. The *Deploy*
job runs `alembic upgrade head` with it before each deployment.

## Every deployment by hand

When CI cannot deploy. Deploy a commit of `main` with nothing changed on top, so the images match the
commit they are named after:

```powershell
git switch main
git pull
git status --short    # must print nothing

$project = gcloud config get-value project
$project                       # the project's ID: if empty, run gcloud init
$tag = git rev-parse --short HEAD
$registry = "europe-west1-docker.pkg.dev/$project/rowen"

docker build --platform=linux/amd64 --provenance=false --tag "$registry/api:$tag" backend
docker build --platform=linux/amd64 --provenance=false --tag "$registry/web:$tag" frontend
docker push "$registry/api:$tag"
docker push "$registry/web:$tag"

# The revision that gets the requests now
$serving = gcloud run services describe rowen --region=europe-west1 --format=json |
    ConvertFrom-Json | ForEach-Object { $_.status.traffic } | Where-Object { $_.percent -eq 100 } |
    ForEach-Object { $_.revisionName }
$serving                       # such as rowen-00012-abc or rowen-7335d05

(Get-Content deploy/cloud-run.yaml) -replace 'PROJECT_ID', $project -replace 'IMAGE_TAG', $tag -replace 'SERVING_REVISION', $serving |
    Set-Content "$env:TEMP\rowen-run.yaml"
gcloud run services replace "$env:TEMP\rowen-run.yaml" --region=europe-west1

# Try the new revision at its own address, then send it the requests
$candidate = gcloud run services describe rowen --region=europe-west1 --format=json |
    ConvertFrom-Json | ForEach-Object { $_.status.traffic } | Where-Object { $_.tag -eq "candidate" } |
    ForEach-Object { $_.url }
curl.exe -sI "$candidate/"
curl.exe -s "$candidate/api/decks"
gcloud run services update-traffic rowen --region=europe-west1 --to-revisions="rowen-$tag=100"
```

Cloud Run runs only `linux/amd64` images, whatever the computer is.
`--provenance=false` leaves out the build's record that Docker Desktop
otherwise pushes beside each image, which Artifact Registry could count as
versions of its own.

`services replace` creates a new revision of the service, named after the
commit, and starts it beside the one that answers now, which keeps all the
requests ([ADR 0016](adr/0016-check-a-revision-before-it-gets-the-requests.md)).
The new one gets the tag `candidate`, an address of its own; `update-traffic`
then sends it the requests. Adding `--dry-run` to `services replace` checks
the file without deploying. CI runs the same commands. If the deployment brings a migration, run it first, in `backend`,
with the address for the migrations:

```powershell
$env:DATABASE_URL = Read-Host "The address for the migrations"
uv run alembic upgrade head
Remove-Item Env:DATABASE_URL
```

## The first time only: open it to everyone

The very first deployment has no revision to keep the requests: for that one,
the `traffic` part of `deploy/cloud-run.yaml` must be only
`- latestRevision: true` with `percent: 100`.

A new service only answers callers with a Google account that may call it.
This lets anyone call it, as a public website:

```powershell
gcloud run services add-iam-policy-binding rowen --region=europe-west1 --member=allUsers --role=roles/run.invoker
```

The service's address:

```powershell
$url = gcloud run services describe rowen --region=europe-west1 --format="value(status.url)"
curl.exe -sI "$url/"              # 200, with the Content-Security-Policy
curl.exe -s "$url/api/decks"      # the decks
```

## Checking the limits on requests

CI cannot try how nginx finds the visitor's address behind Cloud Run
([ADR 0011](adr/0011-limit-requests-per-address.md)). After a deployment that
changes `frontend/nginx.conf`, send a request with a made-up address, then
read the logs:

```powershell
$url = gcloud run services describe rowen --region=europe-west1 --format="value(status.url)"
curl.exe -s -o NUL -H "X-Forwarded-For: 203.0.113.9" "$url/api/decks"
gcloud run services logs read rowen --region=europe-west1 --limit=10
```

nginx's line for that request must start with your own address, not
`203.0.113.9` nor `169.254.…`. Then new matches in a row must end in 429:

```powershell
1..10 | ForEach-Object { curl.exe -s -o NUL -w "%{http_code} " --data "{}" "$url/api/matches" }
#   422 422 422 422 422 422 429 429 429 429
```

The body `{}` names no deck, so the API turns each request down (422) and no
match is made, but nginx counts it. Two things that look like checks do not
work from a computer far from the server:

- Requests for the decks in a row: each one takes about a tenth of a second
  to come back, so they arrive at about 7 a second, and the limit of 5 a
  second with a burst of 20 lasts beyond 40 of them.
- A `POST` with no body (`-X POST` alone): curl sends no `Content-Length`,
  and Google's front end answers 411 before nginx sees it.

## When something goes wrong

When the *Deploy* job fails, GitHub sends an email. If it failed before
*Move the traffic*, the visitors still meet the earlier revision: look at the
logs, and merge a fix. If the game breaks later, go back to an earlier
revision (below) until a fix is merged, but only to one that knows the
database as it is now.

What the containers printed (each request, and any error):

```powershell
gcloud run services logs read rowen --region=europe-west1 --limit=50
```

Go back to an earlier revision (its name comes from the list, such as
`rowen-7806113`); the next deployment keeps it until its own new revision
passes the check. `--remove-tags` takes the `candidate` address off the
broken revision:

```powershell
gcloud run revisions list --service=rowen --region=europe-west1
gcloud run services update-traffic rowen --region=europe-west1 --to-revisions=REVISION_NAME=100 --remove-tags=candidate
```

Never go back to a revision older than the database's newest migration
(`git log -- backend/migrations/versions` gives its commit). The migrations
only add, so the older code still starts, but it does not know what they
added, and it breaks the matches that use it. The newest one came with
`rowen-3b8f05f` (a match keeps a copy of its built deck): a revision older
than it replays such a match from the faction's own deck instead (an error,
or, worse, new moves from the wrong cards, kept for good), and older ones
also let anyone read a player's match and finish a match without keeping
its result. A page left open keeps sending moves to whichever revision
answers. If the newest revision that knows the database is the broken one,
fix it forward: revert the change on `main` and let CI deploy the revert.
Going down a migration (`alembic downgrade`) is no way back either: it
throws away what the migration kept.

Take the game offline (the images stay in the store):

```powershell
gcloud run services delete rowen --region=europe-west1
```

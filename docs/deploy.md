# Deploying to Google Cloud Run

The game runs on [Cloud Run](https://cloud.google.com/run) as one service,
`rowen`, in the `europe-west1` region: nginx with the page and the web API run
side by side in each instance ([ADR 0010](adr/0010-deploy-on-cloud-run.md),
[`deploy/cloud-run.yaml`](../deploy/cloud-run.yaml)). The images are kept in
Artifact Registry, Google's store for images.

**Every merge to `main` deploys itself**: once CI passes on `main`, the
*Deploy* job builds the images, pushes them, updates the service and checks
that the game answers ([`ci.yml`](../.github/workflows/ci.yml),
[ADR 0012](adr/0012-deploy-from-ci.md)). To deploy `main` again, open
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
service as `rowen-run`:

```powershell
$project = gcloud config get-value project
$number = gcloud projects describe $project --format="value(projectNumber)"
$deployer = "rowen-deploy@$project.iam.gserviceaccount.com"

gcloud iam service-accounts create rowen-deploy --display-name="Rowen's deployments from GitHub"
gcloud run services add-iam-policy-binding rowen --region=europe-west1 --member="serviceAccount:$deployer" --role=roles/run.developer
gcloud artifacts repositories add-iam-policy-binding rowen --location=europe-west1 --member="serviceAccount:$deployer" --role=roles/artifactregistry.writer
gcloud iam service-accounts add-iam-policy-binding "rowen-run@$project.iam.gserviceaccount.com" --member="serviceAccount:$deployer" --role=roles/iam.serviceAccountUser
```

Trust GitHub's tokens from this repository only (`1393642354` is its ID:
`https://api.github.com/repos/Serodio1/Rowen` shows it), then let the jobs in
`production` act as `rowen-deploy`:

```powershell
gcloud iam workload-identity-pools create github --location=global --display-name="GitHub Actions"
gcloud iam workload-identity-pools providers create-oidc rowen --location=global --workload-identity-pool=github --display-name="Rowen's CI" --issuer-uri="https://token.actions.githubusercontent.com" --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.repository_id=assertion.repository_id" --attribute-condition="assertion.repository_id == '1393642354'"
gcloud iam service-accounts add-iam-policy-binding $deployer --role=roles/iam.workloadIdentityUser --member="principal://iam.googleapis.com/projects/$number/locations/global/workloadIdentityPools/github/subject/repo:Serodio1/Rowen:environment:production"

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

(Get-Content deploy/cloud-run.yaml) -replace 'PROJECT_ID', $project -replace 'IMAGE_TAG', $tag |
    Set-Content "$env:TEMP\rowen-run.yaml"
gcloud run services replace "$env:TEMP\rowen-run.yaml" --region=europe-west1
```

Cloud Run runs only `linux/amd64` images, whatever the computer is.
`--provenance=false` leaves out the build's record that Docker Desktop
otherwise pushes beside each image, which Artifact Registry could count as
versions of its own.

`services replace` creates a new revision of the service, starts it, and
sends it all the requests once its containers' startup probes pass. Adding
`--dry-run` to it checks the file without deploying. Matches in memory are
lost with every deployment, until the database (#55). CI runs the same
commands.

## The first time only: open it to everyone

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

When the *Deploy* job fails, GitHub sends an email. If it failed in *Check
the game online*, the new revision already gets the requests: look at the
logs, and go back to the earlier revision (below) until a fix is merged.

What the containers printed (each request, and any error):

```powershell
gcloud run services logs read rowen --region=europe-west1 --limit=50
```

Go back to an earlier revision (its name comes from the list, such as
`rowen-00002-abc`); the next deployment sends the requests to its new revision
again:

```powershell
gcloud run revisions list --service=rowen --region=europe-west1
gcloud run services update-traffic rowen --region=europe-west1 --to-revisions=REVISION_NAME=100
```

Take the game offline (the images stay in the store):

```powershell
gcloud run services delete rowen --region=europe-west1
```

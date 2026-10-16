# Deploying to Google Cloud Run

The game runs on [Cloud Run](https://cloud.google.com/run) as one service,
`rowen`, in the `europe-west1` region: nginx with the page and the web API run
side by side in each instance ([ADR 0010](adr/0010-deploy-on-cloud-run.md),
[`deploy/cloud-run.yaml`](../deploy/cloud-run.yaml)). The images are built on
a computer with Docker and kept in Artifact Registry, Google's store for
images. Deploying from CI on every merge comes later (#56).

The commands below are for PowerShell on Windows, run from the repository's
folder, with the [gcloud CLI](https://cloud.google.com/sdk/docs/install)
signed in (`gcloud init`) as the project's owner, and the project chosen as its
default. Docker Desktop must be running.

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

## Every deployment

Deploy a commit of `main` with nothing changed on top, so the images match the
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
lost with every deployment, until the database (#55).

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

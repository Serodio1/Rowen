# Deploying to Google Cloud Run

The game runs on [Cloud Run](https://cloud.google.com/run) as one service,
`rowen`, in the `europe-west1` region: nginx with the page and the web API run
side by side in each instance ([ADR 0010](adr/0010-deploy-on-cloud-run.md),
[`deploy/cloud-run.yaml`](../deploy/cloud-run.yaml)). The images are built on
a computer with Docker and kept in Artifact Registry, Google's store for
images. Deploying from CI on every merge comes later (#56).

The commands below are for PowerShell on Windows, run from the repository's
folder, with the [gcloud CLI](https://cloud.google.com/sdk/docs/install)
signed in (`gcloud init`) and the project chosen as its default. Docker
Desktop must be running.

## Once per project

Turn on the three Google APIs the deployment uses, and nothing else:

```powershell
gcloud services enable run.googleapis.com artifactregistry.googleapis.com iam.googleapis.com
gcloud services list --enabled    # compute.googleapis.com must not be listed
```

Create the image store, and the policy that keeps only the last 3 versions of
each image (the store is free up to 0.5 GB). Artifact Registry applies the
policy about once a day:

```powershell
gcloud artifacts repositories create rowen --repository-format=docker --location=europe-west1
gcloud artifacts repositories set-cleanup-policies rowen --location=europe-west1 --policy=deploy/cleanup-policy.json
```

Create the service's own identity, with no roles: the game calls no other
Google service.

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
$tag = git rev-parse --short HEAD
$registry = "europe-west1-docker.pkg.dev/$project/rowen"

docker build --tag "$registry/api:$tag" backend
docker build --tag "$registry/web:$tag" frontend
docker push "$registry/api:$tag"
docker push "$registry/web:$tag"

(Get-Content deploy/cloud-run.yaml) -replace 'PROJECT_ID', $project -replace 'IMAGE_TAG', $tag |
    Set-Content "$env:TEMP\rowen-run.yaml"
gcloud run services replace "$env:TEMP\rowen-run.yaml" --region=europe-west1
```

`services replace` creates a new revision of the service, starts it, and
sends it the requests once its containers' startup probes pass. Adding
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

## When something goes wrong

What the containers printed (each request, and any error):

```powershell
gcloud run services logs read rowen --region=europe-west1 --limit=50
```

Go back to an earlier revision, then back to the newest once it is fixed:

```powershell
gcloud run revisions list --service=rowen --region=europe-west1
gcloud run services update-traffic rowen --region=europe-west1 --to-revisions=<revision>=100
gcloud run services update-traffic rowen --region=europe-west1 --to-latest
```

Take the game offline (the images stay in the store):

```powershell
gcloud run services delete rowen --region=europe-west1
```

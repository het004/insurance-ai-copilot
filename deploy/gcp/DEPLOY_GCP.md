# Deploying to Google Cloud (Cloud Run, me-central2 / Dammam)

## What gets created

```
Browser ──HTTPS──▶ copilot-web  (Cloud Run · Next.js)
                        │  /api/* proxied server-to-server
                        ▼
                   copilot-api  (Cloud Run · FastAPI · 1 instance)
                        ├── Gemini API key ◀── Secret Manager (gemini-api-key)
                        ├── neural voice   ──▶ Microsoft speech service (edge-tts)
                        └── demo data      ◀─▶ Cloud Storage  gs://<project>-copilot-state/copilot-state/
                                               (SQLite DB · Customer 360 .xlsx · uploaded documents)
```

| Resource | Name | Notes |
|---|---|---|
| Artifact Registry repo | `copilot` (me-central2) | container images |
| Cloud Run service | `copilot-api` | 1 vCPU / 2 GiB · **max 1 instance** · CPU always allocated while running · 15-min request timeout |
| Cloud Run service | `copilot-web` | 512 MiB · up to 3 instances |
| Cloud Storage bucket | `<project>-copilot-state` | private; holds the demo data between restarts |
| Secret | `gemini-api-key` | your Gemini key (optional — without it the offline demo agent runs) |
| Service account | `copilot-api-sa` | backend identity: bucket read/write + secret access only |

**Why the backend runs as a single instance:**
- **Chat sessions** live in memory.
- **The demo data** is one SQLite file, so there must be exactly one writer.

**How the demo data survives restarts:**
- Cloud Run's disk is temporary.
- At startup the backend restores its data from the bucket.
- It uploads changes every 20 seconds, and again on shutdown.

## Before you start (one-time, ~5 minutes)

You need a GCP project:
- with **billing enabled**
- where you are **Owner**, or have Editor plus Security Admin

The script enables the APIs it needs itself.

| Check | How |
|---|---|
| Billing is on | Console → Billing → *My projects* → your project shows a billing account |
| You can create resources in me-central2 | If the script later says the location isn't allowed, see *Troubleshooting* |
| Public URLs are allowed | Some company organisations block "allUsers" access; see *Troubleshooting* |

## Steps

1. **Open Cloud Shell.** Go to https://console.cloud.google.com, pick your project in the top bar, then click the **>_ Activate Cloud Shell** icon at the top right.
2. **Upload the code.** In the Cloud Shell window, open the **⋮** menu → **Upload** → choose `insurance-ai-copilot.zip`. The version that includes `backend/.env` lets the script pick up your Gemini key automatically.
3. **Unzip and enter the folder:**
   ```bash
   unzip -o insurance-ai-copilot.zip && cd insurance-ai-copilot
   ```
4. **Deploy:**
   ```bash
   bash deploy/gcp/deploy.sh
   ```
   - The script asks for the project ID only if Cloud Shell has no project selected.
   - It asks for the Gemini key if it doesn't find one in `backend/.env`. Press Enter to skip it.
   - The first run takes about 10–15 minutes, most of it building the two images.
5. **Open the URL it prints**: `https://copilot-web-<number>.me-central2.run.app`. The microphone works because Cloud Run serves HTTPS. The staff console is at `/console`.
6. **(Optional) Avoid cold starts during a live demo:**
   ```bash
   MIN_INSTANCES=1 bash deploy/gcp/deploy.sh
   ```
   This keeps one instance of each service warm. It costs money 24/7, so set it back afterwards with `MIN_INSTANCES=0 bash deploy/gcp/deploy.sh`.

## Updating after code changes

Upload the new zip, unzip it over the folder, and run `bash deploy/gcp/deploy.sh` again. It builds new images and deploys new revisions. The demo data in the bucket is kept.

## Useful commands

```bash
# Backend logs (Gemini errors, "Neural TTS unavailable", state sync)
gcloud run services logs read copilot-api --region me-central2 --limit 100

# Change the Gemini key, then restart the backend so it reads the new version
printf '%s' 'NEW_KEY' | gcloud secrets versions add gemini-api-key --data-file=-
gcloud run services update copilot-api --region me-central2 --update-env-vars RESTART=$(date +%s)

# Download the Customer 360 workbook
gcloud storage cp gs://$(gcloud config get-value project)-copilot-state/copilot-state/art_customer_360.xlsx .

# Reset the demo data to the seed: delete the snapshot, then restart the backend
gcloud storage rm -r gs://$(gcloud config get-value project)-copilot-state/copilot-state
gcloud run services update copilot-api --region me-central2 --update-env-vars RESTART=$(date +%s)

# Remove everything
bash deploy/gcp/teardown.sh
```

> **Editing the workbook in the cloud:** you can still download it from the staff console. Edits made to a downloaded copy are not uploaded back automatically.

## Troubleshooting

| Problem | Fix |
|---|---|
| `Location me-central2 is not available` / `constraints/gcp.resourceLocations` | Your organisation restricts regions. Run `REGION=me-central1 bash deploy/gcp/deploy.sh` (Doha) or ask your admin to allow me-central2 |
| `FAILED_PRECONDITION … allUsers` / org policy *Domain restricted sharing* blocks public access | Ask your GCP admin to exempt this project from `iam.allowedPolicyMemberDomains` (company projects often enforce it). The alternative is a login in front (IAP) plus identity tokens between the two services — a code change, not just a flag |
| Build fails with `PERMISSION_DENIED` pushing to Artifact Registry | Grant the Compute Engine default service account the *Cloud Build Service Account* role (the script tries this) |
| Replies tagged *offline agent* | The Gemini key is missing, invalid or out of credit — check the backend logs |
| Voice sounds robotic | The backend couldn't reach the neural voice service — check for `Neural TTS unavailable` in the logs; the browser voice is used instead |
| First message is slow | Cold start (the backend loads the knowledge base). Use `MIN_INSTANCES=1` for live demos |
| Signed-in customer becomes *Guest* | The backend restarted (scale-to-zero after ~15 idle minutes) — sessions are in memory; identify again |

## Cost

- **With the default `MIN_INSTANCES=0`:** you pay only while someone is using the app, plus about 15 idle minutes after that. Storage, the registry and the secret cost cents.
- **With `MIN_INSTANCES=1`:** both services run all day and are billed continuously.
- The Gemini API is billed separately, in AI Studio.

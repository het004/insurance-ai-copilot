#!/usr/bin/env bash
# Remove everything deploy.sh created (services, images, secret, bucket with the demo data, service account).
# Run from the repository root:  bash deploy/gcp/teardown.sh
set -uo pipefail
PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${REGION:-me-central2}"
REPO="${REPO:-copilot}"; API_SERVICE="${API_SERVICE:-copilot-api}"; WEB_SERVICE="${WEB_SERVICE:-copilot-web}"
SECRET_NAME="${SECRET_NAME:-gemini-api-key}"; SA_NAME="${SA_NAME:-copilot-api-sa}"
BUCKET="${BUCKET:-${PROJECT_ID}-copilot-state}"
echo "This deletes the Copilot services, images, Gemini key secret, service account and gs://$BUCKET in $PROJECT_ID."
read -rp "Type the project ID to confirm: " CONFIRM
[[ "$CONFIRM" == "$PROJECT_ID" ]] || { echo "Cancelled."; exit 1; }
gcloud run services delete "$WEB_SERVICE" --region "$REGION" --quiet
gcloud run services delete "$API_SERVICE" --region "$REGION" --quiet
gcloud artifacts repositories delete "$REPO" --location "$REGION" --quiet
gcloud secrets delete "$SECRET_NAME" --quiet
gcloud storage rm -r "gs://$BUCKET" --quiet
gcloud iam service-accounts delete "${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" --quiet
echo "Done."

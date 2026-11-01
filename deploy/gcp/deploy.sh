#!/usr/bin/env bash
# Deploy the Al Rajhi Takaful AI Voice Copilot to Google Cloud Run.
#
# Run from the repository root in Cloud Shell:
#     bash deploy/gcp/deploy.sh
#
# Safe to re-run: every step is idempotent, and a re-run deploys new revisions with your latest code.
# Override any setting with an environment variable, e.g.  REGION=me-central1 bash deploy/gcp/deploy.sh
set -euo pipefail

# ------------------------------------------------------------------ settings
PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${REGION:-me-central2}"                      # Dammam
REPO="${REPO:-copilot}"                              # Artifact Registry repository
API_SERVICE="${API_SERVICE:-copilot-api}"            # FastAPI backend
WEB_SERVICE="${WEB_SERVICE:-copilot-web}"            # Next.js frontend
SECRET_NAME="${SECRET_NAME:-gemini-api-key}"
SA_NAME="${SA_NAME:-copilot-api-sa}"
SPEECH_LANG="${SPEECH_LANG:-en-US}"
MIN_INSTANCES="${MIN_INSTANCES:-0}"                  # 1 = no cold start during a demo (always-on cost)
TAG="$(date +%Y%m%d-%H%M%S)"

say()  { printf '\n\033[1;34m▶ %s\033[0m\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }

[[ -d backend && -d frontend ]] || { echo "Run this from the repository root (the folder with backend/ and frontend/)."; exit 1; }
if [[ -z "$PROJECT_ID" || "$PROJECT_ID" == "(unset)" ]]; then
  read -rp "GCP project ID: " PROJECT_ID
fi
gcloud config set project "$PROJECT_ID" >/dev/null
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
BUCKET="${BUCKET:-${PROJECT_ID}-copilot-state}"
REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}"
API_IMAGE="${REGISTRY}/${API_SERVICE}:${TAG}"
WEB_IMAGE="${REGISTRY}/${WEB_SERVICE}:${TAG}"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "Project  : $PROJECT_ID ($PROJECT_NUMBER)"
echo "Region   : $REGION"
echo "Services : $API_SERVICE (backend), $WEB_SERVICE (frontend)"
echo "Data     : gs://$BUCKET"

# ------------------------------------------------------------------ 1. APIs
say "1/8 Enabling APIs (first time takes a minute)"
gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com \
  secretmanager.googleapis.com storage.googleapis.com iam.googleapis.com --quiet
ok "APIs enabled"

# ------------------------------------------------------------------ 2. Artifact Registry
say "2/8 Container registry"
if ! gcloud artifacts repositories describe "$REPO" --location "$REGION" >/dev/null 2>&1; then
  gcloud artifacts repositories create "$REPO" --repository-format=docker --location="$REGION" \
    --description="AI Voice Copilot images" --quiet
fi
ok "$REGISTRY"
# Newer projects build with the Compute Engine default service account — let it push images and write logs.
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/cloudbuild.builds.builder" --condition=None --quiet >/dev/null 2>&1 \
  && ok "Cloud Build can push images" || warn "Couldn't grant the build role (fine if builds already work)"

# ------------------------------------------------------------------ 3. Storage bucket for the demo data
say "3/8 Cloud Storage bucket for SQLite + Customer 360 workbook + uploads"
if ! gcloud storage buckets describe "gs://$BUCKET" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://$BUCKET" --location="$REGION" --uniform-bucket-level-access \
    --public-access-prevention --quiet
fi
ok "gs://$BUCKET"

# ------------------------------------------------------------------ 4. Service account for the backend
say "4/8 Backend service account"
if ! gcloud iam service-accounts describe "$SA_EMAIL" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$SA_NAME" --display-name="AI Voice Copilot backend" --quiet
  sleep 5
fi
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" --member="serviceAccount:$SA_EMAIL" \
  --role="roles/storage.objectAdmin" --quiet >/dev/null
ok "$SA_EMAIL can read/write gs://$BUCKET"

# ------------------------------------------------------------------ 5. Gemini key in Secret Manager
say "5/8 Gemini API key (Secret Manager)"
HAVE_SECRET=0
if gcloud secrets describe "$SECRET_NAME" >/dev/null 2>&1; then
  HAVE_SECRET=1; ok "Secret '$SECRET_NAME' exists (to change it: gcloud secrets versions add $SECRET_NAME --data-file=-)"
else
  KEY="${GEMINI_API_KEY:-}"
  if [[ -z "$KEY" && -f backend/.env ]]; then
    KEY="$(grep -E '^GEMINI_API_KEY=' backend/.env | head -1 | cut -d= -f2- | tr -d '"'"'"' \r')"
    [[ -n "$KEY" ]] && echo "  Found GEMINI_API_KEY in backend/.env"
  fi
  if [[ -z "$KEY" ]]; then
    read -rsp "  Paste your Gemini API key (or press Enter to run with the offline demo agent): " KEY; echo
  fi
  if [[ -n "$KEY" ]]; then
    printf '%s' "$KEY" | gcloud secrets create "$SECRET_NAME" --replication-policy=automatic --data-file=- --quiet >/dev/null
    HAVE_SECRET=1; ok "Stored as secret '$SECRET_NAME'"
  else
    warn "No key — the backend will use the offline demo agent"
  fi
fi
if [[ $HAVE_SECRET == 1 ]]; then
  gcloud secrets add-iam-policy-binding "$SECRET_NAME" --member="serviceAccount:$SA_EMAIL" \
    --role="roles/secretmanager.secretAccessor" --quiet >/dev/null
fi

# ------------------------------------------------------------------ 6. Backend
say "6/8 Building and deploying the backend ($API_SERVICE)"
gcloud builds submit backend --tag "$API_IMAGE" --quiet
WEB_URL_GUESS="https://${WEB_SERVICE}-${PROJECT_NUMBER}.${REGION}.run.app"
API_ENV="STATE_BUCKET=${BUCKET},DATA_DIR=/data,INSURER_NAME=Al Rajhi Takaful,INSURER_SHORT=Al Rajhi Takaful,GEMINI_MODEL=gemini-2.5-flash,LOG_LEVEL=INFO"
API_ARGS=(
  --image "$API_IMAGE" --region "$REGION" --service-account "$SA_EMAIL"
  --allow-unauthenticated
  --cpu 1 --memory 2Gi --no-cpu-throttling        # CPU stays on between requests so data syncs to the bucket
  --min-instances "$MIN_INSTANCES" --max-instances 1   # ONE instance: one SQLite writer, one chat-session store
  --concurrency 40 --timeout 900                  # long-lived streaming responses for the live progress panel
  --set-env-vars "^@^${API_ENV//,/@}@CORS_ORIGINS=${WEB_URL_GUESS}"
)
[[ $HAVE_SECRET == 1 ]] && API_ARGS+=(--set-secrets "GEMINI_API_KEY=${SECRET_NAME}:latest")
gcloud run deploy "$API_SERVICE" "${API_ARGS[@]}" --quiet
API_URL="$(gcloud run services describe "$API_SERVICE" --region "$REGION" --format='value(status.url)')"
ok "Backend: $API_URL"

# ------------------------------------------------------------------ 7. Frontend
say "7/8 Building and deploying the frontend ($WEB_SERVICE)"
gcloud builds submit frontend --config deploy/gcp/cloudbuild-frontend.yaml --quiet \
  --substitutions "_IMAGE=${WEB_IMAGE},_BACKEND_URL=${API_URL},_SPEECH_LANG=${SPEECH_LANG}"
gcloud run deploy "$WEB_SERVICE" --image "$WEB_IMAGE" --region "$REGION" \
  --allow-unauthenticated --cpu 1 --memory 512Mi --min-instances "$MIN_INSTANCES" --max-instances 3 \
  --concurrency 80 --timeout 900 --quiet
WEB_URL="$(gcloud run services describe "$WEB_SERVICE" --region "$REGION" --format='value(status.url)')"
ok "Frontend: $WEB_URL"

# ------------------------------------------------------------------ 8. Allow the frontend's real URL(s) on the backend
say "8/8 Final wiring"
gcloud run services update "$API_SERVICE" --region "$REGION" --quiet \
  --update-env-vars "^@^CORS_ORIGINS=${WEB_URL},${WEB_URL_GUESS}" >/dev/null
ok "CORS allows $WEB_URL"
if ! curl -fsS "$API_URL/api/health" >/dev/null; then
  warn "The backend URL isn't publicly reachable. If your organisation blocks public (allUsers) access,"
  warn "see 'Organisation policy blocks public access' in deploy/gcp/DEPLOY_GCP.md."
fi

cat <<EOF

────────────────────────────────────────────────────────────────────────
  ✅ Deployed

  Open the app:      $WEB_URL
  Staff console:     $WEB_URL/console
  Backend API docs:  $API_URL/docs
  Demo data bucket:  gs://$BUCKET/copilot-state/

  Logs:   gcloud run services logs read $API_SERVICE --region $REGION --limit 50
  Update: re-run  bash deploy/gcp/deploy.sh   after changing the code
────────────────────────────────────────────────────────────────────────
EOF

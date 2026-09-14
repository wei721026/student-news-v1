# Publication Webhook｜Cloud Run + Cloud Storage Deployment

V1 publisher 的工作很單純：接收已通過 Publication Gate 的 **現成** HTML / PDF / email payload，保存 immutable version，同時更新 latest pointer。它不生成教材內容。

## 需要準備

- Google Cloud project
- Artifact Registry Docker repository
- Cloud Storage bucket
- Cloud Run runtime service account
- Secret Manager secret（建議名稱 `student-news-webhook-secret`）
- 對外靜態 URL base（例如 `https://storage.googleapis.com/<bucket>` 或既有 CDN/domain）

Runtime service account 對 bucket 只需能讀寫物件；建議最小化授權。

## Build image

從 repo root：

```bash
export PROJECT_ID="..."
export REGION="asia-east1"
export REPOSITORY="student-news"
export TAG="v1-0"

gcloud builds submit \
  --config publisher/cloudbuild.yaml \
  --substitutions=_REGION="$REGION",_REPOSITORY="$REPOSITORY",_TAG="$TAG" \
  .
```

## Deploy Cloud Run

```bash
export IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/student-news-publisher:${TAG}"
export BUCKET="..."
export PUBLIC_BASE_URL="https://storage.googleapis.com/${BUCKET}"
export RUNTIME_SA="student-news-publisher@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud run deploy student-news-publisher \
  --image "$IMAGE" \
  --region "$REGION" \
  --service-account "$RUNTIME_SA" \
  --set-env-vars "PUBLICATION_STORAGE=GCS,PUBLISHER_BUCKET=${BUCKET},PUBLIC_BASE_URL=${PUBLIC_BASE_URL}" \
  --set-secrets "WEBHOOK_SECRET=student-news-webhook-secret:latest" \
  --no-invoker-iam-check
```

Cloud Run endpoint 雖可被連線，但 `/publish` 仍要求 `X-Webhook-Secret`。若組織要求 private Cloud Run，需另做 GitHub OIDC / IAM invocation；不要把 shared-secret endpoint 硬改成假 private。

## Cloud Storage public read

學生 HTML/PDF 若要直接公開，bucket objects 必須可公開讀取。若組織啟用了 Public Access Prevention，不能直接用 public GCS URL；此時**停止公開部署**，改接既有可公開 hosting / CDN，再回填 `PUBLIC_BASE_URL`。

不要為了繞過組織政策而降低權限治理。

## Health check

```bash
curl -fsS "https://<cloud-run-url>/healthz"
```

應得到：

```json
{"ok": true}
```

## Worker secrets

把 Cloud Run publish endpoint（含 `/publish`）與同一 secret 加到 GitHub repository secrets：

- `PUBLICATION_WEBHOOK_URL`
- `PUBLICATION_WEBHOOK_SECRET`

在 webhook 尚未可用前，worker 會停在 `READY`，不會偽裝成 `PUBLISHED`。

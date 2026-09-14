# Publication Webhook V1

This service receives already-rendered HTML/PDF/email JSON from the Python worker.
It does **not** generate or rewrite lesson content.

## Required environment

- `WEBHOOK_SECRET`
- `PUBLISHER_BUCKET`
- `PUBLIC_BASE_URL` (for a public GCS bucket, e.g. `https://storage.googleapis.com/BUCKET_NAME`)
- `PUBLICATION_STORAGE=GCS`

The worker sends multipart form-data to `POST /publish`.

Each release is retained at:

- `issues/{Issue_ID}/versions/{Version}/index.html`
- `issues/{Issue_ID}/versions/{Version}/lesson.pdf`
- `issues/{Issue_ID}/versions/{Version}/email.json`
- `issues/{Issue_ID}/versions/{Version}/version.json`

Latest pointers are copied to `issues/{Issue_ID}/...`.

For local smoke tests only, set `PUBLICATION_STORAGE=LOCAL` and `LOCAL_PUBLIC_ROOT=./public`.

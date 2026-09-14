# GitHub Actions → Google Cloud Workload Identity Federation 設定

## 為什麼改
組織政策 `iam.disableServiceAccountKeyCreation` 阻擋 service account JSON key 建立。
V1.0.1 工程 patch 不修改教材 Data Contract；只把 GitHub Actions 的 Google 驗證改為短效 OIDC / Workload Identity Federation。

## GitHub Secrets
- `OPENAI_API_KEY`
- `GOOGLE_SHEET_ID`
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_SERVICE_ACCOUNT`
- `PUBLICATION_WEBHOOK_URL`（可先不設）
- `PUBLICATION_WEBHOOK_SECRET`（可先不設）

不再需要：
- `GOOGLE_SERVICE_ACCOUNT_JSON`

## Google Cloud 最小設定
1. 保留既有 service account，不建立 key。
2. 建立 Workload Identity Pool。
3. 建立 GitHub OIDC Provider，issuer：
   `https://token.actions.githubusercontent.com/`
4. Attribute mapping 至少包含：
   - `google.subject=assertion.sub`
   - `attribute.repository=assertion.repository`
   - `attribute.repository_owner=assertion.repository_owner`
5. Attribute condition 限制到你的 GitHub owner/repository；不要允許任意 GitHub repository。
6. 讓該 GitHub repository identity 對 service account 具有 `roles/iam.workloadIdentityUser`。
7. Google Sheet 仍分享給該 service account email（Editor）。

## Workflow
`.github/workflows/daily.yml` 已加入：
- `permissions: id-token: write`
- `google-github-actions/auth@v3`
- ADC credential file

`src/sheets_gateway.py` 已改為：
- GitHub/WIF：使用 `google.auth.default(scopes=...)`
- 舊 JSON key：仍相容，但不是正式建議路徑

## First live smoke
Publication webhook 先不設，先驗證：
GitHub workflow → WIF auth → Google Sheet → Issue / RUN_LOG → QA → READY

只有上述成功後才接 Publication webhook。

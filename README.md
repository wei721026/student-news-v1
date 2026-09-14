# Student News V1.0｜Engineering Deployment Package

本 repo 接手既有「自學型時事素養教材系統」V1.0 規格，只做工程部署，不重新設計教材、不重決 Data Contract、教學流程、QA 規則或 Core / Extension 邏輯。

## 1. V1 架構

```text
Google Sheet (control plane)
        │
        ▼
Python Automation Worker
Discovery → Verification → Fact QA → Structured Content → Teaching QA
        │
        ├── PDF Renderer
        └── Public HTML Renderer
                    │
                    ▼
              Layout QA → READY
                    │
              Approval = YES
                    │
                    ▼
         Publication Webhook / GCS
                    │
         HTML_URL / PDF_URL 回寫
                    │
                    ▼
             GAS Email Delivery
```

**沒有 PDF → HTML。** PDF 與 HTML 都由同一份 Structured Content 母資料產生。

## 2. V1 邊界

本版不加入 Audio、帳號、成績、LMS、學生追蹤、個人化推薦或聊天機器人。

正式預設：
- `TIMEZONE = Asia/Taipei`
- `PUBLISH_MODE = APPROVAL`
- `AUTO_PUBLISH_ALLOWED = NO`
- Mon / Wed / Fri = ZH
- Tue / Thu / Sat = EN
- Sun = REVIEW，**禁止新新聞搜尋，只讀前六篇已通過 QA 的 mother data**
- Discovery 最多 3 候選
- Teaching revision 最多 2 次
- Layout revision 最多 2 次

## 3. Publication Gate

公開發布必須同時符合：

```text
Status = READY
Fact_QA = PASS
Teaching_QA = PASS
Layout_QA = PASS
Approval = YES
PUBLICATION_WEBHOOK_URL exists
PUBLICATION_WEBHOOK_SECRET exists
```

任何 `BLOCKED_*` 不可公開。Webhook 尚未完成時保持 `READY`，不寫入假的公開 URL。

## 4. Repo 結構

- `src/`：Python worker、QA gates、Sheet gateway、HTML/PDF renderer、Email payload、publication client
- `publisher/`：Publication Webhook；將 HTML/PDF/email payload 發布到 versioned + latest 路徑
- `gas/`：Sheet menu、Approval、Retry、Publish trigger、Email Delivery、Email retry
- `tests/`：Python acceptance + GAS core tests
- `demo/`：以既有 One-Week Trial mother data 產生的本機輸出
- `handoff/`：既有交接文件、凍結 Data Contract、更新後 control workbook、部署與驗收報告
- `.github/workflows/daily.yml`：每日 worker
- `.github/workflows/ci.yml`：回歸測試

## 5. Google Sheet

沿用既有 control workbook；僅新增 V1 部署需要的欄位 / tabs：

ISSUES 新增：
- `Email_Status`
- `Email_Sent_At`
- `Email_Attachment`
- `Email_Error`

新增：
- `SUBSCRIBERS`
- `EMAIL_LOG`

`EMAIL_LOG` 以 `Issue_ID + Recipient` 建立 delivery key，已 `SENT` 的 key 不重複寄送。

更新版 workbook：
`handoff/Student_News_Control_V1.0_Deployment.xlsx`

## 6. Public HTML V1

已實作：
- Responsive 大字閱讀；手機 360 CSS px 無 document overflow
- headline / date / category / version / last checked
- Quick Start / 30 秒先懂
- Core 預設展開
- Extension 收合
- Checkpoint
- 答案預設隱藏，按鈕後顯示
- 我卡住了 / I'M STUCK 收合
- 英文日中文救援預設收合
- compact sources + 可點來源
- PDF download
- correction notice / version
- BLOCKED gate

HTML renderer 不生成或改寫教材內容。

## 7. PDF V1

日常 ZH / EN 與 Sunday Review 都從同一份 Structured Content 產生。Sunday 使用 renderer adapter 讀既有 `week_cards / recall / connections / evidence_check`，不是 Data Contract V1.1。

## 8. Email Delivery GAS V1

GAS 只做控制與寄送，不接管 Discovery / Verification / Fact QA / Structured Content / Teaching QA / PDF Render。

Menu：
- Approve Today
- Retry Blocked
- Publish Ready
- View Run Log
- Email Delivery
- Retry Failed Email

Email 只對 `PUBLISHED` 且具有實際 `HTML_URL / PDF_URL` 的 Issue 寄送。寄送失敗只更新 Email 狀態，不把文章狀態改回失敗。

## 9. Local Regression

```bash
python -m unittest -v tests.test_acceptance
node tests/gas_core_test.js
```

目前封版結果：
- Python acceptance：21 / 21 PASS
- GAS core tests：PASS
- ZH / EN / REVIEW 產生 PDF：各 2 頁
- Sunday PDF 另驗證 page 1 有完整週卡 / 連結內容，page 2 有「做完再看」與週追蹤 prompt

詳見：`handoff/ACCEPTANCE_REPORT_V1.0.md`

## 10. Worker Secrets

GitHub Actions 需要：
- `OPENAI_API_KEY`
- `GOOGLE_SHEET_ID`
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_SERVICE_ACCOUNT`
- `PUBLICATION_WEBHOOK_URL`
- `PUBLICATION_WEBHOOK_SECRET`

Google Sheet 必須分享給 `GCP_SERVICE_ACCOUNT` 對應的 service account email，至少可編輯既有 control plane。

> 2026-09 Auth Patch：正式 GitHub Actions 路徑改採 Workload Identity Federation (OIDC)，不再要求下載長效 `GOOGLE_SERVICE_ACCOUNT_JSON` 金鑰。`src/sheets_gateway.py` 會優先使用 Application Default Credentials；若舊環境已有 JSON key，仍保留相容性。

## 11. Publisher Environment

Publication webhook 預設使用 Cloud Run + Cloud Storage：

- `WEBHOOK_SECRET`：與 `PUBLICATION_WEBHOOK_SECRET` 相同
- `PUBLISHER_BUCKET`
- `PUBLIC_BASE_URL`
- `PUBLICATION_STORAGE=GCS`

詳見 `publisher/DEPLOYMENT.md`。

## 12. GAS 權限 / Script Properties

需要：
- 綁定更新後的 Google Sheet
- Spreadsheet 權限
- UrlFetch 權限
- MailApp 寄信權限

若要讓 GAS 的「Publish Ready / Retry Blocked」立即觸發 GitHub Action，再設定：
- `GITHUB_OWNER`
- `GITHUB_REPO`
- `GITHUB_TOKEN`
- `GITHUB_WORKFLOW`（預設 `daily.yml`）
- `GITHUB_REF`（預設 `main`）

沒有 GitHub dispatch properties 時，Approval 仍可完成；worker 會由下一次 scheduler 接手。

## 13. 現行部署狀態

此交付包已完成本機工程施工與 package-level regression，但**尚未使用真實 Google / GitHub / Cloud / Email 帳號執行外部發布**，因本工作階段未取得那些帳號權限與 Secrets。

因此目前正式狀態是：

- Release State：`Candidate`
- Handoff：`Prepared`
- External publication：`NOT EXECUTED`
- 不宣稱任何 Issue 已因本次工程施工而正式 `PUBLISHED`

取得 Secrets / 權限後，依 `handoff/DEPLOYMENT_RESULT_V1.0.md` 的 live smoke test 順序即可完成最後部署驗收。

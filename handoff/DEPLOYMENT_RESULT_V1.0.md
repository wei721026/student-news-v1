# Student News V1.0｜Deployment Result & Live Handoff
日期：2026-09-14

## 目前做到哪裡

已完成 V1 工程部署包、Public HTML renderer、PDF renderer orchestration、Publication webhook、Google Sheet 擴充、GAS 控制與 Email Delivery、GitHub Actions 與回歸測試。

本次沒有修改 Data Contract，也沒有重新設計教材、教學流程、QA 規則或 Core / Extension 邏輯。

目前 Release State 為 **Candidate**；Handoff 為 **Prepared**。由於尚未取得真實 Google / GitHub / Cloud / Email 權限，本次沒有把任何 Issue 宣稱為正式 PUBLISHED。

## 本次工程修正

原 automation 骨架中幾個會阻止 V1 驗收的問題已在工程層處理：
- HTML 答案改為預設隱藏、按鈕後顯示。
- Sources 改用 Sheet source records 解析為可點公開連結。
- READY 不再把 local file path 寫入 `HTML_URL / PDF_URL`。
- Publication webhook 改為上傳實際 HTML / PDF / email payload bytes，而非傳遠端無法讀取的本機路徑。
- Sunday 以 Sheet 前六篇 QA PASS mother data 為唯一輸入，不使用 web search。
- Sunday Review 補上 HTML / PDF adapter；未修改 frozen contract。
- Publisher 保存 versioned artifacts + latest pointer，支援 correction history。
- Email Delivery 使用 `Issue_ID + Recipient` 防重寄；寄信失敗不回滾文章狀態。

## Live deployment 還需要的 3 組權限

### A. GitHub / Worker
- GitHub repository
- `OPENAI_API_KEY`
- `GOOGLE_SHEET_ID`
- `GCP_WORKLOAD_IDENTITY_PROVIDER`\n- `GCP_SERVICE_ACCOUNT`
- `PUBLICATION_WEBHOOK_URL`
- `PUBLICATION_WEBHOOK_SECRET`
- 將 Sheet 分享給 service account（Editor）

### B. Google Cloud Publisher
- Cloud project / Artifact Registry / Cloud Run deploy 權限
- Cloud Storage bucket
- Cloud Run runtime service account 對 bucket 的 object write 權限
- Secret Manager 中的 webhook secret
- 可公開讀取 HTML/PDF 的 hosting URL；若組織 Public Access Prevention 阻擋 public bucket，需改接既有 public hosting，不能假裝已發布

### C. Apps Script / Email
- 將 `gas/Code.gs` / `appsscript.json` 綁定更新後 Sheet
- Spreadsheet / UrlFetch / MailApp 授權
- 若要從 GAS 即時觸發 GitHub workflow，再提供 GitHub dispatch token；若不提供，scheduler 仍可接手

## Live smoke test 順序

1. 上傳 repo，設定 GitHub secrets。
2. 將 `handoff/Student_News_Control_V1.0_Deployment.xlsx` 匯入 / 更新既有 Google Sheet；確認原 tabs 保留，且有 SUBSCRIBERS / EMAIL_LOG。
3. 部署 publisher；`/healthz` 回傳成功。
4. 將 publisher `/publish` URL 與 secret 放入 GitHub secrets。
5. 手動 `workflow_dispatch` 跑一篇 READY 測試；未 Approval 時必須停 READY。
6. Sheet 設 `Approval=YES`，再次跑 worker；確認回寫真實 `HTML_URL / PDF_URL` 且 Status=PUBLISHED。
7. 由 GAS 執行 Email Delivery；確認訂閱條件、附件、EMAIL_LOG、RUN_LOG。
8. 對同一期再執行一次 Email Delivery；確認已 SENT recipient 不重寄。
9. 模擬一筆 Email failure，再執行 Retry Failed Email；確認文章仍維持 PUBLISHED。
10. 跑 correction sample；確認 latest 指向新版、舊版 versioned artifact 仍存在。

## 完成條件

以上 live smoke test 通過後，才可把 external deployment 從 Candidate 更新為 Last Known Good。若沒有 live 權限，本交付只能標示為「部署包已完成、外部部署待授權」，不能寫成正式上線。


## Auth Patch 2026-09-14
GitHub → Google Cloud 驗證改採 Workload Identity Federation，不需 service account JSON key；Data Contract V1.0 未變更。詳見 `WIF_GITHUB_SETUP_V1.0.1.md`。

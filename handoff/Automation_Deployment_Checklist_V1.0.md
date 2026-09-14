# Automation Deployment Checklist V1.0

## 一次性設定

- [ ] 建立 GitHub repository
- [ ] 上傳 `Student_News_Automation_V1.0/` 內容到 repo root
- [ ] 建立 Google Cloud service account
- [ ] 啟用 Google Sheets API / Drive API
- [ ] 把 Google Sheet 分享給 service account email（Editor）
- [ ] GitHub Secret：`OPENAI_API_KEY`
- [ ] GitHub Secret：`GOOGLE_SHEET_ID`
- [ ] GitHub Secret：`GOOGLE_SERVICE_ACCOUNT_JSON`
- [ ] `PUBLICATION_WEBHOOK_URL` 先可留空

## 首次測試

- [ ] `AUTOMATION!PUBLISH_MODE = APPROVAL`
- [ ] `AUTO_PUBLISH_ALLOWED = NO`
- [ ] GitHub Actions → Run workflow
- [ ] ISSUES 出現今天 issue
- [ ] RUN_LOG 有 DISCOVERY
- [ ] Fact QA 能 PASS 或 BLOCK
- [ ] READY issue 產生 Data_Path / PDF / HTML
- [ ] Approval 未 YES 時不 Publish
- [ ] BLOCKED 不產公開頁

## 星期日

- [ ] 不做 web search
- [ ] 前六篇 mother data 可讀
- [ ] 產生 review
- [ ] 仍走 Layout QA

## HTML 上線後

- [ ] 設 `PUBLICATION_WEBHOOK_URL`
- [ ] Approval YES 能發布
- [ ] 回寫 HTML_URL / PDF_URL / Published_At
- [ ] Correction version 指向最新版

## 最後才考慮

- [ ] `PUBLISH_MODE=AUTO`
- [ ] `AUTO_PUBLISH_ALLOWED=YES`

建議至少累積 2–4 週穩定資料後再開。

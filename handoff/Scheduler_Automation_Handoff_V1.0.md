# Scheduler / Automation Handoff V1.0

## 決策

Automation V1.0 採：

**Google Sheet control plane + Python worker + OpenAI Responses API + GitHub Actions scheduler**

預設為：

**APPROVAL Mode**

也就是研究、查核、Structured Content、Teaching QA、PDF Render、Layout QA 全自動，
但公開發布仍需 `Approval=YES`。

---

## 每日時間

時區：`Asia/Taipei`

GitHub Actions：
`21:00–23:30 UTC` 每 30 分鐘喚醒一次，
對應臺北時間約 `05:00–07:30`。

Controller 是 idempotent：
- PUBLISHED 不重跑
- BLOCKED 不重跑
- READY + Approval pending 不重跑研究
- 當日不存在 issue 時，自動 seed

---

## 星期規則

- Mon / Wed / Fri → ZH
- Tue / Thu / Sat → EN
- Sun → REVIEW

星期日：
**不使用 web search**
只讀前六篇 mother data。

---

## Research Pipeline

1. Discovery：`gpt-5.6-luna` + web search
2. Verification：`gpt-5.6-terra` + web search
3. Critical Claim gate
4. Structured Content：`gpt-5.6-terra`
5. Teaching QA：`gpt-5.6-terra`
6. Renderer
7. Layout QA
8. READY
9. Approval / Publish

OpenAI Responses API 支援 built-in web search 與 structured JSON output。

---

## Retry

- 最多 3 個候選新聞
- Teaching revision 最多 2 次
- Layout content revision 最多 2 次
- 超過限制 → BLOCKED

品質閘門優先於每日必發。

---

## Publishing

`PUBLISH_MODE=APPROVAL`

只有：
- Fact PASS
- Teaching PASS
- Layout PASS
- Status READY
- Approval YES
- PUBLICATION_WEBHOOK 已設定

才可以 Publish。

若 webhook 尚未完成：
停在 READY。

---

## BLOCK

- `BLOCKED_SOURCE`
- `BLOCKED_PEDAGOGY`
- `BLOCKED_LAYOUT`

BLOCKED：
- 不 publish
- 不自動弱化 QA
- 進 RUN_LOG
- 等人處理

---

## Secrets

GitHub Repository Secrets：

- `OPENAI_API_KEY`
- `GOOGLE_SHEET_ID`
- `GOOGLE_SERVICE_ACCOUNT_JSON`
- `PUBLICATION_WEBHOOK_URL`（HTML 工程完成後才需要）

---

## 上線順序

1. 建 GitHub repo
2. 放入 Automation V1.0 package
3. Google Sheet 分享給 service account email
4. 建 3 個必要 secrets
5. 手動 `workflow_dispatch` 跑一次
6. 確認 Sheet `RUN_LOG`
7. 維持 APPROVAL Mode 2–4 週
8. HTML publication webhook 穩定後再考慮 AUTO

# Student News V1.0｜Acceptance Report
日期：2026-09-14

## 結論

本機 / package-level regression 已完成。Python acceptance 21/21 PASS；GAS core tests PASS。Data Contract 未修改；Sunday 採既有 trial review shape 的 renderer adapter。

下表「PASS_LOCAL」表示程式與代表性資料已在本環境執行驗證；「PASS_CODE / LIVE_PENDING」表示邏輯與靜態 / 單元測試已通過，但仍需真實 Google / Email 帳號完成最後 live smoke test。

| # | 驗收項目 | 結果 | 證據 |
|---|---|---|---|
| 1 | 中文 READY article | PASS_LOCAL | `test_01_zh_ready_article` |
| 2 | 英文 READY article | PASS_LOCAL | `test_02_en_ready_article` |
| 3 | Sunday Review | PASS_LOCAL | `test_03_sunday_review` + Sunday PDF adapter test |
| 4 | BLOCKED sample 不可 public | PASS_LOCAL | `test_04_blocked_not_public` |
| 5 | Correction sample 顯示新版 / 保留舊版 | PASS_LOCAL | `test_05_correction_notice`, `test_18_publication_keeps_previous_versions` |
| 6 | 手機 360px 無水平 overflow | PASS_LOCAL | `test_19_mobile_360_no_document_overflow` |
| 7 | Answers 預設隱藏 | PASS_LOCAL | `test_06_answers_hidden_by_default` |
| 8 | Rescue 預設收合 | PASS_LOCAL | `test_07_rescue_collapsed_by_default` |
| 9 | 英文中文救援預設收合 | PASS_LOCAL | `test_07_rescue_collapsed_by_default` |
| 10 | Source links 可點 | PASS_LOCAL | `test_08_source_links_clickable` |
| 11 | PDF link 正確 | PASS_LOCAL | `test_09_pdf_link_matches`；ZH/EN/REVIEW 皆產 2 頁 PDF |
| 12 | Sheet Status 阻止錯誤發布 | PASS_LOCAL | `test_10_fact_gate_blocks_publish`, `test_11_teaching_and_layout_gate_blocks_publish` |
| 13 | Approval YES 才 publish | PASS_LOCAL | `test_12_approval_yes_required`, `test_14_publish_gate_passes_only_complete_ready` |
| 14 | SUBSCRIBERS 篩選正確 | PASS_CODE / LIVE_PENDING | `tests/gas_core_test.js` |
| 15 | 中文訂閱只收中文 | PASS_CODE / LIVE_PENDING | GAS `shouldReceive_` test |
| 16 | 英文訂閱只收英文 | PASS_CODE / LIVE_PENDING | GAS `shouldReceive_` test |
| 17 | Sunday preference 正確 | PASS_CODE / LIVE_PENDING | GAS `shouldReceive_` test |
| 18 | PDF 能作 Email attachment | PASS_CODE / LIVE_PENDING | GAS attachment path / fetch test；真實 MailApp 尚待授權 |
| 19 | 同一期不重複寄送 | PASS_CODE / LIVE_PENDING | `Issue_ID|recipient` idempotency test + EMAIL_LOG |
| 20 | Email failure 可 retry | PASS_CODE / LIVE_PENDING | `retryFailedEmails()` 僅處理 FAILED/PARTIAL；article Status 不回滾 |
| 21 | RUN_LOG 有完整紀錄 | PASS_CODE / LIVE_PENDING | Worker / GAS 均具 append log；真實 Sheet 寫入待 service account 權限 |

## 額外 regression

- Structured Content → PDF Renderer + HTML Renderer，共用母資料。
- READY 階段不把本機路徑假寫為公開 URL。
- Publication webhook 成功回傳真實 URL 後才改為 PUBLISHED。
- Webhook URL / shared secret 任一缺少，停在 READY。
- Source direct URL 缺失時不公開。
- Sunday 只選前六篇 ZH/EN、QA 全 PASS 的 mother data；Sunday LLM 路徑不啟用 web search。
- Sunday PDF 不只檢查「2 頁」，亦驗證週卡內容與第二頁回顧 prompt 實際存在。
- Email retry 不改文章 PUBLISHED 狀態。
- Correction publisher 保留 `versions/<version>/`，並更新 latest `version.json` pointer。

## 尚未執行的 live 驗證

因本工作階段未取得外部帳號與 Secrets，尚未真實執行：
1. GitHub Actions 對真實 Sheet 的 scheduler run。
2. Cloud Run / Cloud Storage publication webhook。
3. Apps Script bound Sheet menu / MailApp 真實寄信。

因此本報告不宣稱已正式上線或已有真實訂閱者收到 Email。


## Publisher HTTP route 測試狀態

`publisher/core.py` 的 versioned/latest 寫入已由 acceptance test 實際執行通過；`publisher/app.py` 亦已通過 Python compile。  
本沙箱未預裝 Flask，且無法連網安裝 publisher dependency，因此 multipart HTTP route 沒有在本沙箱 runtime 啟動。Repo 已加入 `tests/test_publisher_http.py`，CI 會在安裝 `publisher/requirements.txt` 後執行；Cloud Run live smoke 仍列為正式部署必要驗收，不把它誤寫成已完成。

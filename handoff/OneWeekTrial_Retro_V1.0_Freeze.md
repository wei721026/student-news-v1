# One-Week Trial Retro｜V0.2 → V1.0 Freeze Review

## 結論

**PASS：可以進入 HTML Engineering Handoff。**

本週完成：
- D1 中文｜生活經濟／能源｜DATA_STORY
- D2 英文｜太空／AI｜LANGUAGE_SCAFFOLD
- D3 中文｜健康／生物／公共衛生｜GUIDED_READING
- D4 英文｜地理／地圖｜LANGUAGE_SCAFFOLD
- D5 中文｜運動／數學資料判讀｜DATA_STORY
- D6 英文｜氣候／資料判讀｜LANGUAGE_SCAFFOLD
- D7 週日回顧｜只讀 D1–D6 母資料，不搜尋新新聞

另外完成：
- 1 個 `BLOCKED_SOURCE` sample
- 1 個 `Correction / Version` workflow sample

---

## 1. Schema Stability

D1–D7 全部沿用 V0.2 Contract。

一週期間：
- **0 次結構性 Schema 修改**
- 有調整的是內容長度、print renderer spacing、學生版呈現密度
- `background / sections / language_support / provenance / presentation / qa` 足以支援所有案例

因此：

**V0.2 Contract 可以凍結為 V1.0。**

---

## 2. QA Gate 實測

### Fact QA
成功處理：
- 官方＋新聞交叉確認
- 醫療政策的個人建議邊界
- 月球 AI 的 `estimate ≠ proof`
- UN 決議的 `encourages ≠ bans`
- U18 報導的來源細節衝突
- 氣候的 month vs long-term

### BLOCKED
日月潭候選稿因「全台首次／全台首創」無足夠證據：

`Fact QA = BLOCK`

Teaching / Layout 不啟動，沒有 PDF。

**Gate 有效。**

### Correction
模擬輸出層數字錯植：

`v1.0-test → Claim mismatch → CORRECTION_REQUIRED → v1.1-test`

**Version workflow 有效。**

---

## 3. Print Pipeline 實測

共同硬規格：
- A4 2頁上限
- Core 第1頁完成
- 主要正文 ≥ 15.4pt
- 來源 ≥ 11.5pt
- Overflow 不靠縮小主要正文處理

實測：
- D1：2頁
- D2：初次3頁 → content/framing revision → 2頁
- D3：2頁
- D4：初次3頁 → framing revision → 2頁
- D5：2頁
- D6：初次3頁 → framing/content de-duplication → 2頁
- D7：2頁

結論：
**Print renderer 可行；母資料完整與學生 Print 呈現必須分離。**

---

## 4. Content Mix

本週涵蓋：
- 國內生活經濟
- 國際太空／AI
- 國內健康／公共政策
- 國際地理／地圖
- 國內運動／數學資料
- 國際氣候／資料
- 週回顧

沒有同一類題材連續壟斷。

中英交替：
`ZH → EN → ZH → EN → ZH → EN → REVIEW`

成立。

---

## 5. 自學設計實測

穩定保留：
- 30 秒先懂 / Quick Start
- 最小必要背景
- Core / Extension 分流
- 至少一次 immediate self-check
- Rescue
- One Thing
- Compact Sources
- 英文中文救援只在第2頁

不同 Interaction Style 確實需要存在：
- DATA_STORY
- LANGUAGE_SCAFFOLD
- GUIDED_READING

未來可再加入，但不需要為 HTML V1 先擴充。

---

## 6. 現在可以交工程，但不是把產品重新設計一次

HTML 工程任務應是：

> **依 V1.0 Contract 渲染同一份母資料，加入紙本做不到但已明確定義的互動。**

工程端不得重新決定：
- 教材區塊
- QA Gate
- 字級最低要求
- Core Complete
- 新聞內容
- Fact Claim

---

## 7. V1.0 Freeze

正式凍結：
- Data Contract V1.0
- State machine
- QA Gate
- PDF print contract
- Sheet control model
- Core / Extension logic
- ZH / EN learning differences

下一階段：
**Public HTML V1 Engineering**

暫不加入：
- Audio
- Login
- Scores
- LMS
- Personalized recommendations
- Student tracking

# HTML Engineering Handoff Pack｜V1.0

## 任務一句話

把已經驗證過的 `Structured Content V1.0` 渲染成學生可用的 responsive HTML。

**不要重新設計教材，也不要重新生成新聞。**

---

# 1. Inputs

工程端應讀：

- `issue_contract_v1_0.json`
- 每一期 `*_structured_content_*_READY.json`
- Google Sheet 控制台中的 issue/status/version/path
- Fact / QA 狀態只作顯示與 gate，不作內容生成

---

# 2. Public HTML Required Components

## Header
顯示：
- date
- language
- category
- headline
- version
- last checked

## Core
預設展開：
- hook
- quick summary
- background / language scaffold
- Core sections
- checkpoint(s)
- Core Complete

## Extension
預設可折疊：
- Extension sections
- Level tasks
- exam connection

## Help
按鈕：
- `我卡住了`
- `I'M STUCK`
- English day: `中文救援｜真的卡住再看`

## Answers
學生先作答，再按：
- `查看答案`
- `Check answer`

不要一開始把全部答案攤開。

## Sources
顯示 compact source cards：
- publisher
- date
- title
- direct source link

## Footer
- Download PDF
- Version
- Correction notice if any

---

# 3. Responsive Rules

- 手機／平板／桌機都不得出現小字牆
- reading width 建議控制在約 65–75 characters
- 行距約 1.55–1.7
- 手機正文不得因 desktop CSS 被縮小
- Core 內容在手機上仍按照同一閱讀順序
- 不做三欄 newspaper layout

---

# 4. Print

Public HTML 的 `@media print` 可作輔助，
但正式 PDF V1 仍以既有 Print Renderer 為主。

HTML 必須提供：
`Download PDF`

PDF 和 HTML 都來自同一 Structured Content。

---

# 5. Status Rules

只有：
- READY
- APPROVED
- PUBLISHED

可以產 public student page。

以下狀態不得公開：
- SCHEDULED
- VERIFYING
- DRAFTING
- REVISE
- BLOCKED_*

BLOCKED sample 已提供。

---

# 6. Correction Rules

如果 current version > previous version：
- student page 顯示最新版本
- 可顯示短更正通知
- 不應默默覆蓋歷史
- PDF download 指向最新版本
- Version history 可留在後台

Correction workflow sample 已提供。

---

# 7. Accessibility

- Semantic headings
- Buttons keyboard accessible
- `aria-expanded` for collapsibles
- visual assets require alt text
- 不用顏色作為唯一狀態訊號
- 字級可由瀏覽器放大
- source links 有清楚文字

---

# 8. V1 Explicit Non-goals

不要在這一階段加入：
- Audio
- TTS
- Account
- Student score storage
- Parent dashboard
- Gamification
- AI tutor chat
- Personalized content

V1 先證明：
**同一份母資料能穩定提供好讀 HTML + PDF。**

---

# 9. Acceptance Tests

HTML V1 至少要通過：

1. 中文 READY sample 可渲染
2. 英文 READY sample 可渲染
3. Review sample 可渲染
4. BLOCKED sample 無 public page
5. Correction sample 可顯示 version notice
6. Mobile width 360px 不橫向溢出
7. Desktop 不超寬文字牆
8. Answers 預設隱藏
9. Rescue 預設收合
10. English Chinese-rescue 預設收合
11. Source links 可點
12. PDF link 對應同一 issue/version

---

# 10. Do Not Reinterpret the Contract

如果工程端覺得某欄位不好呈現：
先調 Renderer。

不要修改：
- JSON 結構
- teaching logic
- QA meaning
- claim data

若真的需要 contract change：
回產品／內容端另開 V1.1 Review。

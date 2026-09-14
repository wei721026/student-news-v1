# 自學型時事素養教材系統｜Implementation Pack V1.0

狀態：**PRODUCTION CONTRACT FROZEN / READY FOR HTML ENGINEERING**

核心原則：

> **Data-based → PDF-first → HTML-ready → Audio-later**

---

## 已驗證

### 內容
- 中文與英文交替
- 國內／國際混合
- 經濟、AI、健康、地理、運動、氣候
- 週日不讀新新聞，只做提取與連結

### QA
- Fact QA
- Teaching QA
- Layout QA
- BLOCKED_SOURCE
- Correction / Version workflow

### Print
- A4 2頁
- Core page 1
- ≥15.4pt main reading text
- ≥11.5pt sources
- Overflow → revise content/framing, never shrink core text

---

# V1.0 Single Source of Truth

```text
Sources / Claims / Fact Pack
        ↓
Structured Content V1.0
        ├─ Internal HTML/CSS → Print PDF
        └─ Public HTML V1
```

Google Sheet：
- 控制狀態
- 管理來源索引
- 管 QA
- 管版本
- 管概念與選題平衡

Google Sheet **不是**全文內容母檔，也不負責判定新聞真偽。

---

# Public HTML V1 Scope

HTML V1 只做：

1. Responsive large-text reading
2. Core / Extension sections
3. `我卡住了 / I'M STUCK` collapsible help
4. Answer reveal
5. Chinese rescue collapse on English days
6. Source links
7. Download matching PDF
8. Issue version / last-checked date
9. Correction notice if present

暫時不做：
- Audio
- Login
- Scores
- Analytics
- Student tracking
- Personalized recommendations
- Chatbot

---

# State Gate

```text
SCHEDULED
→ DISCOVERY
→ VERIFYING
→ VERIFIED
→ DRAFTING
→ CONTENT_QA
→ RENDERING
→ LAYOUT_QA
→ READY
→ APPROVED / PUBLISHED
```

任何 Critical Claim：
`UNVERIFIED → BLOCKED_SOURCE`

任何 Teaching QA：
`BLOCK → BLOCKED_PEDAGOGY`

任何 Renderer：
`Overflow requiring smaller core text → BLOCKED_LAYOUT / CONTENT REVISION`

---

# Engineering Rule

工程端只可：
- render
- hide/show
- navigate
- link
- print/download
- display version/status

工程端不可：
- 改新聞事實
- 新增背景
- 自動重新寫文章
- 取消 QA
- 把答案改成另一個內容
- 自行縮字破壞 print contract

---

# HTML Handoff Gate

已完成：
- 4 Pilot ✅
- One-Week Trial 6 issues ✅
- Sunday Review ✅
- BLOCKED sample ✅
- Correction sample ✅
- Schema stable for full week ✅

**Gate result: PASS**

下一階段：
`Public HTML V1 Engineering`

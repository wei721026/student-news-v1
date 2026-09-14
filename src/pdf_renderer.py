from __future__ import annotations

from html import escape
from pathlib import Path

import fitz
from weasyprint import HTML


def _txt(value) -> str:
    return escape(str(value or ""))


def _is_en(structured: dict) -> bool:
    return str((structured.get("metadata") or {}).get("language", "")).lower().startswith("en")


def _is_review(structured: dict) -> bool:
    lang = str((structured.get("metadata") or {}).get("language", "")).upper()
    return lang == "REVIEW" or bool(structured.get("week_cards"))


def _categories(meta: dict) -> str:
    values = meta.get("categories") or []
    if isinstance(values, str):
        return values
    return " × ".join(str(x) for x in values[:4])


def _accent(meta: dict) -> tuple[str, str, str]:
    style = str(meta.get("interaction_style") or "").upper()
    if style == "LANGUAGE_SCAFFOLD":
        return "#315f86", "#eef4f9", "#b7cada"
    if style == "GUIDED_READING":
        return "#3d765f", "#eff6f2", "#bdd3c7"
    if style == "POLICY_MODEL":
        return "#6d557c", "#f4f0f6", "#cfc2d7"
    if style == "MYSTERY_DISCOVERY":
        return "#87514f", "#f8f1f0", "#dbc4c2"
    return "#75621f", "#f7f4e8", "#d7cda8"


def _checkpoint_html(
    checkpoint: dict,
    *,
    en: bool,
    question_label: str | None = None,
) -> str:
    if not checkpoint or not checkpoint.get("enabled"):
        return ""
    choices = checkpoint.get("choices") or []
    choices_html = ""
    if choices:
        choices_html = "<ol class='choices'>" + "".join(
            f"<li>{_txt(choice)}</li>" for choice in choices
        ) + "</ol>"
    label_html = (
        f"<span class='q-label'>{_txt(question_label)}</span> "
        if question_label else ""
    )
    response_label = "My answer" if en else "我的答案"
    return (
        "<div class='checkpoint'>"
        f"{label_html}<b>{_txt(checkpoint.get('prompt'))}</b>"
        f"{choices_html}"
        f"<div class='response-line'>{response_label}：________________________</div>"
        "</div>"
    )


def _answer_key_items(structured: dict, *, en: bool) -> list[dict]:
    items: list[dict] = []
    question_no = 1
    sections = structured.get("sections") or []

    for role in ("CORE", "EXTENSION"):
        for section in [s for s in sections if s.get("role") == role]:
            checkpoint = section.get("checkpoint") or {}
            if not checkpoint.get("enabled") or not checkpoint.get("prompt"):
                continue
            answer = str(checkpoint.get("answer") or "").strip()
            explanation = str(checkpoint.get("explanation") or "").strip()
            if answer or explanation:
                items.append(
                    {
                        "label": f"Q{question_no}",
                        "answer": answer,
                        "explanation": explanation,
                    }
                )
            question_no += 1

    levels = structured.get("levels") or {}
    level_labels = {"basic": "★", "standard": "★★", "challenge": "★★★"}
    for key in ("basic", "standard", "challenge"):
        item = levels.get(key) or {}
        if not item.get("enabled", True) or not item.get("prompt"):
            continue
        answer = str(item.get("answer") or "").strip()
        if answer:
            items.append(
                {
                    "label": level_labels[key],
                    "answer": answer,
                    "explanation": "",
                }
            )
    return items


def _answer_key_html(structured: dict, *, en: bool) -> str:
    items = _answer_key_items(structured, en=en)
    if not items:
        return ""
    title = (
        "ANSWERS & EXPLANATIONS | Check after you finish"
        if en else "答案與解析｜做完再看"
    )
    note = (
        "Go back to the article and check the evidence before reading the answer."
        if en else "先回到文章找證據，再看這裡。"
    )
    rows = []
    for item in items:
        explanation = str(item.get("explanation") or "").strip()
        explanation_html = (
            f"<span class='answer-expl'>{_txt(explanation)}</span>"
            if explanation else ""
        )
        rows.append(
            "<div class='answer-row'>"
            f"<b>{_txt(item.get('label'))}</b> {_txt(item.get('answer'))}"
            f"{explanation_html}</div>"
        )
    return (
        "<div class='answer-key'>"
        f"<div class='answer-key-title'>{title}</div>"
        f"<div class='answer-key-note'>{note}</div>"
        + "".join(rows)
        + "</div>"
    )


def _source_rows(structured: dict, source_records: list[dict] | None) -> str:
    records = source_records or []
    by_id = {
        str(row.get("Source_ID") or row.get("source_id") or ""): row
        for row in records
    }
    ids = list((structured.get("provenance") or {}).get("source_ids") or [])
    rows = []
    for sid in ids[:5]:
        record = by_id.get(str(sid), {})
        publisher = record.get("Publisher") or record.get("publisher") or sid
        date = record.get("Source_Published_Date") or record.get("published") or ""
        rows.append(
            f"<div><b>{_txt(sid)}</b> {_txt(publisher)}"
            + (f" <span class='muted'>{_txt(date)}</span>" if date else "")
            + "</div>"
        )
    if not rows:
        rows = [f"<div>{_txt(sid)}</div>" for sid in ids[:5]]
    return "".join(rows)


def _daily_css(structured: dict) -> str:
    meta = structured.get("metadata") or {}
    accent, soft, line = _accent(meta)
    return f"""
@page {{
  size:A4;
  margin:8mm 12mm 12mm;
  @bottom-left {{
    content:"Student News · " attr(data-footer);
    font-size:8.3pt; color:#777;
  }}
  @bottom-right {{
    content:counter(page) " / " counter(pages);
    font-size:8.3pt; color:#777;
  }}
}}
* {{ box-sizing:border-box; }}
html, body {{ margin:0; padding:0; }}
body {{
  font-family:"Noto Sans CJK TC","Noto Sans TC","Noto Sans",Arial,sans-serif;
  color:#222;
}}
.sheet {{ break-after:page; min-height:260mm; }}
.sheet:last-child {{ break-after:auto; }}
.kicker {{
  font-size:9.5pt; font-weight:800; letter-spacing:.05em;
  color:#666; text-transform:uppercase; margin-bottom:1mm;
}}
h1 {{
  color:{accent}; font-size:21.5pt; line-height:1.12;
  margin:1mm 0 1mm; font-weight:900;
}}
.hook {{
  font-size:13.8pt; line-height:1.32; font-weight:750;
  margin:0 0 2mm;
}}
.quick {{
  border-left:4px solid {accent}; background:{soft};
  border-radius:7px; padding:2.2mm 3mm;
  font-size:13.4pt; line-height:1.36; margin:1.5mm 0 2mm;
}}
.label {{
  color:{accent}; font-size:9.5pt; font-weight:900;
  letter-spacing:.03em; margin:2mm 0 .8mm;
}}
.grid2 {{
  display:grid; grid-template-columns:1fr 1fr;
  gap:2mm; margin:1.2mm 0 2mm;
}}
.card {{
  border:1px solid {line}; border-radius:7px;
  padding:2mm 2.5mm; background:#fff;
  font-size:11.4pt; line-height:1.28;
}}
.card b {{ color:{accent}; font-size:12.2pt; }}
.words {{
  border:1px solid {line}; border-radius:7px;
  padding:1.5mm 2mm; margin:1mm 0 1.5mm;
  font-size:10.9pt; line-height:1.35;
}}
.focus {{
  border:1px solid {line}; border-radius:7px;
  padding:1.8mm 2.5mm; margin:1mm 0 2mm;
  background:{soft};
}}
.focus .sentence {{
  color:{accent}; font-size:13.2pt; font-weight:850;
  line-height:1.25;
}}
.breakdown {{
  display:grid; grid-template-columns:repeat(4,1fr);
  gap:1.2mm; margin-top:1.2mm;
  font-size:9.2pt; line-height:1.18; color:#555;
}}
.breakdown b {{ color:#555; }}
h2 {{
  color:{accent}; font-size:15.5pt; line-height:1.18;
  margin:2.2mm 0 .7mm;
}}
.article {{
  font-size:14.2pt; line-height:1.38; margin:0 0 1.2mm;
}}
.checkpoint {{
  border:1px solid {line}; border-radius:7px;
  padding:1.8mm 2.5mm; margin:1.5mm 0 1.8mm;
  font-size:10.8pt; line-height:1.28;
}}
.choices {{ margin:.8mm 0 .8mm 5mm; padding-left:4mm; }}
.q-label {{
  display:inline-block; margin-right:1mm; color:{accent};
  font-weight:900; font-size:9.5pt;
}}
.response-line {{
  margin-top:1.2mm; padding-top:.8mm; border-top:1px dotted #bbb;
  color:#666; font-size:9.5pt;
}}
.core-complete {{
  margin-top:2mm; padding:1.4mm 2mm; border-radius:6px;
  background:#f3f3ef; text-align:center;
  font-size:11pt; font-weight:850;
}}
.extension-box {{
  border:1px solid {line}; border-radius:8px;
  padding:2.2mm 2.7mm; margin:1.5mm 0 2mm;
}}
.level {{
  border-left:4px solid {accent}; background:#fafafa;
  padding:1.6mm 2.5mm; margin:1.2mm 0;
  font-size:10.7pt; line-height:1.26;
}}
.level .title {{ color:{accent}; font-size:12.2pt; font-weight:900; }}
.level .response-line {{ margin-top:1mm; }}
.rescue {{
  border:1px solid #d8c783; background:#fffaf0;
  border-radius:8px; padding:2mm 2.5mm;
  font-size:10.5pt; line-height:1.28;
}}
.rescue b {{ font-size:12pt; }}
.bottom-grid {{
  display:grid; grid-template-columns:.9fr 1.1fr;
  gap:2mm; margin-top:2mm;
}}
.one-thing, .sources {{
  border:1px solid {line}; border-radius:8px;
  padding:2mm 2.5mm; min-height:24mm;
  font-size:10.5pt; line-height:1.28;
}}
.one-thing b, .sources b {{ color:{accent}; }}
.write-line {{ border-bottom:1px solid #888; margin-top:5mm; }}
.muted {{ color:#777; font-size:9.2pt; }}
.exam {{
  border-top:1px solid #ddd; padding-top:1.2mm; margin-top:1.5mm;
  font-size:9.8pt; line-height:1.25;
}}
.answer-key {{
  margin-top:2mm; padding-top:1.5mm; border-top:2px solid {accent};
  font-size:9.1pt; line-height:1.22; break-inside:avoid;
}}
.answer-key-title {{
  color:{accent}; font-weight:900; font-size:10.4pt;
}}
.answer-key-note {{ color:#777; font-size:8.6pt; margin:.4mm 0 .8mm; }}
.answer-row {{ margin-top:.55mm; }}
.answer-row b {{ color:{accent}; margin-right:.8mm; }}
.answer-expl {{ color:#666; margin-left:1mm; }}
"""


REVIEW_CSS = """
@page {
  size:A4;
  margin:9mm 12mm 12mm;
  @bottom-left { content:"One-Week Trial · Sunday Review"; font-size:8.8pt; color:#777; }
  @bottom-right { content:counter(page) " / " counter(pages); font-size:8.8pt; color:#777; }
}
* { box-sizing:border-box; }
body { font-family:"Noto Sans CJK TC","Noto Sans",Arial,sans-serif; color:#222; margin:0; }
.sheet { break-after:page; }
.sheet:last-child { break-after:auto; }
.kicker { font-size:10.5pt; font-weight:700; letter-spacing:.02em; color:#555; }
h1 { font-size:21pt; line-height:1.12; margin:1.5mm 0 1mm; }
h2 { font-size:14.5pt; margin:2.2mm 0 1mm; }
.hook { font-size:13.5pt; font-weight:700; line-height:1.35; margin-bottom:1.5mm; }
.quick { font-size:13pt; line-height:1.35; padding:2mm 2.6mm; background:#f5f6f7; border-radius:7px; }
.grid { display:grid; grid-template-columns:repeat(3,1fr); gap:1.5mm; margin:1.5mm 0; }
.card { border:1px solid #d7dadd; border-radius:7px; padding:1.6mm 1.9mm; font-size:10.8pt; line-height:1.27; }
.card b { font-size:11.4pt; }
.pill { display:inline-block; font-size:8.8pt; font-weight:700; color:#555; margin-bottom:.6mm; }
.section { margin-top:1.5mm; }
.row { display:grid; grid-template-columns:1fr 1fr; gap:1.8mm; }
.prompt { font-size:11.3pt; line-height:1.32; }
.answer { font-size:10.8pt; line-height:1.3; color:#444; margin-top:.6mm; }
.choices { font-size:11.2pt; line-height:1.32; margin:1mm 0 0 5mm; }
.footer-card { border:1px solid #d7dadd; border-radius:8px; padding:3mm; font-size:14.5pt; line-height:1.45; }
.review-answer-row { font-size:11.2pt; line-height:1.3; margin-top:1.2mm; }
.review-answer-row b { margin-right:1mm; }
.note { font-size:11.5pt; color:#555; margin-top:3mm; }
"""


def _render_review_pdf(structured: dict, out_dir: Path) -> tuple[Path, int]:
    editorial = structured.get("editorial", {})
    cards = structured.get("week_cards", [])[:6]
    recall = structured.get("recall") or {}
    words = recall.get("english_words", [])[:3]
    connections = structured.get("connections", [])[:2]
    evidence = structured.get("evidence_check") or {}

    cards_html = "".join(
        f"""<div class="card"><span class="pill">{_txt(c.get('day'))}</span><br>
        <b>{_txt(c.get('title'))}</b><br>{_txt(c.get('memory'))}<br>
        <span class="answer">{_txt(c.get('concept'))}</span></div>"""
        for c in cards
    )
    recall_html = "".join(
        f"<div class='card'>{_txt(x)}</div>" for x in (recall.get("events") or [])[:3]
    )
    words_html = "".join(
        f"""<div class="card"><b>{_txt(w.get('word'))}</b><br>
        <span class="prompt">{_txt(w.get('prompt'))}</span></div>"""
        for w in words
    )
    connections_html = "".join(
        f"""<div class="card"><b>{_txt(c.get('title'))}</b><br>
        <span class="prompt">{_txt(c.get('question'))}</span></div>"""
        for c in connections
    )
    choices_html = "".join(
        f"<li>{_txt(choice)}</li>" for choice in (evidence.get("choices") or [])
    )

    review_answers = []
    for w in words:
        if w.get("answer"):
            review_answers.append(
                f"<div class='review-answer-row'><b>{_txt(w.get('word'))}</b>"
                f"{_txt(w.get('answer'))}</div>"
            )
    for c in connections:
        if c.get("answer"):
            review_answers.append(
                f"<div class='review-answer-row'><b>{_txt(c.get('title'))}</b>"
                f"{_txt(c.get('answer'))}</div>"
            )
    if evidence.get("answer"):
        review_answers.append(
            "<div class='review-answer-row'><b>④ 資訊素養</b>"
            f"{_txt(evidence.get('answer'))}</div>"
        )
    review_answers_html = (
        "<div class='footer-card'><b>答案與自我檢查｜做完再看</b>"
        + "".join(review_answers)
        + "</div>"
    )

    html = f"""<!doctype html><html><head><meta charset="utf-8"><style>{REVIEW_CSS}</style></head><body>
    <section class="sheet">
      <div class="kicker">ONE-WEEK TRIAL · SUNDAY REVIEW｜不讀新新聞</div>
      <h1>{_txt(editorial.get('headline'))}</h1>
      <div class="hook">{_txt(editorial.get('hook'))}</div>
      <div class="quick">{_txt(editorial.get('quick_summary'))}</div>
      <h2>六天，六個世界入口</h2>
      <div class="grid">{cards_html}</div>
      <div class="row">
        <div class="section"><h2>① 我還記得什麼？</h2><div class="grid" style="grid-template-columns:1fr">{recall_html}</div></div>
        <div class="section"><h2>② 英文詞重新叫回來</h2><div class="grid" style="grid-template-columns:1fr">{words_html}</div></div>
      </div>
      <div class="row">
        <div class="section"><h2>③ 兩則新聞其實連得起來</h2>{connections_html}</div>
        <div class="section"><h2>④ 這週最重要的一個資訊素養</h2>
          <div class="card"><span class="prompt">{_txt(evidence.get('prompt'))}</span>
          <ol class="choices">{choices_html}</ol></div>
        </div>
      </div>
    </section>
    <section class="sheet">
      <div class="footer-card">{_txt(structured.get('one_week_prompt'))}</div>
      <div class="note">今天不計分。能把一件事重新說出來，就已經完成一次提取練習。</div>
      <div style="margin-top:8mm">{review_answers_html}</div>
    </section>
    </body></html>"""

    issue_id = structured.get("issue_id", "issue")
    html_path = out_dir / f"{issue_id}.print.html"
    pdf_path = out_dir / f"{issue_id}.pdf"
    html_path.write_text(html, encoding="utf-8")
    HTML(string=html, base_url=str(out_dir)).write_pdf(pdf_path)
    with fitz.open(pdf_path) as doc:
        return pdf_path, len(doc)


def _render_daily_pdf(
    structured: dict,
    out_dir: Path,
    source_records: list[dict] | None,
) -> tuple[Path, int]:
    meta = structured.get("metadata") or {}
    editorial = structured.get("editorial") or {}
    sections = structured.get("sections") or []
    core = [s for s in sections if s.get("role") == "CORE"]
    extension = [s for s in sections if s.get("role") == "EXTENSION"]
    en = _is_en(structured)

    category_text = _categories(meta)
    if en:
        kicker = f"STUDENT NEWS · DAILY | ENGLISH × {category_text}"
        quick_label = "30-SECOND QUICK START"
        extension_label = "GO DEEPER ONLY IF YOU WANT TO"
    else:
        kicker = f"STUDENT NEWS · DAILY｜中文時事 × {category_text}"
        quick_label = "30 秒先懂"
        extension_label = "延伸｜想多懂一點再看"

    background_html = ""
    language_support = structured.get("language_support") or {}
    if en:
        words = (language_support.get("key_words") or [])[:5]
        word_bits = " · ".join(
            f"<b>{_txt(w.get('word'))}</b> {_txt(w.get('meaning_zh'))}"
            for w in words
        )
        focus = _txt(language_support.get("focus_sentence"))
        breakdown = language_support.get("sentence_breakdown") or {}
        breakdown_html = "".join(
            f"<div><b>{_txt(k)}</b><br>{_txt(v)}</div>"
            for k, v in list(breakdown.items())[:4]
        )
        background_html = (
            f"<div class='label'>5 WORDS YOU NEED</div><div class='words'>{word_bits}</div>"
            f"<div class='label'>ONE SENTENCE TOGETHER</div>"
            f"<div class='focus'><div class='sentence'>{focus}</div>"
            f"<div class='breakdown'>{breakdown_html}</div></div>"
        )
    else:
        bg = [
            item for item in (structured.get("background") or [])
            if item.get("role", "CORE") == "CORE"
        ][:2]
        if bg:
            cards = "".join(
                f"<div class='card'><b>{_txt(x.get('term'))}</b><br>{_txt(x.get('explanation'))}</div>"
                for x in bg
            )
            background_html = (
                "<div class='label'>讀之前，先懂兩件事</div>"
                f"<div class='grid2'>{cards}</div>"
            )

    core_html = ""
    checkpoint_no = 1
    for section in core[:3]:
        checkpoint = section.get("checkpoint") or {}
        question_label = None
        if checkpoint.get("enabled") and checkpoint.get("prompt"):
            question_label = f"Q{checkpoint_no}"
            checkpoint_no += 1
        core_html += (
            f"<h2>{_txt(section.get('title'))}</h2>"
            f"<p class='article'>{_txt(section.get('text'))}</p>"
            + _checkpoint_html(
                checkpoint,
                en=en,
                question_label=question_label,
            )
        )

    completion = structured.get("completion") or {}
    completion_label = completion.get("student_checkbox_label") or (
        "□ CORE COMPLETE | You can stop here today." if en else "□ 核心任務完成"
    )

    ext_html = ""
    for section in extension[:2]:
        checkpoint = section.get("checkpoint") or {}
        question_label = None
        if checkpoint.get("enabled") and checkpoint.get("prompt"):
            question_label = f"Q{checkpoint_no}"
            checkpoint_no += 1
        ext_html += (
            f"<div class='extension-box'><h2>{_txt(section.get('title'))}</h2>"
            f"<p class='article'>{_txt(section.get('text'))}</p>"
            f"{_checkpoint_html(checkpoint, en=en, question_label=question_label)}</div>"
        )

    level_labels = (
        {
            "basic": "★ Find the fact",
            "standard": "★★ Explain the evidence",
            "challenge": "★★★ Check the headline",
        } if en else {
            "basic": "★ 我找得到重點",
            "standard": "★★ 我能解釋",
            "challenge": "★★★ 我能判斷新聞說法",
        }
    )
    levels = structured.get("levels") or {}
    level_html = ""
    response_label = "My answer" if en else "我的答案"
    for key in ("basic", "standard", "challenge"):
        item = levels.get(key) or {}
        if item.get("enabled", True) and item.get("prompt"):
            level_html += (
                f"<div class='level'><div class='title'>{level_labels[key]}</div>"
                f"<div>{_txt(item.get('prompt'))}</div>"
                f"<div class='response-line'>{response_label}：________________________</div>"
                "</div>"
            )

    rescue = structured.get("rescue") or {}
    rescue_title = "I'M STUCK" if en else "我卡住了"
    rescue_html = (
        f"<div class='rescue'><b>{rescue_title}</b><br>"
        f"① {_txt(rescue.get('hint_1'))}<br>"
        f"② {_txt(rescue.get('hint_2'))}<br>"
        f"③ {_txt(rescue.get('summary'))}</div>"
    )
    if en and language_support.get("zh_rescue_summary"):
        rescue_html = (
            "<div class='grid2' style='align-items:stretch'>"
            f"{rescue_html}"
            "<div class='rescue' style='background:#f7f9fb;border-color:#cbd7e0'>"
            "<b>中文救援｜真的卡住再看</b><br>"
            f"{_txt(language_support.get('zh_rescue_summary'))}</div></div>"
        )

    exam = structured.get("exam_connection") or {}
    exam_html = ""
    if exam.get("enabled"):
        label = "If this became a test question..." if en else "如果它變成考題，可能怎麼考？"
        exam_html = (
            f"<div class='exam'><b>{label}</b><br>{_txt(exam.get('note'))}</div>"
        )

    one_prompt = structured.get("one_thing_prompt") or (
        "One thing I learned today: ____________________________"
        if en else "今天我只記一件事：____________________________"
    )
    source_html = _source_rows(structured, source_records)
    answer_key_html = _answer_key_html(structured, en=en)
    uncertainties = (structured.get("provenance") or {}).get("uncertainties") or []
    uncertainty_html = ""
    if uncertainties:
        uncertainty_html = (
            "<div class='muted' style='margin-top:1mm'>"
            + _txt(uncertainties[0])
            + "</div>"
        )

    css = _daily_css(structured)
    html = f"""<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head>
    <body data-footer="{_txt(structured.get('issue_id'))}">
    <section class="sheet">
      <div class="kicker">{_txt(kicker)}</div>
      <h1>{_txt(editorial.get('headline'))}</h1>
      <div class="hook">{_txt(editorial.get('hook'))}</div>
      <div class="label">{quick_label}</div>
      <div class="quick">{_txt(editorial.get('quick_summary'))}</div>
      {background_html}
      {core_html}
      <div class="core-complete">{_txt(completion_label)}</div>
    </section>
    <section class="sheet">
      <div class="kicker">{extension_label}</div>
      {ext_html}
      {level_html}
      {rescue_html}
      {exam_html}
      <div class="bottom-grid">
        <div class="one-thing"><b>{'One thing I learned today' if en else '今天我只記一件事'}</b>
          <div class="muted">{_txt(one_prompt)}</div><div class="write-line"></div>
        </div>
        <div class="sources"><b>{'Sources & Fact Check | PASS' if en else '來源與查核｜PASS'}</b>
          {source_html}{uncertainty_html}
        </div>
      </div>
      {answer_key_html}
    </section>
    </body></html>"""

    issue_id = structured.get("issue_id", "issue")
    html_path = out_dir / f"{issue_id}.print.html"
    pdf_path = out_dir / f"{issue_id}.pdf"
    html_path.write_text(html, encoding="utf-8")
    HTML(string=html, base_url=str(out_dir)).write_pdf(pdf_path)
    with fitz.open(pdf_path) as doc:
        return pdf_path, len(doc)


def render_pdf_issue(
    structured: dict,
    out_dir: Path,
    source_records: list[dict] | None = None,
) -> tuple[Path, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    if _is_review(structured):
        return _render_review_pdf(structured, out_dir)
    return _render_daily_pdf(structured, out_dir, source_records)

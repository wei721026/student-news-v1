from __future__ import annotations

from pathlib import Path
from html import escape
from weasyprint import HTML
import fitz


BASE_CSS = """
@page {
  size: A4;
  margin: 9mm 13mm 12mm;
  @bottom-left { content: "Student News"; font-size: 8.8pt; color: #777; }
  @bottom-right { content: counter(page) " / " counter(pages); font-size: 8.8pt; color: #777; }
}
* { box-sizing: border-box; }
body { font-family: "Noto Sans CJK TC","Noto Sans",Arial,sans-serif; color:#222; margin:0; }
.sheet { break-after: page; }
.sheet:last-child { break-after: auto; }
h1 { font-size: 22pt; line-height:1.1; margin: 1mm 0; }
h2 { font-size: 16pt; margin: 2mm 0 .5mm; }
p.article { font-size: 15.4pt; line-height:1.38; margin:0; }
.hook { font-size:14.8pt; font-weight:700; line-height:1.3; margin-bottom:2mm; }
.quick { font-size:14.5pt; line-height:1.35; padding:2mm 3mm; background:#f5f6f7; border-radius:8px; }
.card { border:1px solid #d7dadd; border-radius:8px; padding:2mm 2.5mm; margin:1.5mm 0; }
.small { font-size:11.5pt; line-height:1.3; }
.core { font-size:12.6pt; font-weight:700; text-align:center; padding:1.5mm; background:#f3f4f2; border-radius:7px; margin-top:2mm; }
.words { font-size:11.5pt; line-height:1.4; padding:1.5mm 2mm; border:1px solid #ddd; border-radius:7px; margin:1.5mm 0; }
.level { border-left:4px solid #7b8794; padding:1.8mm 2.5mm; margin:1.7mm 0; background:#fafbfc; }
.sources { font-size:11.5pt; line-height:1.22; border-top:1px solid #ddd; padding-top:1.5mm; }
"""


def _txt(value):
    return escape(str(value or ""))


def _section_html(section):
    checkpoint = section.get("checkpoint") or {}
    cp = ""
    if checkpoint.get("enabled"):
        choices = "".join(f"<li>{_txt(x)}</li>" for x in checkpoint.get("choices", []))
        cp = f"""<div class="card small"><b>{_txt(checkpoint.get('prompt'))}</b>
        <ol>{choices}</ol><div>Answer: {_txt(checkpoint.get('answer'))}</div></div>"""
    return f"<h2>{_txt(section.get('title'))}</h2><p class='article'>{_txt(section.get('text'))}</p>{cp}"



REVIEW_CSS = """
@page {
  size: A4;
  margin: 9mm 12mm 12mm;
  @bottom-left { content: "One-Week Trial · Sunday Review"; font-size: 8.8pt; color:#777; }
  @bottom-right { content: counter(page) " / " counter(pages); font-size: 8.8pt; color:#777; }
}
* { box-sizing: border-box; }
body { font-family: "Noto Sans CJK TC","Noto Sans",Arial,sans-serif; color:#222; margin:0; }
.sheet { break-after: page; }
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
.note { font-size:11.5pt; color:#555; margin-top:3mm; }
"""


def _render_review_pdf(structured: dict, out_dir: Path) -> tuple[Path, int]:
    metadata = structured.get("metadata", {})
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
        <span class="prompt">{_txt(w.get('prompt'))}</span><br>
        <span class="answer">自我檢查：{_txt(w.get('answer'))}</span></div>"""
        for w in words
    )
    connections_html = "".join(
        f"""<div class="card"><b>{_txt(c.get('title'))}</b><br>
        <span class="prompt">{_txt(c.get('question'))}</span><br>
        <span class="answer">{_txt(c.get('answer'))}</span></div>"""
        for c in connections
    )
    choices_html = "".join(
        f"<li>{_txt(choice)}</li>" for choice in (evidence.get("choices") or [])
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
      <div class="footer-card"><b>做完再看</b><br>{_txt(evidence.get('answer'))}</div>
      <div class="footer-card" style="margin-top:5mm">{_txt(structured.get('one_week_prompt'))}</div>
      <div class="note">今天不計分。能把一件事重新說出來，就已經完成一次提取練習。</div>
    </section>
    </body></html>"""

    issue_id = structured.get("issue_id", "issue")
    html_path = out_dir / f"{issue_id}.print.html"
    pdf_path = out_dir / f"{issue_id}.pdf"
    html_path.write_text(html, encoding="utf-8")
    HTML(string=html, base_url=str(out_dir)).write_pdf(pdf_path)
    with fitz.open(pdf_path) as doc:
        return pdf_path, len(doc)


def render_pdf_issue(structured: dict, out_dir: Path) -> tuple[Path, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    if str((structured.get("metadata") or {}).get("language", "")).upper() == "REVIEW" or structured.get("week_cards"):
        return _render_review_pdf(structured, out_dir)
    metadata = structured.get("metadata", {})
    editorial = structured.get("editorial", {})
    sections = structured.get("sections", [])
    core_sections = [s for s in sections if s.get("role") == "CORE"]
    ext_sections = [s for s in sections if s.get("role") == "EXTENSION"]

    lang = metadata.get("language", "zh-TW")
    lang_support = structured.get("language_support") or {}
    words_html = ""
    if lang_support.get("enabled"):
        words = lang_support.get("key_words", [])[:5]
        bits = " · ".join(
            f"<b>{_txt(w.get('word'))}</b> {_txt(w.get('meaning_zh'))}"
            for w in words
        )
        focus = _txt(lang_support.get("focus_sentence"))
        words_html = f"<div class='words'>{bits}</div><div class='card small'><b>Focus sentence</b><br>{focus}</div>"
    else:
        bg = structured.get("background", [])[:3]
        if bg:
            bits = "".join(
                f"<div class='card small'><b>{_txt(x.get('term'))}</b><br>{_txt(x.get('explanation'))}</div>"
                for x in bg
            )
            words_html = bits

    sources = structured.get("provenance", {}).get("source_ids", [])
    source_text = " · ".join(_txt(x) for x in sources)

    core_html = "".join(_section_html(s) for s in core_sections)
    ext_html = "".join(_section_html(s) for s in ext_sections)

    rescue = structured.get("rescue") or {}
    levels = structured.get("levels") or {}
    level_html = ""
    for key in ("basic", "standard", "challenge"):
        item = levels.get(key) or {}
        if item.get("enabled", True) and item.get("prompt"):
            level_html += f"<div class='level'><b>{key.upper()}</b><br>{_txt(item.get('prompt'))}<br><span class='small'>{_txt(item.get('answer'))}</span></div>"

    zh_rescue = ""
    if lang_support.get("enabled") and lang_support.get("zh_rescue_summary"):
        zh_rescue = f"<div class='card small'><b>中文救援</b><br>{_txt(lang_support.get('zh_rescue_summary'))}</div>"

    html = f"""<!doctype html><html><head><meta charset="utf-8"><style>{BASE_CSS}</style></head><body>
    <section class="sheet">
      <div class="small">{_txt(metadata.get('publish_date'))} · {_txt(metadata.get('categories'))}</div>
      <h1>{_txt(editorial.get('headline'))}</h1>
      <div class="hook">{_txt(editorial.get('hook'))}</div>
      <div class="quick">{_txt(editorial.get('quick_summary'))}</div>
      {words_html}
      {core_html}
      <div class="core">{_txt((structured.get('completion') or {}).get('student_checkbox_label','□ Core complete'))}</div>
    </section>
    <section class="sheet">
      {ext_html}
      {level_html}
      <div class="card small"><b>I'M STUCK / 我卡住了</b><br>{_txt(rescue.get('hint_1'))}<br>{_txt(rescue.get('hint_2'))}<br>{_txt(rescue.get('summary'))}</div>
      {zh_rescue}
      <div class="sources"><b>Sources</b><br>{source_text}</div>
    </section>
    </body></html>"""

    issue_id = structured.get("issue_id", "issue")
    html_path = out_dir / f"{issue_id}.print.html"
    pdf_path = out_dir / f"{issue_id}.pdf"
    html_path.write_text(html, encoding="utf-8")
    HTML(string=html, base_url=str(out_dir)).write_pdf(pdf_path)

    doc = fitz.open(pdf_path)
    return pdf_path, len(doc)

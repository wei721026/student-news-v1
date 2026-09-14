from __future__ import annotations

from html import escape
from pathlib import Path
from urllib.parse import urlparse

from .gates import public_candidate_gate


class PublicRenderError(RuntimeError):
    pass


CSS = r'''
:root {
  color-scheme: light;
  --ink:#17202a; --muted:#5d6773; --line:#dce2e8; --soft:#f5f7f9;
  --accent:#174f78; --warn:#fff6df; --warn-line:#d89c24;
}
* { box-sizing:border-box; }
html, body { margin:0; padding:0; max-width:100%; overflow-x:hidden; }
body {
  font-family: system-ui, -apple-system, "Noto Sans TC", "Noto Sans CJK TC", "Segoe UI", sans-serif;
  color:var(--ink); background:#fff; font-size:clamp(1.08rem, .98rem + .38vw, 1.26rem);
  line-height:1.68; overflow-wrap:break-word;
}
main { width:min(calc(100% - 2rem), 74ch); margin:0 auto; padding:1.25rem 0 3rem; }
header { border-bottom:1px solid var(--line); padding-bottom:1rem; margin-bottom:1rem; }
.meta { display:flex; flex-wrap:wrap; gap:.35rem .8rem; color:var(--muted); font-size:.86em; }
h1 { font-size:clamp(1.85rem, 1.45rem + 1.4vw, 2.65rem); line-height:1.16; margin:.45rem 0; }
h2 { font-size:1.36em; line-height:1.28; margin:1.45rem 0 .45rem; }
h3 { font-size:1.08em; margin:1rem 0 .35rem; }
p { margin:.45rem 0 .85rem; }
.quick, .hook, .card, .checkpoint, details, .source-card, .correction {
  border:1px solid var(--line); border-radius:.75rem; padding:.9rem 1rem; margin:.85rem 0;
}
.quick { background:var(--soft); }
.hook { border-left:.38rem solid var(--accent); }
.badge {
  display:inline-block; border:1px solid var(--line); border-radius:999px;
  padding:.08rem .5rem; margin:.12rem .2rem .12rem 0; font-size:.82em;
}
.core-label { font-weight:800; color:var(--accent); letter-spacing:.02em; }
.section-text { white-space:pre-line; }
button {
  font:inherit; min-height:44px; border:1px solid #9aa8b5; background:#fff; color:var(--ink);
  border-radius:.6rem; padding:.5rem .8rem; cursor:pointer;
}
button:hover, button:focus-visible { outline:3px solid #b8d9ee; outline-offset:2px; }
.answer { margin-top:.55rem; padding:.75rem; background:var(--soft); border-radius:.55rem; }
details > summary { cursor:pointer; font-weight:800; min-height:44px; display:flex; align-items:center; }
details[open] > summary { margin-bottom:.65rem; }
.source-card { font-size:.88em; }
.source-card a, a { color:#0b5e93; overflow-wrap:anywhere; }
.footer-actions { display:flex; flex-wrap:wrap; gap:.6rem; align-items:center; margin-top:1.2rem; }
.download {
  display:inline-block; padding:.65rem .9rem; border-radius:.6rem;
  background:#174f78; color:#fff; text-decoration:none; font-weight:800;
}
.correction { background:var(--warn); border-color:var(--warn-line); }
img, svg, video, iframe, table { max-width:100%; height:auto; }
pre { max-width:100%; overflow:auto; }
ul, ol { padding-left:1.35rem; }
.core-complete { font-weight:800; margin:1.2rem 0; }
.week-card { border-left:.35rem solid #7b8794; padding:.55rem .8rem; margin:.55rem 0; background:var(--soft); }
@media (max-width:420px) {
  body { font-size:1.08rem; }
  main { width:calc(100% - 1rem); padding-top:.65rem; }
  .quick, .hook, .card, .checkpoint, details, .source-card, .correction {
    padding:.75rem .8rem; border-radius:.62rem;
  }
  .meta { display:grid; grid-template-columns:1fr; gap:.15rem; }
  .footer-actions, button, .download { width:100%; }
}
@media print {
  body { font-size:12pt; }
  main { width:100%; padding:0; }
  button { display:none; }
  .answer[hidden] { display:none !important; }
}
'''


JS = r'''
document.addEventListener("click", function (event) {
  const btn = event.target.closest("[data-answer-target]");
  if (!btn) return;
  const id = btn.getAttribute("data-answer-target");
  const answer = document.getElementById(id);
  if (!answer) return;
  const opening = answer.hasAttribute("hidden");
  if (opening) answer.removeAttribute("hidden"); else answer.setAttribute("hidden", "");
  btn.setAttribute("aria-expanded", opening ? "true" : "false");
  btn.textContent = opening ? (btn.dataset.hideLabel || "Hide answer") : (btn.dataset.showLabel || "View answer");
});
'''


def _t(value) -> str:
    return escape(str(value or ""))


def _safe_link(url: str, *, allow_relative: bool = False) -> str:
    url = str(url or "").strip()
    if allow_relative and url and not url.lower().startswith(("javascript:", "data:")):
        return escape(url, quote=True)
    parsed = urlparse(url)
    if parsed.scheme in ("http", "https"):
        return escape(url, quote=True)
    return ""


def _is_review(structured: dict) -> bool:
    lang = str((structured.get("metadata") or {}).get("language", "")).upper()
    return lang == "REVIEW" or "week_cards" in structured


def _answer_block(answer, explanation, idx: str, lang: str) -> str:
    if not answer:
        return ""
    answer_id = f"answer-{idx}"
    en = str(lang).lower().startswith("en")
    show = "Check answer" if en else "查看答案"
    hide = "Hide answer" if en else "收起答案"
    extra = (
        f"<div><strong>{'Why' if en else '說明'}：</strong>{_t(explanation)}</div>"
        if explanation else ""
    )
    return (
        f'<button type="button" aria-expanded="false" data-answer-target="{answer_id}" '
        f'data-show-label="{_t(show)}" data-hide-label="{_t(hide)}">{_t(show)}</button>'
        f'<div id="{answer_id}" class="answer" hidden><strong>{_t(answer)}</strong>{extra}</div>'
    )


def _render_checkpoint(checkpoint: dict, idx: str, lang: str) -> str:
    if not checkpoint or not checkpoint.get("enabled"):
        return ""
    choices = "".join(f"<li>{_t(x)}</li>" for x in checkpoint.get("choices", []) if x is not None)
    choices_html = f"<ol>{choices}</ol>" if choices else ""
    return (
        f'<div class="checkpoint"><h3>Checkpoint</h3><p>{_t(checkpoint.get("prompt"))}</p>'
        f'{choices_html}'
        f'{_answer_block(checkpoint.get("answer"), checkpoint.get("explanation"), idx, lang)}</div>'
    )


def _render_daily(structured: dict) -> str:
    meta = structured.get("metadata") or {}
    lang = meta.get("language", "zh-TW")
    background = structured.get("background") or []
    sections = structured.get("sections") or []
    core = [item for item in sections if item.get("role") == "CORE"]
    extension = [item for item in sections if item.get("role") == "EXTENSION"]
    out = []

    if background:
        out.append("<section aria-labelledby='background-title'><h2 id='background-title'>Background / 先懂背景</h2>")
        for item in background:
            out.append(
                f'<div class="card"><strong>{_t(item.get("term"))}</strong>'
                f'<p>{_t(item.get("explanation"))}</p></div>'
            )
        out.append("</section>")

    language_support = structured.get("language_support") or {}
    if language_support.get("enabled"):
        out.append("<section aria-labelledby='words-title'><h2 id='words-title'>5 Words</h2><div>")
        for word in (language_support.get("key_words") or [])[:5]:
            out.append(
                f'<span class="badge"><strong>{_t(word.get("word"))}</strong> — '
                f'{_t(word.get("meaning_zh"))}</span>'
            )
        out.append("</div>")
        if language_support.get("focus_sentence"):
            out.append(
                f'<div class="card"><strong>Focus Sentence</strong>'
                f'<p>{_t(language_support.get("focus_sentence"))}</p></div>'
            )
        out.append("</section>")

    out.append('<section aria-labelledby="core-title"><h2 id="core-title"><span class="core-label">Core</span></h2>')
    for i, section in enumerate(core, 1):
        out.append(
            f'<article><h2>{_t(section.get("title"))}</h2>'
            f'<p class="section-text">{_t(section.get("text"))}</p>'
        )
        out.append(_render_checkpoint(section.get("checkpoint") or {}, f"core-{i}", lang))
        out.append("</article>")
    complete = structured.get("completion") or {}
    label = complete.get("student_checkbox_label") or (
        "□ Core Complete" if str(lang).lower().startswith("en") else "□ Core 完成"
    )
    out.append(f'<div class="core-complete"><label><input type="checkbox"> {_t(label)}</label></div></section>')

    levels = structured.get("levels") or {}
    has_levels = any((levels.get(key) or {}).get("prompt") for key in ("basic", "standard", "challenge"))
    if extension or has_levels:
        out.append('<details class="extension"><summary>Extension / 延伸閱讀</summary>')
        for i, section in enumerate(extension, 1):
            out.append(
                f'<article><h2>{_t(section.get("title"))}</h2>'
                f'<p class="section-text">{_t(section.get("text"))}</p>'
            )
            out.append(_render_checkpoint(section.get("checkpoint") or {}, f"ext-{i}", lang))
            out.append("</article>")
        for key in ("basic", "standard", "challenge"):
            item = levels.get(key) or {}
            if item.get("enabled", True) and item.get("prompt"):
                out.append(
                    f'<div class="card"><strong>{_t(key.title())}</strong>'
                    f'<p>{_t(item.get("prompt"))}</p>'
                    f'{_answer_block(item.get("answer"), "", f"level-{key}", lang)}</div>'
                )
        exam = structured.get("exam_connection") or {}
        if exam.get("enabled"):
            subjects = " / ".join(str(x) for x in exam.get("subjects", []))
            out.append(
                f'<div class="card"><strong>Exam connection</strong>'
                f'<p>{_t(subjects)}</p><p>{_t(exam.get("note"))}</p></div>'
            )
        out.append("</details>")

    rescue = structured.get("rescue") or {}
    if any(rescue.get(key) for key in ("hint_1", "hint_2", "summary")):
        rescue_label = "I'M STUCK" if str(lang).lower().startswith("en") else "我卡住了"
        out.append(f'<details class="rescue"><summary>{_t(rescue_label)}</summary>')
        for key in ("hint_1", "hint_2", "summary"):
            if rescue.get(key):
                out.append(f"<p>{_t(rescue.get(key))}</p>")
        out.append("</details>")

    if language_support.get("enabled") and language_support.get("zh_rescue_summary"):
        out.append(
            '<details class="zh-rescue"><summary>中文救援｜真的卡住再看</summary>'
            f'<p>{_t(language_support.get("zh_rescue_summary"))}</p></details>'
        )

    if structured.get("one_thing_prompt"):
        one_label = "One Thing" if str(lang).lower().startswith("en") else "今天只記一件事"
        out.append(
            f'<div class="card"><strong>{one_label}</strong>'
            f'<p>{_t(structured.get("one_thing_prompt"))}</p></div>'
        )
    return "".join(out)


def _render_review(structured: dict) -> str:
    out = ["<section><h2>本週 3–5 件事</h2>"]
    cards = structured.get("week_cards") or []
    for card in cards[:5]:
        out.append(
            f'<div class="week-card"><strong>{_t(card.get("day"))} · {_t(card.get("title"))}</strong>'
            f'<p>{_t(card.get("memory"))}</p><p><small>{_t(card.get("concept"))}</small></p></div>'
        )
    if not cards:
        for section in (structured.get("sections") or [])[:5]:
            out.append(
                f'<div class="week-card"><strong>{_t(section.get("title"))}</strong>'
                f'<p>{_t(section.get("text"))}</p></div>'
            )
    out.append("</section>")

    recall = structured.get("recall") or {}
    events = recall.get("events") or []
    if events:
        out.append("<section><h2>Recall</h2><ul>")
        out.extend(f"<li>{_t(item)}</li>" for item in events[:5])
        out.append("</ul></section>")

    words = recall.get("english_words") or []
    if words:
        out.append("<section><h2>English Recall</h2>")
        for i, word in enumerate(words[:2], 1):
            out.append(
                f'<div class="checkpoint"><strong>{_t(word.get("word"))}</strong>'
                f'<p>{_t(word.get("prompt"))}</p>'
                f'{_answer_block(word.get("answer"), "", f"review-word-{i}", "en")}</div>'
            )
        out.append("</section>")

    connections = structured.get("connections") or []
    if connections:
        out.append("<section><h2>跨新聞連結</h2>")
        for i, item in enumerate(connections[:2], 1):
            out.append(
                f'<div class="checkpoint"><strong>{_t(item.get("title"))}</strong>'
                f'<p>{_t(item.get("question"))}</p>'
                f'{_answer_block(item.get("answer"), "", f"conn-{i}", "zh")}</div>'
            )
        out.append("</section>")

    evidence = structured.get("evidence_check") or {}
    if evidence.get("prompt"):
        choices = "".join(f"<li>{_t(x)}</li>" for x in evidence.get("choices", []))
        out.append(
            f'<div class="checkpoint"><h2>Evidence Check</h2>'
            f'<p>{_t(evidence.get("prompt"))}</p><ol>{choices}</ol>'
            f'{_answer_block(evidence.get("answer"), "", "review-evidence", "zh")}</div>'
        )

    prompt = structured.get("one_week_prompt") or structured.get("one_thing_prompt")
    if prompt:
        out.append(
            f'<div class="card"><strong>這週我最好奇什麼</strong><p>{_t(prompt)}</p></div>'
        )
    return "".join(out)


def _render_sources(
    structured: dict,
    source_records: list[dict] | None,
    related_issue_links: list[dict] | None,
) -> str:
    source_records = source_records or []
    by_id = {
        str(item.get("Source_ID") or item.get("source_id")): item
        for item in source_records
    }
    cards = []
    source_ids = list((structured.get("provenance") or {}).get("source_ids") or [])
    for source_id in source_ids:
        record = by_id.get(str(source_id), {})
        publisher = record.get("Publisher") or record.get("publisher") or source_id
        date = record.get("Source_Published_Date") or record.get("published") or ""
        title = record.get("Title") or record.get("title") or source_id
        url = _safe_link(record.get("URL") or record.get("url") or "")
        link = (
            f'<a href="{url}" target="_blank" rel="noopener noreferrer">{_t(title)}</a>'
            if url else _t(title)
        )
        missing = ' data-source-missing="true"' if not url else ""
        cards.append(
            f'<div class="source-card"{missing}><strong>{_t(publisher)}</strong> · '
            f'{_t(date)}<br>{link}</div>'
        )

    for item in (related_issue_links or []):
        url = _safe_link(item.get("url") or "")
        if url:
            cards.append(
                f'<div class="source-card"><strong>{_t(item.get("label") or "本週文章")}</strong>'
                f'<br><a href="{url}">{_t(item.get("title") or url)}</a></div>'
            )

    if not cards:
        return ""
    return (
        '<section aria-labelledby="sources-title"><h2 id="sources-title">Sources</h2>'
        + "".join(cards)
        + "</section>"
    )


def _correction_html(correction: dict | None) -> str:
    if not correction:
        return ""
    bits = []
    if correction.get("note"):
        bits.append(f"<p>{_t(correction.get('note'))}</p>")
    for label, key in (
        ("Previous version", "previous_version"),
        ("Correction reason", "reason"),
        ("Corrected at", "corrected_at"),
        ("Claim reference", "claim_reference"),
        ("Latest version", "latest_version_pointer"),
    ):
        if correction.get(key):
            bits.append(f"<div><strong>{label}:</strong> {_t(correction.get(key))}</div>")
    return (
        '<aside class="correction" role="note"><strong>Correction notice / 更正通知</strong>'
        + "".join(bits)
        + "</aside>"
    )


def render_public_issue(
    structured: dict,
    *,
    source_records: list[dict] | None = None,
    pdf_href: str = "",
    issue_row: dict | None = None,
    correction: dict | None = None,
    related_issue_links: list[dict] | None = None,
) -> str:
    if issue_row is not None:
        decision = public_candidate_gate(issue_row)
        if not decision.allowed:
            raise PublicRenderError(decision.reason)

    metadata = structured.get("metadata") or {}
    editorial = structured.get("editorial") or {}
    if not structured.get("issue_id") or not editorial.get("headline"):
        raise PublicRenderError("MISSING_REQUIRED_PUBLIC_FIELDS")

    categories = metadata.get("categories") or []
    if isinstance(categories, str):
        categories = [categories]
    version = metadata.get("version") or ""
    lifecycle = structured.get("lifecycle") or {}
    last_checked = lifecycle.get("last_rechecked_at") or ""
    lang = metadata.get("language") or "zh-TW"

    content_html = _render_review(structured) if _is_review(structured) else _render_daily(structured)
    sources_html = _render_sources(structured, source_records, related_issue_links)
    pdf = _safe_link(pdf_href, allow_relative=True)
    pdf_link = (
        f'<a class="download" href="{pdf}">PDF download / 下載 PDF</a>' if pdf else ""
    )
    meta_line = (
        f'<div class="meta"><span>{_t(metadata.get("publish_date"))}</span>'
        f'<span>{_t(lang)}</span>'
        f'<span>{_t(" / ".join(str(x) for x in categories))}</span>'
        f'<span>Version {_t(version)}</span>'
        f'<span>Last checked {_t(last_checked)}</span></div>'
    )
    quick_label = "Quick Start" if str(lang).lower().startswith("en") else "30 秒先懂"
    html_lang = "zh-Hant" if str(lang).lower().startswith("zh") or str(lang).upper() == "REVIEW" else "en"

    return f'''<!doctype html>
<html lang="{_t(html_lang)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_t(editorial.get("headline"))}</title>
<style>{CSS}</style>
</head>
<body>
<main>
<header>
{meta_line}
<h1>{_t(editorial.get("headline"))}</h1>
<div class="hook">{_t(editorial.get("hook"))}</div>
<div class="quick"><strong>{_t(quick_label)}</strong><p>{_t(editorial.get("quick_summary"))}</p></div>
</header>
{_correction_html(correction)}
{content_html}
{sources_html}
<footer>
<div class="footer-actions">
{pdf_link}
<span>Version {_t(version)}</span>
<span>Last checked {_t(last_checked)}</span>
</div>
</footer>
</main>
<script>{JS}</script>
</body>
</html>'''


def write_public_issue(structured: dict, path: Path, **kwargs) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_public_issue(structured, **kwargs), encoding="utf-8")
    return path

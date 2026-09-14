from __future__ import annotations

import json
from pathlib import Path

from .email_payload import build_email_payload
from .pdf_renderer import render_pdf_issue
from .public_renderer import write_public_issue


def render_issue(
    structured: dict,
    out_dir: Path,
    *,
    source_records: list[dict] | None = None,
    issue_row: dict | None = None,
    correction: dict | None = None,
) -> tuple[Path, Path, Path, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    issue_id = structured.get("issue_id", "issue")

    pdf_path, pages = render_pdf_issue(
        structured,
        out_dir,
        source_records=source_records,
    )
    html_path = out_dir / f"{issue_id}.html"
    write_public_issue(
        structured,
        html_path,
        source_records=source_records,
        pdf_href=f"./{pdf_path.name}",
        issue_row=issue_row,
        correction=correction,
    )
    email_payload_path = out_dir / f"{issue_id}.email.json"
    email_payload_path.write_text(
        json.dumps(
            build_email_payload(structured, source_records),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return html_path, pdf_path, email_payload_path, pages

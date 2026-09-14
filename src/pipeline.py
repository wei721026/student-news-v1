from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path

from .contract_validator import ContractError, validate_v1
from .gates import publication_gate
from .openai_gateway import OpenAIGateway
from .publication_client import PublicationError, WebhookPublisher
from .renderer import render_issue
from .settings import Settings
from .sheets_gateway import SheetsGateway


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "issues"
OUT_DIR = ROOT / "out"


def _now(settings: Settings) -> datetime:
    return datetime.now(settings.tz)


def _iso(settings: Settings) -> str:
    return _now(settings).isoformat(timespec="seconds")


def _load_contract() -> str:
    path = ROOT / "issue_contract_v1_0.json"
    if not path.exists():
        raise RuntimeError("issue_contract_v1_0.json missing from repo root")
    return path.read_text(encoding="utf-8")


def _save_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_previous_six(sheet: SheetsGateway, before_date: str) -> list[dict]:
    issue_ids = sheet.previous_six_ready_issue_ids(before_date)
    selected = []
    for issue_id in issue_ids:
        path = DATA_DIR / f"{issue_id}.json"
        if not path.exists():
            raise RuntimeError(f"Sunday mother data missing: {path}")
        obj = json.loads(path.read_text(encoding="utf-8"))
        validate_v1(obj, allow_review_adapter=False)
        selected.append(obj)
    return selected


def _correction_from_issue(issue: dict) -> dict | None:
    reason = issue.get("Correction_Reason")
    previous = issue.get("Previous_Version")
    corrected_at = issue.get("Corrected_At")
    claim_ref = issue.get("Correction_Claim_Ref")
    latest = issue.get("Version")
    if not any((reason, previous, corrected_at, claim_ref)):
        return None
    return {
        "note": issue.get("Correction_Notice") or reason or "",
        "previous_version": previous or "",
        "reason": reason or "",
        "corrected_at": corrected_at or "",
        "claim_reference": claim_ref or "",
        "latest_version_pointer": latest or "",
    }


def _set_structured_qa_pass(structured: dict, settings: Settings):
    reviewed_at = _iso(settings)
    structured.setdefault("qa", {})
    structured["qa"]["fact"] = {
        "status": "PASS",
        "method": "FACT_RESEARCH",
        "reviewed_at": reviewed_at,
        "notes": (structured.get("qa", {}).get("fact") or {}).get("notes", ""),
    }
    structured["qa"]["teaching"] = {
        "status": "PASS",
        "method": "DESK_REVIEW",
        "reviewed_at": reviewed_at,
        "notes": (structured.get("qa", {}).get("teaching") or {}).get("notes", ""),
    }
    structured["qa"]["layout"] = {
        "status": "PASS",
        "method": "RENDER_REVIEW",
        "reviewed_at": reviewed_at,
        "notes": (structured.get("qa", {}).get("layout") or {}).get("notes", ""),
    }


def _publish_if_allowed(
    settings: Settings,
    sheet: SheetsGateway,
    row: int,
    issue: dict,
    structured: dict,
    html_path: Path,
    pdf_path: Path,
    email_payload_path: Path,
    log,
):
    mode = settings.publish_mode.upper()

    if mode == "DRY_RUN":
        sheet.update_issue(row, {"Status": "READY", "Next_Action": "MANUAL_REVIEW"})
        log("PUBLICATION", "WAIT", message="DRY_RUN")
        return

    if mode == "AUTO" and not settings.auto_publish_allowed:
        sheet.update_issue(row, {"Status": "READY", "Next_Action": "AUTO_PUBLISH_DISABLED"})
        log("PUBLICATION", "WAIT", message="AUTO_PUBLISH_ALLOWED=NO")
        return

    decision = publication_gate(
        issue,
        webhook_url=settings.publication_webhook,
        webhook_secret=settings.publication_webhook_secret,
    )
    if not decision.allowed:
        next_action = {
            "APPROVAL_REQUIRED": "WAIT_APPROVAL",
            "PUBLICATION_WEBHOOK_REQUIRED": "WAIT_PUBLICATION_WEBHOOK",
            "PUBLICATION_WEBHOOK_SECRET_REQUIRED": "WAIT_PUBLICATION_WEBHOOK_SECRET",
        }.get(decision.reason, "WAIT_PUBLICATION_GATE")
        sheet.update_issue(row, {"Status": "READY", "Next_Action": next_action})
        log("PUBLICATION", "WAIT", message=decision.reason)
        return

    if "data-source-missing=\"true\"" in html_path.read_text(encoding="utf-8"):
        sheet.update_issue(
            row,
            {
                "Status": "READY",
                "Next_Action": "FIX_SOURCE_LINKS",
                "Last_Error": "Public HTML contains source records without a direct URL",
            },
        )
        log("PUBLICATION", "BLOCK", message="SOURCE_LINK_MISSING")
        return

    publisher = WebhookPublisher(
        settings.publication_webhook,
        settings.publication_webhook_secret,
    )
    started = time.time()
    try:
        result = publisher.publish(
            issue_id=structured["issue_id"],
            version=str((structured.get("metadata") or {}).get("version") or issue.get("Version") or "1.0"),
            html_path=html_path,
            pdf_path=pdf_path,
            email_payload_path=email_payload_path,
            correction=_correction_from_issue(issue),
        )
    except Exception as exc:
        sheet.update_issue(
            row,
            {
                "Status": "READY",
                "Next_Action": "RETRY_PUBLISH",
                "Last_Error": f"Publication failed: {exc}",
            },
        )
        log("PUBLICATION", "ERROR", started=started, message=str(exc))
        return

    structured.setdefault("render", {})
    structured["render"].update(
        {
            "pdf_ready": True,
            "html_public": True,
            "audio_enabled": False,
            "pdf_file": result["pdf_url"],
            "html_file": result["html_url"],
        }
    )
    _save_json(DATA_DIR / f"{structured['issue_id']}.json", structured)

    sheet.update_issue(
        row,
        {
            "Status": "PUBLISHED",
            "Published_At": _iso(settings),
            "HTML_URL": result["html_url"],
            "PDF_URL": result["pdf_url"],
            "Next_Action": "EMAIL_DELIVERY",
            "Last_Error": "",
            "Email_Status": "PENDING",
            "Email_Attachment": result["pdf_url"],
            "Email_Error": "",
        },
    )
    log(
        "PUBLICATION",
        "PASS",
        started=started,
        message=result.get("email_payload_url", ""),
        artifact=result["html_url"],
    )


def _render_until_layout_pass(
    *,
    settings: Settings,
    sheet: SheetsGateway,
    row: int,
    issue_id: str,
    structured: dict,
    source_records: list[dict],
    llm: OpenAIGateway,
    log,
) -> tuple[dict, Path, Path, Path]:
    for revision in range(settings.max_layout_revisions + 1):
        validate_v1(structured)
        _save_json(DATA_DIR / f"{issue_id}.json", structured)
        started = time.time()
        html_path, pdf_path, email_payload_path, pages = render_issue(
            structured,
            OUT_DIR / issue_id,
            source_records=source_records,
        )
        if pages <= 2:
            log(
                "LAYOUT_QA",
                "PASS",
                started=started,
                message=f"{pages} pages",
                artifact=str(pdf_path),
            )
            return structured, html_path, pdf_path, email_payload_path

        log("LAYOUT_QA", "REVISE", started=started, message=f"{pages} pages")
        if revision >= settings.max_layout_revisions:
            sheet.update_issue(
                row,
                {
                    "Status": "BLOCKED_LAYOUT",
                    "Layout_QA": "BLOCK",
                    "Blocked_Reason": f"Still {pages} pages after layout revision limit",
                    "Next_Action": "HUMAN_LAYOUT_REVIEW",
                },
            )
            raise RuntimeError("BLOCKED_LAYOUT_ALREADY_RECORDED")
        structured, _ = llm.condense_for_print(structured)
    raise AssertionError("unreachable")


def _run_sunday(
    settings: Settings,
    sheet: SheetsGateway,
    llm: OpenAIGateway,
    row: int,
    issue: dict,
    issue_id: str,
    date_str: str,
    log,
):
    previous = _load_previous_six(sheet, date_str)
    started = time.time()
    structured, response_id = llm.sunday_review(previous, _load_contract())
    structured["issue_id"] = issue_id
    structured.setdefault("metadata", {})["language"] = "REVIEW"
    validate_v1(structured)
    log("SUNDAY_DRAFT", "PASS", started=started, response_id=response_id)

    for revision in range(settings.max_teaching_revisions + 1):
        started = time.time()
        qa, qa_id = llm.sunday_teaching_qa(structured, previous)
        log("TEACHING_QA", qa["status"], started=started, response_id=qa_id, message=qa.get("notes", ""))
        if qa["status"] == "PASS":
            break
        if qa["status"] == "BLOCK" or revision >= settings.max_teaching_revisions:
            sheet.update_issue(
                row,
                {
                    "Status": "BLOCKED_PEDAGOGY",
                    "Fact_QA": "PASS",
                    "Teaching_QA": "BLOCK",
                    "Blocked_Reason": qa.get("notes") or "Sunday Teaching QA exceeded revision limit",
                    "Next_Action": "HUMAN_REVIEW",
                },
            )
            return
        structured, _ = llm.revise_sunday(
            structured,
            qa.get("revision_instructions", []),
            previous,
        )
        validate_v1(structured)

    sheet.update_issue(
        row,
        {
            "Fact_QA": "PASS",
            "Teaching_QA": "PASS",
            "Status": "RENDERING",
            "Next_Action": "RENDER",
        },
    )

    try:
        structured, html_path, pdf_path, email_payload_path = _render_until_layout_pass(
            settings=settings,
            sheet=sheet,
            row=row,
            issue_id=issue_id,
            structured=structured,
            source_records=[],
            llm=llm,
            log=log,
        )
    except RuntimeError as exc:
        if str(exc) == "BLOCKED_LAYOUT_ALREADY_RECORDED":
            return
        raise

    _set_structured_qa_pass(structured, settings)
    structured.setdefault("render", {}).update(
        {
            "pdf_ready": True,
            "html_public": False,
            "audio_enabled": False,
            "pdf_file": pdf_path.name,
            "html_file": html_path.name,
        }
    )
    _save_json(DATA_DIR / f"{issue_id}.json", structured)

    sheet.update_issue(
        row,
        {
            "Headline": (structured.get("editorial") or {}).get("headline", "Weekly Review"),
            "Fact_QA": "PASS",
            "Teaching_QA": "PASS",
            "Layout_QA": "PASS",
            "Status": "READY",
            "Data_Path": f"data/issues/{issue_id}.json",
            "Next_Action": "WAIT_APPROVAL",
            "Git_Commit": os.getenv("GITHUB_SHA", ""),
        },
    )
    _, refreshed = sheet.find_issue(issue_id)
    _publish_if_allowed(
        settings,
        sheet,
        row,
        refreshed,
        structured,
        html_path,
        pdf_path,
        email_payload_path,
        log,
    )


def _run_daily(
    settings: Settings,
    sheet: SheetsGateway,
    llm: OpenAIGateway,
    row: int,
    issue: dict,
    issue_id: str,
    date_str: str,
    log,
):
    language = issue.get("Language") or "ZH"
    content_language = "zh-TW" if str(language).upper() == "ZH" else "en"
    recent = sheet.recent_context()

    started = time.time()
    sheet.update_issue(row, {"Status": "DISCOVERY", "Next_Action": "DISCOVERY"})
    discovery, discovery_id = llm.discover(
        language=language,
        weekday=issue.get("Day", ""),
        recent_context=recent,
    )
    log("DISCOVERY", "PASS", started=started, response_id=discovery_id)

    candidates = discovery.get("candidates", [])[: settings.max_candidates]
    verified = None
    selected = None

    for candidate in candidates:
        started = time.time()
        sheet.update_issue(row, {"Status": "VERIFYING", "Next_Action": "FACT_QA"})
        fact_pack, verify_id = llm.verify_candidate(candidate)
        critical_bad = [
            claim
            for claim in fact_pack.get("claims", [])
            if claim.get("critical")
            and claim.get("verified_status") not in ("VERIFIED", "VERIFIED_WITH_ATTRIBUTION")
        ]
        if fact_pack.get("fact_qa", {}).get("status") == "PASS" and not critical_bad:
            verified = fact_pack
            selected = candidate
            log("FACT_QA", "PASS", started=started, response_id=verify_id)
            break
        log(
            "FACT_QA",
            "REJECT_CANDIDATE",
            started=started,
            response_id=verify_id,
            message=fact_pack.get("fact_qa", {}).get("notes", ""),
        )

    if not verified:
        sheet.update_issue(
            row,
            {
                "Status": "BLOCKED_SOURCE",
                "Fact_QA": "BLOCK",
                "Blocked_Reason": "No candidate passed Fact QA",
                "Next_Action": "HUMAN_REVIEW",
            },
        )
        log("FACT_QA", "BLOCK", message="No candidate passed Fact QA")
        return

    sheet.append_source_rows(issue_id, verified.get("sources", []))
    sheet.append_claim_rows(issue_id, verified.get("claims", []), date_str)
    sheet.update_issue(
        row,
        {
            "Headline": selected.get("title", ""),
            "Category": selected.get("category", ""),
            "Region": selected.get("region", ""),
            "Fact_QA": "PASS",
            "Status": "VERIFIED",
            "Next_Action": "DRAFTING",
        },
    )
    _save_json(DATA_DIR / f"{issue_id}_fact_pack.json", verified)

    started = time.time()
    structured, draft_id = llm.draft_structured_content(
        issue_id=issue_id,
        language=content_language,
        fact_pack=verified,
        contract_text=_load_contract(),
    )
    structured["issue_id"] = issue_id
    try:
        validate_v1(structured)
    except ContractError as exc:
        sheet.update_issue(
            row,
            {
                "Status": "BLOCKED_CONTRACT",
                "Teaching_QA": "BLOCK",
                "Blocked_Reason": str(exc),
                "Next_Action": "HUMAN_ENGINEERING_REVIEW",
            },
        )
        log("CONTRACT", "BLOCK", started=started, response_id=draft_id, message=str(exc))
        return
    log("DRAFT", "PASS", started=started, response_id=draft_id)

    for revision in range(settings.max_teaching_revisions + 1):
        started = time.time()
        qa, qa_id = llm.teaching_qa(structured, verified)
        log("TEACHING_QA", qa["status"], started=started, response_id=qa_id, message=qa.get("notes", ""))
        if qa["status"] == "PASS":
            break
        if qa["status"] == "BLOCK" or revision >= settings.max_teaching_revisions:
            sheet.update_issue(
                row,
                {
                    "Status": "BLOCKED_PEDAGOGY",
                    "Teaching_QA": "BLOCK",
                    "Blocked_Reason": qa.get("notes") or "Teaching QA exceeded auto revision limit",
                    "Next_Action": "HUMAN_REVIEW",
                },
            )
            return
        structured, _ = llm.revise_content(structured, qa.get("revision_instructions", []))
        validate_v1(structured)

    sheet.update_issue(
        row,
        {
            "Teaching_QA": "PASS",
            "Status": "RENDERING",
            "Next_Action": "RENDER",
        },
    )

    source_records = sheet.source_records_for_issue(issue_id)
    try:
        structured, html_path, pdf_path, email_payload_path = _render_until_layout_pass(
            settings=settings,
            sheet=sheet,
            row=row,
            issue_id=issue_id,
            structured=structured,
            source_records=source_records,
            llm=llm,
            log=log,
        )
    except RuntimeError as exc:
        if str(exc) == "BLOCKED_LAYOUT_ALREADY_RECORDED":
            return
        raise

    _set_structured_qa_pass(structured, settings)
    structured.setdefault("render", {}).update(
        {
            "pdf_ready": True,
            "html_public": False,
            "audio_enabled": False,
            "pdf_file": pdf_path.name,
            "html_file": html_path.name,
        }
    )
    _save_json(DATA_DIR / f"{issue_id}.json", structured)

    sheet.update_issue(
        row,
        {
            "Layout_QA": "PASS",
            "Status": "READY",
            "Data_Path": f"data/issues/{issue_id}.json",
            "Next_Action": "WAIT_APPROVAL",
            "Version": (structured.get("metadata") or {}).get("version") or "1.0",
            "Git_Commit": os.getenv("GITHUB_SHA", ""),
        },
    )

    _, refreshed = sheet.find_issue(issue_id)
    _publish_if_allowed(
        settings,
        sheet,
        row,
        refreshed,
        structured,
        html_path,
        pdf_path,
        email_payload_path,
        log,
    )


def run(settings: Settings):
    run_id = f"run-{uuid.uuid4().hex[:12]}"
    sheet = SheetsGateway()
    llm = OpenAIGateway(settings)
    today = _now(settings)
    date_str = today.date().isoformat()

    row, issue = sheet.ensure_today_issue(date_str, today.weekday())
    issue_id = issue["Issue_ID"]
    sheet.update_issue(
        row,
        {
            "Automation_Run_ID": run_id,
            "Attempt_Count": int(issue.get("Attempt_Count") or 0) + 1,
            "Last_Error": "",
        },
    )

    def log(
        stage,
        status,
        started=None,
        response_id="",
        message="",
        artifact="",
    ):
        duration = time.time() - started if started is not None else 0
        sheet.log(
            timestamp=_iso(settings),
            run_id=run_id,
            issue_id=issue_id,
            stage=stage,
            status=status,
            duration=duration,
            response_id=response_id,
            message=message,
            artifact_path=artifact,
        )

    # Finished and blocked jobs are stable until a person explicitly changes state.
    if str(issue.get("Status") or "").upper() == "PUBLISHED":
        log("CONTROLLER", "SKIP", message="Already PUBLISHED")
        return
    if str(issue.get("Status") or "").upper().startswith("BLOCKED"):
        log("CONTROLLER", "SKIP", message="BLOCKED requires explicit retry")
        return

    # READY never repeats research; it only evaluates the publication gate.
    if str(issue.get("Status") or "").upper() == "READY":
        structured_path = DATA_DIR / f"{issue_id}.json"
        html_path = OUT_DIR / issue_id / f"{issue_id}.html"
        pdf_path = OUT_DIR / issue_id / f"{issue_id}.pdf"
        email_payload_path = OUT_DIR / issue_id / f"{issue_id}.email.json"
        if not all(path.exists() for path in (structured_path, html_path, pdf_path, email_payload_path)):
            missing = [
                str(path)
                for path in (structured_path, html_path, pdf_path, email_payload_path)
                if not path.exists()
            ]
            sheet.update_issue(
                row,
                {
                    "Last_Error": "READY artifacts missing: " + "; ".join(missing),
                    "Next_Action": "RESTORE_READY_ARTIFACTS",
                },
            )
            log("CONTROLLER", "ERROR", message="READY artifacts missing")
            return
        structured = json.loads(structured_path.read_text(encoding="utf-8"))
        _publish_if_allowed(
            settings,
            sheet,
            row,
            issue,
            structured,
            html_path,
            pdf_path,
            email_payload_path,
            log,
        )
        return

    try:
        if today.weekday() == 6 or str(issue.get("Language") or "").upper() == "REVIEW":
            _run_sunday(settings, sheet, llm, row, issue, issue_id, date_str, log)
        else:
            _run_daily(settings, sheet, llm, row, issue, issue_id, date_str, log)
    except Exception as exc:
        # Never turn a runtime failure into a published article.
        # BLOCKED_* states already written by the specific gate are preserved.
        _, current = sheet.find_issue(issue_id)
        current_status = str((current or {}).get("Status") or "")
        if not current_status.startswith("BLOCKED"):
            sheet.update_issue(
                row,
                {
                    "Last_Error": str(exc),
                    "Next_Action": "RETRY_RUNTIME",
                },
            )
        log("PIPELINE", "ERROR", message=str(exc))
        raise

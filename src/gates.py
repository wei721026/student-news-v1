from __future__ import annotations

from dataclasses import dataclass

PASS = "PASS"
PUBLIC_CANDIDATE_STATUSES = {"READY", "APPROVED", "PUBLISHED"}

@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    reason: str

def _upper(value) -> str:
    return str(value or "").strip().upper()

def qa_triplet_pass(issue: dict) -> bool:
    return all(_upper(issue.get(k)) == PASS for k in ("Fact_QA", "Teaching_QA", "Layout_QA"))

def public_candidate_gate(issue: dict) -> GateDecision:
    status = _upper(issue.get("Status"))
    if status.startswith("BLOCKED"):
        return GateDecision(False, "BLOCKED_STATUS")
    if status not in PUBLIC_CANDIDATE_STATUSES:
        return GateDecision(False, "STATUS_NOT_PUBLIC_CANDIDATE")
    if not qa_triplet_pass(issue):
        return GateDecision(False, "QA_NOT_ALL_PASS")
    return GateDecision(True, "PASS")

def publication_gate(issue: dict, *, webhook_url: str, webhook_secret: str = "") -> GateDecision:
    status = _upper(issue.get("Status"))
    if status.startswith("BLOCKED"):
        return GateDecision(False, "BLOCKED_STATUS")
    if status != "READY":
        return GateDecision(False, "STATUS_NOT_READY")
    if not qa_triplet_pass(issue):
        return GateDecision(False, "QA_NOT_ALL_PASS")
    if _upper(issue.get("Approval")) != "YES":
        return GateDecision(False, "APPROVAL_REQUIRED")
    if not (webhook_url or "").strip():
        return GateDecision(False, "PUBLICATION_WEBHOOK_REQUIRED")
    if not (webhook_secret or "").strip():
        return GateDecision(False, "PUBLICATION_WEBHOOK_SECRET_REQUIRED")
    return GateDecision(True, "PASS")

def email_gate(issue: dict) -> GateDecision:
    if _upper(issue.get("Status")) != "PUBLISHED":
        return GateDecision(False, "NOT_PUBLISHED")
    if not str(issue.get("HTML_URL") or "").startswith(("http://", "https://")):
        return GateDecision(False, "HTML_URL_MISSING")
    if not str(issue.get("PDF_URL") or "").startswith(("http://", "https://")):
        return GateDecision(False, "PDF_URL_MISSING")
    return GateDecision(True, "PASS")

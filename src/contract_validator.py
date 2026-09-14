from __future__ import annotations

ALLOWED_LANG = {"zh-TW", "en", "REVIEW"}
ALLOWED_ROLES = {"CORE", "EXTENSION"}
ALLOWED_QA = {"PENDING", "PASS", "REVISE", "BLOCK"}

class ContractError(ValueError):
    pass

def validate_v1(structured: dict, *, allow_review_adapter: bool = True) -> None:
    if not isinstance(structured, dict):
        raise ContractError("Structured Content must be an object")
    required = ["issue_id", "metadata", "editorial", "qa"]
    missing = [k for k in required if k not in structured]
    if missing:
        raise ContractError(f"Missing required keys: {missing}")

    meta = structured.get("metadata") or {}
    lang = meta.get("language")
    if lang not in ALLOWED_LANG:
        raise ContractError(f"Unsupported metadata.language: {lang}")

    editorial = structured.get("editorial") or {}
    for k in ("headline", "hook", "quick_summary"):
        if not isinstance(editorial.get(k), str) or not editorial.get(k).strip():
            raise ContractError(f"editorial.{k} missing")

    # The frozen One-Week Trial contains a REVIEW adapter shape. Supporting it
    # here is a renderer/worker adapter, not a Data Contract change.
    if lang == "REVIEW" and allow_review_adapter and "week_cards" in structured:
        pass
    else:
        sections = structured.get("sections")
        if not isinstance(sections, list) or not sections:
            raise ContractError("sections must be a non-empty list")
        if not any(s.get("role") == "CORE" for s in sections):
            raise ContractError("At least one CORE section is required")
        for s in sections:
            if s.get("role") not in ALLOWED_ROLES:
                raise ContractError(f"Invalid section role: {s.get('role')}")

    qa = structured.get("qa") or {}
    for key in ("fact", "teaching", "layout"):
        status = str((qa.get(key) or {}).get("status") or "PENDING").upper()
        if status not in ALLOWED_QA:
            raise ContractError(f"Invalid qa.{key}.status: {status}")

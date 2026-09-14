from __future__ import annotations

import os

from .pipeline import run
from .settings import Settings
from .sheets_gateway import SheetsGateway


def build_settings() -> Settings:
    # Sheet values are authoritative when available.
    sheet = SheetsGateway()
    raw = sheet.automation_settings()

    return Settings(
        timezone=raw.get("TIMEZONE", "Asia/Taipei"),
        publish_mode=raw.get("PUBLISH_MODE", "APPROVAL"),
        max_candidates=int(raw.get("MAX_CANDIDATES", 3)),
        max_teaching_revisions=int(raw.get("MAX_TEACHING_REVISIONS", 2)),
        max_layout_revisions=int(raw.get("MAX_LAYOUT_REVISIONS", 2)),
        discovery_model=raw.get("DISCOVERY_MODEL", "gpt-5.6-luna"),
        verify_model=raw.get("VERIFY_MODEL", "gpt-5.6-terra"),
        draft_model=raw.get("DRAFT_MODEL", "gpt-5.6-terra"),
        qa_model=raw.get("QA_MODEL", "gpt-5.6-terra"),
        publication_webhook=os.getenv("PUBLICATION_WEBHOOK_URL", "") or raw.get("PUBLICATION_WEBHOOK",""),
        publication_webhook_secret=os.getenv("PUBLICATION_WEBHOOK_SECRET", ""),
        auto_publish_allowed=str(raw.get("AUTO_PUBLISH_ALLOWED","NO")).upper() == "YES",
    )


if __name__ == "__main__":
    run(build_settings())

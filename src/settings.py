from __future__ import annotations

import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo


@dataclass
class Settings:
    timezone: str = "Asia/Taipei"
    publish_mode: str = "APPROVAL"
    max_candidates: int = 3
    max_teaching_revisions: int = 2
    max_layout_revisions: int = 2
    discovery_model: str = "gpt-5.6-luna"
    verify_model: str = "gpt-5.6-terra"
    draft_model: str = "gpt-5.6-terra"
    qa_model: str = "gpt-5.6-terra"
    publication_webhook: str = ""
    publication_webhook_secret: str = ""
    auto_publish_allowed: bool = False

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value



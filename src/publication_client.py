from __future__ import annotations

import json
from pathlib import Path

import requests


class PublicationError(RuntimeError):
    pass


class WebhookPublisher:
    def __init__(self, url: str, secret: str):
        self.url = (url or "").strip()
        self.secret = (secret or "").strip()

    def publish(
        self,
        *,
        issue_id: str,
        version: str,
        html_path: Path,
        pdf_path: Path,
        email_payload_path: Path,
        correction: dict | None = None,
    ) -> dict:
        if not self.url or not self.secret:
            raise PublicationError("Publication webhook URL/secret missing")

        metadata = {
            "issue_id": issue_id,
            "version": version,
            "correction": correction or {},
        }

        with (
            html_path.open("rb") as html_file,
            pdf_path.open("rb") as pdf_file,
            email_payload_path.open("rb") as email_file,
        ):
            response = requests.post(
                self.url,
                headers={"X-Webhook-Secret": self.secret},
                data={"metadata": json.dumps(metadata, ensure_ascii=False)},
                files={
                    "html": (html_path.name, html_file, "text/html; charset=utf-8"),
                    "pdf": (pdf_path.name, pdf_file, "application/pdf"),
                    "email_payload": (
                        email_payload_path.name,
                        email_file,
                        "application/json",
                    ),
                },
                timeout=90,
            )

        response.raise_for_status()
        try:
            result = response.json()
        except Exception as exc:
            raise PublicationError("Publication webhook did not return JSON") from exc

        for key in ("html_url", "pdf_url", "email_payload_url"):
            value = str(result.get(key) or "")
            if not value.startswith(("http://", "https://")):
                raise PublicationError(f"Publication webhook missing valid {key}")
        return result

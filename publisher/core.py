from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_segment(value: str) -> str:
    cleaned = _SAFE.sub("-", str(value or "").strip()).strip("-")
    if not cleaned:
        raise ValueError("empty path segment")
    return cleaned[:180]


@dataclass(frozen=True)
class PublishedPaths:
    html: str
    pdf: str
    email_payload: str
    version_manifest: str


class LocalStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def put(self, key: str, data: bytes, content_type: str):
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


class GCSStore:
    def __init__(self, bucket_name: str):
        from google.cloud import storage
        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket_name)

    def put(self, key: str, data: bytes, content_type: str):
        blob = self.bucket.blob(key)
        blob.upload_from_string(data, content_type=content_type, checksum="auto")
        blob.cache_control = "no-cache" if key.endswith(("index.html", "version.json", "email.json")) else "public, max-age=3600"
        blob.patch()


def publish_bytes(
    store,
    *,
    issue_id: str,
    version: str,
    html_bytes: bytes,
    pdf_bytes: bytes,
    email_payload_bytes: bytes,
    correction: dict | None = None,
) -> PublishedPaths:
    issue = safe_segment(issue_id)
    ver = safe_segment(version)
    base = f"issues/{issue}"
    version_base = f"{base}/versions/{ver}"

    # Immutable versioned artifacts.
    store.put(f"{version_base}/index.html", html_bytes, "text/html; charset=utf-8")
    store.put(f"{version_base}/lesson.pdf", pdf_bytes, "application/pdf")
    store.put(f"{version_base}/email.json", email_payload_bytes, "application/json; charset=utf-8")

    # Latest pointers are real copied artifacts so browsers always open the newest version.
    store.put(f"{base}/index.html", html_bytes, "text/html; charset=utf-8")
    store.put(f"{base}/lesson.pdf", pdf_bytes, "application/pdf")
    store.put(f"{base}/email.json", email_payload_bytes, "application/json; charset=utf-8")

    manifest = {
        "issue_id": issue_id,
        "latest_version": version,
        "latest": {
            "html": f"{base}/index.html",
            "pdf": f"{base}/lesson.pdf",
            "email_payload": f"{base}/email.json",
        },
        "versioned": {
            "html": f"{version_base}/index.html",
            "pdf": f"{version_base}/lesson.pdf",
            "email_payload": f"{version_base}/email.json",
        },
        "correction": correction or {},
    }
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    store.put(f"{version_base}/version.json", manifest_bytes, "application/json; charset=utf-8")
    store.put(f"{base}/version.json", manifest_bytes, "application/json; charset=utf-8")

    return PublishedPaths(
        html=f"{base}/index.html",
        pdf=f"{base}/lesson.pdf",
        email_payload=f"{base}/email.json",
        version_manifest=f"{base}/version.json",
    )

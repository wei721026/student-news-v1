from __future__ import annotations

import hmac
import json
import os
from urllib.parse import quote

from flask import Flask, jsonify, request

from .core import GCSStore, LocalStore, publish_bytes


app = Flask(__name__)


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


def _public_url(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + "/" + "/".join(quote(part) for part in path.split("/"))


def _store():
    mode = os.getenv("PUBLICATION_STORAGE", "GCS").strip().upper()
    if mode == "LOCAL":
        from pathlib import Path
        return LocalStore(Path(os.getenv("LOCAL_PUBLIC_ROOT", "./public")))
    return GCSStore(_required("PUBLISHER_BUCKET"))


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.post("/publish")
def publish():
    expected = _required("WEBHOOK_SECRET")
    actual = request.headers.get("X-Webhook-Secret", "")
    if not hmac.compare_digest(expected, actual):
        return jsonify({"error": "unauthorized"}), 401

    try:
        metadata = json.loads(request.form.get("metadata", "{}"))
        issue_id = metadata["issue_id"]
        version = metadata["version"]

        html_file = request.files["html"]
        pdf_file = request.files["pdf"]
        email_file = request.files["email_payload"]

        html_bytes = html_file.read()
        pdf_bytes = pdf_file.read()
        email_bytes = email_file.read()

        if not html_bytes.startswith(b"<!doctype html>") and b"<html" not in html_bytes[:500].lower():
            raise ValueError("html file is not HTML")
        if not pdf_bytes.startswith(b"%PDF"):
            raise ValueError("pdf file is not PDF")
        json.loads(email_bytes.decode("utf-8"))

        paths = publish_bytes(
            _store(),
            issue_id=issue_id,
            version=version,
            html_bytes=html_bytes,
            pdf_bytes=pdf_bytes,
            email_payload_bytes=email_bytes,
            correction=metadata.get("correction") or {},
        )

        base_url = _required("PUBLIC_BASE_URL")
        return jsonify(
            {
                "issue_id": issue_id,
                "version": version,
                "html_url": _public_url(base_url, paths.html),
                "pdf_url": _public_url(base_url, paths.pdf),
                "email_payload_url": _public_url(base_url, paths.email_payload),
                "version_manifest_url": _public_url(base_url, paths.version_manifest),
            }
        )
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        return jsonify({"error": str(exc)}), 400

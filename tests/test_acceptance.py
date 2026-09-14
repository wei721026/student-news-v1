from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"
sys.path.insert(0, str(ROOT))

from src.contract_validator import validate_v1
from src.email_payload import build_email_payload
from src.gates import publication_gate
from src.public_renderer import PublicRenderError, render_public_issue
from src.renderer import render_issue
from publisher.core import LocalStore, publish_bytes


def load_json(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


SOURCES = load_json("sources.json")


def sources_for(issue_id):
    return [row for row in SOURCES if row["Issue_ID"] == issue_id]


def issue_row(issue_id, language, *, status="READY", fact="PASS", teaching="PASS", layout="PASS", approval="PENDING"):
    return {
        "Issue_ID": issue_id,
        "Language": language,
        "Status": status,
        "Fact_QA": fact,
        "Teaching_QA": teaching,
        "Layout_QA": layout,
        "Approval": approval,
    }


class AcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.zh = load_json("W01D1_ZH_structured_content_v0_2_READY.json")
        cls.en = load_json("W01D2_EN_structured_content_v0_3_READY.json")
        cls.review = load_json("W01D7_REVIEW_structured_content_v0_3_READY.json")
        cls.correction = load_json("W01_CORRECTION_SAMPLE_01.json")

    def test_01_zh_ready_article(self):
        html = render_public_issue(
            self.zh,
            source_records=sources_for(self.zh["issue_id"]),
            pdf_href="./lesson.pdf",
            issue_row=issue_row(self.zh["issue_id"], "ZH"),
        )
        self.assertIn("30 秒先懂", html)
        self.assertIn('class="core-label">Core', html)
        self.assertIn('class="extension"', html)
        self.assertIn('class="rescue"', html)

    def test_02_en_ready_article(self):
        html = render_public_issue(
            self.en,
            source_records=sources_for(self.en["issue_id"]),
            pdf_href="./lesson.pdf",
            issue_row=issue_row(self.en["issue_id"], "EN"),
        )
        self.assertIn("Quick Start", html)
        self.assertIn("5 Words", html)
        self.assertIn("Focus Sentence", html)
        self.assertIn("I&#x27;M STUCK", html)
        self.assertIn('class="zh-rescue"', html)

    def test_03_sunday_review(self):
        validate_v1(self.review)
        html = render_public_issue(
            self.review,
            pdf_href="./lesson.pdf",
            issue_row=issue_row(self.review["issue_id"], "REVIEW"),
        )
        self.assertIn("本週 3–5 件事", html)
        self.assertIn("跨新聞連結", html)
        self.assertIn("這週我最好奇什麼", html)

    def test_04_blocked_not_public(self):
        with self.assertRaises(PublicRenderError):
            render_public_issue(
                self.zh,
                source_records=sources_for(self.zh["issue_id"]),
                pdf_href="./lesson.pdf",
                issue_row=issue_row(self.zh["issue_id"], "ZH", status="BLOCKED_SOURCE"),
            )

    def test_05_correction_notice(self):
        c = self.correction
        correction = {
            "note": c["simulated_v1_1"]["correction_note"],
            "previous_version": c["simulated_v1_0"]["version"],
            "reason": c["simulated_v1_0"]["problem"],
            "corrected_at": "2026-09-14T12:00:00+08:00",
            "claim_reference": c["source_of_truth"]["claim_id"],
            "latest_version_pointer": c["simulated_v1_1"]["latest_version_pointer"],
        }
        html = render_public_issue(
            self.zh,
            source_records=sources_for(self.zh["issue_id"]),
            pdf_href="./lesson.pdf",
            issue_row=issue_row(self.zh["issue_id"], "ZH"),
            correction=correction,
        )
        self.assertIn("Correction notice / 更正通知", html)
        self.assertIn("1.0-test", html)
        self.assertIn("1.1-test", html)
        self.assertIn("C002", html)

    def test_06_answers_hidden_by_default(self):
        html = render_public_issue(
            self.en,
            source_records=sources_for(self.en["issue_id"]),
            pdf_href="./lesson.pdf",
            issue_row=issue_row(self.en["issue_id"], "EN"),
        )
        self.assertIn('class="answer" hidden', html)
        self.assertIn('aria-expanded="false"', html)

    def test_07_rescue_collapsed_by_default(self):
        html = render_public_issue(
            self.en,
            source_records=sources_for(self.en["issue_id"]),
            pdf_href="./lesson.pdf",
            issue_row=issue_row(self.en["issue_id"], "EN"),
        )
        self.assertIn('<details class="rescue">', html)
        self.assertIn('<details class="zh-rescue">', html)
        self.assertNotIn('<details class="rescue" open', html)
        self.assertNotIn('<details class="zh-rescue" open', html)

    def test_08_source_links_clickable(self):
        html = render_public_issue(
            self.en,
            source_records=sources_for(self.en["issue_id"]),
            pdf_href="./lesson.pdf",
            issue_row=issue_row(self.en["issue_id"], "EN"),
        )
        self.assertIn("https://science.nasa.gov/", html)
        self.assertNotIn('data-source-missing="true"', html)

    def test_09_pdf_link_matches(self):
        html = render_public_issue(
            self.zh,
            source_records=sources_for(self.zh["issue_id"]),
            pdf_href="./matching.pdf",
            issue_row=issue_row(self.zh["issue_id"], "ZH"),
        )
        self.assertIn('href="./matching.pdf"', html)

    def test_10_fact_gate_blocks_publish(self):
        issue = issue_row("X", "ZH", fact="BLOCK", approval="YES")
        self.assertFalse(publication_gate(issue, webhook_url="https://example.test/publish", webhook_secret="s").allowed)

    def test_11_teaching_and_layout_gate_blocks_publish(self):
        for key in ("Teaching_QA", "Layout_QA"):
            issue = issue_row("X", "ZH", approval="YES")
            issue[key] = "BLOCK"
            self.assertFalse(publication_gate(issue, webhook_url="https://example.test/publish", webhook_secret="s").allowed)

    def test_12_approval_yes_required(self):
        issue = issue_row("X", "ZH", approval="PENDING")
        decision = publication_gate(issue, webhook_url="https://example.test/publish", webhook_secret="s")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "APPROVAL_REQUIRED")

    def test_13_webhook_required(self):
        issue = issue_row("X", "ZH", approval="YES")
        self.assertEqual(publication_gate(issue, webhook_url="", webhook_secret="s").reason, "PUBLICATION_WEBHOOK_REQUIRED")
        self.assertEqual(publication_gate(issue, webhook_url="https://example.test", webhook_secret="").reason, "PUBLICATION_WEBHOOK_SECRET_REQUIRED")

    def test_14_publish_gate_passes_only_complete_ready(self):
        issue = issue_row("X", "ZH", approval="YES")
        self.assertTrue(publication_gate(issue, webhook_url="https://example.test/publish", webhook_secret="s").allowed)

    def test_15_zh_email_payload(self):
        payload = build_email_payload(self.zh, sources_for(self.zh["issue_id"]))
        self.assertEqual(payload["kind"], "ZH")
        self.assertTrue(payload["quick_start"])
        self.assertTrue(payload["one_thing"])
        self.assertTrue(payload["mini_check"])
        self.assertTrue(payload["sources"])

    def test_16_en_email_payload(self):
        payload = build_email_payload(self.en, sources_for(self.en["issue_id"]))
        self.assertEqual(payload["kind"], "EN")
        self.assertEqual(len(payload["words"]), 5)
        self.assertTrue(payload["focus_sentence"])
        self.assertTrue(payload["mini_check"])

    def test_17_sunday_email_payload(self):
        payload = build_email_payload(self.review, [])
        self.assertEqual(payload["kind"], "REVIEW")
        self.assertGreaterEqual(len(payload["events"]), 3)
        self.assertEqual(len(payload["concepts"]), 3)
        self.assertGreaterEqual(len(payload["english_words"]), 1)
        self.assertTrue(payload["connection"])
        self.assertTrue(payload["curiosity_prompt"])

    def test_18_publication_keeps_previous_versions(self):
        html = render_public_issue(
            self.zh,
            source_records=sources_for(self.zh["issue_id"]),
            pdf_href="./lesson.pdf",
            issue_row=issue_row(self.zh["issue_id"], "ZH"),
        ).encode("utf-8")
        pdf = (FIX / "W01D1_ZH_print_READY.pdf").read_bytes()
        email = json.dumps(
            build_email_payload(self.zh, sources_for(self.zh["issue_id"])),
            ensure_ascii=False,
        ).encode("utf-8")
        with tempfile.TemporaryDirectory() as td:
            store = LocalStore(Path(td))
            publish_bytes(
                store,
                issue_id=self.zh["issue_id"],
                version="1.0-test",
                html_bytes=html,
                pdf_bytes=pdf,
                email_payload_bytes=email,
            )
            publish_bytes(
                store,
                issue_id=self.zh["issue_id"],
                version="1.1-test",
                html_bytes=html,
                pdf_bytes=pdf,
                email_payload_bytes=email,
                correction={
                    "previous_version":"1.0-test",
                    "reason":"claim correction",
                    "claim_reference":"C002",
                },
            )
            root = Path(td) / "issues" / self.zh["issue_id"]
            self.assertTrue((root / "versions" / "1.0-test" / "index.html").exists())
            self.assertTrue((root / "versions" / "1.1-test" / "index.html").exists())
            manifest = json.loads((root / "version.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["latest_version"], "1.1-test")
            self.assertEqual(manifest["correction"]["previous_version"], "1.0-test")

    def test_19_mobile_360_no_document_overflow(self):
        from weasyprint import HTML, CSS
        html = render_public_issue(
            self.en,
            source_records=sources_for(self.en["issue_id"]),
            pdf_href="./lesson.pdf",
            issue_row=issue_row(self.en["issue_id"], "EN"),
        )
        doc = HTML(string=html).render(
            stylesheets=[CSS(string="@page { size: 360px 1200px; margin: 0; }")]
        )
        for page in doc.pages:
            width = page.width
            page_box = page._page_box

            def walk(box):
                yield box
                for child in getattr(box, "children", []) or []:
                    yield from walk(child)

            for box in walk(page_box):
                right = getattr(box, "position_x", 0) + getattr(box, "width", 0)
                self.assertLessEqual(
                    right,
                    width + 0.5,
                    msg=f"360px overflow: {type(box).__name__} right={right} page={width}",
                )

    def test_20_pdf_fixture_is_valid_pdf(self):
        for name in (
            "W01D1_ZH_print_READY.pdf",
            "W01D2_EN_print_READY_v2.pdf",
            "W01D7_REVIEW_print_READY.pdf",
        ):
            self.assertTrue((FIX / name).read_bytes().startswith(b"%PDF"))


    def test_21_sunday_pdf_adapter_renders_review_content(self):
        with tempfile.TemporaryDirectory() as td:
            _, pdf_path, _, pages = render_issue(
                self.review,
                Path(td),
                source_records=[],
                issue_row=issue_row(self.review["issue_id"], "REVIEW"),
            )
            self.assertEqual(pages, 2)
            import fitz
            with fitz.open(pdf_path) as doc:
                page1 = doc[0].get_text("text")
                page2 = doc[1].get_text("text")
            self.assertIn("六天，六個世界入口", page1)
            self.assertIn("Moon AI", page1)
            self.assertIn("做完再看", page2)
            self.assertIn("這週我最想繼續追蹤的一件事", page2)


if __name__ == "__main__":
    unittest.main(verbosity=2)

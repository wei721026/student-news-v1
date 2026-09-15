from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"

from src.pdf_renderer import render_pdf_issue


class DailyPdfSmokeTests(unittest.TestCase):
    def test_daily_pdf_renders_without_page_margin_attr_footer(self):
        structured = json.loads(
            (FIX / "W01D2_EN_structured_content_v0_3_READY.json").read_text(
                encoding="utf-8"
            )
        )

        with tempfile.TemporaryDirectory() as td:
            out_dir = Path(td)
            pdf_path, pages = render_pdf_issue(
                structured,
                out_dir,
                source_records=[],
            )

            self.assertTrue(pdf_path.exists())
            self.assertTrue(pdf_path.read_bytes().startswith(b"%PDF"))
            self.assertGreaterEqual(pages, 1)

            print_html = (
                out_dir / f"{structured['issue_id']}.print.html"
            ).read_text(encoding="utf-8")

            # Regression guard for the 2026-09-15 WeasyPrint crash:
            # page margin boxes have no originating element, so attr(data-footer)
            # can dereference None inside WeasyPrint on some versions.
            self.assertNotIn("attr(data-footer)", print_html)
            self.assertIn(
                f"Student News · {structured['issue_id']}",
                print_html,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)

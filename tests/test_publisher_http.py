from __future__ import annotations
import io, json, os, tempfile, unittest
from pathlib import Path

class PublisherHttpTests(unittest.TestCase):
    def test_publish_multipart_and_auth(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["WEBHOOK_SECRET"] = "test-secret"
            os.environ["PUBLICATION_STORAGE"] = "LOCAL"
            os.environ["LOCAL_PUBLIC_ROOT"] = td
            os.environ["PUBLIC_BASE_URL"] = "https://example.invalid/student-news"

            from publisher.app import app
            client = app.test_client()

            bad = client.post("/publish", headers={"X-Webhook-Secret": "wrong"})
            self.assertEqual(bad.status_code, 401)

            pdf = (Path(__file__).parent / "fixtures" / "W01D1_ZH_print_READY.pdf").read_bytes()
            response = client.post(
                "/publish",
                headers={"X-Webhook-Secret": "test-secret"},
                data={
                    "metadata": json.dumps({"issue_id": "HTTP-TEST-001", "version": "1.0-test"}),
                    "html": (io.BytesIO(b"<!doctype html><html><body>ok</body></html>"), "index.html"),
                    "pdf": (io.BytesIO(pdf), "lesson.pdf"),
                    "email_payload": (io.BytesIO(b'{"kind":"ZH","headline":"test"}'), "email.json"),
                },
                content_type="multipart/form-data",
            )
            self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
            body = response.get_json()
            self.assertTrue(body["html_url"].endswith("/issues/HTTP-TEST-001/index.html"))
            root = Path(td) / "issues" / "HTTP-TEST-001"
            self.assertTrue((root / "versions" / "1.0-test" / "index.html").exists())
            self.assertTrue((root / "version.json").exists())

if __name__ == "__main__":
    unittest.main(verbosity=2)

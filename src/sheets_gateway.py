from __future__ import annotations

import json
import os

import google.auth
import gspread
from google.oauth2.service_account import Credentials

from .settings import required_env


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


class SheetsGateway:
    def __init__(self):
        # Preferred for GitHub Actions: Workload Identity Federation creates
        # short-lived Application Default Credentials (ADC). A legacy JSON key
        # is still supported for local/backward-compatible runs, but is no
        # longer required by the deployment workflow.
        raw_key = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
        if raw_key:
            creds = Credentials.from_service_account_info(json.loads(raw_key), scopes=SCOPES)
        else:
            creds, _ = google.auth.default(scopes=SCOPES)
        self.client = gspread.authorize(creds)
        self.book = self.client.open_by_key(required_env("GOOGLE_SHEET_ID"))
        self.issues = self.book.worksheet("ISSUES")
        self.sources = self.book.worksheet("SOURCES")
        self.claims = self.book.worksheet("CLAIMS")
        self.concepts = self.book.worksheet("CONCEPTS")
        self.automation = self.book.worksheet("AUTOMATION")
        self.run_log = self.book.worksheet("RUN_LOG")

    def automation_settings(self) -> dict:
        rows = self.automation.get_all_values()[3:]
        return {row[0].strip(): row[1].strip() for row in rows if row and row[0].strip()}

    def issue_records(self) -> list[dict]:
        return self.issues.get_all_records()

    def find_issue(self, issue_id: str):
        for idx, record in enumerate(self.issue_records(), start=2):
            if record.get("Issue_ID") == issue_id:
                return idx, record
        return None, None

    def recent_context(self, days: int = 28) -> str:
        rows = []
        for record in self.issue_records()[-30:]:
            if record.get("Headline"):
                rows.append(
                    f"{record.get('Publish_Date')} | {record.get('Language')} | "
                    f"{record.get('Category')} | {record.get('Headline')}"
                )
        return "\n".join(rows[-20:])

    def today_issue(self, date_str: str):
        for idx, record in enumerate(self.issue_records(), start=2):
            if (
                str(record.get("Publish_Date")) == date_str
                and record.get("Program") in ("Production", "OneWeekTrial")
            ):
                return idx, record
        return None, None

    def append_issue(self, values: dict):
        headers = self.issues.row_values(1)
        row = [values.get(header, "") for header in headers]
        self.issues.append_row(row, value_input_option="USER_ENTERED")
        idx = len(self.issues.get_all_values())
        return idx, dict(zip(headers, row))

    def ensure_today_issue(self, date_str: str, weekday: int):
        row, record = self.today_issue(date_str)
        if record:
            return row, record

        if weekday == 6:
            lang, category, interaction = "REVIEW", "週回顧", "GUIDED_READING"
        elif weekday in (0, 2, 4):
            lang, category, interaction = "ZH", "AUTO_SELECT", "GUIDED_READING"
        else:
            lang, category, interaction = "EN", "AUTO_SELECT", "LANGUAGE_SCAFFOLD"

        issue_id = f"{date_str}-{lang}-AUTO"
        values = {
            "Issue_ID": issue_id,
            "Program": "Production",
            "Publish_Date": date_str,
            "Day": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][weekday],
            "Language": lang,
            "Region": "MIXED",
            "Category": category,
            "Interaction_Style": interaction,
            "Headline": "AUTO_PENDING",
            "Status": "SCHEDULED",
            "Fact_QA": "PENDING",
            "Teaching_QA": "PENDING",
            "Layout_QA": "PENDING",
            "Version": "1.0",
            "Time_Sensitivity": "TIME_SENSITIVE",
            "Evidence_Maturity": "DEVELOPING_EVENT",
            "Approval": "PENDING",
            "Attempt_Count": 0,
            "Next_Action": "DISCOVERY" if weekday != 6 else "SUNDAY_REVIEW",
            "Email_Status": "PENDING",
        }
        return self.append_issue(values)

    def update_issue(self, row: int, updates: dict):
        headers = self.issues.row_values(1)
        index = {header: i + 1 for i, header in enumerate(headers)}
        for key, value in updates.items():
            if key in index:
                self.issues.update_cell(row, index[key], value)

    def source_records_for_issue(self, issue_id: str) -> list[dict]:
        return [
            record
            for record in self.sources.get_all_records()
            if record.get("Issue_ID") == issue_id
        ]

    def previous_six_ready_issue_ids(self, before_date: str) -> list[str]:
        eligible = []
        for record in self.issue_records():
            publish_date = str(record.get("Publish_Date") or "")
            if not publish_date or publish_date >= before_date:
                continue
            if str(record.get("Language") or "").upper() not in ("ZH", "EN"):
                continue
            if str(record.get("Status") or "").upper() not in ("READY", "APPROVED", "PUBLISHED"):
                continue
            if any(str(record.get(key) or "").upper() != "PASS" for key in ("Fact_QA", "Teaching_QA", "Layout_QA")):
                continue
            eligible.append((publish_date, str(record.get("Issue_ID"))))
        eligible.sort(key=lambda item: (item[0], item[1]))
        ids = [item[1] for item in eligible[-6:]]
        if len(ids) != 6:
            raise RuntimeError("Sunday review requires exactly six prior QA-PASS ZH/EN mother-data issues")
        return ids

    def append_source_rows(self, issue_id: str, source_rows: list[dict]):
        headers = self.sources.row_values(1)
        rows = []
        for source in source_rows:
            mapped = {
                "Issue_ID": issue_id,
                "Source_ID": source.get("source_id", ""),
                "Source_Type": source.get("source_type", ""),
                "Publisher": source.get("publisher", ""),
                "Title": source.get("title", ""),
                "URL": source.get("url", ""),
                "Source_Published_Date": source.get("published", ""),
                "Primary_Flag": "YES" if source.get("primary") else "NO",
                "Verified_Flag": "YES",
            }
            rows.append([mapped.get(header, "") for header in headers])
        if rows:
            self.sources.append_rows(rows, value_input_option="USER_ENTERED")

    def append_claim_rows(self, issue_id: str, claim_rows: list[dict], checked_at: str):
        headers = self.claims.row_values(1)
        rows = []
        for claim in claim_rows:
            mapped = {
                "Issue_ID": issue_id,
                "Claim_ID": claim.get("claim_id", ""),
                "Claim_Level": claim.get("level", ""),
                "Claim_Type": "AUTO",
                "Claim_Text": claim.get("text", ""),
                "Critical_Flag": "YES" if claim.get("critical") else "NO",
                "Source_IDs": ";".join(claim.get("source_ids", [])),
                "Verified_Status": claim.get("verified_status", ""),
                "Evidence_Note": "",
                "Checked_At": checked_at,
            }
            rows.append([mapped.get(header, "") for header in headers])
        if rows:
            self.claims.append_rows(rows, value_input_option="USER_ENTERED")

    def log(
        self,
        *,
        timestamp: str,
        run_id: str,
        issue_id: str,
        stage: str,
        status: str,
        duration: float = 0,
        response_id: str = "",
        message: str = "",
        artifact_path: str = "",
    ):
        self.run_log.append_row(
            [
                timestamp,
                run_id,
                issue_id,
                stage,
                status,
                round(duration, 2),
                response_id,
                message,
                artifact_path,
            ],
            value_input_option="USER_ENTERED",
        )

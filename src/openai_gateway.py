from __future__ import annotations

import json
import os
import re
import time
from datetime import date, datetime

from openai import OpenAI, RateLimitError

from .schemas import DISCOVERY_SCHEMA, FACT_SCHEMA, QA_SCHEMA


class OpenAIGateway:
    """
    Compatibility adapter for Student News V1.

    The rest of the pipeline still imports OpenAIGateway so we do not need to
    touch the already-tested pipeline. This implementation sends requests to
    Groq's OpenAI-compatible API.

    Browser search and structured output are intentionally separated because
    Groq does not allow browser_search and Structured Outputs in the same call.
    """

    SEARCH_MODEL = "openai/gpt-oss-20b"
    CORE_MODEL = "openai/gpt-oss-120b"
    RATE_LIMIT_MAX_RETRIES = 6
    RATE_LIMIT_FALLBACK_WAIT_SEC = 30.0
    RATE_LIMIT_MAX_WAIT_SEC = 900.0

    def __init__(self, settings):
        self.settings = settings
        raw = os.getenv("GROQ_API_KEY", "")
        api_key = "".join(raw.strip().strip('`"\'').split())
        if not api_key:
            raise RuntimeError("Missing required environment variable: GROQ_API_KEY")

        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
            timeout=90.0,
            # Groq free-tier TPM is low enough that a normal multi-stage run can
            # legitimately hit 429 between consecutive CORE_MODEL calls. We own
            # the retry timing below so GitHub Actions waits instead of failing.
            max_retries=0,
        )

    @staticmethod
    def _rid(response) -> str:
        return str(getattr(response, "id", "") or "")

    @staticmethod
    def _compact_json(value) -> str:
        """Serialize mother data compactly to reduce Groq TPM pressure."""
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _parse_wait_duration(raw: str) -> float | None:
        """
        Parse Groq wait strings such as:
        - "20.587s"
        - "4m31.728s"
        - "1h2m3.5s"
        """
        value = str(raw or "").strip().lower()
        if not value:
            return None

        try:
            return float(value)
        except ValueError:
            pass

        match = re.fullmatch(
            r"(?:(?P<h>[0-9]+(?:\.[0-9]+)?)h)?"
            r"(?:(?P<m>[0-9]+(?:\.[0-9]+)?)m)?"
            r"(?:(?P<s>[0-9]+(?:\.[0-9]+)?)s)?",
            value,
        )
        if not match or not any(match.groupdict().values()):
            return None

        hours = float(match.group("h") or 0)
        minutes = float(match.group("m") or 0)
        seconds = float(match.group("s") or 0)
        return hours * 3600 + minutes * 60 + seconds

    @classmethod
    def _retry_after_seconds(cls, exc: Exception) -> float:
        response = getattr(exc, "response", None)
        headers = getattr(response, "headers", None) or {}

        raw = headers.get("retry-after") or headers.get("Retry-After")
        parsed = cls._parse_wait_duration(raw)
        if parsed is not None:
            return parsed

        # Groq error messages can contain:
        # "Please try again in 20.587s."
        # "Please try again in 4m31.728s."
        match = re.search(
            r"try again in\s*((?:[0-9]+(?:\.[0-9]+)?h)?"
            r"(?:[0-9]+(?:\.[0-9]+)?m)?"
            r"(?:[0-9]+(?:\.[0-9]+)?s))",
            str(exc),
            re.I,
        )
        if match:
            parsed = cls._parse_wait_duration(match.group(1))
            if parsed is not None:
                return parsed

        return cls.RATE_LIMIT_FALLBACK_WAIT_SEC

    def _call_with_rate_limit_retry(self, call, *, label: str):
        """
        Respect Groq's 429 retry window instead of failing the scheduled run.

        This is deliberately narrow: only 429 / RateLimitError is retried here.
        Other API, schema or application errors still fail fast and remain visible.
        """
        total_attempts = self.RATE_LIMIT_MAX_RETRIES + 1
        for attempt in range(1, total_attempts + 1):
            try:
                return call()
            except RateLimitError as exc:
                if attempt >= total_attempts:
                    print(
                        f"GROQ_RATE_LIMIT_EXHAUSTED label={label} "
                        f"attempt={attempt}/{total_attempts}"
                    )
                    raise
                requested_wait = max(1.0, self._retry_after_seconds(exc) + 2.0)
                wait_sec = min(requested_wait, self.RATE_LIMIT_MAX_WAIT_SEC)
                print(
                    f"GROQ_RATE_LIMIT_WAIT label={label} "
                    f"attempt={attempt}/{total_attempts} "
                    f"requested_wait={requested_wait:.1f}s wait={wait_sec:.1f}s"
                )
                time.sleep(wait_sec)

    def _structured(
        self,
        *,
        prompt: str,
        schema: dict,
        name: str,
        model: str | None = None,
    ) -> tuple[dict, str]:
        selected_model = model or self.CORE_MODEL
        response = self._call_with_rate_limit_retry(
            lambda: self.client.responses.create(
                model=selected_model,
                input=prompt,
                reasoning={"effort": "low"},
                text={
                    "format": {
                        "type": "json_schema",
                        "name": name,
                        "schema": schema,
                        "strict": True,
                    }
                },
            ),
            label=f"structured:{name}:{selected_model}",
        )
        return json.loads(response.output_text), self._rid(response)

    def _json_object(
        self,
        *,
        prompt: str,
        model: str | None = None,
    ) -> tuple[dict, str]:
        selected_model = model or self.CORE_MODEL
        response = self._call_with_rate_limit_retry(
            lambda: self.client.responses.create(
                model=selected_model,
                input=prompt,
                reasoning={"effort": "low"},
                text={"format": {"type": "json_object"}},
            ),
            label=f"json_object:{selected_model}",
        )
        return json.loads(response.output_text), self._rid(response)

    def _web_research(
        self,
        *,
        prompt: str,
    ) -> tuple[str, str]:
        response = self._call_with_rate_limit_retry(
            lambda: self.client.responses.create(
                model=self.SEARCH_MODEL,
                input=prompt,
                reasoning={"effort": "low"},
                tool_choice="required",
                tools=[{"type": "browser_search"}],
            ),
            label=f"browser_search:{self.SEARCH_MODEL}",
        )
        text = (response.output_text or "").strip()
        if not text:
            raise RuntimeError("Groq browser_search returned empty research text")
        return text, self._rid(response)

    FRESHNESS_DAYS = 7

    def _local_today(self) -> date:
        return datetime.now(self.settings.tz).date()

    def _apply_freshness_gate(self, fact_pack: dict) -> dict:
        """
        Daily Student News must be anchored in a genuinely current event.
        Older background is allowed, but at least one cited source must have
        a parseable publication date within the last FRESHNESS_DAYS.
        """
        today = self._local_today()
        recent = []
        parsed = []
        for source in fact_pack.get("sources", []):
            raw = str(source.get("published") or "").strip()
            if not raw:
                continue
            try:
                published = date.fromisoformat(raw[:10])
            except ValueError:
                continue
            age = (today - published).days
            parsed.append((source.get("source_id") or "", published.isoformat(), age))
            if -1 <= age <= self.FRESHNESS_DAYS:
                recent.append(source)

        if recent:
            return fact_pack

        qa = fact_pack.setdefault("fact_qa", {})
        qa["status"] = "BLOCK"
        existing = str(qa.get("notes") or "").strip()
        detail = (
            f"FRESHNESS_GATE: no cited source has a parseable publication date "
            f"within {self.FRESHNESS_DAYS} days of {today.isoformat()}. "
            "Do not substitute an old report or evergreen topic for today's current-affairs issue."
        )
        if parsed:
            detail += " Parsed dates: " + ", ".join(
                f"{sid or '?'}={published} (age {age}d)"
                for sid, published, age in parsed
            )
        qa["notes"] = (existing + " " + detail).strip()
        return fact_pack

    def discover(
        self,
        *,
        language: str,
        weekday: str,
        recent_context: str,
    ) -> tuple[dict, str]:
        today = self._local_today().isoformat()
        research_prompt = f"""
You are researching TODAY'S current-affairs lesson for learners age 13+ in Taiwan.

Local publication date: {today}
Scheduled language: {language}
Weekday: {weekday}

Recent 4-week content context:
{recent_context}

Use live browser search.

HARD FRESHNESS RULE:
- Candidate stories must be anchored in a genuine event, release, decision,
  announcement, result, newly published report, or newly changed public fact
  dated within the last 7 days.
- Older facts may be used only as background to explain that current event.
- Do NOT choose an old report, historical record, or evergreen explainer merely
  because it is educational.
- If a candidate's "why now" cannot name what happened recently, reject it.

Find 3-5 credible candidates. Prioritize:
1. official/original sources;
2. research institutions;
3. high-quality news;
4. diverse categories and geography.

Avoid repeating recent topics above.
Do not choose a story merely because it is sensational.
For Chinese days, Taiwan topics are welcome but not mandatory.
For English days, prefer topics explainable at about A2-B1/B1.

For every candidate, include:
- title
- language
- region
- category
- why it matters NOW, explicitly naming the recent event
- educational value
- at least one FULL absolute source URL beginning with http

Do not invent URLs.
"""
        research, research_id = self._web_research(prompt=research_prompt)

        format_prompt = f"""
Convert the live-research notes below into the required discovery JSON.
Use ONLY information and URLs present in the research notes.
Do not add, repair, guess, or invent URLs.
Preserve the recent-event reason in `why_now`.
Do not output an evergreen candidate that lacks a recent event.

LIVE RESEARCH:
{research}
"""
        data, format_id = self._structured(
            prompt=format_prompt,
            schema=DISCOVERY_SCHEMA,
            name="discovery_candidates",
        )
        return data, f"{research_id}|{format_id}"

    def verify_candidate(self, candidate: dict) -> tuple[dict, str]:
        today = self._local_today().isoformat()
        research_prompt = f"""
Fact-check this current-affairs candidate for a learner-facing article.

Local publication date: {today}

CANDIDATE:
{json.dumps(candidate, ensure_ascii=False, indent=2)}

Use live browser search again. Do not trust the candidate summary.

Requirements:
- First verify the recent-event anchor: what happened within the last 7 days?
- Prefer an official/original source plus a strong independent second source.
- Verify names, dates, places, numbers, policy conditions, study design and rankings.
- Separate stable background from news facts.
- Do not rewrite "may" as "will", association as causation, or scenario as prediction.
- If sources disagree, describe the conflict and narrow the claim.
- Include FULL absolute URLs for every source used.
- Capture the actual source publication date as YYYY-MM-DD whenever visible.
- Never invent a date or URL.
- If critical claims cannot be supported, say so clearly.
- If the recent-event anchor cannot be verified, Fact QA must BLOCK.
"""
        research, research_id = self._web_research(prompt=research_prompt)

        format_prompt = f"""
Build the verified Fact Pack JSON from the live verification notes below.

Rules:
- Use ONLY facts, dates and URLs present in the notes.
- Do not invent missing publication dates; use an empty string if unavailable.
- A critical claim may use VERIFIED or VERIFIED_WITH_ATTRIBUTION only when the
  research notes actually support it.
- fact_qa.status must be BLOCK if any critical claim lacks sufficient support.
- fact_qa.status must also be BLOCK if the story lacks a verified recent-event anchor.
- Provide at least two source records when the research supports two sources.

LIVE VERIFICATION NOTES:
{research}
"""
        data, format_id = self._structured(
            prompt=format_prompt,
            schema=FACT_SCHEMA,
            name="verified_fact_pack",
        )
        data = self._apply_freshness_gate(data)
        return data, f"{research_id}|{format_id}"

    def draft_structured_content(
        self,
        *,
        issue_id: str,
        language: str,
        fact_pack: dict,
        contract_text: str,
    ) -> tuple[dict, str]:
        is_english = str(language).lower().startswith("en")
        profile = """
GOLD MASTER PRODUCT PROFILE — ENGLISH
- `language_support.enabled` MUST be true.
- Exactly 5 essential words with concise Traditional Chinese meanings.
- One useful focus sentence from the lesson, plus a short sentence_breakdown.
- Create 3 substantive CORE reading sections. Together, the CORE reading should
  normally contain about 280-420 English words, excluding the quick summary,
  vocabulary cards, questions, rescue, sources and answer key.
- The 3 CORE sections must create a real reading flow:
  what happened -> evidence/data/context -> what the evidence does or does not mean.
- At least 2 CORE checkpoints should require reading the article, not merely
  recalling the quick summary.
- 1 optional EXTENSION section may add depth, but must never carry information
  required to understand the main event.
- levels.basic / standard / challenge must progress from evidence retrieval ->
  explanation/integration -> evidence/headline judgment.
- rescue must contain two actionable hints plus a concise main-idea summary.
- zh_rescue_summary is allowed ONLY here, in the rescue layer.
- exam_connection enabled; one_thing_prompt present.
- completion.student_checkbox_label should read:
  "□ CORE COMPLETE | You can stop here today."
""" if is_english else """
GOLD MASTER PRODUCT PROFILE — CHINESE
- `language_support.enabled` MUST be false.
- Do NOT create English-word cards, Focus Sentence, sentence breakdown, or
  Chinese-rescue duplication.
- Prefer 2 concise CORE background concept cards when they genuinely help.
- Create 3 substantive CORE reading sections. Together, the CORE reading should
  normally contain about 500-800 Chinese characters, excluding the quick
  summary, questions, rescue, sources and answer key.
- The 3 CORE sections must create a real reading flow:
  發生什麼 -> 背景/關鍵數據或條件 -> 證據能支持到哪裡、不能推到哪裡.
- At least 2 CORE checkpoints should require reading the article, not merely
  recalling the quick summary.
- Use 1 optional EXTENSION section only after the CORE is already complete.
- levels.basic / standard / challenge must progress from:
  找文本證據 -> 整合/解釋 -> 判斷新聞說法、數據或證據界線.
- rescue must contain two concrete hints plus one concise summary.
- exam_connection enabled; one_thing_prompt present.
- completion.student_checkbox_label should read "□ 核心任務完成".
"""
        prompt = f"""
Create Structured Content for issue {issue_id}.
Language: {language}

FACT PACK:
{json.dumps(fact_pack, ensure_ascii=False, indent=2)}

V1.0 CONTRACT EXAMPLE:
{contract_text}

{profile}

GLOBAL GOLD MASTER RULES:
- Return JSON only and keep the frozen contract field organization.
- Do NOT add, remove, rename or restructure Data Contract fields.
- This is a DAILY CURRENT-AFFAIRS product, not an evergreen encyclopedia page.
- editorial.headline and hook must lead with the verified recent event.
- lifecycle.event_date must represent the current event when supported.
- Older facts belong in background only.
- quick_summary must stay a 2-4 sentence orientation. It MUST NOT replace the article.
- ARTICLE DEPTH GATE: CORE must be a genuine learner-facing explainer with enough
  evidence and context that a student has something substantial to read.
- Across CORE, explicitly answer:
  (1) what happened,
  (2) what background is needed,
  (3) what key data/evidence/conditions matter,
  (4) what causal or evidentiary limit must not be overstated,
  (5) why the event matters now.
- Questions must never substitute for missing article content.
- EXTENSION is optional and must not contain information required to answer the
  main CORE questions.
- LITERACY QUESTION GATE:
  * at least 3 student questions across checkpoints and levels must require the
    article itself to answer reliably;
  * at least 1 question must integrate information from two different parts of
    the article;
  * at least 1 must interpret data, conditions, comparison, wording or evidence;
  * at least 1 must judge whether a headline/claim goes beyond the evidence;
  * MCQ distractors must be plausible misreadings, not silly obviously-wrong options;
  * at least 2 of the 3 level questions must NOT be answerable from quick_summary alone.
- Answers and explanations MAY remain in Structured Content as mother data, but
  `presentation.answers` MUST be `SEPARATE`. They must not be written into the
  visible question text.
- The PDF renderer will place answers together at the END OF PAGE 2.
- The HTML renderer must hide answers by default and reveal them only after learner action.
- CORE should still fit a 10-15 minute self-study session.
- Do not add facts beyond the Fact Pack.
- Keep uncertainty and evidence limits visible.
- Source IDs in provenance must come from the Fact Pack.
- Avoid generic textbook wording such as "this unit" when a more concrete
  news-facing sentence is possible.
"""
        return self._json_object(prompt=prompt)

    def teaching_qa(
        self,
        structured: dict,
        fact_pack: dict,
    ) -> tuple[dict, str]:
        prompt = f"""
Review this learner-facing Structured Content against BOTH factual safety and
the established One-Week Trial Gold Master product profile.

FACT PACK:
{json.dumps(fact_pack, ensure_ascii=False, indent=2)}

CONTENT:
{json.dumps(structured, ensure_ascii=False, indent=2)}

PASS only if all are true:
1. A 13+ learner can self-study it in about 10-15 minutes.
2. No unsupported claim, exaggerated causality, invented number, URL or source.
3. The headline/hook clearly explain the current news event rather than turning
   the lesson into an old/evergreen topic.
4. ARTICLE DEPTH PASS:
   - quick_summary is only an orientation, not the whole article;
   - there are 3 substantive CORE reading sections with a coherent reading flow;
   - Chinese CORE normally totals about 500-800 Chinese characters, or English
     CORE about 280-420 English words, unless the verified Fact Pack genuinely
     cannot support that much without padding;
   - the CORE explains what happened, context, evidence/data/conditions,
     evidence limits, and why it matters now.
5. EXTENSION is optional and is not required to understand the main event.
6. LITERACY QA PASS:
   - at least 3 questions require reading the article itself;
   - at least 1 question integrates two different parts of the article;
   - at least 1 interprets data/conditions/comparison/evidence language;
   - at least 1 judges whether a claim/headline exceeds the evidence;
   - MCQ distractors are plausible misreadings;
   - at least 2 level questions cannot be answered from quick_summary alone.
7. basic -> standard -> challenge meaningfully progress in thinking.
8. ANSWER SEPARATION PASS:
   - `presentation.answers` is `SEPARATE`;
   - answer/explanation data exist where needed but are not embedded inside
     visible prompt text or choices.
9. Rescue is concrete, not a duplicate of the article.
10. The structure resembles the established Gold Master rather than a generic
    worksheet full of undifferentiated text boxes.
11. If metadata.language is zh-TW: language_support.enabled MUST be false; no
    Focus Sentence or duplicated 中文救援.
12. If metadata.language is en: exactly 5 key words, a focus sentence, useful
    sentence breakdown, and zh_rescue_summary only in the rescue layer.
13. one_thing_prompt and exam_connection are present and useful.

Return REVISE when the problems can be repaired without new research.
Return BLOCK when factual/currentness problems require new research.

When returning REVISE, revision_instructions must be specific and minimal.
Always ask what can be deleted.
"""
        return self._structured(
            prompt=prompt,
            schema=QA_SCHEMA,
            name="teaching_qa",
        )

    def revise_content(
        self,
        structured: dict,
        instructions: list[str],
    ) -> tuple[dict, str]:
        prompt = f"""
Revise this Structured Content JSON.

CONTENT:
{self._compact_json(structured)}

REVISION INSTRUCTIONS:
{self._compact_json(instructions)}

Rules:
- JSON only.
- Preserve verified facts and claim/source references.
- Do not invent new facts.
- Preserve Core/Extension distinction.
- Preserve the Gold Master language-specific profile: Chinese has no language_support; English keeps exactly 5 words + focus sentence.
- Keep the current-news anchor prominent in headline, hook and quick summary.
- Preserve ARTICLE DEPTH: do not solve a revision by collapsing CORE into a
  summary. Keep 3 substantive CORE reading sections unless the Fact Pack cannot
  safely support them.
- Preserve LITERACY QUESTION quality: questions must require the article, not
  just quick_summary; keep plausible distractors and evidence-based reasoning.
- Keep `presentation.answers = "SEPARATE"`.
- Answers/explanations may remain in mother data but must not be embedded in
  prompt text or choices.
- Prefer deleting repetition, redundant framing and optional extension content
  BEFORE shortening essential CORE evidence/context.
"""
        return self._json_object(prompt=prompt)

    def condense_for_print(self, structured: dict) -> tuple[dict, str]:
        prompt = f"""
This Structured Content rendered to more than 2 A4 pages.

CONTENT:
{self._compact_json(structured)}

Condense for a two-page print layout while preserving:
- all critical verified meaning;
- the recent-event anchor;
- ARTICLE DEPTH: keep a coherent 3-part CORE reading flow and do not reduce the
  article to a quick summary;
- LITERACY QA: keep at least 3 reading-dependent questions, including one
  cross-section integration question, one data/condition/evidence question and
  one claim/headline judgment;
- Core Complete;
- English 5-word + focus-sentence scaffold when present;
- rescue and compact sources;
- `presentation.answers = "SEPARATE"`.

Remove in this order:
1. repeated wording;
2. decorative framing;
3. optional extension detail;
4. redundant hints.
Do NOT remove essential CORE evidence/context just to make the page fit.
Do not solve overflow by requesting smaller main body text.
Return JSON only. Do not add facts.
"""
        return self._json_object(prompt=prompt)

    def sunday_review(
        self,
        previous_six: list[dict],
        contract_text: str,
    ) -> tuple[dict, str]:
        prompt = f"""
Create a Sunday weekly review using ONLY the six Structured Content objects below.
Do not search for new news and do not add new facts.

V1.0 CONTRACT EXAMPLE:
{contract_text}

MOTHER DATA:
{json.dumps(previous_six, ensure_ascii=False, indent=2)}

Return a normal V1-compatible Structured Content JSON object with:
issue_id, metadata, editorial, background, sections, levels, rescue,
language_support, provenance, exam_connection, concept_ids,
one_thing_prompt, completion, qa.

Use `sections` to organize:
- CORE: this week's 3-5 event recalls and 3 concept recalls;
- CORE: 1-2 English-word recalls;
- CORE: 2 cross-news connections;
- CORE: 1 evidence/data judgment;
- EXTENSION: curiosity reflection if useful.

Goals:
- retrieval, not a weekly test;
- no new facts;
- no scores;
- Sunday review language may be REVIEW / mixed Chinese-English.
"""
        return self._json_object(prompt=prompt)

    def sunday_teaching_qa(
        self,
        structured: dict,
        previous_six: list[dict],
    ) -> tuple[dict, str]:
        prompt = f"""
Review this Sunday learner-facing weekly review.

SOURCE OF TRUTH:
The only allowed factual basis is the six READY mother-data objects below.
Do not search the web and do not introduce new facts.

MOTHER DATA:
{json.dumps(previous_six, ensure_ascii=False, indent=2)}

REVIEW CONTENT:
{json.dumps(structured, ensure_ascii=False, indent=2)}

Return PASS if:
- it is self-study friendly for age 13+;
- it is retrieval/review rather than a scored weekly test;
- all factual content is supported by the six mother-data objects;
- it includes useful cross-news connections without inventing facts.

Return REVISE if it can be safely repaired without new research.
Return BLOCK if it cannot be repaired safely.
"""
        return self._structured(
            prompt=prompt,
            schema=QA_SCHEMA,
            name="sunday_teaching_qa",
        )

    def revise_sunday(
        self,
        structured: dict,
        instructions: list[str],
        previous_six: list[dict],
    ) -> tuple[dict, str]:
        prompt = f"""
Revise this Sunday Structured Content JSON using ONLY the six mother-data objects below.

MOTHER DATA:
{json.dumps(previous_six, ensure_ascii=False, indent=2)}

CONTENT:
{json.dumps(structured, ensure_ascii=False, indent=2)}

REVISION INSTRUCTIONS:
{json.dumps(instructions, ensure_ascii=False, indent=2)}

Rules:
- JSON only.
- Do not search for or add new facts.
- Preserve all source issue references.
- Keep review/retrieval tone; no scores.
- Prefer deletion/condensing over adding material.
"""
        return self._json_object(prompt=prompt)

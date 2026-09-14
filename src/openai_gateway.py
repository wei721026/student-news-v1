from __future__ import annotations

import json
import os
from datetime import date, datetime

from openai import OpenAI

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
            max_retries=1,
        )

    @staticmethod
    def _rid(response) -> str:
        return str(getattr(response, "id", "") or "")

    def _structured(
        self,
        *,
        prompt: str,
        schema: dict,
        name: str,
        model: str | None = None,
    ) -> tuple[dict, str]:
        response = self.client.responses.create(
            model=model or self.CORE_MODEL,
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
        )
        return json.loads(response.output_text), self._rid(response)

    def _json_object(
        self,
        *,
        prompt: str,
        model: str | None = None,
    ) -> tuple[dict, str]:
        response = self.client.responses.create(
            model=model or self.CORE_MODEL,
            input=prompt,
            reasoning={"effort": "low"},
            text={"format": {"type": "json_object"}},
        )
        return json.loads(response.output_text), self._rid(response)

    def _web_research(
        self,
        *,
        prompt: str,
    ) -> tuple[str, str]:
        response = self.client.responses.create(
            model=self.SEARCH_MODEL,
            input=prompt,
            reasoning={"effort": "low"},
            tool_choice="required",
            tools=[{"type": "browser_search"}],
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
- 2 concise CORE sections. At least one CORE checkpoint; ideally one fact check
  and one evidence-language check.
- 1 optional EXTENSION section.
- levels.basic / standard / challenge must progress from fact -> explanation ->
  evidence/headline judgment.
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
- Use 2 concise CORE sections when the Fact Pack supports them. At least one
  CORE checkpoint.
- Use 1 optional EXTENSION section.
- levels.basic / standard / challenge must progress from:
  找得到重點 -> 能解釋 -> 能判斷新聞說法/資料界線.
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
- This is a DAILY CURRENT-AFFAIRS product, not an evergreen encyclopedia page.
- editorial.headline and hook must lead with the verified recent event.
- lifecycle.event_date must represent the current event when supported.
- Older facts belong in background only.
- First-page Core should fit a 10-15 minute self-study session.
- quick_summary should be 2-4 short sentences, not a long paragraph.
- CORE should teach one main information-literacy idea, not every fact found.
- EXTENSION is optional and must not be required to understand the main point.
- Three challenge levels should be short and meaningfully different.
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
4. CORE is concise, has at least one checkpoint, and ends with a clear completion cue.
5. EXTENSION is optional.
6. basic -> standard -> challenge meaningfully progress in thinking.
7. Rescue is concrete, not a duplicate of the article.
8. The structure resembles the established Gold Master rather than a generic
   worksheet full of undifferentiated text boxes.
9. If metadata.language is zh-TW: language_support.enabled MUST be false; no
   Focus Sentence or duplicated 中文救援.
10. If metadata.language is en: exactly 5 key words, a focus sentence, useful
    sentence breakdown, and zh_rescue_summary only in the rescue layer.
11. one_thing_prompt and exam_connection are present and useful.

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
{json.dumps(structured, ensure_ascii=False, indent=2)}

REVISION INSTRUCTIONS:
{json.dumps(instructions, ensure_ascii=False, indent=2)}

Rules:
- JSON only.
- Preserve verified facts and claim/source references.
- Prefer deletion/condensing over adding content.
- Do not invent new facts.
- Preserve Core/Extension distinction.
- Preserve the Gold Master language-specific profile: Chinese has no language_support; English keeps exactly 5 words + focus sentence.
- Keep the current-news anchor prominent in headline, hook and quick summary.
"""
        return self._json_object(prompt=prompt)

    def condense_for_print(self, structured: dict) -> tuple[dict, str]:
        prompt = f"""
This Structured Content rendered to more than 2 A4 pages.

CONTENT:
{json.dumps(structured, ensure_ascii=False, indent=2)}

Condense framing/repetition while preserving:
- all critical verified meaning;
- Core Complete;
- at least one Core checkpoint;
- English 5-word + focus-sentence scaffold when present;
- rescue and compact sources.

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

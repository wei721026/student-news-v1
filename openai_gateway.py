from __future__ import annotations

import json
import os

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

    def discover(
        self,
        *,
        language: str,
        weekday: str,
        recent_context: str,
    ) -> tuple[dict, str]:
        research_prompt = f"""
You are researching current-affairs stories for learners age 13+ in Taiwan.

Scheduled language: {language}
Weekday: {weekday}

Recent 4-week content context:
{recent_context}

Use live browser search.
Find 3-5 credible candidate stories that are current enough to justify a
current-affairs lesson. Prioritize:
1. official/original sources;
2. research institutions;
3. high-quality news;
4. diverse categories and geography.

Avoid repeating the recent topics above.
Do not choose a story merely because it is sensational.
For Chinese days, Taiwan topics are welcome but not mandatory.
For English days, prefer topics that can be explained at about A2-B1/B1.

For every candidate, include:
- title
- language
- region
- category
- why it matters now
- educational value
- at least one FULL absolute source URL beginning with http

Do not invent URLs.
"""
        research, research_id = self._web_research(prompt=research_prompt)

        format_prompt = f"""
Convert the live-research notes below into the required discovery JSON.
Use ONLY information and URLs present in the research notes.
Do not add, repair, guess, or invent URLs.

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
        research_prompt = f"""
Fact-check this current-affairs candidate for a learner-facing article.

CANDIDATE:
{json.dumps(candidate, ensure_ascii=False, indent=2)}

Use live browser search again. Do not trust the candidate summary.

Requirements:
- Prefer an official/original source plus a strong independent second source.
- Verify names, dates, places, numbers, policy conditions, study design and rankings.
- Separate stable background from news facts.
- Do not rewrite "may" as "will", association as causation, or scenario as prediction.
- If sources disagree, describe the conflict and narrow the claim.
- Include FULL absolute URLs for every source used.
- Never invent URLs.
- If critical claims cannot be supported, say so clearly.
"""
        research, research_id = self._web_research(prompt=research_prompt)

        format_prompt = f"""
Build the verified Fact Pack JSON from the live verification notes below.

Rules:
- Use ONLY facts and URLs present in the notes.
- Do not invent missing publication dates; use an empty string if unavailable.
- A critical claim may use VERIFIED or VERIFIED_WITH_ATTRIBUTION only when the
  research notes actually support it.
- fact_qa.status must be BLOCK if any critical claim lacks sufficient support.
- Provide at least two source records when the research supports two sources.

LIVE VERIFICATION NOTES:
{research}
"""
        data, format_id = self._structured(
            prompt=format_prompt,
            schema=FACT_SCHEMA,
            name="verified_fact_pack",
        )
        return data, f"{research_id}|{format_id}"

    def draft_structured_content(
        self,
        *,
        issue_id: str,
        language: str,
        fact_pack: dict,
        contract_text: str,
    ) -> tuple[dict, str]:
        prompt = f"""
Create Structured Content for issue {issue_id}.
Language: {language}

FACT PACK:
{json.dumps(fact_pack, ensure_ascii=False, indent=2)}

V1.0 CONTRACT EXAMPLE:
{contract_text}

Requirements:
- Return JSON only.
- Follow the contract's field organization.
- First page Core should fit a 10-15 minute self-study session.
- Core must have at least one checkpoint and a clear Core Complete.
- Extension must be optional.
- Chinese: background/institutions/data/causality scaffolding.
- English: 5 essential words, one focus sentence, sentence breakdown by meaning,
  then short article sections; Chinese rescue only in the rescue layer.
- Do not add news facts beyond the Fact Pack.
- Keep limitations / uncertainty in the learning design where needed.
"""
        return self._json_object(prompt=prompt)

    def teaching_qa(
        self,
        structured: dict,
        fact_pack: dict,
    ) -> tuple[dict, str]:
        prompt = f"""
Review this learner-facing structured content.

FACT PACK:
{json.dumps(fact_pack, ensure_ascii=False, indent=2)}

CONTENT:
{json.dumps(structured, ensure_ascii=False, indent=2)}

Return:
PASS if a 13+ learner can self-study it and no unsupported claims were introduced.
REVISE if it is too dense, too test-like, background is missing, or removable content remains.
BLOCK if it cannot be repaired safely without new research.

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

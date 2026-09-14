from __future__ import annotations

import json
from openai import OpenAI

from .schemas import DISCOVERY_SCHEMA, FACT_SCHEMA, QA_SCHEMA


class OpenAIGateway:
    def __init__(self, settings):
        self.settings = settings
        self.client = OpenAI()

    def _json(self, *, model: str, prompt: str, schema: dict, name: str, web: bool = False) -> tuple[dict, str]:
        kwargs = {
            "model": model,
            "input": prompt,
            "store": False,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": name,
                    "schema": schema,
                    "strict": True,
                }
            },
        }
        if web:
            kwargs["tools"] = [{"type": "web_search", "search_context_size": "high"}]

        response = self.client.responses.create(**kwargs)
        return json.loads(response.output_text), response.id

    def discover(self, *, language: str, weekday: str, recent_context: str) -> tuple[dict, str]:
        prompt = f"""
You are selecting a current-affairs self-study article for learners age 13+ in Taiwan.

Scheduled language: {language}
Weekday: {weekday}

Recent 4-week content context:
{recent_context}

Find 3-5 credible candidate stories. Prioritize:
1. official/original sources;
2. research institutions;
3. high-quality news;
4. diverse categories and geography.

Do not choose a story merely because it is sensational.
Avoid repeating the recent categories/topics.
For Chinese days, Taiwan topics are welcome but not mandatory.
For English days, the final article must be readable at about A2-B1/B1.

Return source URLs that can be used in verification.
"""
        return self._json(
            model=self.settings.discovery_model,
            prompt=prompt,
            schema=DISCOVERY_SCHEMA,
            name="discovery_candidates",
            web=True,
        )

    def verify_candidate(self, candidate: dict) -> tuple[dict, str]:
        prompt = f"""
Fact-check this candidate for a self-study current-affairs issue:

{json.dumps(candidate, ensure_ascii=False, indent=2)}

Rules:
- Search the web again; do not trust the candidate summary.
- Prefer official/original sources plus a strong second source.
- Verify names, dates, places, numbers, policy conditions, study design, rankings.
- Separate stable background from news facts.
- Do not rewrite may as will, association as causation, scenario as prediction.
- Critical A/B claims without enough evidence must cause fact_qa.status=BLOCK.
- If sources disagree, record an evidence conflict and shrink the claim.
- Do not invent URLs.
"""
        return self._json(
            model=self.settings.verify_model,
            prompt=prompt,
            schema=FACT_SCHEMA,
            name="verified_fact_pack",
            web=True,
        )

    def draft_structured_content(self, *, issue_id: str, language: str, fact_pack: dict, contract_text: str) -> tuple[dict, str]:
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
        # The full content contract is large and may evolve in presentation fields.
        # We deliberately use JSON object mode here and validate required V1 keys in pipeline.py.
        response = self.client.responses.create(
            model=self.settings.draft_model,
            input=prompt,
            store=False,
            text={"format": {"type": "json_object"}},
        )
        return json.loads(response.output_text), response.id

    def teaching_qa(self, structured: dict, fact_pack: dict) -> tuple[dict, str]:
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
        return self._json(
            model=self.settings.qa_model,
            prompt=prompt,
            schema=QA_SCHEMA,
            name="teaching_qa",
            web=False,
        )

    def revise_content(self, structured: dict, instructions: list[str]) -> tuple[dict, str]:
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
        response = self.client.responses.create(
            model=self.settings.draft_model,
            input=prompt,
            store=False,
            text={"format": {"type": "json_object"}},
        )
        return json.loads(response.output_text), response.id

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
        response = self.client.responses.create(
            model=self.settings.qa_model,
            input=prompt,
            store=False,
            text={"format": {"type": "json_object"}},
        )
        return json.loads(response.output_text), response.id

    def sunday_review(self, previous_six: list[dict], contract_text: str) -> tuple[dict, str]:
        prompt = f"""
Create a Sunday weekly review using ONLY the six Structured Content objects below.\nDo not search for new news and do not add new facts.\n\nV1.0 CONTRACT EXAMPLE:\n{contract_text}\n\nMOTHER DATA:\n{json.dumps(previous_six, ensure_ascii=False, indent=2)}

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
        response = self.client.responses.create(
            model=self.settings.qa_model,
            input=prompt,
            store=False,
            text={"format": {"type": "json_object"}},
        )
        return json.loads(response.output_text), response.id

    def sunday_teaching_qa(self, structured: dict, previous_six: list[dict]) -> tuple[dict, str]:
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
        return self._json(
            model=self.settings.qa_model,
            prompt=prompt,
            schema=QA_SCHEMA,
            name="sunday_teaching_qa",
            web=False,
        )

    def revise_sunday(self, structured: dict, instructions: list[str], previous_six: list[dict]) -> tuple[dict, str]:
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
        response = self.client.responses.create(
            model=self.settings.qa_model,
            input=prompt,
            store=False,
            text={"format": {"type": "json_object"}},
        )
        return json.loads(response.output_text), response.id


from __future__ import annotations

def _source_cards(structured: dict, source_records: list[dict] | None) -> list[dict]:
    source_records = source_records or []
    by_id = {str(x.get("Source_ID") or x.get("source_id")): x for x in source_records}
    out = []
    for sid in list((structured.get("provenance") or {}).get("source_ids") or [])[:3]:
        r = by_id.get(str(sid), {})
        out.append({
            "publisher": r.get("Publisher") or r.get("publisher") or str(sid),
            "date": r.get("Source_Published_Date") or r.get("published") or "",
            "title": r.get("Title") or r.get("title") or str(sid),
            "url": r.get("URL") or r.get("url") or "",
        })
    return out

def _first_checkpoint(structured: dict) -> str:
    for section in structured.get("sections") or []:
        cp = section.get("checkpoint") or {}
        if cp.get("enabled") and cp.get("prompt"):
            return str(cp.get("prompt"))
    return ""

def build_email_payload(structured: dict, source_records: list[dict] | None = None) -> dict:
    meta = structured.get("metadata") or {}
    editorial = structured.get("editorial") or {}
    language = str(meta.get("language") or "")
    common = {
        "issue_id": structured.get("issue_id"),
        "date": meta.get("publish_date"),
        "version": meta.get("version"),
        "headline": editorial.get("headline"),
        "quick_start": editorial.get("quick_summary"),
        "sources": _source_cards(structured, source_records),
    }

    if language.upper() == "REVIEW" or "week_cards" in structured:
        cards = structured.get("week_cards") or []
        events = [{"title": x.get("title"), "memory": x.get("memory")} for x in cards[:5]]
        concepts = []
        for x in cards:
            c = x.get("concept")
            if c and c not in concepts:
                concepts.append(c)
        words = [
            x.get("word")
            for x in (structured.get("recall") or {}).get("english_words", [])
            if x.get("word")
        ][:2]
        connections = structured.get("connections") or []
        return common | {
            "kind": "REVIEW",
            "events": events,
            "concepts": concepts[:3],
            "english_words": words,
            "connection": (connections[0] if connections else {}),
            "curiosity_prompt": structured.get("one_week_prompt") or structured.get("one_thing_prompt") or "",
        }

    if language.lower().startswith("en"):
        ls = structured.get("language_support") or {}
        words = [x.get("word") for x in ls.get("key_words", []) if x.get("word")][:5]
        return common | {
            "kind": "EN",
            "words": words,
            "focus_sentence": ls.get("focus_sentence") or "",
            "mini_check": _first_checkpoint(structured),
        }

    rescue = structured.get("rescue") or {}
    return common | {
        "kind": "ZH",
        "one_thing": structured.get("one_thing_prompt") or rescue.get("summary") or "",
        "mini_check": _first_checkpoint(structured),
    }

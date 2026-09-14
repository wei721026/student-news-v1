DISCOVERY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["candidates"],
    "properties": {
        "candidates": {
            "type": "array",
            "minItems": 1,
            "maxItems": 5,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "title", "language", "region", "category", "why_now",
                    "educational_value", "source_urls"
                ],
                "properties": {
                    "title": {"type": "string"},
                    "language": {"type": "string"},
                    "region": {"type": "string"},
                    "category": {"type": "string"},
                    "why_now": {"type": "string"},
                    "educational_value": {"type": "string"},
                    "source_urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1
                    }
                }
            }
        }
    }
}

FACT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "event", "why_now", "claims", "sources", "limitations",
        "do_not_overstate", "evidence_conflicts", "fact_qa"
    ],
    "properties": {
        "event": {"type": "string"},
        "why_now": {"type": "string"},
        "claims": {
            "type": "array",
            "minItems": 2,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "claim_id", "level", "text", "critical",
                    "source_ids", "verified_status"
                ],
                "properties": {
                    "claim_id": {"type": "string"},
                    "level": {"type": "string"},
                    "text": {"type": "string"},
                    "critical": {"type": "boolean"},
                    "source_ids": {"type": "array", "items": {"type": "string"}},
                    "verified_status": {"type": "string"}
                }
            }
        },
        "sources": {
            "type": "array",
            "minItems": 2,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "source_id", "source_type", "publisher", "title",
                    "url", "published", "primary"
                ],
                "properties": {
                    "source_id": {"type": "string"},
                    "source_type": {"type": "string"},
                    "publisher": {"type": "string"},
                    "title": {"type": "string"},
                    "url": {"type": "string"},
                    "published": {"type": "string"},
                    "primary": {"type": "boolean"}
                }
            }
        },
        "limitations": {"type": "array", "items": {"type": "string"}},
        "do_not_overstate": {"type": "array", "items": {"type": "string"}},
        "evidence_conflicts": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["claim", "resolution"],
                "properties": {
                    "claim": {"type": "string"},
                    "resolution": {"type": "string"}
                }
            }
        },
        "fact_qa": {
            "type": "object",
            "additionalProperties": False,
            "required": ["status", "notes"],
            "properties": {
                "status": {"type": "string", "enum": ["PASS", "BLOCK"]},
                "notes": {"type": "string"}
            }
        }
    }
}

QA_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["status", "notes", "revision_instructions"],
    "properties": {
        "status": {"type": "string", "enum": ["PASS", "REVISE", "BLOCK"]},
        "notes": {"type": "string"},
        "revision_instructions": {"type": "array", "items": {"type": "string"}}
    }
}

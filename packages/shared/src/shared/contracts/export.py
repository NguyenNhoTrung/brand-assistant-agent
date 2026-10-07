"""`python -m shared.contracts.export out.json` — JSON Schema cho json-schema-to-typescript."""

import json
import sys

from pydantic import BaseModel

from shared import contracts

MODELS: list[type[BaseModel]] = [
    contracts.JobCreate,
    contracts.JobCreated,
    contracts.JobView,
    contracts.FinalPayload,
    contracts.EventEnvelope,
    contracts.ProblemDetail,
    contracts.ConversationView,
    contracts.MessageView,
    contracts.Feedback,
    contracts.SourceView,
    contracts.KbEntry,
    contracts.IngestRequest,
]


def build() -> dict:
    defs: dict = {}
    for m in MODELS:
        schema = m.model_json_schema(ref_template="#/$defs/{model}")
        defs.update(schema.pop("$defs", {}))
        defs[m.__name__] = schema
    defs["EventType"] = {"type": "string", "enum": list(contracts.EVENT_TYPES)}
    return {
        "title": "Contracts",
        "type": "object",
        "properties": {name: {"$ref": f"#/$defs/{name}"} for name in defs},
        "$defs": defs,
    }


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "contracts.schema.json"
    with open(out, "w") as f:
        json.dump(build(), f, indent=2, ensure_ascii=False)

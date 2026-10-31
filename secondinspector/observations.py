from dataclasses import dataclass

from secondinspector.api import spark_json

KINDS = ["defect", "component_ok", "room_change", "chatter"]

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["observations"],
    "properties": {
        "observations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "turn_id", "kind", "room", "component_phrase", "defect_phrase",
                    "location_hint", "sop_section",
                ],
                "properties": {
                    "turn_id": {"type": "string"},
                    "kind": {"type": "string", "enum": KINDS},
                    "room": {"type": "string"},
                    "component_phrase": {"type": "string"},
                    "defect_phrase": {"type": "string"},
                    "location_hint": {"type": "string"},
                    "sop_section": {"type": "string"},
                },
            },
        }
    },
}

PROMPT = """You turn a home inspector's spoken narration into structured observations.
Each turn has an id, a time window, and the words spoken. For every turn, output one or more observations:
- kind: "defect" if the inspector reports a problem, "component_ok" if they say something was checked and is fine,
  "room_change" if they announce a room, area or floor, otherwise "chatter".
- room: the room or area being inspected at that moment, carried forward from earlier room_change turns ("" if unknown).
- component_phrase: the building component as a short concrete noun phrase an object detector can find,
  1-3 words, e.g. "door", "door trim", "hinge", "wall", "baseboard", "ceiling" ("" if none).
- defect_phrase: the defect as one concrete noun an object detector can find, e.g. "crack", "scuff", "stain",
  "gap", "rust", "hole" ("" if none). Never use vague words like "damage" or "issue".
- location_hint: where on the component, in the inspector's words or a short paraphrase ("" if none).
- sop_section: the InterNACHI Standards of Practice section, one of Roof, Exterior, Structure, Heating, Cooling,
  Plumbing, Electrical, Fireplace, Attic, Interior ("" for room_change or chatter).
Do not add findings the inspector did not say. If one turn mentions two separate defects, output two observations.

Turns:
"""


@dataclass
class Observation:
    turn_id: str
    kind: str
    room: str
    component_phrase: str
    defect_phrase: str
    location_hint: str
    sop_section: str
    utterance: str
    t_start: float
    t_end: float


def extract(client, turns):
    lines = [f"[{t.turn_id}] {t.start_ms / 1000:.1f}-{t.end_ms / 1000:.1f}s: {t.text}" for t in turns]
    content = [{"type": "input_text", "text": PROMPT + "\n".join(lines)}]
    result = spark_json(client, content, SCHEMA, "inspection_observations")
    return attach_turns(result["observations"], turns)


def attach_turns(items, turns):
    by_id = {t.turn_id: t for t in turns}
    observations = []
    for item in items:
        turn = by_id.get(item["turn_id"])
        if turn is None:
            continue
        observations.append(
            Observation(
                **item,
                utterance=turn.text,
                t_start=turn.start_ms / 1000,
                t_end=turn.end_ms / 1000,
            )
        )
    return observations

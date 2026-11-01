"""Coverage check: for each room, which required items the walkthrough showed, mentioned, tested or missed."""

import asyncio
import re
from collections import defaultdict
from dataclasses import dataclass

from secondinspector import align, verify
from secondinspector.api import spark_json

HOUSE = "house"
ALL_ROOMS = ("bedroom", "bathroom", "kitchen", "laundry", "garage", "hallway", "living")

# Checked in order, so "bathroom" wins for a name like "bedroom bathroom".
ROOM_WORDS = {
    "bathroom": ("bath", "powder room", "restroom", "washroom", "toilet"),
    "kitchen": ("kitchen",),
    "bedroom": ("bedroom", "nursery", "guest room"),
    "laundry": ("laundry", "utility", "mechanical"),
    "garage": ("garage",),
    "hallway": ("hall", "landing", "corridor", "stair"),
    "living": ("living", "family", "dining", "office", "den"),
}

TEST_WORDS = ("test", "tested", "testing", "trip", "tripped", "trips", "reset")
# One Spark call checks at most this many boxed frames.
MAX_IMAGES_PER_CHECK = 8


@dataclass(frozen=True)
class Item:
    key: str
    label: str
    sam_phrase: str
    sop_section: str
    rooms: tuple[str, ...]  # room types where it is required; (HOUSE,) means once per walkthrough
    keywords: tuple[str, ...]  # words that count as the inspector mentioning it
    question: str = ""  # what Spark must confirm is in SAM's box; empty skips the check
    max_tracks: int = 2


GFCI = "gfci_outlet"

CHECKLIST = [
    Item("smoke_detector", "Smoke detector", "smoke detector", "Electrical", ("bedroom", "hallway"),
         ("smoke detector", "smoke alarm"),
         "a smoke alarm or a combined smoke and carbon monoxide alarm (not a light, speaker or sprinkler)"),
    Item("co_detector", "Carbon monoxide detector", "carbon monoxide detector", "Electrical", ("bedroom", "hallway"),
         ("carbon monoxide", "co detector", "co alarm"),
         "a carbon monoxide alarm or a combined smoke and carbon monoxide alarm"),
    Item("outlet", "Outlet", "electrical outlet", "Electrical", ALL_ROOMS,
         ("outlet", "receptacle", "socket"), "an electrical wall outlet (receptacle)"),
    # SAM finds every outlet; Spark then decides which ones are GFCIs from the TEST/RESET buttons.
    Item(GFCI, "GFCI outlet", "electrical outlet", "Electrical", ("kitchen", "bathroom", "laundry", "garage"),
         ("gfci", "gfi", "ground fault"), "an electrical wall outlet (receptacle)", max_tracks=4),
    Item("exhaust_fan", "Exhaust fan", "exhaust fan", "Attic", ("bathroom",), ("exhaust", "fan"),
         "a bathroom exhaust fan grille (not a light, or a heating/cooling supply register)"),
    Item("water_heater", "Water heater", "water heater", "Plumbing", ("laundry", "garage"),
         ("water heater", "hot water heater"), "a water heater tank or tankless water heater"),
    Item("pressure_relief_valve", "Pressure relief valve", "pressure relief valve", "Plumbing", ("laundry", "garage"),
         ("pressure relief valve", "temperature pressure relief", "tpr valve", "t&p valve"),
         "a water heater temperature and pressure relief valve, not an ordinary pipe fitting"),
    Item("window", "Window", "window", "Interior", ALL_ROOMS, ("window",), "a window"),
    Item("door", "Door", "door", "Interior", ALL_ROOMS, ("door",), "a door"),
    Item("sink", "Sink", "sink", "Plumbing", ("kitchen", "bathroom", "laundry"), ("sink", "basin"),
         "a sink basin, not a toilet or bathtub"),
    Item("toilet", "Toilet", "toilet", "Plumbing", ("bathroom",), ("toilet", "commode"),
         "a toilet, not a sink or bathtub"),
    Item("ceiling", "Ceiling looked at", "ceiling", "Interior", ALL_ROOMS, ("ceiling",)),
    Item("electrical_panel", "Electrical panel", "electrical panel", "Electrical", (HOUSE,), ("panel", "breaker"),
         "an electrical panel or breaker box"),
]

CHECK_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["checks"],
    "properties": {
        "checks": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["index", "verdict", "gfci", "note"],
                "properties": {
                    "index": {"type": "integer"},
                    "verdict": {"type": "string", "enum": ["yes", "no", "unclear"]},
                    "gfci": {"type": "string", "enum": ["yes", "no", "unclear", "n/a"]},
                    "note": {"type": "string"},
                },
            },
        }
    },
}

CHECK_PROMPT = """You are checking an object detector's work for a home inspector. Each image has a red box where
the detector found something. For each image, answer whether the object inside the red box is what is asked.
- verdict: "yes" if it clearly is, "no" if it is clearly something else, "unclear" if the box is too small,
  blurry or ambiguous to tell.
- gfci: for electrical outlets only, "yes" if TEST and RESET buttons are visible on that outlet, "no" if it is
  clearly a standard outlet without them, "unclear" if you cannot tell; "n/a" for anything that is not an outlet.
- note: a few words on what is in the box, for a human to review.
Return one check per image, using the image's index.

{questions}"""

FLAG_NOTE = ("Outlet without visible TEST/RESET buttons in a room that needs GFCI protection; "
             "confirm whether an upstream GFCI outlet or breaker protects it.")


@dataclass
class Room:
    name: str
    type: str
    t_start: float
    t_end: float


def has_word(text, words):
    text = text.lower()
    return any(re.search(rf"\b{re.escape(word)}\b", text) for word in words)


def room_type(name):
    name = name.lower()
    for kind, words in ROOM_WORDS.items():
        if any(re.search(rf"\b{re.escape(word)}", name) for word in words):
            return kind
    return "other"


def rooms_from(observed, duration, override=None):
    """Split the clip into rooms wherever the narration's room changes."""
    if override:
        return [Room(override, room_type(override), 0.0, duration)]
    rooms = []
    for observation in sorted(observed, key=lambda o: o.t_start):
        name = observation.room.strip()
        if not name or (rooms and rooms[-1].name.lower() == name.lower()):
            continue
        start = observation.t_start if rooms else 0.0
        if rooms:
            rooms[-1].t_end = start
        rooms.append(Room(name, room_type(name), start, duration))
    return rooms or [Room("", "other", 0.0, duration)]


def room_at(rooms, t):
    for room in rooms:
        if room.t_start <= t < room.t_end:
            return room
    return rooms[-1]


def mentions(item, room, observed):
    said = {}
    for observation in observed:
        if room.t_start <= observation.t_start < room.t_end and has_word(observation.utterance, item.keywords):
            said[observation.turn_id] = observation.utterance
    return list(said.values())


def top_tracks(detections, t_start, t_end, limit, fps=2):
    """The best frame of each of the `limit` objects SAM tracked longest inside the window."""
    lo, hi = align.to_frame(t_start, fps), align.to_frame(t_end, fps)
    tracks = defaultdict(list)
    for detection in detections:
        if lo <= detection.frame <= hi:
            tracks[detection.object_id].append(detection)
    ranked = sorted(
        tracks.values(), key=lambda hits: (len(hits), max(d.confidence or 0 for d in hits)), reverse=True
    )
    return [max(hits, key=lambda d: d.confidence or 0) for hits in ranked[:limit]]


def status(seen, said, tested):
    if tested:
        return "tested"
    if seen and said:
        return "inspected"
    if seen:
        return "seen_not_mentioned"
    if said:
        return "mentioned_not_seen"
    return "not_seen"


def check_candidates(client, candidates):
    """Ask Spark, in batches, whether each boxed object is what SAM was prompted for."""
    results = []
    for start in range(0, len(candidates), MAX_IMAGES_PER_CHECK):
        batch = candidates[start:start + MAX_IMAGES_PER_CHECK]
        questions = "\n".join(f"[{i}] Is the object in the red box {c['question']}?" for i, c in enumerate(batch))
        content = [{"type": "input_text", "text": CHECK_PROMPT.format(questions=questions)}]
        for i, candidate in enumerate(batch):
            content.append({"type": "input_text", "text": f"Image [{i}]"})
            content.append(verify.image_part(candidate["evidence_path"]))
        checks = {c["index"]: c for c in spark_json(client, content, CHECK_SCHEMA, "coverage_check")["checks"]}
        missing = {"verdict": "unclear", "gfci": "n/a", "note": "not checked"}
        results += [{k: v for k, v in checks.get(i, missing).items() if k != "index"} for i in range(len(batch))]
    return results


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "room"


def check_room(inspector, room, items, detections, observed):
    candidates = []
    for item in items:
        for detection in top_tracks(detections[item.key], room.t_start, room.t_end, item.max_tracks):
            candidates.append({
                "item": item.key,
                "question": item.question,
                "frame": detection.frame,
                "box": list(detection.box),
                "confidence": detection.confidence,
                "sam_object_id": detection.object_id,
            })
    for i, candidate in enumerate(candidates):
        stem = f"coverage-{slug(room.name)}-{candidate['item']}-{i}"
        [image] = verify.render(inspector.proxy, [candidate["frame"]], candidate["box"], inspector.evidence_dir, stem)
        candidate["evidence_path"] = str(image)
    to_check = [c for c in candidates if c["question"]]
    for candidate, result in zip(to_check, check_candidates(inspector.spark, to_check)):
        candidate.update(result)
    for candidate in candidates:
        if not candidate["question"]:
            candidate.update(verdict="yes", gfci="n/a", note="presence only; not checked by Spark")

    report, flags = [], []
    for item in items:
        mine = [c for c in candidates if c["item"] == item.key]
        expected = room.type in item.rooms
        if item.key == GFCI:
            seen = [c for c in mine if c["verdict"] == "yes" and c["gfci"] == "yes"]
            if expected:
                flags += [{**c, "note": FLAG_NOTE} for c in mine if c["verdict"] == "yes" and c["gfci"] == "no"]
        else:
            seen = [c for c in mine if c["verdict"] == "yes"]
        said = mentions(item, room, observed)
        tested = item.key == GFCI and any(has_word(s, TEST_WORDS) for s in said)
        if not (expected or seen or said):
            continue
        report.append({
            "item": item.key,
            "label": item.label,
            "sop_section": item.sop_section,
            "expected": expected,
            "status": status(bool(seen), bool(said), tested),
            "evidence": seen[0] if seen else None,
            "mentions": said,
            "candidates": mine,
        })
    return {
        "room": room.name,
        "type": room.type,
        "t_start": room.t_start,
        "t_end": room.t_end,
        "items": report,
        "gfci_flags": flags,
    }


async def check(inspector, observed, rooms):
    """Run SAM once per checklist item, then check every room (and the house as a whole) in parallel."""
    house = Room(HOUSE, HOUSE, 0.0, rooms[-1].t_end)
    present = {room.type for room in rooms}
    # An unknown room still gets every item looked for, so what was seen is reported.
    items = [i for i in CHECKLIST if HOUSE in i.rooms or "other" in present or present & set(i.rooms)]
    found = await asyncio.gather(*(inspector.detections(item.sam_phrase) for item in items))
    detections = {item.key: hits for item, hits in zip(items, found)}
    scopes = [(room, [i for i in items if HOUSE not in i.rooms]) for room in rooms]
    scopes.append((house, [i for i in items if HOUSE in i.rooms]))
    return list(await asyncio.gather(*(
        asyncio.to_thread(check_room, inspector, room, scope, detections, observed)
        for room, scope in scopes if scope
    )))

import argparse
import asyncio
import hashlib
import json
import shutil
from dataclasses import asdict
from pathlib import Path

from secondinspector import (
    alarm,
    align,
    api,
    asr,
    coverage,
    media,
    observations,
    sam,
    verify,
)

# A box covering most of the frame ("wall", "door") does not localise anything useful.
MAX_BOX_FRACTION = 0.4
# More parallel SAM streams than this started timing out.
SAM_CONCURRENCY = 2
SAM_ATTEMPTS = 3

UNSPOKEN_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["candidates"],
    "properties": {
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "description", "component_phrase", "defect_phrase", "t_start", "t_end",
                ],
                "properties": {
                    "description": {"type": "string"},
                    "component_phrase": {"type": "string"},
                    "defect_phrase": {"type": "string"},
                    "t_start": {"type": "number"},
                    "t_end": {"type": "number"},
                },
            },
        }
    },
}

UNSPOKEN_PROMPT = """Act as a home inspector's second pair of eyes reviewing this walkthrough video.
List visible candidates for human review: cracks, separations at trim joints, gaps, scuffs, stains,
water marks, discoloured patches, rust, holes or damage on walls, doors, trim, floors and ceilings.
For each candidate give:
- description: what is visible and where, without declaring a defect.
- component_phrase: the component as a 1-3 word concrete noun phrase, e.g. "door trim", "wall", "hinge".
- defect_phrase: one concrete noun an object detector can find, e.g. "crack", "scuff", "stain", "gap".
- t_start, t_end: when it is visible, in seconds from the start of the video.
Include faint or ambiguous candidates; each one is checked again later. Skip uniform door clearance gaps,
reflections and shadows, and anything that is not part of the building: rugs, mats, furniture, shoes and
other belongings. If nothing is visible, return an empty list."""

MATCH_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["matches"],
    "properties": {
        "matches": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["candidate", "spoken"],
                "properties": {"candidate": {"type": "integer"}, "spoken": {"type": "integer"}},
            },
        }
    },
}

MATCH_PROMPT = """An inspector narrated findings during a walkthrough, and a reviewer listed visual candidates.
For each candidate, give the index of the spoken finding that describes the same physical issue (same component
and same spot), or -1 if the inspector never mentioned it. Times are seconds in the same video.

Spoken findings:
{spoken}

Candidates:
{candidates}"""


class Inspector:
    """Shared state for one clip: the uploaded proxy, cached SAM runs and output folders."""

    def __init__(self, client, spark, file_id, proxy, out):
        self.client = client
        self.spark = spark
        self.file_id = file_id
        self.proxy = proxy
        self.size = media.frame_size(proxy)
        self.video_key = hashlib.sha1(Path(proxy).read_bytes()).hexdigest()[:12]
        self.sam_dir = out / "sam"
        self.evidence_dir = out / "evidence"
        self.sam_runs = {}
        self.sam_slots = asyncio.Semaphore(SAM_CONCURRENCY)

    def detections(self, phrase):
        # One SAM run per phrase, shared by every finding that asks for it.
        if phrase not in self.sam_runs:
            self.sam_runs[phrase] = asyncio.ensure_future(self.segment(phrase))
        return self.sam_runs[phrase]

    async def segment(self, phrase):
        async with self.sam_slots:
            # SAM streams sometimes drop mid-response; one reset should not sink the whole clip.
            for attempt in range(SAM_ATTEMPTS):
                try:
                    return await sam.run_concept(
                        self.client, self.file_id, phrase, self.sam_dir, video_key=self.video_key
                    )
                except Exception:
                    if attempt == SAM_ATTEMPTS - 1:
                        raise
                    await asyncio.sleep(2 ** attempt)

    async def find_evidence(self, item, stem):
        """Try the defect phrase, then the component phrase; keep the first box Spark agrees with."""
        for phrase in dict.fromkeys(p for p in (item["defect_phrase"], item["component_phrase"]) if p):
            located = align.locate(await self.detections(phrase), item["t_start"], item["t_end"])
            if located is None or align.box_fraction(located.box, self.size) > MAX_BOX_FRACTION:
                continue
            finding = await asyncio.to_thread(self.evidence, item, located, stem)
            if finding["inside_box"] and finding["status"] != "not_visible":
                return finding
        return await asyncio.to_thread(self.evidence, item, None, stem)

    def evidence(self, item, located, stem):
        frames = verify.keyframes(located, item["t_start"], item["t_end"])
        box = located.box if located else None
        images = verify.render(self.proxy, frames, box, self.evidence_dir, stem)
        claim = item.get("utterance") or item.get("description") or claim_text(item)
        result = verify.check(self.spark, claim, images, boxed=box is not None)
        return {
            **item,
            "frame": frames[result["best_image"]],
            "box": list(box) if box else None,
            "sam_phrase": located.phrase if located else None,
            "sam_object_id": located.object_id if located else None,
            "sam_frames": located.frames if located else [],
            "confidence": located.confidence if located else None,
            "status": result["status"],
            "inside_box": result["inside_box"],
            "description": result["description"],
            "evidence_path": str(images[result["best_image"]]),
        }


def claim_text(item):
    parts = [item.get("defect_phrase"), "on the" if item.get("component_phrase") else "",
             item.get("component_phrase"), f"({item['location_hint']})" if item.get("location_hint") else ""]
    return " ".join(p for p in parts if p) or item.get("utterance", "")


def covered(candidate, spoken, slack=5.0):
    for finding in spoken:
        same_track = (
            candidate["sam_phrase"] is not None
            and candidate["sam_phrase"] == finding["sam_phrase"]
            and candidate["sam_object_id"] == finding["sam_object_id"]
        )
        if same_track:
            return True
        near = (candidate["t_start"] <= finding["t_end"] + slack
                and finding["t_start"] <= candidate["t_end"] + slack)
        if near and candidate["box"] and finding["box"] and align.boxes_overlap(candidate["box"], finding["box"]):
            return True
    return False


def spoken_matches(spark, spoken, candidates):
    """Ask Spark which candidates repeat something the inspector already said."""
    if not spoken or not candidates:
        return {}
    spoken_lines = [
        f"[{i}] {f['t_start']:.1f}-{f['t_end']:.1f}s said: \"{f['utterance']}\"; seen: {f['description']}"
        for i, f in enumerate(spoken)
    ]
    candidate_lines = [
        f"[{i}] {c['t_start']:.1f}-{c['t_end']:.1f}s {c['description']}" for i, c in enumerate(candidates)
    ]
    prompt = MATCH_PROMPT.format(spoken="\n".join(spoken_lines), candidates="\n".join(candidate_lines))
    result = api.spark_json(spark, [{"type": "input_text", "text": prompt}], MATCH_SCHEMA, "spoken_matches")
    return {
        m["candidate"]: m["spoken"]
        for m in result["matches"]
        if 0 <= m["candidate"] < len(candidates) and 0 <= m["spoken"] < len(spoken)
    }


async def run(clip, out_root="data/processed", room=None):
    clip = Path(clip)
    out = Path(out_root) / clip.stem
    shutil.rmtree(out / "evidence", ignore_errors=True)
    proxy = media.make_proxy(clip, out / "proxy.mp4")
    wav = media.make_wav(clip, out / "audio.wav")

    payload = await asyncio.to_thread(asr.transcribe, wav)
    (out / "asr.json").write_text(json.dumps(payload, indent=2) + "\n")
    turns = asr.parse_turns(payload)

    spark = api.sync_client()
    async with api.async_client() as client:
        file_id = await sam.upload_video(client, proxy)
        inspector = Inspector(client, spark, file_id, proxy, out)
        # Narration parsing and the silent video review do not depend on each other.
        observed, review = await asyncio.gather(
            asyncio.to_thread(observations.extract, spark, turns),
            asyncio.to_thread(
                api.spark_json,
                spark,
                [{"type": "input_text", "text": UNSPOKEN_PROMPT}, {"type": "input_video", "file_id": file_id}],
                UNSPOKEN_SCHEMA,
                "unspoken_candidates",
            ),
        )
        (out / "observations.json").write_text(json.dumps([asdict(o) for o in observed], indent=2) + "\n")
        rooms = coverage.rooms_from(observed, media.duration(proxy), room)
        defects = [{**asdict(o), "source": "spoken"} for o in observed if o.kind == "defect"]
        reviewed = [
            {**c, "room": coverage.room_at(rooms, c["t_start"]).name, "utterance": "", "source": "unspoken"}
            for c in review["candidates"]
        ]
        # The coverage check shares the SAM cache with the defect search and runs alongside it.
        found, covered_rooms = await asyncio.gather(
            asyncio.gather(
                *(inspector.find_evidence(item, f"spoken-{i}") for i, item in enumerate(defects)),
                *(inspector.find_evidence(item, f"unspoken-{i}") for i, item in enumerate(reviewed)),
            ),
            coverage.check(inspector, observed, rooms),
        )
        await alarm.audit_rooms(inspector, client, clip, covered_rooms)
    (out / "coverage.json").write_text(json.dumps(covered_rooms, indent=2) + "\n")
    spoken, candidates = list(found[: len(defects)]), list(found[len(defects):])

    visible = [c for c in candidates if c["status"] != "not_visible" and not covered(c, spoken)]
    matches = spoken_matches(spark, spoken, visible)
    for index, candidate in enumerate(visible):
        candidate["matches_spoken"] = matches.get(index)
    unspoken = [c for c in visible if c["matches_spoken"] is None]
    findings = {
        "clip": str(clip),
        "transcript": payload.get("transcript", ""),
        "spoken": spoken,
        "unspoken": unspoken,
        "unspoken_covered_or_rejected": [c for c in candidates if c not in unspoken],
        "coverage": covered_rooms,
    }
    (out / "findings.json").write_text(json.dumps(findings, indent=2) + "\n")
    return findings


def main():
    parser = argparse.ArgumentParser(description="Narration-guided Spark + SAM inspection pass")
    parser.add_argument("clip")
    parser.add_argument("--out", default="data/processed")
    parser.add_argument("--room", help="treat the whole clip as this room, e.g. bedroom, instead of using narration")
    args = parser.parse_args()
    findings = asyncio.run(run(args.clip, args.out, args.room))
    for finding in findings["spoken"] + findings["unspoken"]:
        print(
            f"[{finding['source']:8}] {finding['t_start']:5.1f}-{finding['t_end']:5.1f}s "
            f"{finding['status']:11} frame {finding['frame']:3} box {finding['box']} "
            f"{finding['utterance'] or finding['description'][:80]}"
        )
        print(f"           evidence: {finding['evidence_path']}")
    print_coverage(findings["coverage"])
    print(f"Wrote {Path(args.out) / Path(args.clip).stem / 'findings.json'}")


def print_coverage(rooms):
    print("\nCoverage")
    for room in rooms:
        print(f"  {room['room'] or 'unknown room'} ({room['type']}) {room['t_start']:.1f}-{room['t_end']:.1f}s")
        for item in room["items"]:
            needed = "required" if item["expected"] else ""
            evidence = item["evidence"]["evidence_path"] if item["evidence"] else ""
            print(f"    {item['status']:19} {item['label']:18} {needed:8} {evidence}")
            if item.get("test_audit"):
                tests = ", ".join(f"{t['test']} {t['status']}" for t in item["test_audit"]["tests"])
                print(f"                        test audit ({item['test_audit']['procedure_source']}): {tests}")
        for flag in room["gfci_flags"]:
            print(f"    gfci_flag           frame {flag['frame']:3} {flag['note']}")
            print(f"                        evidence: {flag['evidence_path']}")


if __name__ == "__main__":
    main()

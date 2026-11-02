"""Smoke alarm agent: find the alarm, read its label, look up its manual, and audit the test the inspector ran."""

import argparse
import asyncio
import base64
import json
import re
from pathlib import Path
from urllib.parse import urlparse

import httpx
import openai

from secondinspector import api, media, sam, verify

SAM_PHRASE = "smoke detector"
MAX_VIEWS = 4
MAX_MANUAL_TRIES = 3
# Spark's inline file limit is 50 MB.
MAX_PDF_BYTES = 45_000_000

IDENTIFY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["brand", "model", "kind", "power", "voice", "label_text", "features", "confidence"],
    "properties": {
        "brand": {"type": "string"},
        "model": {"type": "string"},
        "kind": {"type": "string", "enum": ["smoke", "co", "smoke_co", "heat", "unknown"]},
        "power": {"type": "string", "enum": ["hardwired", "battery", "unknown"]},
        "voice": {"type": "string", "enum": ["yes", "no", "unknown"]},
        "label_text": {"type": "string"},
        "features": {"type": "string"},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    },
}

IDENTIFY_PROMPT = """These images show one smoke or carbon monoxide alarm from a home inspection walkthrough.
- label_text: every printed word, logo and number you can read, exactly as printed.
- brand, model: as printed; "unknown" if not readable. Never guess a model number from the shape.
- kind: "smoke_co" only if the label or a CO marking shows it is combined; "unknown" if you cannot tell.
- power: "hardwired" if a wired base or interconnect is visible, "battery" if clearly battery-only, else "unknown".
- voice: "yes" if the label mentions voice or talking alerts.
- features: a short visual description (shape, buttons, vents, LEDs, nearby modules) to help find the model.
- confidence: in the brand and kind."""

SEARCH_PROMPT = """Find the official manufacturer user manual (PDF) for this home smoke/CO alarm, preferably on the
manufacturer's own site. Then summarise the test procedure it gives: how to start the test and every signal
(voice message, beep pattern, LED) the alarm should produce for each part of the test.
Alarm: {description}"""

PROCEDURE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["manual_models", "tests", "notes"],
    "properties": {
        "manual_models": {"type": "string"},
        "tests": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "how", "expected_signals", "required"],
                "properties": {
                    "name": {"type": "string"},
                    "how": {"type": "string"},
                    "expected_signals": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["kind", "detail"],
                            "properties": {
                                "kind": {"type": "string", "enum": ["voice", "beep_pattern", "led", "chirp"]},
                                "detail": {"type": "string"},
                            },
                        },
                    },
                    "required": {"type": "boolean"},
                },
            },
        },
        "notes": {"type": "string"},
    },
}

PROCEDURE_PROMPT = """From {source}, list what a home inspector's push-button test of this alarm must show.
Alarm as identified: {description}
- manual_models: the model numbers the manual covers ("" if not from a manual).
- tests: one entry per distinct part of the test sequence a user should hear, e.g. a "fire" (smoke) part and a
  "co" part for a combination alarm. "how" says how to start it (button, press or hold, how long).
  expected_signals lists each voice message (exact words), beep pattern (e.g. "temporal-3: 3 beeps then pause"),
  LED and chirp. required is true if the manual expects it in every test.
- notes: anything else that affects judging a test, such as interconnected alarms also sounding."""

EVENTS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["events"],
    "properties": {
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["t_start", "t_end", "source", "kind", "detail"],
                "properties": {
                    "t_start": {"type": "number"},
                    "t_end": {"type": "number"},
                    "source": {"type": "string", "enum": ["alarm", "inspector"]},
                    "kind": {
                        "type": "string",
                        "enum": ["voice", "beep_pattern", "chirp", "led", "button_press", "speech"],
                    },
                    "detail": {"type": "string"},
                },
            },
        }
    },
}

EVENTS_PROMPT = """Watch and listen to this home inspection clip of a ceiling smoke/CO alarm.
List, with start and end seconds, everything relevant to an alarm test:
- source "alarm": spoken voice messages (exact words), beep patterns (count beeps per group: 3 beeps then a
  pause is "temporal-3", 4 beeps then a pause is "temporal-4"), single chirps, and LED colour changes.
- source "inspector": the inspector's speech, and any visible press of the alarm's button (say press or hold).
Say "unclear" in detail when the sound is masked. If no test happens, list only what is there."""

AUDIT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["tests", "summary"],
    "properties": {
        "tests": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["test", "status", "t_start", "t_end", "heard", "missing"],
                "properties": {
                    "test": {"type": "string"},
                    "status": {"type": "string", "enum": ["done", "partial", "not_done"]},
                    "t_start": {"type": "number"},
                    "t_end": {"type": "number"},
                    "heard": {"type": "string"},
                    "missing": {"type": "string"},
                },
            },
        },
        "summary": {"type": "string"},
    },
}

AUDIT_PROMPT = """You audit a home inspector's smoke alarm test against the test procedure for that alarm.
Procedure (from {source}):
{procedure}

What happened in the clip:
{events}

For every test in the procedure, using its exact name:
- status: judge each part by the signals that tell it apart, its beep pattern and its voice message (if it has
  one). "done" if both were heard, "partial" if only one was, "not_done" if that part never sounded.
  A pattern listed more than once is satisfied when it was heard repeating. Brief confirmation chirps and LED
  changes are easy for a phone to miss: list them under missing but do not lower the status for them.
- t_start, t_end: when that part sounded (-1 if not done).
- heard: the matching signals. missing: expected signals that were not heard ("" if none).
summary: one or two sentences for the inspection report. Mention technique that differs from the procedure
(for example holding the button instead of a quick press) without changing any status for it."""


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def describe(device):
    parts = [device["brand"], device["model"], device["kind"].replace("_", " + "), f"power: {device['power']}",
             f"voice alerts: {device['voice']}", f"label text: {device['label_text']}", device["features"]]
    return "; ".join(p for p in parts if p and p != "unknown")


def area(box):
    return (box[2] - box[0]) * (box[3] - box[1])


def best_views(detections, limit=MAX_VIEWS, min_gap=4):
    """The frames where the alarm looks biggest (closest), spread out so they are not near-duplicates."""
    largest = {}
    for detection in detections:
        if detection.frame not in largest or area(detection.box) > area(largest[detection.frame].box):
            largest[detection.frame] = detection
    picks = []
    for detection in sorted(largest.values(), key=lambda d: area(d.box), reverse=True):
        if all(abs(detection.frame - p.frame) >= min_gap for p in picks):
            picks.append(detection)
        if len(picks) == limit:
            break
    return picks


async def find_alarm(inspector, stem):
    """Crops of the alarm from the frames where SAM sees it biggest; whole frames if SAM finds none."""
    views = best_views(await inspector.detections(SAM_PHRASE))
    if not views:
        frames = media.duration(inspector.proxy) * 2
        return [{"frame": f, "box": None, "path": str(media.extract_frame(
            inspector.proxy, f, inspector.evidence_dir / f"{stem}-whole-{f}.jpg"))}
            for f in sorted({int(frames * k / (MAX_VIEWS + 1)) for k in range(1, MAX_VIEWS + 1)})]
    crops = []
    for i, detection in enumerate(views):
        raw = media.extract_frame(inspector.proxy, detection.frame, inspector.evidence_dir / f"{stem}-{i}-raw.jpg")
        crops.append({
            "frame": detection.frame,
            "box": list(detection.box),
            "path": str(media.crop(raw, detection.box, inspector.size, inspector.evidence_dir / f"{stem}-{i}.jpg")),
        })
    return crops


def identify(spark, images, events=()):
    sounds = [f"{e['kind']}: {e['detail']}" for e in events if e["source"] == "alarm"]
    note = ("\nThe alarm was also heard producing: " + "; ".join(sounds) +
            "\nUse what it says (e.g. fire or carbon monoxide warnings) to judge kind and voice.") if sounds else ""
    content = [{"type": "input_text", "text": IDENTIFY_PROMPT + note}]
    content += [verify.image_part(image) for image in images]
    return api.spark_json(spark, content, IDENTIFY_SCHEMA, "alarm_identity")


def rank_manuals(urls, brand):
    """PDFs on the manufacturer's own domain first, then other PDFs."""
    pdfs = [url for url in urls if urlparse(url).path.lower().endswith(".pdf")]
    brand = slug(brand).replace("-", "")
    own = [url for url in pdfs if brand and brand in urlparse(url).netloc.replace("-", "")]
    return own + [url for url in pdfs if url not in own]


def find_manual(spark, device):
    answer, urls = api.spark_search(spark, SEARCH_PROMPT.format(description=describe(device)))
    return {"ranked": rank_manuals(urls, device["brand"]), "candidates": urls[:10], "search_answer": answer}


def download(url, manuals_dir):
    """Fetch the PDF ourselves: manufacturer sites often block Spark's fetcher through robots.txt."""
    target = Path(manuals_dir) / f"{slug(Path(urlparse(url).path).stem)[:80]}.pdf"
    if not target.exists():
        response = httpx.get(url, timeout=60, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        if not response.content.startswith(b"%PDF") or len(response.content) > MAX_PDF_BYTES:
            raise ValueError(f"not a usable PDF: {url}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(response.content)
    return target


def pdf_part(path):
    data = base64.b64encode(Path(path).read_bytes()).decode("ascii")
    return {"type": "input_file", "filename": Path(path).name, "file_data": f"data:application/pdf;base64,{data}"}


def test_procedure(spark, device, manual_urls, manuals_dir):
    """Read the procedure from the first manual that downloads and parses; else Spark's knowledge, unverified."""
    prompt = PROCEDURE_PROMPT.format(source="the attached manufacturer manual", description=describe(device))
    for url in manual_urls[:MAX_MANUAL_TRIES]:
        try:
            content = [{"type": "input_text", "text": prompt}, pdf_part(download(url, manuals_dir))]
            return {**api.spark_json(spark, content, PROCEDURE_SCHEMA, "alarm_procedure"),
                    "source": "manual", "source_url": url}
        except (httpx.HTTPError, ValueError, openai.APIError, RuntimeError):
            continue
    prompt = PROCEDURE_PROMPT.format(source="your general knowledge of this kind of alarm (no manual was available)",
                                     description=describe(device))
    return {**api.spark_json(spark, [{"type": "input_text", "text": prompt}], PROCEDURE_SCHEMA, "alarm_procedure"),
            "source": "spark_knowledge", "source_url": None}


def lookup(spark, device, manuals_dir):
    """The manual and procedure for this alarm, cached per brand/model/kind so repeat runs skip the search."""
    key = slug(" ".join([device["brand"], device["model"], device["kind"], device["voice"]])) or "unknown"
    cache = Path(manuals_dir) / f"{key}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    manual = find_manual(spark, device) if device["brand"] != "unknown" else {"ranked": [], "candidates": []}
    entry = {"manual": manual, "procedure": test_procedure(spark, device, manual["ranked"], manuals_dir)}
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(entry, indent=2) + "\n")
    return entry


def heard(spark, video_id):
    content = [{"type": "input_text", "text": EVENTS_PROMPT}, {"type": "input_video", "file_id": video_id}]
    return api.spark_json(spark, content, EVENTS_SCHEMA, "alarm_events")["events"]


def audit(spark, procedure, events):
    source = "the manufacturer manual" if procedure["source"] == "manual" else "general knowledge, unverified"
    lines = [f"{e['t_start']:.1f}-{e['t_end']:.1f}s {e['source']} {e['kind']}: {e['detail']}" for e in events]
    prompt = AUDIT_PROMPT.format(
        source=source,
        procedure=json.dumps(procedure["tests"], indent=1),
        events="\n".join(lines) or "(nothing)",
    )
    result = api.spark_json(spark, [{"type": "input_text", "text": prompt}], AUDIT_SCHEMA, "alarm_audit")
    answers = {a["test"].lower(): a for a in result["tests"]}
    tests = []
    for test in procedure["tests"]:
        answer = answers.get(test["name"].lower()) or {
            "test": test["name"], "status": "not_done", "t_start": -1, "t_end": -1, "heard": "", "missing": "all",
        }
        tests.append({**answer, "test": test["name"], "required": test["required"]})
    return {
        "tests": tests,
        "exhaustive": bool(tests) and all(t["status"] == "done" for t in tests if t["required"]),
        "pressed": any(e["kind"] == "button_press" for e in events),
        "summary": result["summary"],
    }


def in_window(events, t_start, t_end, slack=2.0):
    return [e for e in events if e["t_end"] >= t_start - slack and e["t_start"] <= t_end + slack]


def audited_status(outcome):
    if outcome["exhaustive"]:
        return "tested"
    if any(t["status"] != "not_done" for t in outcome["tests"]):
        return "test_incomplete"
    return None


async def audit_rooms(inspector, client, clip, rooms, manuals_dir="data/manuals"):
    """For the main pipeline: audit the alarm test in every room where coverage confirmed a smoke detector."""
    targets = [(room, item) for room in rooms for item in room["items"]
               if item["item"] == "smoke_detector" and item["evidence"]]
    if not targets:
        return
    video_id = await sam.upload_video(client, clip)
    events = await asyncio.to_thread(heard, inspector.spark, video_id)
    views = await find_alarm(inspector, "alarm")
    device = await asyncio.to_thread(identify, inspector.spark, [v["path"] for v in views], events)
    entry = await asyncio.to_thread(lookup, inspector.spark, device, manuals_dir)
    for room, item in targets:
        mine = in_window(events, room["t_start"], room["t_end"])
        outcome = await asyncio.to_thread(audit, inspector.spark, entry["procedure"], mine)
        item["test_audit"] = {
            "device": device,
            "procedure_source": entry["procedure"]["source"],
            "manual_url": entry["procedure"]["source_url"],
            "events": mine,
            **outcome,
        }
        item["status"] = audited_status(outcome) or item["status"]


async def run(clips, out_root="data/processed", manuals_dir="data/manuals"):
    from secondinspector.pipeline import Inspector

    clips = [Path(clip) for clip in clips]
    spark = api.sync_client()
    async with api.async_client() as client:
        inspectors = []
        for clip in clips:
            out = Path(out_root) / clip.stem
            proxy = media.make_proxy(clip, out / "proxy.mp4")
            inspectors.append(Inspector(client, spark, await sam.upload_video(client, proxy), proxy, out))
        views = [crop for inspector in inspectors for crop in await find_alarm(inspector, "alarm")]
        # The proxy has no sound, so listening uses the original clip. What the alarm says helps identify it.
        video_ids = [await sam.upload_video(client, clip) for clip in clips]
        events = await asyncio.gather(*(asyncio.to_thread(heard, spark, vid) for vid in video_ids))
        device = await asyncio.to_thread(identify, spark, [v["path"] for v in views], [e for es in events for e in es])
        entry = await asyncio.to_thread(lookup, spark, device, manuals_dir)
        audits = await asyncio.gather(*(asyncio.to_thread(audit, spark, entry["procedure"], e) for e in events))
    results = []
    for clip, inspector, clip_events, clip_audit in zip(clips, inspectors, events, audits):
        result = {
            "clip": str(clip),
            "device": device,
            "views": views,
            "manual": entry["manual"],
            "procedure": entry["procedure"],
            "events": clip_events,
            "audit": clip_audit,
        }
        (inspector.sam_dir.parent / "alarm.json").write_text(json.dumps(result, indent=2) + "\n")
        results.append(result)
    return results


def print_result(result):
    device, procedure, outcome = result["device"], result["procedure"], result["audit"]
    print(f"\n{result['clip']}")
    print(f"  alarm: {device['brand']} {device['model']} ({device['kind']}, {device['power']}, "
          f"voice {device['voice']}, confidence {device['confidence']})")
    source = procedure["source_url"] or "Spark knowledge (unverified, no manual found)"
    print(f"  procedure: {procedure['manual_models'] or '-'} from {source}")
    print(f"  button pressed: {'yes' if outcome['pressed'] else 'no'}")
    for test in outcome["tests"]:
        when = f"{test['t_start']:.1f}-{test['t_end']:.1f}s" if test["t_start"] >= 0 else ""
        print(f"    {test['status']:9} {test['test']:12} {when:12} {test['heard']}")
        if test["missing"]:
            print(f"              missing: {test['missing']}")
    print(f"  exhaustive: {'yes' if outcome['exhaustive'] else 'no'}. {outcome['summary']}")


def main():
    parser = argparse.ArgumentParser(description="Identify a smoke alarm, find its manual and audit the test")
    parser.add_argument("clips", nargs="+", help="clips of the same alarm; each one's test is audited")
    parser.add_argument("--out", default="data/processed")
    parser.add_argument("--manuals", default="data/manuals")
    args = parser.parse_args()
    for result in asyncio.run(run(args.clips, args.out, args.manuals)):
        print_result(result)


if __name__ == "__main__":
    main()

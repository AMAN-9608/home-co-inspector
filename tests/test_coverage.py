import asyncio
from pathlib import Path

from secondinspector import coverage, sam
from secondinspector.observations import Observation


def said(t, text, room="", turn_id=None, kind="chatter"):
    return Observation(turn_id or f"t{t}", kind, room, "", "", "", "", text, t, t + 1.0)


def detection(frame, object_id="0", confidence=0.5, phrase="smoke detector"):
    return sam.Detection(phrase, frame, object_id, (10, 10, 50, 50), confidence)


def test_room_type_from_spoken_names():
    assert coverage.room_type("Master Bedroom") == "bedroom"
    assert coverage.room_type("downstairs bathroom") == "bathroom"
    assert coverage.room_type("kitchen") == "kitchen"
    assert coverage.room_type("upstairs hallway") == "hallway"
    assert coverage.room_type("garden") == "other"


def test_rooms_split_where_the_narration_changes_room():
    observed = [
        said(2.0, "this is the bedroom", "bedroom", kind="room_change"),
        said(5.0, "walls look fine", "Bedroom"),
        said(20.0, "now the bathroom", "bathroom", kind="room_change"),
    ]
    rooms = coverage.rooms_from(observed, 40.0)
    assert [(r.name, r.type, r.t_start, r.t_end) for r in rooms] == [
        ("bedroom", "bedroom", 0.0, 20.0),
        ("bathroom", "bathroom", 20.0, 40.0),
    ]
    assert coverage.room_at(rooms, 25.0).name == "bathroom"
    assert coverage.room_at(rooms, 99.0).name == "bathroom"


def test_rooms_fall_back_to_the_override_or_an_unknown_room():
    assert coverage.rooms_from([], 30.0, override="bedroom") == [coverage.Room("bedroom", "bedroom", 0.0, 30.0)]
    assert coverage.rooms_from([], 30.0) == [coverage.Room("", "other", 0.0, 30.0)]


def test_mentions_only_count_whole_words_inside_the_room():
    item = next(i for i in coverage.CHECKLIST if i.key == coverage.GFCI)
    room = coverage.Room("bathroom", "bathroom", 10.0, 30.0)
    observed = [
        said(12.0, "GFCI by the sink tested fine"),
        said(14.0, "the gfcis are fine"),
        said(40.0, "another GFCI"),
    ]
    assert coverage.mentions(item, room, observed) == ["GFCI by the sink tested fine"]


def test_top_tracks_rank_by_frames_seen_then_confidence():
    detections = (
        [detection(f, "a", 0.4) for f in (2, 3, 4)]
        + [detection(3, "b", 0.9)]
        + [detection(90, "c", 0.9)]
    )
    best = coverage.top_tracks(detections, 0.0, 10.0, limit=2)
    assert [(d.object_id, d.frame) for d in best] == [("a", 2), ("b", 3)]


def test_status_order():
    assert coverage.status(seen=True, said=True, tested=True) == "tested"
    assert coverage.status(seen=True, said=True, tested=False) == "inspected"
    assert coverage.status(seen=True, said=False, tested=False) == "seen_not_mentioned"
    assert coverage.status(seen=False, said=True, tested=False) == "mentioned_not_seen"
    assert coverage.status(seen=False, said=False, tested=False) == "not_seen"


def test_check_candidates_batches_and_fills_missing_answers(monkeypatch, tmp_path):
    image = tmp_path / "f.jpg"
    image.write_bytes(b"jpg")
    calls = []

    def fake_spark(client, content, schema, name):
        calls.append(content)
        return {"checks": [{"index": 0, "verdict": "yes", "gfci": "no", "note": "outlet"}]}

    monkeypatch.setattr(coverage, "spark_json", fake_spark)
    monkeypatch.setattr(coverage, "MAX_IMAGES_PER_CHECK", 2)
    candidates = [{"question": "an outlet", "evidence_path": str(image)} for _ in range(3)]

    results = coverage.check_candidates(None, candidates)

    assert len(calls) == 2
    assert results[0] == {"verdict": "yes", "gfci": "no", "note": "outlet"}
    assert results[1]["verdict"] == "unclear"
    assert results[2] == results[0]


class FakeInspector:
    def __init__(self, tmp_path, found):
        self.proxy = tmp_path / "proxy.mp4"
        self.evidence_dir = tmp_path / "evidence"
        self.spark = None
        self.found = found

    def detections(self, phrase):
        future = asyncio.get_running_loop().create_future()
        future.set_result(self.found.get(phrase, []))
        return future


def fake_render(video, frames, box, out_dir, stem):
    return [Path(out_dir) / f"{stem}-f{frames[0]}.jpg"]


def test_check_reports_each_room_and_the_house(monkeypatch, tmp_path):
    answers = {
        "an electrical wall outlet (receptacle)": {"verdict": "yes", "gfci": "no", "note": "plain outlet"},
    }
    monkeypatch.setattr(coverage.verify, "render", fake_render)
    monkeypatch.setattr(
        coverage, "check_candidates",
        lambda client, candidates: [answers.get(c["question"], {"verdict": "no", "gfci": "n/a", "note": ""})
                                    for c in candidates],
    )
    inspector = FakeInspector(tmp_path, {
        "electrical outlet": [detection(50, "o1", phrase="electrical outlet")],
        "ceiling": [detection(4, "c1", phrase="ceiling"), detection(44, "c2", phrase="ceiling")],
    })
    observed = [
        said(1.0, "bedroom", "bedroom", kind="room_change"),
        said(20.0, "bathroom next", "bathroom", kind="room_change"),
        said(26.0, "tested the GFCI by the sink, it trips"),
    ]
    rooms = coverage.rooms_from(observed, 40.0)

    bedroom, bathroom, house = asyncio.run(coverage.check(inspector, observed, rooms))

    bedroom_items = {i["item"]: i for i in bedroom["items"]}
    assert bedroom_items["smoke_detector"]["status"] == "not_seen"
    assert bedroom_items["smoke_detector"]["expected"]
    assert bedroom_items["ceiling"]["status"] == "seen_not_mentioned"
    assert coverage.GFCI not in bedroom_items

    bathroom_items = {i["item"]: i for i in bathroom["items"]}
    assert bathroom_items[coverage.GFCI]["status"] == "tested"
    assert bathroom_items["exhaust_fan"]["status"] == "not_seen"
    [flag] = bathroom["gfci_flags"]
    assert flag["frame"] == 50 and "upstream" in flag["note"]

    assert house["room"] == coverage.HOUSE
    assert [(i["item"], i["status"]) for i in house["items"]] == [("electrical_panel", "not_seen")]


def test_pipeline_writes_coverage_and_tags_unspoken_candidates_with_their_room(monkeypatch, tmp_path):
    from contextlib import asynccontextmanager

    from secondinspector import pipeline

    observed = [said(1.0, "bedroom", "bedroom", kind="room_change"),
                said(20.0, "bathroom", "bathroom", kind="room_change")]
    candidate = {"description": "stain", "component_phrase": "ceiling", "defect_phrase": "stain",
                 "t_start": 25.0, "t_end": 26.0}

    @asynccontextmanager
    async def fake_client():
        yield None

    async def fake_upload(client, path):
        return "file-1"

    async def fake_evidence(self, item, stem):
        return {**item, "status": "confirmed", "box": None, "sam_phrase": None, "sam_object_id": None}

    async def fake_check(inspector, seen, rooms):
        return [{"room": r.name, "type": r.type, "t_start": r.t_start, "t_end": r.t_end,
                 "items": [], "gfci_flags": []} for r in rooms]

    monkeypatch.setattr(pipeline.media, "make_proxy", lambda clip, target: target)
    monkeypatch.setattr(pipeline.media, "make_wav", lambda clip, target: target)
    monkeypatch.setattr(pipeline.media, "frame_size", lambda video: (720, 1280))
    monkeypatch.setattr(pipeline.media, "duration", lambda video: 40.0)
    monkeypatch.setattr(pipeline.asr, "transcribe", lambda wav: {"turns": [], "transcript": ""})
    monkeypatch.setattr(pipeline.api, "sync_client", lambda: None)
    monkeypatch.setattr(pipeline.api, "async_client", fake_client)
    monkeypatch.setattr(pipeline.api, "spark_json", lambda *args: {"candidates": [candidate]})
    monkeypatch.setattr(pipeline.sam, "upload_video", fake_upload)
    monkeypatch.setattr(pipeline.observations, "extract", lambda spark, turns: observed)
    monkeypatch.setattr(pipeline.Inspector, "find_evidence", fake_evidence)
    monkeypatch.setattr(pipeline.coverage, "check", fake_check)
    monkeypatch.setattr(pipeline, "spoken_matches", lambda spark, spoken, visible: {})
    out = tmp_path / "out"
    (out / "walk").mkdir(parents=True)
    (out / "walk" / "proxy.mp4").write_bytes(b"mp4")

    findings = asyncio.run(pipeline.run(tmp_path / "walk.mp4", out))

    assert [r["room"] for r in findings["coverage"]] == ["bedroom", "bathroom"]
    assert (out / "walk" / "coverage.json").exists()
    assert findings["unspoken"][0]["room"] == "bathroom"

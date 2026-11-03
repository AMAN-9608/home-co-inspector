import asyncio
import json
from pathlib import Path

import openai

from secondinspector import alarm, sam

DEVICE = {"brand": "Kidde", "model": "unknown", "kind": "smoke_co", "power": "hardwired", "voice": "yes",
          "label_text": "KIDDE", "features": "round white unit", "confidence": "high"}

PROCEDURE = {
    "manual_models": "30CUAR-VCA",
    "tests": [
        {"name": "fire", "how": "press and release", "required": True,
         "expected_signals": [{"kind": "beep_pattern", "detail": "temporal-3"}, {"kind": "voice", "detail": "Fire!"}]},
        {"name": "co", "how": "same press", "required": True,
         "expected_signals": [{"kind": "beep_pattern", "detail": "temporal-4"},
                              {"kind": "voice", "detail": "Warning! Carbon monoxide!"}]},
    ],
    "notes": "",
    "source": "manual",
    "source_url": "https://brand.kidde.com/m/x/UG.pdf",
}


def detection(frame, box):
    return sam.Detection("smoke detector", frame, "0", box, 0.9)


def test_best_views_pick_the_biggest_boxes_spread_apart():
    detections = [
        detection(10, (0, 0, 100, 100)),
        detection(11, (0, 0, 90, 90)),
        detection(30, (0, 0, 80, 80)),
        detection(30, (0, 0, 10, 10)),
        detection(50, (0, 0, 20, 20)),
    ]
    assert [d.frame for d in alarm.best_views(detections, limit=2)] == [10, 30]


def test_rank_manuals_puts_the_makers_own_pdfs_first():
    urls = [
        "https://manuals.plus/kidde/30cuar.pdf",
        "https://www.kidde.com/products/combo",
        "https://brand.kidde.com/m/x/UG_30CUAR.pdf",
    ]
    assert alarm.rank_manuals(urls, "Kidde") == [urls[2], urls[0]]
    assert alarm.rank_manuals(urls, "First Alert") == [urls[0], urls[2]]
    assert alarm.rank_manuals(urls[1:2], "Kidde") == []


def test_procedure_tries_the_next_manual_then_falls_back(monkeypatch, tmp_path):
    calls, fetched = [], []

    def fake_download(url, manuals_dir):
        fetched.append(url)
        if "blocked" in url:
            raise ValueError("not a usable PDF")
        path = tmp_path / "ok.pdf"
        path.write_bytes(b"%PDF-1.4")
        return path

    def fake_spark(client, content, schema, name):
        calls.append(content)
        if any(part.get("type") == "input_file" for part in content):
            raise openai.APIError("bad file", request=None, body=None)
        return {"manual_models": "", "tests": PROCEDURE["tests"], "notes": ""}

    monkeypatch.setattr(alarm, "download", fake_download)
    monkeypatch.setattr(alarm.api, "spark_json", fake_spark)
    result = alarm.test_procedure(None, DEVICE, ["https://a/blocked.pdf", "https://b/ok.pdf"], tmp_path)
    assert fetched == ["https://a/blocked.pdf", "https://b/ok.pdf"]
    assert calls[0][1]["file_data"].startswith("data:application/pdf;base64,")
    assert result["source"] == "spark_knowledge" and result["source_url"] is None


def test_procedure_reads_the_first_manual_that_works(monkeypatch, tmp_path):
    path = tmp_path / "ok.pdf"
    path.write_bytes(b"%PDF-1.4")
    monkeypatch.setattr(alarm, "download", lambda url, manuals_dir: path)
    monkeypatch.setattr(alarm.api, "spark_json",
                        lambda *a: {"manual_models": "30CUAR-VCA", "tests": PROCEDURE["tests"], "notes": ""})
    result = alarm.test_procedure(None, DEVICE, ["https://brand.kidde.com/UG.pdf"], tmp_path)
    assert result["source"] == "manual" and result["source_url"] == "https://brand.kidde.com/UG.pdf"


def test_download_rejects_a_page_that_is_not_a_pdf(monkeypatch, tmp_path):
    class Response:
        content = b"<html>blocked</html>"

        def raise_for_status(self):
            pass

    monkeypatch.setattr(alarm.httpx, "get", lambda *a, **k: Response())
    try:
        alarm.download("https://brand.kidde.com/m/x/UG.pdf", tmp_path)
    except ValueError:
        pass
    else:
        raise AssertionError("accepted a non-PDF")
    assert not list(tmp_path.iterdir())


def test_identify_passes_what_the_alarm_said(monkeypatch):
    seen = []
    monkeypatch.setattr(alarm.api, "spark_json", lambda client, content, schema, name: seen.append(content) or DEVICE)
    events = [{"t_start": 15, "t_end": 17, "source": "alarm", "kind": "voice", "detail": "Fire! Fire!"},
              {"t_start": 1, "t_end": 5, "source": "inspector", "kind": "speech", "detail": "this is the alarm"}]
    alarm.identify(None, [], events)
    assert "voice: Fire! Fire!" in seen[0][0]["text"]
    assert "this is the alarm" not in seen[0][0]["text"]


def test_lookup_searches_once_then_uses_the_cache(monkeypatch, tmp_path):
    searches = []

    def fake_search(client, prompt):
        searches.append(prompt)
        return "answer", ["https://brand.kidde.com/m/x/UG.pdf"]

    monkeypatch.setattr(alarm.api, "spark_search", fake_search)
    monkeypatch.setattr(alarm, "test_procedure",
                        lambda spark, device, urls, manuals_dir: {**PROCEDURE, "source_url": urls[0]})

    first = alarm.lookup(None, DEVICE, tmp_path)
    second = alarm.lookup(None, DEVICE, tmp_path)

    assert len(searches) == 1 and "Kidde" in searches[0]
    assert first == second
    assert first["procedure"]["source_url"] == "https://brand.kidde.com/m/x/UG.pdf"


def test_lookup_skips_the_search_for_an_unknown_brand(monkeypatch, tmp_path):
    monkeypatch.setattr(alarm.api, "spark_search", lambda *a: (_ for _ in ()).throw(AssertionError("searched")))
    monkeypatch.setattr(alarm, "test_procedure",
                        lambda spark, device, urls, manuals_dir: {**PROCEDURE, "source": "spark_knowledge",
                                                                  "source_url": None})
    entry = alarm.lookup(None, {**DEVICE, "brand": "unknown"}, tmp_path)
    assert entry["manual"]["ranked"] == [] and entry["procedure"]["source"] == "spark_knowledge"


def fake_audit(answers):
    def spark(client, content, schema, name):
        return {"tests": answers, "summary": "summary"}
    return spark


def test_audit_is_exhaustive_when_every_required_part_sounded(monkeypatch):
    monkeypatch.setattr(alarm.api, "spark_json", fake_audit([
        {"test": "Fire", "status": "done", "t_start": 11, "t_end": 19, "heard": "temporal-3, Fire!", "missing": ""},
        {"test": "co", "status": "done", "t_start": 19, "t_end": 26, "heard": "temporal-4", "missing": ""},
    ]))
    events = [{"t_start": 9, "t_end": 10, "source": "inspector", "kind": "button_press", "detail": "press"}]
    result = alarm.audit(None, PROCEDURE, events)
    assert result["exhaustive"] and result["pressed"]
    assert [t["test"] for t in result["tests"]] == ["fire", "co"]


def test_audit_marks_a_missing_part_not_done(monkeypatch):
    monkeypatch.setattr(alarm.api, "spark_json", fake_audit([
        {"test": "fire", "status": "done", "t_start": 11, "t_end": 19, "heard": "temporal-3", "missing": ""},
    ]))
    result = alarm.audit(None, PROCEDURE, [])
    assert not result["exhaustive"] and not result["pressed"]
    assert result["tests"][1]["status"] == "not_done"


class FakeInspector:
    def __init__(self, tmp_path, found):
        self.proxy = tmp_path / "proxy.mp4"
        self.evidence_dir = tmp_path / "evidence"
        self.size = (720, 1280)
        self.found = found

    async def detections(self, phrase):
        return self.found


def test_find_alarm_crops_the_biggest_views(monkeypatch, tmp_path):
    monkeypatch.setattr(alarm.media, "extract_frame", lambda video, frame, target: Path(target))
    crops = []
    monkeypatch.setattr(alarm.media, "crop",
                        lambda image, box, size, target: crops.append(box) or Path(target))
    inspector = FakeInspector(tmp_path, [detection(4, (10, 10, 60, 60)), detection(20, (10, 10, 200, 200))])

    views = asyncio.run(alarm.find_alarm(inspector, "alarm"))

    assert [v["frame"] for v in views] == [20, 4]
    assert crops == [(10, 10, 200, 200), (10, 10, 60, 60)]


def test_find_alarm_uses_whole_frames_when_sam_finds_nothing(monkeypatch, tmp_path):
    monkeypatch.setattr(alarm.media, "extract_frame", lambda video, frame, target: Path(target))
    monkeypatch.setattr(alarm.media, "duration", lambda video: 10.0)
    views = asyncio.run(alarm.find_alarm(FakeInspector(tmp_path, []), "alarm"))
    assert [v["frame"] for v in views] == [4, 8, 12, 16]
    assert all(v["box"] is None for v in views)


def test_audit_prompt_names_an_unverified_source(monkeypatch):
    seen = []

    def spark(client, content, schema, name):
        seen.append(content[0]["text"])
        return {"tests": [], "summary": ""}

    monkeypatch.setattr(alarm.api, "spark_json", spark)
    alarm.audit(None, {**PROCEDURE, "source": "spark_knowledge"}, [])
    assert "unverified" in seen[0]
    assert json.dumps(PROCEDURE["tests"], indent=1) in seen[0]


def room_with(item):
    return {"room": "hallway", "type": "hallway", "t_start": 10.0, "t_end": 40.0, "items": [item], "gfci_flags": []}


def test_audit_rooms_does_nothing_without_a_confirmed_detector(monkeypatch, tmp_path):
    async def no_upload(client, path):
        raise AssertionError("uploaded")

    monkeypatch.setattr(alarm.sam, "upload_video", no_upload)
    rooms = [room_with({"item": "smoke_detector", "status": "not_seen", "evidence": None})]
    asyncio.run(alarm.audit_rooms(FakeInspector(tmp_path, []), None, tmp_path / "clip.mp4", rooms))
    assert "test_audit" not in rooms[0]["items"][0]


def test_audit_rooms_audits_only_the_rooms_window_and_marks_it_tested(monkeypatch, tmp_path):
    async def upload(client, path):
        return "file-1"

    events = [
        {"t_start": 2, "t_end": 3, "source": "alarm", "kind": "voice", "detail": "Fire!"},
        {"t_start": 15, "t_end": 18, "source": "alarm", "kind": "voice", "detail": "Fire!"},
    ]
    audited = []

    def fake_audit(spark, procedure, mine):
        audited.append(mine)
        return {"tests": [{"test": "fire", "status": "done"}], "exhaustive": True, "pressed": True, "summary": ""}

    monkeypatch.setattr(alarm.sam, "upload_video", upload)
    monkeypatch.setattr(alarm, "heard", lambda spark, video_id: events)
    monkeypatch.setattr(alarm, "find_alarm", lambda inspector, stem: asyncio.sleep(0, result=[]))
    monkeypatch.setattr(alarm, "identify", lambda spark, images, heard_events: DEVICE)
    monkeypatch.setattr(alarm, "lookup", lambda spark, device, manuals_dir: {"procedure": PROCEDURE})
    monkeypatch.setattr(alarm, "audit", fake_audit)
    inspector = FakeInspector(tmp_path, [])
    inspector.spark = None
    item = {"item": "smoke_detector", "status": "seen_not_mentioned", "evidence": {"frame": 30}}

    asyncio.run(alarm.audit_rooms(inspector, None, tmp_path / "clip.mp4", [room_with(item)]))

    assert audited == [events[1:]]
    assert item["status"] == "tested"
    assert item["test_audit"]["manual_url"] == PROCEDURE["source_url"]
    assert "Model number not readable" in item["test_audit"]["disclaimer"]


def test_audited_status():
    assert alarm.audited_status({"exhaustive": True, "tests": []}) == "tested"
    assert alarm.audited_status({"exhaustive": False, "tests": [{"status": "partial"}]}) == "test_incomplete"
    assert alarm.audited_status({"exhaustive": False, "tests": [{"status": "not_done"}]}) is None


def test_disclaimer_explains_an_inferred_model_or_an_unverified_procedure():
    note = alarm.disclaimer(DEVICE, PROCEDURE)
    assert "Model number not readable" in note
    assert "30CUAR-VCA" in note and "Kidde, smoke + co, voice" in note
    assert alarm.disclaimer({**DEVICE, "model": "30CUAR-VCA"}, PROCEDURE) == ""
    assert "unverified" in alarm.disclaimer(DEVICE, {**PROCEDURE, "source": "spark_knowledge"})

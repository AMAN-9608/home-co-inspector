import json, os, time
from secondinspector import ui_helpers as h


def test_discover(tmp_path):
    (tmp_path / "a").mkdir(); (tmp_path / "a/findings.json").write_text("{}")
    (tmp_path / "b").mkdir()
    time.sleep(0.01)
    (tmp_path / "c").mkdir(); (tmp_path / "c/findings.json").write_text("{}")
    os.utime(tmp_path / "a/findings.json", (1, 1))
    assert [p.name for p in h.discover_processed(tmp_path)] == ["c", "a"]
    assert h.discover_processed(tmp_path / "nope") == []


def test_chips():
    assert h.status_chip("inspected")[0] == "Inspected"
    assert h.status_chip("not_seen")[1] == "#d93025"
    assert h.status_chip("weird_one")[0] == "Weird one"


def test_review_label_shows_inspector_decision_and_model_status():
    finding = {"id": "spoken-0", "status": "uncertain"}
    state = {"items": {"spoken-0": {"decision": "accepted"}}}
    assert h.review_label(finding, state) == "Accepted · Model: uncertain"
    state["items"]["spoken-0"]["decision"] = "rejected"
    assert h.review_label(finding, state) == "Rejected · Model: uncertain"
    state["items"]["spoken-0"]["decision"] = "pending"
    assert h.review_label(finding, state) == "Pending · Model: uncertain"


def test_coverage_rooms_accepts_pipeline_list_and_preserves_duplicate_rooms():
    rooms = [{"room": "Bathroom", "items": []}, {"room": "Bathroom", "items": []}]
    assert h.coverage_rooms(rooms) == rooms


def test_group_and_ai():
    fs = [{"room": "k", "t_start": 5}, {"room": None, "t_start": 1}, {"room": "k", "t_start": 2, "source": "unspoken"}]
    g = h.group_by_room(fs)
    assert [f["t_start"] for f in g["k"]] == [2, 5]
    assert "Unassigned" in g
    assert h.is_ai(g["k"][0]) and not h.is_ai(g["k"][1])
    assert h.source_label("unspoken").startswith("AI")


def test_raw_and_paths(tmp_path):
    (tmp_path / "ev.jpg").write_bytes(b"x")
    (tmp_path / "findings.json").write_text(json.dumps({"spoken": [{"source": "spoken"}], "unspoken": [{"source": "unspoken", "id": "u"}]}))
    fs = h.raw_findings(tmp_path)
    assert [f["id"] for f in fs] == ["spoken-0", "u"]
    assert h.resolve_path("ev.jpg", tmp_path) == tmp_path / "ev.jpg"
    assert h.resolve_path("missing.jpg", tmp_path) is None
    assert h.fmt_time(75.5) == "01:15.5"
    assert h.coverage_counts([{"status": "tested"}, {"status": "tested"}]) == {"tested": 2}

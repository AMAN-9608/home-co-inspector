import json
import shutil
from pathlib import Path

import pytest

from secondinspector import review

FIXTURE = Path(__file__).parent / "fixtures" / "review"


@pytest.fixture
def out(tmp_path):
    shutil.copy(FIXTURE / "findings.json", tmp_path / "findings.json")
    return tmp_path


def test_candidate_ids(out):
    items = review.candidates(out)
    assert [f["id"] for f in items] == ["spoken-0", "spoken-1", "unspoken-0"]
    assert set(items[0]) == set(review.SCHEMA)
    assert items[2]["measurement"] is None


def test_level_json_included(out):
    (out / "level.json").write_text(json.dumps({"findings": [{"id": "sensor-0", "source": "sensor", "measurement": 2.1}]}))
    assert review.candidates(out)[-1]["id"] == "sensor-0"
    assert "sensor-0" in review.load(out)["items"]


def test_fresh_state(out):
    state = review.load(out)
    assert review.pending(state) == ["spoken-0", "spoken-1", "unspoken-0"]
    assert state["added"] == [] and state["signed_by"] is None


def test_decisions(out):
    state = review.load(out)
    review.decide(state, "spoken-0", "accepted")
    review.decide(state, "spoken-1", "edited", {"description": "Hairline crack."}, note="clarified")
    assert state["items"]["spoken-0"]["decided_at"]
    assert state["items"]["spoken-1"]["edits"] == {"description": "Hairline crack."}
    assert review.pending(state) == ["unspoken-0"]


def test_invalid_decisions(out):
    state = review.load(out)
    with pytest.raises(ValueError):
        review.decide(state, "spoken-0", "maybe")
    with pytest.raises(ValueError):
        review.decide(state, "spoken-0", "edited")
    with pytest.raises(ValueError):
        review.decide(state, "spoken-0", "edited", {"t_start": 0})
    with pytest.raises(KeyError):
        review.decide(state, "spoken-9", "accepted")


def test_add(out):
    state = review.load(out)
    assert review.add(state, {"room": "garage", "description": "No GFCI."}) == "inspector-1"
    assert state["added"][0]["source"] == "inspector"
    assert state["added"][0]["box"] is None
    assert review.add(state, {}) == "inspector-2"


def test_sign(out):
    state = review.load(out)
    with pytest.raises(ValueError):
        review.sign(state, "Pat")
    for fid in review.pending(state):
        review.decide(state, fid, "accepted")
    with pytest.raises(ValueError):
        review.sign(state, " ")
    review.sign(state, "Pat")
    assert state["signed_by"] == "Pat" and state["signed_at"]
    review.decide(state, "spoken-0", "rejected")
    assert state["signed_by"] is None and state["signed_at"] is None
    review.sign(state, "Pat")
    review.add(state, {"description": "x"})
    assert state["signed_at"] is None


def test_final_findings(out):
    state = review.load(out)
    review.decide(state, "spoken-0", "accepted")
    review.decide(state, "spoken-1", "edited", {"status": "confirmed", "room": "garage"})
    review.decide(state, "unspoken-0", "rejected", note="cover present")
    review.add(state, {"description": "Missed"})
    final = review.final_findings(out, state)
    assert [f["id"] for f in final] == ["spoken-0", "spoken-1", "inspector-1"]
    assert final[1]["room"] == "garage"


def test_save_load_roundtrip(out):
    state = review.load(out)
    review.decide(state, "spoken-0", "rejected", note="dup")
    review.add(state, {"room": "attic"})
    path = review.save(out, state)
    assert path.name == "review.json" and not (out / "review.json.tmp").exists()
    assert review.load(out) == state

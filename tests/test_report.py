import json
import shutil
from pathlib import Path

from secondinspector import report

FIXTURE = Path(__file__).parent / "fixtures" / "report_min"


def setup(tmp_path, **files):
    shutil.copy(FIXTURE / "findings.json", tmp_path / "findings.json")
    for name, data in files.items():
        (tmp_path / f"{name}.json").write_text(json.dumps(data))
    return tmp_path


def test_ids_assigned_by_list_position(tmp_path):
    findings = report.load_findings(setup(tmp_path))
    assert [f["id"] for f in findings] == ["spoken-0", "unspoken-0"]
    assert set(findings[0]) == set(report.FIELDS)


def test_missing_optional_files_ok_and_pending_labeled(tmp_path):
    text = report.build(setup(tmp_path)).read_text(encoding="utf-8")
    assert "DRAFT — not signed" in text
    assert text.count(report.UNCONFIRMED) == 1
    assert "Items not inspected" in text and "Coverage</h2>" not in text


def test_rejected_omitted_edits_applied_added_included(tmp_path):
    review = {"items": {"unspoken-0": {"decision": "rejected"},
                        "spoken-0": {"decision": "edited", "edits": {"description": "Edited text."}}},
              "added": [{"room": "garage", "description": "Missing smoke detector."}]}
    text = report.build(setup(tmp_path), review=review).read_text(encoding="utf-8")
    assert "Faint diagonal" not in text
    assert "Edited text." in text and "Thin seam" not in text
    assert "Missing smoke detector." in text and ">Inspector<" in text
    assert report.UNCONFIRMED not in text


def test_review_file_signed_header(tmp_path):
    review = {"items": {}, "added": [], "signed_by": "Jane Doe", "signed_at": "2026-11-02T10:00:00"}
    text = report.build(setup(tmp_path, review=review)).read_text(encoding="utf-8")
    assert "Reviewed and signed by Jane Doe on November 02, 2026" in text
    assert "DRAFT" not in text


def test_level_and_coverage_rendered(tmp_path):
    level = {"findings": [{"room": "kitchen", "description": "Floor slopes", "measurement": "1.2 deg"}],
             "rooms": {"kitchen": {"max_slope_deg": 1.2, "svg": "<svg id='dots'></svg>"}}}
    coverage = {"rooms": {"kitchen": {"items": [{"item": "smoke detector", "status": "not_seen"},
                                                {"item": "sink", "status": "tested"}]}}}
    text = report.build(setup(tmp_path, level=level, coverage=coverage)).read_text(encoding="utf-8")
    assert "<svg id='dots'>" in text and "Kitchen: smoke detector" in text
    assert text.count(report.UNCONFIRMED) == 2


def test_report_accepts_pipeline_coverage_list(tmp_path):
    coverage = [{"room": "bathroom", "items": [{"item": "toilet", "label": "Toilet", "status": "not_seen"}]}]
    text = report.build(setup(tmp_path, coverage=coverage)).read_text()
    assert "Toilet" in text
    assert "not seen in the footage" in text.lower()


def test_report_applies_decisions_to_inspector_added_findings(tmp_path):
    state = {"items": {"inspector-1": {"decision": "edited", "edits": {"description": "Corrected"}},
                       "inspector-2": {"decision": "rejected"}},
             "added": [{"id": "inspector-1", "description": "Original"},
                       {"id": "inspector-2", "description": "Should not appear"}]}
    text = report.build(setup(tmp_path), review=state).read_text()
    assert "Corrected" in text
    assert "Original" not in text
    assert "Should not appear" not in text

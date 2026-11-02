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


def test_current_pipeline_coverage_list_is_reported(tmp_path):
    coverage = [{"room": "garage", "items": [{"item": "smoke_detector", "label": "Smoke detector", "status": "not_seen"}]}]
    text = report.build(setup(tmp_path, coverage=coverage)).read_text(encoding="utf-8")
    assert "Garage: Smoke detector" in text
    assert "Coverage</h2>" in text


def test_property_address_is_escaped_and_report_has_navigation(tmp_path):
    text = report.render(setup(tmp_path), None, property_address='123 Jane Doe Street <NJ>')
    assert '123 Jane Doe Street &lt;NJ&gt;' in text
    assert '[Property address]' not in text
    assert 'Contents' in text
    assert 'href="#findings"' in text and 'id="findings"' in text


def test_svg_evidence_keeps_its_image_type(tmp_path):
    evidence = tmp_path / 'level-garage.svg'
    evidence.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"></svg>')
    tag = report.image_tag(str(evidence), tmp_path, 'Floor level evidence')
    assert 'data:image/svg+xml;base64,' in tag


def test_mentioned_but_not_seen_coverage_has_readable_label(tmp_path):
    coverage = [{'room': 'garage', 'items': [{'item': 'panel', 'label': 'Electrical panel', 'status': 'mentioned_not_seen'}]}]
    text = report.build(setup(tmp_path, coverage=coverage)).read_text(encoding='utf-8')
    assert '>Mentioned, not seen</td>' in text

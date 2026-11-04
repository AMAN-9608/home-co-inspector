import json
import math
import shutil
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from secondinspector import level

FIXTURE = Path(__file__).parent / "fixtures" / "level_readings.json"


def test_slope_combines_pitch_and_roll():
    s, _ = level.slope(3.0, 4.0)
    expected = math.degrees(math.atan(math.hypot(math.tan(math.radians(3)), math.tan(math.radians(4)))))
    assert s == pytest.approx(expected)
    assert level.slope(0, 0)[0] == 0


def test_rise_conversion():
    in10, mmm = level.rise(math.degrees(math.atan(0.01)))
    assert in10 == pytest.approx(1.2)
    assert mmm == pytest.approx(10.0)


@pytest.mark.parametrize("pitch,roll,downhill", [(1, 0, 180), (-1, 0, 0), (0, 1, 90), (0, -1, 270)])
def test_downhill_direction(pitch, roll, downhill):
    assert level.slope(pitch, roll)[1] == pytest.approx(downhill)


def test_threshold_flag():
    assert not level.measure({"pitch_deg": 0.1, "roll_deg": 0.1}, 0.45)["over_threshold"]
    assert level.measure({"pitch_deg": 0.5, "roll_deg": 0.0}, 0.45)["over_threshold"]


def test_analyze_fixture(tmp_path):
    shutil.copy(FIXTURE, tmp_path / level.READINGS)
    r = level.analyze(tmp_path)
    assert {f["id"] for f in r["findings"]} == {"level-kitchen-fridge", "level-living-room-east-wall"}
    f = r["findings"][0]
    assert f["source"] == "sensor" and f["status"] == "measured" and f["sop_section"] == "Structure"
    assert set(f["measurement"]) == {"slope_deg", "in_per_10ft", "mm_per_m", "downhill_deg", "threshold_deg", "over_threshold"}
    assert (tmp_path / "level-kitchen.svg").read_text().startswith("<svg")
    assert json.loads((tmp_path / "level.json").read_text())["rooms"]["Kitchen"]["max_slope_deg"] > 0.45


def test_server_post(tmp_path):
    srv = level.make_server(tmp_path, port=0, host="127.0.0.1")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        body = json.dumps({"room": "A", "spot": "b", "t": "x", "pitch_deg": 0.2, "roll_deg": 0.1, "samples": 5}).encode()
        headers = {"Content-Type": "application/json", "X-Level-Token": srv.token}
        req = urllib.request.Request(url + "/readings", body, headers)
        assert json.loads(urllib.request.urlopen(req).read())["count"] == 1
        assert len(json.loads((tmp_path / level.READINGS).read_text())) == 1
        bad = urllib.request.Request(url + "/readings", b"{}", headers)
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(bad)
        assert b"<html" in urllib.request.urlopen(url + "/?t=" + srv.token).read()
    finally:
        srv.shutdown()
        srv.server_close()


def test_server_rejects_untrusted_readings(tmp_path):
    srv = level.make_server(tmp_path, port=0, host="127.0.0.1")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/readings"

    def post(body, token=srv.token):
        req = urllib.request.Request(url, json.dumps(body).encode(), {"X-Level-Token": token})
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(req)
        return error.value.code

    try:
        reading = {"room": "A", "spot": "b", "pitch_deg": 0.2, "roll_deg": 0.1}
        assert post(reading, token="") == 403
        assert post(reading, token="wrong") == 403
        assert post({**reading, "pitch_deg": "nan"}) == 400
        assert post({**reading, "spot": "x" * (level.MAX_TEXT + 1)}) == 400
        assert post([reading] * (level.MAX_READINGS + 1)) == 413
        assert not (tmp_path / level.READINGS).exists()
    finally:
        srv.shutdown()
        srv.server_close()


def test_svg_escapes_room_and_spot(tmp_path):
    (tmp_path / level.READINGS).write_text(json.dumps(
        [{"room": "<b>kitchen", "spot": "<script>alert(1)</script>", "pitch_deg": 2, "roll_deg": 0}]))
    level.analyze(tmp_path)
    svg = (tmp_path / "level-b-kitchen.svg").read_text()
    assert "<script>" not in svg and "&lt;script&gt;" in svg and "&lt;b&gt;kitchen" in svg

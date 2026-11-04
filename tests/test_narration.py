import json
from types import SimpleNamespace
from unittest.mock import Mock

from secondinspector import align, asr, observations, pipeline, sam, verify


def detection(frame, object_id="0", box=(0, 0, 10, 10), confidence=0.5, phrase="crack"):
    return sam.Detection(phrase, frame, object_id, box, confidence)


def test_window_is_padded_and_clamped_at_zero():
    assert align.window(1.0, 2.0) == (0.0, 6.0)
    assert align.window(10.0, 12.0) == (7.0, 16.0)


def test_locate_keeps_only_detections_inside_the_spoken_window():
    detections = [detection(f) for f in range(37, 46)] + [detection(5, object_id="1")]
    located = align.locate(detections, t_start=20.46, t_end=21.74)
    assert located.object_id == "0"
    assert located.frames == list(range(37, 46))
    assert align.locate(detections, t_start=30.0, t_end=31.0) is None


def test_locate_prefers_the_object_seen_most_then_highest_confidence():
    detections = [detection(40, "a", confidence=0.9)] + [detection(f, "b", confidence=0.2) for f in (39, 40, 41)]
    located = align.locate(detections, t_start=20.0, t_end=20.5)
    assert located.object_id == "b"


def test_box_helpers():
    assert align.box_fraction((0, 0, 360, 640), (720, 1280)) == 0.25
    assert align.boxes_overlap((0, 0, 10, 10), (5, 5, 20, 20))
    assert not align.boxes_overlap((0, 0, 10, 10), (10, 10, 20, 20))


def test_parse_turns_drops_empty_transcripts():
    payload = {
        "turns": [
            {"turnId": "t1", "startMs": 1260, "endMs": 2460, "transcript": " first floor. "},
            {"turnId": "t2", "startMs": 3000, "endMs": 3100, "transcript": ""},
        ]
    }
    turns = asr.parse_turns(payload)
    assert turns == [asr.Turn("t1", 1260, 2460, "first floor.", None)]


def test_transcribe_posts_wav_with_keywords(tmp_path, monkeypatch):
    wav = tmp_path / "audio.wav"
    wav.write_bytes(b"RIFF")
    monkeypatch.setenv("MODEL_API_KEY", "test-key")
    client = Mock()
    client.post.return_value = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"turns": []})

    assert asr.transcribe(wav, keywords=["hinge"], client=client) == {"turns": []}

    call = client.post.call_args
    assert call.args[0].endswith("/asr/transcribe")
    assert call.kwargs["headers"]["Authorization"] == "Bearer test-key"
    request = json.loads(call.kwargs["files"]["request"][1])
    assert request["mode"] == "ENDPOINTING"
    assert request["keywords"] == ["hinge"]


def test_observations_take_times_and_words_from_their_turn():
    turns = [asr.Turn("3", 20460, 21740, "cracks around the frame.")]
    items = [
        {"turn_id": "3", "kind": "defect", "room": "first floor", "component_phrase": "frame",
         "defect_phrase": "crack", "location_hint": "around the frame", "sop_section": "Interior"},
        {"turn_id": "missing", "kind": "chatter", "room": "", "component_phrase": "",
         "defect_phrase": "", "location_hint": "", "sop_section": ""},
    ]
    [observation] = observations.attach_turns(items, turns)
    assert observation.utterance == "cracks around the frame."
    assert (observation.t_start, observation.t_end) == (20.46, 21.74)


def test_boxes_from_records_skips_masks():
    records = [
        {"kind": "box", "object_id": 0, "left": 1, "top": 2, "right": 3, "bottom": 4,
         "frame": {"frame_index": 37}, "confidence": 0.7},
        {"kind": "mask", "object_id": 0, "frame": {"frame_index": 37}},
    ]
    assert sam.boxes_from_records("crack", records) == [detection(37, box=(1, 2, 3, 4), confidence=0.7)]


def test_keyframes_without_a_box_use_the_middle_of_the_window():
    assert verify.keyframes(None, 10.0, 12.0) == [22]
    located = align.Located("crack", "0", [37, 40, 45], 40, (0, 0, 1, 1), 0.7)
    assert verify.keyframes(located, 20.0, 21.0) == [37, 40, 45]


def finding(t_start, t_end, box, phrase=None, object_id=None):
    return {"t_start": t_start, "t_end": t_end, "box": box, "sam_phrase": phrase, "sam_object_id": object_id}


def test_candidate_on_the_same_track_or_spot_counts_as_spoken():
    spoken = [finding(20.5, 21.7, [373, 399, 500, 532], "crack", "0")]
    assert pipeline.covered(finding(30.0, 31.0, None, "crack", "0"), spoken)
    assert pipeline.covered(finding(15.0, 22.5, [400, 420, 480, 500]), spoken)
    assert not pipeline.covered(finding(30.0, 33.0, [400, 420, 480, 500]), spoken)
    assert not pipeline.covered(finding(15.0, 22.5, [0, 0, 100, 100]), spoken)

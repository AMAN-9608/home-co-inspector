import json
import runpy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import openai


def test_spark_spike_sends_video_and_frames_and_saves_responses(tmp_path, monkeypatch):
    frames = tmp_path / "data/processed/original-frames"
    frames.mkdir(parents=True)
    for second in (10, 22, 33):
        (frames / f"{second}s.jpg").write_bytes(b"image")
    response = SimpleNamespace(
        status="completed",
        output_text="observation",
        model_dump=lambda **_: {"status": "completed"},
    )
    create = Mock(return_value=response)
    monkeypatch.setattr(
        openai,
        "OpenAI",
        lambda **_: SimpleNamespace(responses=SimpleNamespace(create=create)),
    )
    monkeypatch.setenv("MODEL_API_KEY", "test-key")
    monkeypatch.chdir(tmp_path)
    script = Path(__file__).resolve().parents[1] / "scripts/spark_spike.py"

    runpy.run_path(str(script), run_name="__main__")

    assert create.call_count == 4
    media = [call.kwargs["input"][0]["content"][1] for call in create.call_args_list]
    assert [item["type"] for item in media] == [
        "input_video",
        "input_image",
        "input_image",
        "input_image",
    ]
    output = tmp_path / "data/processed/spark-review-candidates"
    assert sorted(path.name for path in output.glob("*.json")) == [
        "frame-10s.json",
        "frame-22s.json",
        "frame-33s.json",
        "video.json",
    ]
    assert json.loads((output / "video.json").read_text())["status"] == "completed"

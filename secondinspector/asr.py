import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

import httpx

KEYWORDS = [
    "trim", "casing", "miter", "jamb", "hinge", "baseboard", "drywall",
    "hairline", "crack", "scuff", "stain", "gap", "caulk", "GFCI",
    "efflorescence", "flashing", "water heater", "smoke detector",
    "smoke alarm", "ground fault", "exhaust fan", "electrical panel", "breaker",
    "bedroom", "bathroom",
]


@dataclass
class Turn:
    turn_id: str
    start_ms: int
    end_ms: int
    text: str
    speaker: str | None = None


def parse_turns(payload):
    return [
        Turn(
            turn_id=str(turn.get("turnId", index)),
            start_ms=int(turn["startMs"]),
            end_ms=int(turn["endMs"]),
            text=turn.get("transcript", "").strip(),
            speaker=turn.get("speaker"),
        )
        for index, turn in enumerate(payload.get("turns", []))
        if turn.get("transcript", "").strip()
    ]


def transcribe(wav_path, keywords=KEYWORDS, client=None):
    request = {
        "mode": "ENDPOINTING",
        "model": "muse-voice-transcribe-1.0",
        "audioEncoding": "WAV",
        "keywords": keywords,
    }
    base_url = os.environ.get("base_url", "https://api.meta.ai/v1").rstrip("/")
    wav_path = Path(wav_path)
    client = client or httpx.Client(timeout=300)
    response = client.post(
        f"{base_url}/asr/transcribe",
        params={"sessionId": str(uuid.uuid4())},
        headers={"Authorization": f"Bearer {os.environ['MODEL_API_KEY']}"},
        files={
            "request": (None, json.dumps(request), "application/json"),
            "audio": (wav_path.name, wav_path.read_bytes(), "audio/wav"),
        },
    )
    response.raise_for_status()
    return response.json()

import base64
import json
import os
from pathlib import Path

from openai import OpenAI

client = OpenAI(base_url="https://api.meta.ai/v1", api_key=os.environ["MODEL_API_KEY"])
output = Path("data/processed/spark-review-candidates")
output.mkdir(exist_ok=True)
prompt = (
    "Act as a home inspector's second pair of eyes. Flag visual observations for human review, "
    "including hairline lines or apparent separations along door edges, trim and trim-to-wall joints, "
    "including diagonal corner lines, as well as subtle wall scuffs, skid marks, dark streaks, "
    "smudges and light discolored patches. For every candidate describe its visible appearance, "
    "location, and approximate video time if applicable. Include faint or ambiguous candidates "
    "as uncertain; they may be normal seams, lighting, shadow or blur. Do not declare a defect "
    "or invent details that are not visible. If no candidates are visible, say so."
)
inputs = [("video", {"type": "input_video", "file_id": "file-28771685195834190"})]
for seconds in (10, 22, 33):
    image = Path(f"data/processed/original-frames/{seconds}s.jpg")
    data = base64.b64encode(image.read_bytes()).decode("ascii")
    inputs.append(
        (
            f"frame-{seconds}s",
            {"type": "input_image", "image_url": f"data:image/jpeg;base64,{data}"},
        )
    )
for name, media in inputs:
    print(f"Analyzing {name}...", flush=True)
    response = client.responses.create(
        model="muse-spark-1.3",
        input=[
            {"role": "user", "content": [{"type": "input_text", "text": prompt}, media]}
        ],
    )
    path = output / f"{name}.json"
    path.write_text(json.dumps(response.model_dump(mode="json"), indent=2) + "\n")
    print(f"Status: {response.status}; saved {path}", flush=True)
    print(response.output_text, flush=True)
    if response.status != "completed":
        raise RuntimeError(f"Incomplete response for {name}: {response.status}")

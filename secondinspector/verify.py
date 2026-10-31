import base64
from pathlib import Path

from secondinspector import media
from secondinspector.api import spark_json

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["status", "inside_box", "best_image", "description"],
    "properties": {
        "status": {"type": "string", "enum": ["confirmed", "uncertain", "not_visible"]},
        "inside_box": {"type": "boolean"},
        "best_image": {"type": "integer"},
        "description": {"type": "string"},
    },
}

PROMPT = """You are a home inspector's second pair of eyes, checking evidence for one observation.
Observation: {claim}
{box_note}
Answer with:
- status: "confirmed" if the observation is clearly visible, "uncertain" if something matching it may be visible
  but could be a normal seam, shadow, reflection or blur, "not_visible" if nothing in the images supports it.
- inside_box: true only if what supports the observation lies inside the red box; false if it is elsewhere
  in the image or if there is no box.
- best_image: the 0-based index of the image that shows it best.
- description: one or two sentences describing what is visible and where, for a human to review in person.
  Do not declare a defect or speculate about causes."""


def keyframes(located, t_start, t_end, fps=2):
    if located is None:
        return [round((t_start + t_end) / 2 * fps)]
    frames = located.frames
    picks = [frames[0], located.best_frame, frames[-1]]
    return list(dict.fromkeys(picks))


def render(video, frames, box, out_dir, stem):
    paths = []
    for frame in frames:
        raw = media.extract_frame(video, frame, Path(out_dir) / f"{stem}-f{frame}-raw.jpg")
        if box is None:
            paths.append(raw)
            continue
        paths.append(media.draw_box(raw, box, Path(out_dir) / f"{stem}-f{frame}.jpg"))
        raw.unlink()
    return paths


def check(client, claim, images, boxed):
    box_note = (
        "Each image has a red box where an object detector found it." if boxed else
        "No detector box is available; look at the whole image."
    )
    content = [{"type": "input_text", "text": PROMPT.format(claim=claim, box_note=box_note)}]
    for image in images:
        data = base64.b64encode(Path(image).read_bytes()).decode("ascii")
        content.append({"type": "input_image", "image_url": f"data:image/jpeg;base64,{data}"})
    result = spark_json(client, content, SCHEMA, "evidence_check")
    result["best_image"] = min(max(result["best_image"], 0), len(images) - 1)
    return result

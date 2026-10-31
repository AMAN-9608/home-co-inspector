import json
from contextlib import aclosing
from dataclasses import asdict, dataclass
from pathlib import Path

from meta_sam_parser import parse_responses_stream, video_segmentation_format


@dataclass
class Detection:
    phrase: str
    frame: int
    object_id: str
    box: tuple[int, int, int, int]
    confidence: float | None


async def stream_events(stream):
    completed = set()
    async for event in stream:
        data = event.model_dump() if hasattr(event, "model_dump") else dict(event)
        lane = (
            data.get("item_id"),
            data.get("output_index"),
            data.get("content_index"),
        )
        if data.get("type") == "response.output_text.done":
            if lane not in completed:
                completed.add(lane)
                yield data
            continue
        yield data
        part = data.get("part")
        if (
            data.get("type") == "response.content_part.done"
            and lane not in completed
            and isinstance(part, dict)
            and part.get("type") == "output_text"
            and isinstance(part.get("text"), str)
        ):
            completed.add(lane)
            yield {
                "type": "response.output_text.done",
                "item_id": lane[0],
                "output_index": lane[1],
                "content_index": lane[2],
                "text": part["text"],
            }


async def upload_video(client, path):
    path = Path(path)
    uploaded = await client.files.create(
        file=(path.name, path.read_bytes(), "video/mp4"), purpose="user_data"
    )
    return uploaded.id


def boxes_from_records(phrase, records):
    detections = []
    for record in records:
        record = record if isinstance(record, dict) else asdict(record)
        if record.get("kind") != "box":
            continue
        detections.append(
            Detection(
                phrase=phrase,
                frame=record["frame"]["frame_index"],
                object_id=str(record["object_id"]),
                box=(record["left"], record["top"], record["right"], record["bottom"]),
                confidence=record.get("confidence"),
            )
        )
    return detections


async def segment(client, file_id, phrase):
    stream = await client.responses.create(
        model="sam-3.1",
        stream=True,
        input=[
            {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": phrase},
                    {"type": "input_video", "file_id": file_id},
                ],
            }
        ],
        metadata={"include_confidence": "true", "mask_encoding": "one_bit"},
    )
    async with stream, aclosing(stream_events(stream)) as events:
        parsed = parse_responses_stream(events, video_segmentation_format())
        async with parsed:
            result = await parsed.final_result()
    if result.outcome.status != "completed" or any(
        d.severity == "error" for d in result.diagnostics
    ):
        raise RuntimeError(
            f"SAM returned incomplete or invalid results for {phrase}: {result.outcome}; {result.diagnostics}"
        )
    return [asdict(record) for record in result.records]


async def run_concept(client, file_id, phrase, cache_dir, video_key=None):
    """Segment one phrase over the whole video, reusing a cached result for the same video."""
    cache = Path(cache_dir) / f"{video_key or file_id}-{phrase.replace(' ', '-')}.json"
    if cache.exists():
        records = json.loads(cache.read_text())
    else:
        records = await segment(client, file_id, phrase)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(records, indent=2) + "\n")
    return boxes_from_records(phrase, records)

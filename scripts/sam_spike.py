import asyncio
import json
import os
from contextlib import aclosing
from dataclasses import asdict
from pathlib import Path

from meta_sam_parser import parse_responses_stream, video_segmentation_format
from openai import AsyncOpenAI

from secondinspector.sam import stream_events


async def main():
    video = Path("data/processed/room-proxy.mp4")
    output = Path("data/processed/sam")
    output.mkdir(parents=True, exist_ok=True)
    async with AsyncOpenAI(
        base_url="https://api.meta.ai/v1", api_key=os.environ["MODEL_API_KEY"]
    ) as client:
        video_bytes = await asyncio.to_thread(video.read_bytes)
        uploaded = await client.files.create(
            file=(video.name, video_bytes, "video/mp4"), purpose="user_data"
        )
        print(f"Uploaded video: {uploaded.id}", flush=True)
        for concept in ("crack", "wall mark"):
            print(f"Searching for {concept}...", flush=True)
            stream = await client.responses.create(
                model="sam-3.1",
                stream=True,
                input=[
                    {
                        "type": "message",
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": concept},
                            {"type": "input_video", "file_id": uploaded.id},
                        ],
                    }
                ],
            )
            async with stream, aclosing(stream_events(stream)) as events:
                parsed = parse_responses_stream(events, video_segmentation_format())
                async with parsed:
                    result = await parsed.final_result()
            if result.outcome.status != "completed" or any(
                d.severity == "error" for d in result.diagnostics
            ):
                raise RuntimeError(
                    f"SAM returned incomplete or invalid results for {concept}: {result.outcome}; {result.diagnostics}"
                )
            path = output / f"{concept.replace(' ', '-')}.json"
            path.write_text(json.dumps(asdict(result), indent=2) + "\n")
            print(f"Saved {len(result.records)} records to {path}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())

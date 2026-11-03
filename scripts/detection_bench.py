"""Measure SAM phrases on processed clips: which frames and tracks each phrase finds, all from the SAM cache.

    uv run --env-file .env python scripts/detection_bench.py "smoke detector|smoke alarm" data/processed/*/

Each clip folder needs a proxy.mp4; results are cached under its sam/ folder, so re-runs cost nothing.
"""

import asyncio
import collections
import sys
from pathlib import Path

from secondinspector import api, sam
from secondinspector.pipeline import Inspector


def summarise(detections):
    frames = sorted({d.frame for d in detections})
    tracks = collections.Counter(d.object_id for d in detections)
    best = max((d.confidence or 0 for d in detections), default=0)
    span = f"{frames[0] / 2:.1f}-{frames[-1] / 2:.1f}s" if frames else "-"
    return f"{len(frames):3} frames {span:12} {len(tracks)} tracks  max conf {best:.2f}"


async def main(phrases, clip_dirs):
    async with api.async_client() as client:
        for clip_dir in map(Path, clip_dirs):
            proxy = clip_dir / "proxy.mp4"
            inspector = Inspector(client, None, None, proxy, clip_dir)
            cached = all((inspector.sam_dir / f"{inspector.video_key}-{p.replace(' ', '-')}.json").exists()
                         for p in phrases)
            inspector.file_id = None if cached else await sam.upload_video(client, proxy)
            print(clip_dir.name)
            for phrase in phrases:
                print(f"  {phrase:32} {summarise(await inspector.detections(phrase))}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1].split("|"), sys.argv[2:]))

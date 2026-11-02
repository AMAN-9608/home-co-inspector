from collections import defaultdict
from dataclasses import dataclass

PAD_BEFORE = 3.0
PAD_AFTER = 4.0


@dataclass
class Located:
    phrase: str
    object_id: str
    frames: list[int]
    best_frame: int
    box: tuple[int, int, int, int]
    confidence: float | None


def window(t_start, t_end, pad_before=PAD_BEFORE, pad_after=PAD_AFTER):
    return max(0.0, t_start - pad_before), t_end + pad_after


def to_frame(seconds, fps=2):
    return round(seconds * fps)


def locate(detections, t_start, t_end, fps=2, pad_before=PAD_BEFORE, pad_after=PAD_AFTER):
    """Pick the tracked object seen most inside the padded time window, and its best frame."""
    start, end = window(t_start, t_end, pad_before, pad_after)
    lo, hi = to_frame(start, fps), to_frame(end, fps)
    tracks = defaultdict(list)
    for detection in detections:
        if lo <= detection.frame <= hi:
            tracks[detection.object_id].append(detection)
    if not tracks:
        return None
    centre = to_frame((t_start + t_end) / 2, fps)
    object_id, hits = max(
        tracks.items(),
        key=lambda item: (len(item[1]), max(d.confidence or 0 for d in item[1])),
    )
    best = max(hits, key=lambda d: (d.confidence or 0, -abs(d.frame - centre)))
    return Located(
        phrase=best.phrase,
        object_id=object_id,
        frames=sorted(d.frame for d in hits),
        best_frame=best.frame,
        box=best.box,
        confidence=best.confidence,
    )


def box_fraction(box, frame_size):
    left, top, right, bottom = box
    width, height = frame_size
    return (right - left) * (bottom - top) / (width * height)


def boxes_overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]

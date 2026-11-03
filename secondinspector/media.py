import os
import shutil
import subprocess
from pathlib import Path


def ffmpeg_bin(name="ffmpeg"):
    found = shutil.which(name)
    if found:
        return found
    winget = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/WinGet/Packages"
    for candidate in winget.glob(f"Gyan.FFmpeg*/*/bin/{name}.exe"):
        return str(candidate)
    raise FileNotFoundError(f"{name} not found; install ffmpeg and add it to PATH")


def run_ffmpeg(*args):
    subprocess.run(
        [ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y", *map(str, args)],
        check=True,
    )


def frame_size(video):
    result = subprocess.run(
        [ffmpeg_bin("ffprobe"), "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", str(video)],
        check=True, capture_output=True, text=True,
    )
    width, height = result.stdout.strip().split(",")[:2]
    return int(width), int(height)


def duration(video):
    result = subprocess.run(
        [ffmpeg_bin("ffprobe"), "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(video)],
        check=True, capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def make_proxy(source, target, fps=2):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        "-i", source, "-vf", f"fps={fps}", "-an", "-c:v", "libx264",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", target,
    )
    return target


def make_wav(source, target, sample_rate=16000):
    # Phone narration is often quiet; loudnorm brings it up before ASR.
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        "-i", source, "-vn", "-af", "loudnorm", "-ac", "1",
        "-ar", sample_rate, "-c:a", "pcm_s16le", target,
    )
    return target


def extract_frame(video, frame_index, target, fps=2):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        "-i", video, "-vf", f"select=eq(n\\,{frame_index})", "-frames:v", "1",
        "-q:v", "2", target,
    )
    return target


def crop(image, box, frame_size, target, pad=0.6):
    """Cut out the box plus `pad` of its size on every side, kept inside the frame."""
    left, top, right, bottom = box
    width, height = frame_size
    dx, dy = (right - left) * pad, (bottom - top) * pad
    x0, y0 = max(0, int(left - dx)), max(0, int(top - dy))
    x1, y1 = min(width, int(right + dx)), min(height, int(bottom + dy))
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg("-i", image, "-vf", f"crop={x1 - x0}:{y1 - y0}:{x0}:{y0}", "-q:v", "2", target)
    return target


def draw_box(image, box, target, color="red"):
    left, top, right, bottom = box
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        "-i", image, "-vf",
        f"drawbox=x={left}:y={top}:w={right - left}:h={bottom - top}:color={color}@0.9:t=4",
        "-q:v", "2", target,
    )
    return target

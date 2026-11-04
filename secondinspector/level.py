"""Floor level from the phone's tilt sensor.

  python -m secondinspector.level serve --out data/processed/<name> [--port 8000]
  python -m secondinspector.level analyze data/processed/<name>

`serve` hosts web/level.html and appends POST /readings to <out>/level_readings.json.
iOS only exposes DeviceOrientationEvent over HTTPS (after a permission tap), so on a
phone open the page through a tunnel, e.g.  cloudflared tunnel --url http://localhost:8000
The tunnel is public, so POST /readings needs the token `serve` prints; open the page
with ?t=<token> appended to the tunnel URL.
`analyze` writes <out>/level.json plus a dot map per room, level-<room>.svg.
"""
import argparse
import hmac
import json
import math
import re
import secrets
import threading
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

PAGE = Path(__file__).resolve().parent.parent / "web" / "level.html"
READINGS = "level_readings.json"
MAX_BODY = 64 * 1024
MAX_READINGS = 2000
MAX_TEXT = 100

# VERIFY before the demo (PLAN.md needs a cited threshold). Candidate source: NAHB
# Residential Construction Performance Guidelines, "floors should not be more than 1/4 in
# out of level within any 32 in" -> atan(0.25/32) = 0.45 deg. Confirm wording/edition.
THRESHOLD_DEG = 0.45


def slope(pitch_deg, roll_deg):
    """Total slope angle and downhill direction (0 = toward phone's top edge, 90 = right edge)."""
    tb, tg = math.tan(math.radians(pitch_deg)), math.tan(math.radians(roll_deg))
    slope_deg = math.degrees(math.atan(math.hypot(tb, tg)))
    downhill = math.degrees(math.atan2(tg, -tb)) % 360 if slope_deg > 0 else 0.0
    return slope_deg, downhill


def rise(slope_deg):
    g = math.tan(math.radians(slope_deg))
    return g * 120, g * 1000


def measure(reading, threshold_deg=THRESHOLD_DEG):
    s, d = slope(reading["pitch_deg"], reading["roll_deg"])
    in10, mmm = rise(s)
    return {"slope_deg": round(s, 3), "in_per_10ft": round(in10, 3), "mm_per_m": round(mmm, 2),
            "downhill_deg": round(d, 1), "threshold_deg": threshold_deg, "over_threshold": s > threshold_deg}


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-") or "x"


def finding(reading, m, svg):
    room, spot = reading.get("room", ""), reading.get("spot", "")
    return {
        "id": f"level-{slug(room)}-{slug(spot)}", "source": "sensor", "room": room,
        "sop_section": "Structure", "component_phrase": "floor", "defect_phrase": "out of level",
        "description": f"Floor at {spot or 'this spot'} slopes {m['slope_deg']:.2f} deg "
                       f"({m['in_per_10ft']:.2f} in per 10 ft), over the {m['threshold_deg']} deg threshold. "
                       "Recheck with a level and consider structural evaluation.",
        "utterance": "", "t_start": None, "t_end": None, "frame": None, "box": None,
        "status": "measured", "evidence_path": svg, "measurement": m,
    }


def svg_map(room, items, threshold_deg):
    n = len(items)
    cols = max(1, math.ceil(math.sqrt(n)))
    rows = max(1, math.ceil(n / cols))
    w, h = cols * 160, rows * 160 + 30
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" font-family="sans-serif" font-size="12">',
           f'<text x="8" y="18" font-weight="bold">{escape(str(room))} (threshold {threshold_deg} deg)</text>']
    for i, (r, m) in enumerate(items):
        cx, cy = (i % cols) * 160 + 80, (i // cols) * 160 + 100
        color = "#d62728" if m["over_threshold"] else "#2ca02c"
        out.append(f'<circle cx="{cx}" cy="{cy}" r="8" fill="{color}"/>')
        if m["slope_deg"] > 0:
            a = math.radians(m["downhill_deg"])
            ln = 20 + min(m["slope_deg"] / max(threshold_deg, 1e-6), 3) * 15
            x2, y2 = cx + ln * math.sin(a), cy - ln * math.cos(a)
            out.append(f'<line x1="{cx}" y1="{cy}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="3"/>')
            out.append(f'<circle cx="{x2:.1f}" cy="{y2:.1f}" r="3" fill="{color}"/>')
        out.append(f'<text x="{cx}" y="{cy - 60}" text-anchor="middle">{escape(str(r.get("spot", "")))}</text>')
        out.append(f'<text x="{cx}" y="{cy + 60}" text-anchor="middle">{m["slope_deg"]:.2f} deg</text>')
    out.append("</svg>")
    return "\n".join(out)


def analyze(out_dir, threshold_deg=THRESHOLD_DEG):
    out_dir = Path(out_dir)
    readings = json.loads((out_dir / READINGS).read_text())
    by_room = {}
    for r in readings:
        by_room.setdefault(r.get("room", ""), []).append((r, measure(r, threshold_deg)))
    findings, rooms, seen = [], {}, set()
    for room, items in by_room.items():
        svg = out_dir / f"level-{slug(room)}.svg"
        svg.write_text(svg_map(room, items, threshold_deg))
        rooms[room] = {"max_slope_deg": max(m["slope_deg"] for _, m in items), "svg": str(svg)}
        for r, m in items:
            if m["over_threshold"]:
                f = finding(r, m, str(svg))
                base, k = f["id"], 2
                while f["id"] in seen:
                    f["id"], k = f"{base}-{k}", k + 1
                seen.add(f["id"])
                findings.append(f)
    result = {"readings": readings, "findings": findings, "rooms": rooms}
    (out_dir / "level.json").write_text(json.dumps(result, indent=2))
    return result


def append_reading(out_dir, reading):
    path = Path(out_dir) / READINGS
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(path.read_text()) if path.exists() else []
    data.append(reading)
    path.write_text(json.dumps(data, indent=2))
    return len(data)


def valid_reading(it):
    """Raise ValueError or TypeError unless `it` looks like a reading level.html sends."""
    if not isinstance(it, dict):
        raise TypeError("reading must be an object")
    for key in ("pitch_deg", "roll_deg"):
        if not math.isfinite(float(it[key])):
            raise ValueError(f"{key} must be finite")
    for key in ("room", "spot", "t"):
        if not isinstance(it.get(key, ""), str) or len(it.get(key, "")) > MAX_TEXT:
            raise ValueError(f"{key} must be text up to {MAX_TEXT} characters")
    return it


def make_server(out_dir, port=8000, host="127.0.0.1", token=None):
    """The server's `token` attribute must be sent as X-Level-Token with every POST."""
    token = token or secrets.token_urlsafe(16)
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if urlsplit(self.path).path in ("/", "/level.html"):
                self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            else:
                self._send(404, b'{"error":"not found"}')

        def do_POST(self):
            if urlsplit(self.path).path != "/readings":
                return self._send(404, b'{"error":"not found"}')
            if not hmac.compare_digest(self.headers.get("X-Level-Token", "").encode(), token.encode()):
                return self._send(403, b'{"error":"missing or wrong token; open the link printed by serve"}')
            try:
                length = int(self.headers.get("Content-Length", 0))
                if not 0 < length <= MAX_BODY:
                    return self._send(413, b'{"error":"reading too large"}')
                r = json.loads(self.rfile.read(length))
                items = [valid_reading(it) for it in (r if isinstance(r, list) else [r])]
            except (ValueError, KeyError, TypeError):
                return self._send(400, b'{"error":"bad reading"}')
            with lock:
                path = Path(out_dir) / READINGS
                existing = len(json.loads(path.read_text())) if path.exists() else 0
                if existing + len(items) > MAX_READINGS:
                    return self._send(413, b'{"error":"too many readings for this inspection"}')
                for it in items:
                    n = append_reading(out_dir, it)
            self._send(200, json.dumps({"ok": True, "count": n}).encode())

        def log_message(self, *a):
            pass

    server = ThreadingHTTPServer((host, port), Handler)
    server.token = token
    return server


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve", help="serve level.html; iOS needs HTTPS: cloudflared tunnel --url http://localhost:8000")
    s.add_argument("--out", required=True)
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--host", default="127.0.0.1",
                   help="0.0.0.0 also accepts phones on the local network (the token is still required)")
    a = sub.add_parser("analyze")
    a.add_argument("out_dir")
    a.add_argument("--threshold", type=float, default=THRESHOLD_DEG)
    args = p.parse_args(argv)
    if args.cmd == "serve":
        server = make_server(args.out, args.port, args.host)
        print(f"http://localhost:{args.port}/?t={server.token}")
        print(f"phone: cloudflared tunnel --url http://localhost:{args.port}, then open <tunnel URL>/?t={server.token}")
        server.serve_forever()
    else:
        r = analyze(args.out_dir, args.threshold)
        n, k = len(r["readings"]), len(r["findings"])
        print(f"{n} readings, {k} over threshold -> {Path(args.out_dir) / 'level.json'}")


if __name__ == "__main__":
    main()

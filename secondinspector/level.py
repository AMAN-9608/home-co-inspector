"""Floor level from the phone's tilt sensor.

  python -m secondinspector.level serve --out data/processed/<name> [--port 8000]
  python -m secondinspector.level analyze data/processed/<name>

`serve` hosts web/level.html and appends POST /readings to <out>/level_readings.json.
iOS only exposes DeviceOrientationEvent over HTTPS (after a permission tap), so on a
phone open the page through a tunnel, e.g.  cloudflared tunnel --url http://localhost:8000
`analyze` writes <out>/level.json plus a dot map per room, level-<room>.svg.
"""
import argparse
import json
import math
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PAGE = Path(__file__).resolve().parent.parent / "web" / "level.html"
READINGS = "level_readings.json"

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
           f'<text x="8" y="18" font-weight="bold">{room} (threshold {threshold_deg} deg)</text>']
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
        out.append(f'<text x="{cx}" y="{cy - 60}" text-anchor="middle">{r.get("spot", "")}</text>')
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


def make_server(out_dir, port=8000, host="0.0.0.0"):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path in ("/", "/level.html"):
                self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            else:
                self._send(404, b'{"error":"not found"}')

        def do_POST(self):
            if self.path != "/readings":
                return self._send(404, b'{"error":"not found"}')
            try:
                r = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                items = r if isinstance(r, list) else [r]
                for it in items:
                    float(it["pitch_deg"]), float(it["roll_deg"])
            except (ValueError, KeyError, TypeError):
                return self._send(400, b'{"error":"bad reading"}')
            for it in items:
                n = append_reading(out_dir, it)
            self._send(200, json.dumps({"ok": True, "count": n}).encode())

        def log_message(self, *a):
            pass

    return ThreadingHTTPServer((host, port), Handler)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve", help="serve level.html; iOS needs HTTPS: cloudflared tunnel --url http://localhost:8000")
    s.add_argument("--out", required=True)
    s.add_argument("--port", type=int, default=8000)
    a = sub.add_parser("analyze")
    a.add_argument("out_dir")
    a.add_argument("--threshold", type=float, default=THRESHOLD_DEG)
    args = p.parse_args(argv)
    if args.cmd == "serve":
        print(f"http://localhost:{args.port}/  (phone: cloudflared tunnel --url http://localhost:{args.port})")
        make_server(args.out, args.port).serve_forever()
    else:
        r = analyze(args.out_dir, args.threshold)
        n, k = len(r["readings"]), len(r["findings"])
        print(f"{n} readings, {k} over threshold -> {Path(args.out_dir) / 'level.json'}")


if __name__ == "__main__":
    main()

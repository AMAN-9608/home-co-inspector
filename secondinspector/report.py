import argparse
import base64
import html
import json
import mimetypes
from collections import Counter
from datetime import datetime
from pathlib import Path

FIELDS = [
    "id", "source", "room", "sop_section", "component_phrase", "defect_phrase", "description",
    "utterance", "t_start", "t_end", "frame", "box", "status", "evidence_path", "measurement",
]
BADGES = {"spoken": "Spoken", "unspoken": "AI-detected", "sensor": "Sensor", "inspector": "Inspector"}
COVERAGE_LABELS = {
    "inspected": "Inspected", "tested": "Tested",
    "seen_not_mentioned": "Seen, not mentioned", "not_seen": "Not seen",
    "mentioned_not_seen": "Mentioned, not seen",
}
STATUS_LABELS = {"confirmed": "Located in video", "uncertain": "Needs on-site check", "measured": "Measured"}
UNCONFIRMED = "AI finding — not yet confirmed by inspector"
LIMITATIONS = (
    "This inspection is a visual, non-invasive assessment of readily accessible areas on the date of "
    "inspection. It does not include areas concealed by finishes, furniture, stored items or weather, and "
    "is not a guarantee or warranty of any component. Items listed as not inspected were not observed and "
    "should be evaluated before closing."
)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def normalize(finding, **defaults):
    item = {field: finding.get(field) for field in FIELDS}
    for key, value in defaults.items():
        if item.get(key) is None:
            item[key] = value
    item["sop_section"] = item["sop_section"] or "General"
    item["room"] = item["room"] or "Unspecified"
    return item


def load_findings(out_dir):
    out_dir = Path(out_dir)
    data = read_json(out_dir / "findings.json")
    findings = []
    for source in ("spoken", "unspoken"):
        for i, f in enumerate(data.get(source, [])):
            findings.append(normalize(f, id=f"{source}-{i}", source=source))
    level = read_json(out_dir / "level.json") or {}
    for i, f in enumerate(level.get("findings", [])):
        findings.append(normalize(f, id=f"sensor-{i}", source="sensor", sop_section="Structure"))
    return findings


def apply_review(findings, review):
    if not review:
        return [dict(f, confirmed=False) for f in findings]
    items = review.get("items", {})
    result = []
    for f in findings:
        entry = items.get(f["id"], {})
        decision = entry.get("decision", "pending")
        if decision == "rejected":
            continue
        f = dict(f, **(entry.get("edits") or {})) if decision == "edited" else dict(f)
        f["confirmed"] = decision in ("accepted", "edited")
        f["note"] = entry.get("note")
        result.append(f)
    for i, f in enumerate(review.get("added", [])):
        result.append(dict(normalize(f, id=f"inspector-{i}"), source="inspector", confirmed=True,
                           note=f.get("note")))
    return result


def resolve_image(path, out_dir):
    if not path:
        return None
    path = Path(str(path).replace("\\", "/"))
    for candidate in (path, out_dir / path, out_dir / "evidence" / path.name):
        if candidate.is_file():
            return candidate
    return None


def image_tag(path, out_dir, alt):
    found = resolve_image(path, out_dir)
    if not found:
        return '<div class="noimg">No evidence image</div>'
    mime = mimetypes.guess_type(found.name)[0] or "application/octet-stream"
    data = base64.b64encode(found.read_bytes()).decode()
    return f'<img src="data:{mime};base64,{data}" alt="{esc(alt)}">'


def esc(value):
    return html.escape("" if value is None else str(value))


def timestamp(f):
    if f.get("t_start") is None:
        return ""
    def fmt(t):
        return f"{int(t) // 60}:{int(t) % 60:02d}"
    end = f" – {fmt(f['t_end'])}" if f.get("t_end") is not None else ""
    return f"{fmt(f['t_start'])}{end}"


def finding_card(f, out_dir):
    title = " ".join(p for p in (f.get("component_phrase"), "—" if f.get("defect_phrase") else "",
                                 f.get("defect_phrase")) if p) or "Finding"
    meta = [f'<span class="badge {f["source"]}">{BADGES.get(f["source"], f["source"])}</span>']
    if timestamp(f):
        meta.append(f'<span class="ts">Video {timestamp(f)}</span>')
    if f.get("status"):
        meta.append(f'<span class="status">{esc(STATUS_LABELS.get(f["status"], f["status"]))}</span>')
    body = [f'<p>{esc(f.get("description"))}</p>']
    if f.get("utterance"):
        body.append(f'<p class="quote">Inspector said: “{esc(f["utterance"])}”</p>')
    if f.get("measurement") is not None:
        body.append(f'<p><b>Measurement:</b> {esc(f["measurement"])}</p>')
    if f.get("note"):
        body.append(f'<p><b>Inspector note:</b> {esc(f["note"])}</p>')
    if not f["confirmed"] and f["source"] in ("unspoken", "sensor"):
        body.append(f'<p class="unconfirmed">{UNCONFIRMED}</p>')
    return (f'<article class="finding" id="{esc(f["id"])}"><div class="img">'
            f'{image_tag(f.get("evidence_path"), out_dir, title)}</div><div class="text">'
            f'<h4>{esc(title)}</h4><div class="meta">{"".join(meta)}</div>{"".join(body)}</div></article>')


def findings_section(findings, out_dir):
    if not findings:
        return "<section><h2>Findings</h2><p>No findings recorded.</p></section>"
    parts = ["<section><h2>Findings</h2>"]
    for section in sorted({f["sop_section"] for f in findings}):
        parts.append(f"<h3>{esc(section)}</h3>")
        in_section = [f for f in findings if f["sop_section"] == section]
        for room in sorted({f["room"] for f in in_section}):
            parts.append(f'<h4 class="room">{esc(room.title())}</h4>')
            parts += [finding_card(f, out_dir) for f in in_section if f["room"] == room]
    return "".join(parts) + "</section>"


def summary_section(findings):
    by_source = Counter(BADGES.get(f["source"], f["source"]) for f in findings)
    by_status = Counter(STATUS_LABELS.get(f.get("status"), f.get("status") or "Not rated") for f in findings)
    unconfirmed = sum(1 for f in findings if not f["confirmed"])
    cells = [f'<div class="stat"><b>{len(findings)}</b>Total findings</div>']
    cells += [f'<div class="stat"><b>{n}</b>{esc(k)}</div>' for k, n in sorted(by_source.items())]
    cells += [f'<div class="stat"><b>{n}</b>{esc(k)}</div>' for k, n in sorted(by_status.items())]
    cells.append(f'<div class="stat"><b>{unconfirmed}</b>Awaiting inspector review</div>')
    note = method_note(findings) + (" Every finding below was reviewed by the signing inspector." if not unconfirmed else "")
    return (f'<section><h2>Summary</h2><p class="method">{esc(note)}</p>'
            f'<div class="stats">{"".join(cells)}</div></section>')


def method_note(findings):
    spoken = sum(f["source"] == "spoken" for f in findings)
    ai = sum(f["source"] == "unspoken" for f in findings)
    added = sum(f["source"] == "inspector" for f in findings)
    sensor = sum(f["source"] == "sensor" for f in findings)
    parts = [f"{spoken} narrated by the inspector on site",
             f"{ai} flagged by AI review of the video that the inspector did not mention"]
    if sensor:
        parts.append(f"{sensor} from phone floor-level measurements")
    if added:
        parts.append(f"{added} added by the inspector during review")
    return "How this report was made: " + "; ".join(parts) + "."


def level_section(level):
    rooms = (level or {}).get("rooms") or {}
    if not rooms:
        return ""
    parts = ["<section><h2>Floor level</h2>"]
    for room, info in rooms.items():
        parts.append(f'<div class="level"><h4>{esc(room.title())} — max slope '
                     f'{esc(info.get("max_slope_deg"))}°</h4>{info.get("svg") or ""}</div>')
    return "".join(parts) + "</section>"


def coverage_rooms(coverage):
    if isinstance(coverage, list):
        return {entry.get("room") or "Unspecified": {**entry, "items": [
            {**item, "item": item.get("label") or item.get("item")}
            for item in entry.get("items", [])]} for entry in coverage}
    return (coverage or {}).get("rooms") or {}


def coverage_section(coverage):
    rooms = coverage_rooms(coverage)
    if not rooms:
        return ""
    rows = [f'<tr><td>{esc(room.title())}</td><td>{esc(i.get("item"))}</td>'
            f'<td class="cov {esc(i.get("status"))}">{COVERAGE_LABELS.get(i.get("status"), esc(i.get("status")))}</td></tr>'
            for room, info in rooms.items() for i in info.get("items", [])]
    return ('<section><h2>Coverage</h2><table><thead><tr><th>Room</th><th>Item</th><th>Status</th></tr>'
            f'</thead><tbody>{"".join(rows)}</tbody></table></section>')


def not_inspected_section(coverage):
    rooms = coverage_rooms(coverage)
    missing = [f"<li>{esc(room.title())}: {esc(i.get('item'))}</li>" for room, info in rooms.items()
               for i in info.get("items", []) if i.get("status") == "not_seen"]
    listing = f"<ul>{''.join(missing)}</ul>" if missing else (
        "<p>No checklist items were recorded as not seen.</p>" if rooms else "")
    return f'<section><h2>Items not inspected</h2>{listing}<p class="limits">{LIMITATIONS}</p></section>'


def signature(review):
    if review and review.get("signed_by"):
        when = review.get("signed_at") or ""
        try:
            # signed_at is stored in UTC; show the inspector's local date.
            when = datetime.fromisoformat(when).astimezone().strftime("%B %d, %Y")
        except ValueError:
            pass
        return f'<div class="signed">Reviewed and signed by {esc(review["signed_by"])} on {esc(when)}</div>'
    return '<div class="draft">DRAFT — not signed</div>'


CSS = """
body{font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:#1f2933;background:#fff;margin:0}
main{max-width:900px;margin:0 auto;padding:32px 24px}
header{border-bottom:3px solid #1c2328;padding-bottom:16px;margin-bottom:8px}
header h1{margin:0;color:#1c2328;font-size:28px}
.prop{color:#52606d;margin:4px 0}
.draft,.signed{display:inline-block;margin-top:8px;padding:6px 12px;border-radius:4px;font-weight:600}
.draft{background:#fdecea;color:#c2302a;border:1px solid #f5c2bd}
.signed{background:#e2f2e8;color:#1f7a4d;border:1px solid #a9d3b9}
h2{color:#1c2328;border-bottom:1px solid #d3dadd;padding-bottom:4px;margin-top:32px}
h3{margin:24px 0 8px;color:#2c3740}
h4.room{color:#55606a;text-transform:uppercase;font-size:13px;letter-spacing:.05em}
.stats{display:flex;flex-wrap:wrap;gap:12px}
.stat{border:1px solid #d3dadd;border-radius:6px;padding:10px 14px;min-width:110px;font-size:13px;color:#52606d}
.stat b{display:block;font-size:22px;color:#1f2933}
.finding{display:flex;gap:16px;border:1px solid #d3dadd;border-radius:6px;padding:12px;margin:10px 0;break-inside:avoid}
.finding .img{flex:0 0 280px}.finding img{width:100%;border-radius:4px}
.noimg{background:#eef1f2;color:#5f6b74;height:160px;display:flex;align-items:center;justify-content:center;border-radius:4px}
.finding h4{margin:0 0 6px;text-transform:capitalize}.finding p{margin:6px 0;font-size:14px}
.meta{display:flex;gap:8px;flex-wrap:wrap;font-size:12px}
.badge{padding:2px 8px;border-radius:10px;font-weight:600;color:#fff}
.badge.spoken{background:#1c2328}.badge.unspoken{background:#1d6aae}.badge.sensor{background:#55606a}.badge.inspector{background:#1f7a4d}
.ts,.status{color:#52606d;background:#eef1f2;padding:2px 8px;border-radius:10px}
.quote{color:#52606d;font-style:italic}
.unconfirmed{color:#c2302a;font-weight:600;font-size:13px}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{border:1px solid #d3dadd;padding:6px 10px;text-align:left}th{background:#eef1f2}
.cov.not_seen{color:#c2302a;font-weight:600}.cov.seen_not_mentioned{color:#55606a}
.level svg{max-width:100%;height:auto}
.limits{font-size:13px;color:#52606d}
.method{font-size:14px;color:#2c3740;background:#f3f5f4;border-left:3px solid #1c2328;padding:10px 14px;margin:8px 0 14px}
footer{margin-top:40px;border-top:1px solid #d3dadd;padding-top:12px;font-size:12px;color:#5f6b74}
.contents{padding:8px 18px 14px;background:#f3f5f4;border:1px solid #e1e6e8;border-radius:6px;margin-top:22px}.contents h2{border:0;margin:12px 0 6px;font-size:17px}.contents ol{columns:2;font-size:12px;line-height:2;color:#55606a;padding-left:20px}.contents a{color:inherit;text-decoration:none}
@media (max-width:640px){.finding{flex-direction:column}.finding .img{flex:none}}
@media print{main{max-width:none;padding:0}h2{break-after:avoid}.finding{flex-direction:row}
.badge,.draft,.signed,th{-webkit-print-color-adjust:exact;print-color-adjust:exact}@page{margin:16mm}}
"""


def rebrand_legacy_report(text):
    return text.replace('<footer>Prepared with Second Inspector, an AI assistant.',
                        '<footer>Prepared with Home Co-Inspector, an AI assistant.')


def render(out_dir, review, property_address="[Property address]"):
    out_dir = Path(out_dir)
    findings = apply_review(load_findings(out_dir), review)
    level = read_json(out_dir / "level.json")
    coverage = read_json(out_dir / "coverage.json")
    sections = [("summary", "Summary", summary_section(findings)),
                ("findings", "Findings by system & room", findings_section(findings, out_dir)),
                ("floor-level", "Floor level", level_section(level)),
                ("coverage", "Coverage", coverage_section(coverage)),
                ("limitations", "Items not inspected & limitations", not_inspected_section(coverage))]
    contents = '<nav class="contents" aria-label="Report contents"><h2>Contents</h2><ol>' + ''.join(
        f'<li><a href="#{key}">{esc(title)}</a></li>' for key, title, body in sections if body) + '</ol></nav>'
    body = ''.join(text.replace('<section>', f'<section id="{key}">', 1)
                   for key, _, text in sections)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Inspection Report – Home Co-Inspector</title>
<style>{CSS}</style></head><body><main>
<header><h1>Home Inspection Report</h1><p class="prop">Property: {esc(property_address)}</p>
<p class="prop">Generated {datetime.now():%B %d, %Y}</p>{signature(review)}</header>
{contents}{body}
<footer>Prepared with Home Co-Inspector, an AI assistant. AI-detected and sensor findings are flags for the
inspector to evaluate; the licensed inspector is solely responsible for the contents of this report.</footer>
</main></body></html>"""


def build(out_dir, review=None):
    out_dir = Path(out_dir)
    if review is None:
        review = read_json(out_dir / "review.json")
    path = out_dir / "report.html"
    path.write_text(render(out_dir, review), encoding="utf-8")
    return path


def main():
    parser = argparse.ArgumentParser(description="Build the HTML inspection report.")
    parser.add_argument("out_dir")
    print(build(parser.parse_args().out_dir))


if __name__ == "__main__":
    main()

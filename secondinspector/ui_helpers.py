"""Pure helpers for the Streamlit app (no streamlit import)."""
from __future__ import annotations

import json
from pathlib import Path

CHIPS = {
    "inspected": ("Inspected", "#1e8e3e"),
    "seen_not_mentioned": ("Seen, not mentioned", "#e37400"),
    "not_seen": ("Not seen", "#d93025"),
    "tested": ("Tested", "#1a73e8"),
}
AI_SOURCES = {"unspoken"}
SOURCE_LABELS = {
    "spoken": "Inspector said",
    "unspoken": "AI — needs your confirmation",
    "sensor": "Sensor",
    "inspector": "Added by inspector",
}


def discover_processed(root) -> list[Path]:
    """Folders under root that contain findings.json, newest first."""
    root = Path(root)
    if not root.is_dir():
        return []
    dirs = [p for p in root.iterdir() if p.is_dir() and (p / "findings.json").is_file()]
    return sorted(dirs, key=lambda p: (p / "findings.json").stat().st_mtime, reverse=True)


def status_chip(status: str) -> tuple[str, str]:
    """(label, hex color) for a coverage status."""
    return CHIPS.get(status, (str(status).replace("_", " ").capitalize(), "#5f6368"))


def is_ai(finding: dict) -> bool:
    return finding.get("source") in AI_SOURCES


def source_label(source: str) -> str:
    return SOURCE_LABELS.get(source, str(source))


def review_label(finding, state):
    decision = (state or {}).get("items", {}).get(finding["id"], {}).get("decision")
    if not decision and finding.get("source") == "inspector":
        decision = "accepted"
    label = decision.capitalize() if decision else ""
    if finding.get("status") and finding.get("source") != "inspector":
        label += (" · " if label else "") + f"Model: {finding['status']}"
    return label


def group_by_room(findings: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for f in findings:
        out.setdefault(f.get("room") or "Unassigned", []).append(f)
    for items in out.values():
        items.sort(key=lambda f: (f.get("t_start") is None, f.get("t_start") or 0))
    return out


def raw_findings(out_dir) -> list[dict]:
    """Fallback when review module is absent: findings.json with synthetic ids."""
    data = json.loads((Path(out_dir) / "findings.json").read_text(encoding="utf-8"))
    out = []
    for i, f in enumerate(data.get("spoken", []) + data.get("unspoken", [])):
        f = dict(f)
        f.setdefault("id", f"{f.get('source', 'f')}-{i}")
        out.append(f)
    return out


def resolve_path(p, repo_root) -> Path | None:
    """Evidence paths are stored relative to repo root, possibly with backslashes."""
    if not p:
        return None
    path = Path(str(p).replace("\\", "/"))
    if not path.is_absolute():
        path = Path(repo_root) / path
    return path if path.is_file() else None


def fmt_time(t) -> str:
    if t is None:
        return "--:--"
    t = float(t)
    return f"{int(t // 60):02d}:{t % 60:04.1f}"


def load_optional_json(out_dir, name):
    p = Path(out_dir) / name
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def coverage_counts(items: list[dict]) -> dict[str, int]:
    c: dict[str, int] = {}
    for it in items:
        c[it.get("status", "?")] = c.get(it.get("status", "?"), 0) + 1
    return c


def coverage_rooms(coverage):
    if isinstance(coverage, list):
        return coverage
    return [{**info, "room": name} for name, info in (coverage or {}).get("rooms", {}).items()]



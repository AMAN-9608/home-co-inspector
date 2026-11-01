import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = ["id", "source", "room", "sop_section", "component_phrase", "defect_phrase", "description",
          "utterance", "t_start", "t_end", "frame", "box", "status", "evidence_path", "measurement"]
EDITABLE = {"description", "room", "sop_section", "component_phrase", "defect_phrase", "status"}
DECISIONS = {"pending", "accepted", "edited", "rejected"}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize(finding, **overrides):
    out = {key: finding.get(key) for key in SCHEMA}
    out.update(overrides)
    return out


def candidates(out_dir):
    out_dir = Path(out_dir)
    found = json.loads((out_dir / "findings.json").read_text())
    items = []
    for source in ("spoken", "unspoken"):
        for i, finding in enumerate(found.get(source, [])):
            items.append(normalize(finding, id=f"{source}-{i}", source=finding.get("source") or source))
    level = out_dir / "level.json"
    if level.exists():
        items += [normalize(f) for f in json.loads(level.read_text()).get("findings", [])]
    return items


def blank_item():
    return {"decision": "pending", "edits": {}, "note": "", "decided_at": None}


def load(out_dir):
    path = Path(out_dir) / "review.json"
    state = json.loads(path.read_text()) if path.exists() else {
        "items": {}, "added": [], "signed_by": None, "signed_at": None}
    for finding in candidates(out_dir):
        state["items"].setdefault(finding["id"], blank_item())
    return state


def unsign(state):
    state["signed_by"] = None
    state["signed_at"] = None


def decide(state, finding_id, decision, edits=None, note=""):
    if finding_id not in state["items"]:
        raise KeyError(f"unknown finding {finding_id}")
    if decision not in DECISIONS:
        raise ValueError(f"invalid decision {decision}")
    edits = edits or {}
    if decision == "edited" and not edits:
        raise ValueError("edited requires edits")
    bad = set(edits) - EDITABLE
    if bad:
        raise ValueError(f"not editable: {sorted(bad)}")
    state["items"][finding_id] = {"decision": decision, "edits": dict(edits) if decision == "edited" else {},
                                  "note": note, "decided_at": None if decision == "pending" else now()}
    unsign(state)
    return state


def add(state, finding):
    taken = {f["id"] for f in state["added"]}
    n = len(state["added"]) + 1
    while f"inspector-{n}" in taken:
        n += 1
    new = normalize(finding, id=f"inspector-{n}", source="inspector")
    state["added"].append(new)
    unsign(state)
    return new["id"]


def pending(state):
    return [fid for fid, item in state["items"].items() if item["decision"] == "pending"]


def sign(state, name):
    if not name or not name.strip():
        raise ValueError("signer name required")
    if pending(state):
        raise ValueError(f"pending findings: {pending(state)}")
    state["signed_by"] = name.strip()
    state["signed_at"] = now()
    return state


def final_findings(out_dir, state):
    out = []
    for finding in candidates(out_dir):
        item = state["items"].get(finding["id"], blank_item())
        if item["decision"] == "accepted":
            out.append(finding)
        elif item["decision"] == "edited":
            out.append({**finding, **item["edits"]})
    return out + [dict(f) for f in state["added"]]


def save(out_dir, state):
    path = Path(out_dir) / "review.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2) + "\n")
    os.replace(tmp, path)
    return path


def show(finding):
    print(f"\n[{finding['id']}] {finding['room']} / {finding['component_phrase']} / {finding['defect_phrase']}")
    for key in ("sop_section", "utterance", "description", "status", "evidence_path"):
        if finding.get(key):
            print(f"  {key}: {finding[key]}")


def walkthrough(out_dir):
    state = load(out_dir)
    by_id = {f["id"]: f for f in candidates(out_dir)}
    for fid in pending(state):
        show(by_id[fid])
        choice = input("  (a)ccept (e)dit (r)eject (s)kip: ").strip().lower()
        if choice == "a":
            decide(state, fid, "accepted")
        elif choice == "r":
            decide(state, fid, "rejected", note=input("  reason: "))
        elif choice == "e":
            edits = {}
            for key in sorted(EDITABLE):
                value = input(f"  {key} [{by_id[fid][key]}]: ").strip()
                if value:
                    edits[key] = value
            if edits:
                decide(state, fid, "edited", edits)
        save(out_dir, state)
    while input("\nAdd a missed finding? (y/N): ").strip().lower() == "y":
        add(state, {key: input(f"  {key}: ").strip() or None for key in sorted(EDITABLE)})
        save(out_dir, state)
    if pending(state):
        print(f"Still pending: {', '.join(pending(state))}")
    else:
        name = input("Sign as (blank to skip): ").strip()
        if name:
            sign(state, name)
    print(f"Wrote {save(out_dir, state)}")


def main():
    parser = argparse.ArgumentParser(description="Review AI findings and sign the report.")
    parser.add_argument("out_dir")
    walkthrough(parser.parse_args().out_dir)


if __name__ == "__main__":
    main()

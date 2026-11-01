"""Second Inspector UI.  Run: uv run streamlit run app.py"""
from __future__ import annotations

import asyncio
import importlib
import threading
import time
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from secondinspector import ui_helpers as h

ROOT = Path(__file__).resolve().parent
PROCESSED = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw"
EDITABLE = ["room", "sop_section", "component_phrase", "defect_phrase", "description"]

st.set_page_config(page_title="Second Inspector", page_icon="🏠", layout="wide")
st.markdown(
    """<style>
.chip{display:inline-block;padding:2px 10px;border-radius:12px;color:#fff;font-size:0.8rem;font-weight:600;margin-right:6px}
.ai-card{border-left:6px solid #e37400;background:rgba(227,116,0,0.08);padding:8px 12px;border-radius:6px;margin-bottom:6px}
.hu-card{border-left:6px solid #1a73e8;padding:8px 12px;border-radius:6px;margin-bottom:6px}
</style>""",
    unsafe_allow_html=True,
)


def chip(label, color):
    return f'<span class="chip" style="background:{color}">{label}</span>'


def missing(mod):
    st.info(f"`secondinspector.{mod}` is not available on this branch yet. "
            "This section lights up once it is merged.")


def import_mod(name):
    try:
        return importlib.import_module(f"secondinspector.{name}")
    except ImportError:
        return None


# ---------- background pipeline (only runs when the user clicks Analyze) ----------
def start_pipeline(clip: Path):
    job = {"done": False, "error": None, "out": None}

    def work():
        try:
            from secondinspector import pipeline
            asyncio.run(pipeline.run(str(clip), out_root=str(PROCESSED)))
            job["out"] = PROCESSED / clip.stem
        except Exception as e:  # surfaced in UI
            job["error"] = repr(e)
        finally:
            job["done"] = True

    threading.Thread(target=work, daemon=True).start()
    st.session_state.job = job


# ---------- sidebar ----------
st.sidebar.title("Second Inspector")
st.sidebar.caption("AI co-inspector. You confirm every finding.")
folders = h.discover_processed(PROCESSED)
mode = st.sidebar.radio("Mode", ["Replay processed room", "Analyze new clip"])
out_dir = None
if mode.startswith("Replay"):
    if folders:
        names = [p.name for p in folders]
        default = names.index("garage_door_video") if "garage_door_video" in names else 0
        out_dir = PROCESSED / st.sidebar.selectbox("Processed room", names, index=default)
    else:
        st.sidebar.warning("No processed folders in data/processed/.")
else:
    up = st.sidebar.file_uploader("Room clip", type=["mp4", "mov", "m4v"])
    job = st.session_state.get("job")
    running = bool(job and not job["done"])
    if up and st.sidebar.button("Analyze room", type="primary", disabled=running):
        RAW.mkdir(parents=True, exist_ok=True)
        clip = RAW / up.name
        clip.write_bytes(up.getbuffer())
        start_pipeline(clip)
        st.rerun()
    if job:
        if not job["done"]:
            with st.sidebar.status("Analyzing room (about 5 minutes)...", state="running"):
                st.write("Transcribing, matching findings, scanning frames.")
            time.sleep(3)
            st.rerun()
        elif job["error"]:
            st.sidebar.error(f"Pipeline failed: {job['error']}")
        else:
            st.sidebar.success("Analysis complete.")
            out_dir = job["out"]

page = st.sidebar.radio("Section", ["Review queue", "Room status", "Report"])
if out_dir is None:
    st.title("Second Inspector")
    st.write("Pick a processed room (replay) or upload a clip to analyze.")
    st.stop()
st.title(f"Inspection: {out_dir.name}")

review = import_mod("review")


def get_state():
    key = f"state::{out_dir}"
    if key not in st.session_state and review:
        st.session_state[key] = review.load(out_dir)
    return st.session_state.get(key)


def set_state(s):
    st.session_state[f"state::{out_dir}"] = s
    review.save(out_dir, s)


def room_status_page():
    cov = h.load_optional_json(out_dir, "coverage.json")
    level = h.load_optional_json(out_dir, "level.json")
    st.markdown(" ".join(chip(*h.status_chip(s)) for s in h.CHIPS), unsafe_allow_html=True)
    st.subheader("Coverage checklist")
    if not cov:
        st.info("No coverage.json for this room yet (built by the coverage step).")
    else:
        for room, info in cov.get("rooms", {}).items():
            items = info.get("items", [])
            counts = h.coverage_counts(items)
            summary = ", ".join(f"{n} {h.status_chip(s)[0].lower()}" for s, n in counts.items())
            with st.expander(f"{room} — {summary}", expanded=True):
                for it in items:
                    c1, c2 = st.columns([3, 2])
                    c1.write(it.get("item", "?"))
                    c2.markdown(chip(*h.status_chip(it.get("status"))), unsafe_allow_html=True)
                    ev = h.resolve_path(it.get("evidence_path"), ROOT)
                    if ev:
                        c1.image(str(ev), width=220)
    st.subheader("Floor level")
    if not level:
        st.info("No level.json (phone sensor readings) for this room.")
    else:
        for room, info in level.get("rooms", {}).items():
            st.metric(f"{room}: max slope", f"{float(info.get('max_slope_deg') or 0):.2f}°")
            if info.get("svg"):
                st.markdown(info["svg"], unsafe_allow_html=True)
        for f in level.get("findings", []):
            st.warning(f.get("description", str(f)))


def finding_card(f, state, pend):
    fid, ai = f["id"], h.is_ai(f)
    with st.container(border=True):
        img, body = st.columns([2, 3])
        ev = h.resolve_path(f.get("evidence_path"), ROOT)
        if ev:
            img.image(str(ev), width="stretch")
        else:
            img.caption("No evidence frame")
        badge = chip(h.source_label(f.get("source")), "#e37400" if ai else "#1a73e8")
        state_txt = "pending" if fid in pend else (f.get("status") or "")
        body.markdown(
            f'<div class="{"ai-card" if ai else "hu-card"}">{badge}'
            f'<b>{f.get("component_phrase") or ""} — {f.get("defect_phrase") or ""}</b>'
            f' &nbsp;<code>{h.fmt_time(f.get("t_start"))}</code> &nbsp;<i>{state_txt}</i></div>',
            unsafe_allow_html=True,
        )
        body.write(f.get("description") or "")
        if f.get("utterance"):
            body.markdown(f"> “{f['utterance']}”")
        if f.get("sop_section"):
            body.caption(f"SOP: {f['sop_section']}")
        if not review:
            return
        b1, b2, b3 = body.columns(3)
        if b1.button("Accept", key=f"acc{fid}", type="primary"):
            set_state(review.decide(state, fid, "accepted"))
            st.rerun()
        if b2.button("Edit", key=f"ed{fid}"):
            st.session_state[f"editing{fid}"] = True
        if b3.button("Reject", key=f"rj{fid}"):
            st.session_state[f"rejecting{fid}"] = True
        if st.session_state.get(f"editing{fid}"):
            with body.form(f"edform{fid}"):
                edits = {k: (st.text_area(k, value=str(f.get(k) or "")) if k == "description"
                             else st.text_input(k, value=str(f.get(k) or ""))) for k in EDITABLE}
                note = st.text_input("Note")
                if st.form_submit_button("Save edit"):
                    st.session_state[f"editing{fid}"] = False
                    set_state(review.decide(state, fid, "edited", edits=edits, note=note))
                    st.rerun()
        if st.session_state.get(f"rejecting{fid}"):
            with body.form(f"rjform{fid}"):
                note = st.text_input("Why reject?")
                if st.form_submit_button("Confirm reject"):
                    st.session_state[f"rejecting{fid}"] = False
                    set_state(review.decide(state, fid, "rejected", note=note))
                    st.rerun()


def review_page():
    if review:
        state = get_state()
        findings = list(review.candidates(out_dir))
        known = {f["id"] for f in findings}
        added = state.get("added", []) if isinstance(state, dict) else []
        findings += [f for f in added if f.get("id") not in known]
        pend = set(review.pending(state))
    else:
        missing("review")
        st.caption("Showing raw findings.json read-only.")
        state, findings, pend = None, h.raw_findings(out_dir), set()
    total = len(findings)
    done = total - len(pend)
    st.progress(done / total if total else 1.0,
                text=f"{done} of {total} reviewed" if review else f"{total} findings")

    for room, items in h.group_by_room(findings).items():
        st.subheader(room.title())
        for f in items:
            finding_card(f, state, pend)

    if not review:
        return
    with st.expander("Add missed finding"):
        with st.form("addform", clear_on_submit=True):
            new = {k: (st.text_area(k) if k == "description" else st.text_input(k)) for k in EDITABLE}
            if st.form_submit_button("Add finding"):
                new.update(source="inspector", status="accepted")
                review.add(state, new)
                set_state(state)
                st.rerun()
    st.divider()
    name = st.text_input("Inspector name for sign-off")
    if st.button("Sign inspection", type="primary", disabled=bool(pend) or not name):
        try:
            set_state(review.sign(state, name))
            st.success(f"Signed by {name}.")
        except ValueError as e:
            st.error(str(e))
    if pend:
        st.caption(f"{len(pend)} finding(s) still pending. Review all before signing.")


def report_page():
    report = import_mod("report")
    key = f"report::{out_dir}"
    if not report:
        missing("report")
    elif st.button("Generate report", type="primary"):
        st.session_state[key] = str(report.build(out_dir, review=get_state() if review else None))
    rp = st.session_state.get(key)
    if not rp and (out_dir / "report.html").is_file():
        rp = str(out_dir / "report.html")
    if rp:
        html = Path(rp).read_text(encoding="utf-8")
        st.download_button("Download report.html", html,
                           file_name=f"{out_dir.name}_report.html", mime="text/html")
        components.html(html, height=900, scrolling=True)


{"Review queue": review_page, "Room status": room_status_page, "Report": report_page}[page]()

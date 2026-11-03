# Demo gap analysis: Second Inspector web app

Branch: `demo-polish`, cut from `packaging` (1b12d6d). Reviewed on 2026-11-02 by running
`python -m secondinspector.webapp` in replay mode on the committed
`data/processed/garage_door_video/` demo, at desktop and phone (375 px) widths. I went through
start → Analyze/Replay → review queue → accept / edit / reject → add missing finding → sign-off →
Reports → Print / Save as PDF.

## What the demo data actually contains

This shapes what a judge can see, so it comes first:

- 2 spoken findings: "cracks along the door", which SAM did not locate, and "cracks around the frame", which SAM located at 75% confidence with a red box drawn on the frame.
- 1 AI-only finding: a faint wall scuff.
- 2 AI flags that independently matched spoken findings (`unspoken_covered_or_rejected` with `matches_spoken`).
- 2 floor-level sensor findings, for the kitchen and living room.
- **No video** (`proxy.mp4` and the raw clip are not in Git), **no `coverage.json`** and an empty transcript.

So "jump the video to this moment" and "coverage summary per room" have nothing to show in the
committed demo. The fixes below work without video and show the video when it exists.

## Ranked gaps

Impact is for the hackathon judge (J) and for a working inspector (I). Effort: S is under an hour,
M is a few hours, L is a day or more.

| # | Gap | Who | Impact | Effort | Status |
|---|-----|-----|--------|--------|--------|
| 1 | **The review screen's big evidence panel is static.** It always shows finding #1's thumbnail, and with no video the timestamp buttons only show a toast saying the video is unavailable. The most visual part of the screen does nothing. | J, I | High | M | **Fixed.** The panel is now a "Selected finding" stage with a large evidence frame (SAM's red box visible), time range, the inspector's spoken quote and trust badges. Clicking a card or its timestamp selects it; with video, it seeks. |
| 2 | **No visible reason to trust a finding.** SAM confidence, whether SAM located the defect, and the fact that a second AI pass independently flagged the same crack are all in `findings.json` but never shown. This is the core "AI checks your work" story. | J, I | High | S | **Fixed.** The API now returns `confidence`, `located` and `corroborated`. Cards show "Located in video · 75%", "Not pinpointed" or "AI saw it too". |
| 3 | **The landing page never explains the pipeline.** The hero copy is warm but vague ("a second pair of eyes"). A judge can't tell in 10 seconds what is narrated, what the AI does, or what Meta models are involved. | J | High | S | **Fixed.** A four-step strip: Narrate as you film → AI finds it in the video (Muse Spark + SAM 3.1) → A second look (Spark) → You approve & sign. |
| 4 | **The demo replay is a generic spinner.** Its three stages ("Read the inspector's narration", …) show only "Complete". | J | High | S | **Fixed.** Stages name the real steps and report results from the clip: "2 defects heard in the narration", "1 of 2 pinpointed in the video", "1 unmentioned issue flagged · 2 spoken confirmed by AI". |
| 5 | **Getting to the demo takes 3 clicks** (Analyze new clip → Replay tab → Start). | J | Med | S | **Fixed.** The hero has a "Watch the demo replay" button that opens the replay tab directly. |
| 6 | **Review is mouse-only.** Inspectors triaging dozens of findings want speed. | I | Med | S | **Fixed.** J/K move, A accepts, E edits, R rejects. After a decision it moves to the next pending finding. A hint row shows on pointer devices. |
| 7 | **The report's sign-off date is wrong in the evening.** `signed_at` is UTC, so a 7 pm sign-off in New York printed tomorrow's date, while "Generated" showed today's date. | I | Med | S | **Fixed.** The date is converted to local time, with a test. |
| 8 | **The report summary uses pipeline jargon** ("Status: uncertain", "Status: unrated") and doesn't say how the findings were produced. A client can't interpret it. | I, J | Med | S | **Fixed.** Labels now read "Located in video", "Needs on-site check" and "Measured". A "How this report was made" note gives the counts narrated by the inspector, flagged by AI, measured and added. It also says every finding was reviewed, but only when that is true. |
| 9 | **The report sidebar listed sections the report doesn't have** ("Evidence photographs", "Inspection & sign-off details"). | J | Low | S | **Fixed.** It now mirrors the generated report's sections. |
| 10 | `ruff check secondinspector` failed on `packaging` (UP017 in `review.py`). | dev | Low | S | **Fixed.** |
| 11 | **No video in the committed demo,** so the strongest moment (click a finding, watch the crack) can't be shown. | J | High | S–M | Open. Committing a trimmed 10–20 s `proxy.mp4` (a few MB) would enable it; the UI already handles it. This is a data and repo-size call for the team. |
| 12 | **No coverage checklist in the demo** (smoke detectors, GFCI, fans, panel). | J, I | High | M | Open. The coverage and smoke-alarm audit live on the `coverage` / `smoke-alarm` branches, which this task said not to merge. The review panel and report already render `coverage.json` when present. |
| 13 | **No severity or recommendation per finding** (e.g. "Repair: qualified carpenter", "Safety"). This is the main value of an inspection report to a client. | I | High | M | Open. It needs a schema change (`review.EDITABLE`, report template, edit form) and agreement on a severity scale. The report deliberately avoids inventing severity today. |
| 14 | **The client report looks plain:** no cover page, company logo, photo of the property or executive summary of "top issues". | I, J | Med | M | Partly fixed (provenance note, plain labels). A cover page and top-issues list are left for a design pass. |
| 15 | **Bounding boxes are baked into JPEGs.** The UI can't toggle the box or show it on raw frames. | I | Low | M | Open. The `box` coordinates are in the data, so an SVG overlay would work, but it needs each frame's source resolution to scale correctly. Not worth the risk before the demo. |
| 16 | **Live analysis progress is coarse** (3 stages, inferred from files on disk) with no ETA. | I | Med | M | Open. It needs pipeline progress hooks. Replay is what will be demoed. |
| 17 | **No undo after a decision.** You can re-decide, but there is no "undo last". | I | Low | S | Open. Re-deciding covers it; low value for the demo. |
| 18 | **Inspector-added findings can't be edited or deleted** once added. | I | Med | M | Open. It needs new server endpoints and `review.py` support. |
| 19 | **Clip naming is heuristic** (`roomTitle` hard-codes "garage" → "Garage & interior", although the findings are on the "first floor"). | J | Low | S | Open. A cosmetic mismatch; changing it risks the existing showcase checks. |
| 20 | **A guided "presenter mode"** (auto-advancing tooltips) | J | Med | M–L | Not done. The story strip, the one-click replay and the narrated replay stages cover most of what a guided tour would. |

## What a judge sees now (2-minute script)

1. **Landing:** the hero, then the four-step strip explains the pipeline and the models.
2. **Watch the demo replay:** the stages report real numbers from the clip.
3. **Review:** the first pending finding is selected. Its evidence frame, the quote "cracks along the door" and "Not pinpointed · AI saw it too" are shown. Press J to reach "Frame — Crack" with the SAM box and "Located in video · 75%". Press J again to reach the AI-only "Wall — Scuff" ("Not mentioned in the narration. AI flagged it from the footage at 00:30.").
4. Press A / E / R to decide. Add a missing finding. Sign off.
5. **Report:** the summary explains how it was made, the dates are right and the labels are plain. Print / Save as PDF.

## Inspector daily-use notes (not fixed, for the roadmap)

- **Speed:** keyboard review helps. Bulk "accept all located findings" would help more on long clips.
- **Trust:** show the raw frame and the boxed frame side by side; show the transcript with the matching words highlighted (the transcript is empty in the demo).
- **Editing:** add free-text recommendation and severity fields; allow editing inspector-added items.
- **Report:** add a cover page, a top-issues summary, client-friendly wording for each SOP section, and page numbers in print.

# UX critique and fixes: Second Inspector web app

Branch: `ux-skills-pass`, cut from `demo-polish`. This follows the "critique, fix the top 3, then polish" loop
suggested for the hackathon. I ran the `design-critique` skill against the running app (replay mode,
1366 × 850 and 375 × 812) instead of installing `shadcn` and `impeccable`, for these reasons:

- **shadcn/ui is a React component kit.** This app is vanilla JS with no build step and no Node dependencies,
  so adopting it would mean a rewrite a day before the deadline.
- **`npx skills add pbakaus/impeccable` runs third-party code.** The research itself flagged that it passed
  only 1 of 3 security scanners. Its `critique` / `audit` / `polish` steps map onto the design-critique and
  accessibility checks done here.

## Overall impression

The visual identity is strong: a calm green palette, serif headlines and a clear four-step story. The biggest
problem was **scale**. Most of the interface was set at 9–11 px, so on a laptop or a projector, which is how
judges will see it, the findings, badges and buttons were hard to read.

## Findings

| # | Finding | Severity | Status |
|---|---------|----------|--------|
| 1 | **Text too small.** Measured on the review screen, 69 of 115 text elements were 9–10 px, including finding descriptions (11 px), quotes (10 px), trust badges (9 px) and decision buttons (10 px). | 🔴 Critical | **Fixed.** Type scale raised: 7→10, 8→11, 9→12, 10→13, 11→14, 12→14, 13→15 px. Headings above 14 px are unchanged, so the hierarchy holds. |
| 2 | **Low-contrast grey text.** Body copy (`#747d73`), card metadata, step labels, quotes and badge text were 2.4–4.1 : 1 on the paper background, below WCAG AA (4.5 : 1). | 🔴 Critical | **Fixed.** 38 text colours on light backgrounds are darkened in hue to ≥ 4.8 : 1. Decorative strokes (house drawing, arrows, separators) and text on the dark sidebar and video frame are untouched. Sidebar captions are brightened. |
| 3 | **"Watch the demo replay" opened a modal that needed a second click.** The button promises a demo but asks the presenter to pick a clip and press Start. | 🟡 Moderate | **Fixed.** It starts the replay of the first processed clip right away. The modal is still reachable from Analyze new clip → Replay. |
| 4 | **Decided findings looked like undecided ones.** An accepted card still said "Accept"; only the fill colour changed. | 🟡 Moderate | **Fixed.** The chosen button now reads **Accepted** or **Rejected**. |
| 5 | **Badge row clutter.** A card can carry four same-weight chips (source, location, AI agreement, decision), so nothing stands out. | 🟢 Minor | Open. Possible fix: move the decision into the action bar (now partly done by #4) and drop the duplicate "Accepted" chip. |
| 6 | **Sensor thumbnails are unreadable.** The floor-level charts are cropped to 105 px squares. | 🟢 Minor | Open. Possible fix: show a level icon with the slope number instead of a chart crop. |
| 7 | **The committed demo is already signed off.** A judge who opens the app sees "All caught up" and a signed review, and so misses the decision step. | 🟡 Moderate | Open. `data/processed/garage_door_video/review.json` is local and untracked; delete it before the demo to start from a fresh, unreviewed state. |

## What works well

- The four-step story and the replay stages explain the pipeline in seconds.
- The selected-finding panel shows the evidence frame, spoken quote and trust badges side by side.
- Keyboard review (J/K/A/E/R), focus rings, reduced-motion support and native modal focus are already in place.
- There is no horizontal scroll at 375 px, both before and after the type change.

## Before the demo

1. Delete or move `data/processed/garage_door_video/review.json` so the review starts unreviewed.
2. Give one person the task "review this clip and produce a report" and watch without helping. Fix wherever
   they hesitate.

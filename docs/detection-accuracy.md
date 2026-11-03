# Detection accuracy: smoke alarms first

A kitchen walkthrough clip (23 s, 720x1280, 120 fps phone video) showed a ceiling detector for about 6 s, and the
pipeline reported no smoke detector at all. This note covers why, what was measured, and what changed.

## Diagnosis

The device is a commercial-style **heat detector** head on a kitchen ceiling (white base, grey vented cap). It
is in frame from 14 s to 19 s and again around 21-22.5 s, mid-frame, about 100-190 px wide in a 720 px frame,
evenly lit and mostly sharp. The inspector's only words are "I'm in the kitchen right now, this is the sprinkler".

SAM was **not** the problem. `sam.run_concept` with the existing phrase `"smoke detector"` on the 2 fps proxy found
one track on 14 frames (14.0-22.5 s, confidence 0.84). The boxes sit tightly on the device. The proxy frames
SAM skipped (39-42) are frames where the detector is out of view. So more fps or a higher-resolution proxy has
nothing to recover here. The proxy is already at the source's 720x1280 resolution.

The detection was lost in two places after SAM:

1. **Coverage never searched for it.** `coverage.check` only ran an item's SAM phrase if a room that requires it
   was in the clip (or the room was unknown). The narration names the room "kitchen", and smoke detectors are
   required only in bedrooms and hallways, so the search was skipped.
2. **Spark's crop check rejected it.** Even with a box, the check question was "a smoke or carbon monoxide alarm
   (not a light fixture, speaker, sprinkler or motion sensor)". Spark answered `no`: "ceiling heat detector, not
   smoke alarm".

Since coverage never confirmed a detector, `alarm.audit_rooms` never ran either.

A third failure only showed up after fixing the first two:

3. **Spark was shown the worst frame of the track.** `coverage.top_tracks` picks each track's frame by
   confidence, but SAM gives a whole track one confidence (0.84 on all 14 frames). So ties went to the first
   frame, 28, where the detector is a 32x85 px sliver at the frame edge, and Spark answered `unclear`. Frame 34
   shows it at 188x181 px.

## What was tried

Clips (all under `data/processed/`; earlier clips were re-measured from their cached proxies):

| Clip | Contents |
|---|---|
| **kitchen** (new) | kitchen walkthrough, ceiling heat detector, called a "sprinkler" |
| **first-floor** | residential smoke/CO alarm on a hallway ceiling, no test |
| **first-floor-check** | same alarm, push-button test |
| **stairs** | stairs walkthrough, no alarm (false-positive control) |

### SAM phrases (video mode, 2 fps proxy; 1 SAM call per phrase per clip)

Frames with a box / tracks / best confidence:

| Phrase | kitchen | first-floor | first-floor-check | stairs |
|---|---|---|---|---|
| `smoke detector` (current) | 14 / 1 / 0.84 | 20 / 3 / 0.94 | 73 / 1 / 0.94 | 0 |
| `smoke alarm` | 14 / 1 / 0.82 | 22 / 2 / 0.93 | 75 / 2 / 0.92 | 0 |
| `heat detector` | 0 | 0 | 0 | 0 |
| `carbon monoxide detector` | 0 | 3 / 1 / 0.75 | 68 / 1 / 0.74 | 0 |
| `round white device on ceiling` | 13 / 1 / 0.93 | 20 / 2 / 0.91 | 73 / 1 / 0.84 | 0 |

`smoke detector` matches or beats every alternative on recall. `smoke alarm` adds 2 frames (1 s earlier) on
first-floor and nothing elsewhere. `heat detector` finds nothing, not even on the clip that has one. No phrase
produced a false positive on stairs. Merging phrases would cost 2-5x the SAM calls for no meaningful gain.

### Spark crop check (1 Spark call per batch of up to 8 boxed frames)

| Case | Old question | Broader question (smoke, heat or CO) |
|---|---|---|
| kitchen heat detector, frame 34 | **no** ("heat detector, not smoke alarm") | **yes** |
| first-floor-check alarm, frame 5 | yes | yes |
| first-floor, box on empty ceiling | no | no |
| kitchen tube light | no | no |
| stairs wall corner | no | no |

The broader question fixes the heat detector and changes nothing else.

**Zoomed crop instead of a boxed full frame** (same Spark calls, 3 small boxes: a 101x97 px detector, a 32x85 px
detector cut off at the frame edge, and a 51x53 px outlet): the verdicts were identical (yes / unclear / yes),
so a zoomed re-check before rejecting was not built.

### SAM image mode and box/point prompts (1 SAM call per keyframe)

The Meta API exposes SAM 3.1 image segmentation through the same Responses call: an `input_image` (data URL)
instead of `input_video`, parsed with `meta_sam_parser.image_segmentation_format()`. Box and point prompts are
supported through `meta_sam_parser.build_object_prompt`, sent as the `input_text`. On a 720x1280 keyframe at
21.5 s, where the detector is half cut off at the right edge:

| Prompt | Box | Confidence |
|---|---|---|
| text `smoke detector` | (633, 867, 720, 964) | 0.55 |
| one positive point on the detector | (632, 867, 720, 965) | 0.94 |

Both work. That makes a "Spark finds the time and rough spot, SAM segments from a point" fallback possible. It
was not built, because SAM in video mode never missed a visible detector on these clips, so there was nothing
for it to recover.

### Retraining or fine-tuning SAM

Not available. The API lists `sam-3.1` as a model, but `fine_tuning.jobs.list()` returns 404, and nothing
documents uploading labelled images for SAM. The nearest thing is the visual prompt above: a box or point on
one frame (a visual exemplar), which video mode propagates. That covers the "teach it what this looks like"
case per clip without training. Because the misses here were downstream of SAM, it would not have helped.

## Results

| Clip | Technique | Detector reported? | SAM confidence | Extra calls per clip |
|---|---|---|---|---|
| kitchen | baseline pipeline | **no** (not searched; Spark would say no) | 0.84 | - |
| kitchen | phrase merge (5 phrases) | no (same coverage gate) | 0.93 best | +4 SAM |
| kitchen | broader Spark question only | no (still not searched) | 0.84 | 0 |
| kitchen | search every room + broader question | no: Spark `unclear` on the frame-28 sliver | 0.84 | +1-2 SAM when a room type is missing |
| kitchen | **+ biggest view of each track** | **yes**: `seen_not_mentioned`, frame 36, "ceiling-mounted smoke/heat detector" | 0.84 | same as above |
| first-floor | baseline / new | yes / yes (new view: frame 19, 200x238 px; Spark reads "Kidde") | 0.94 | 0 |
| first-floor-check | baseline / new | yes / yes (new view: frame 15, 362x387 px; Spark reads "Kidde") | 0.94 | 0 |
| stairs | baseline / new | no detector / no detector (correct; no phrase fires) | - | 0 |

The kitchen row is a full end-to-end pipeline run. The earlier clips were re-checked from their cached SAM
runs: the new `top_tracks` pick, rendered and sent to Spark with the new question.

With the detector confirmed, `alarm.audit_rooms` now runs on the kitchen clip. Spark could not read a brand or
model (`unknown`, low confidence), no manual was found, and no test was heard, so the audit has no tests. That is
correct for this clip.

One side effect on the same run: the kitchen outlet's GFCI flag disappeared. Its representative frame moved from
18 to 20 (51x53 to 55x58 px, same outlet, plug covering its face), and Spark's GFCI answer went from `no` to
`unclear`. Re-asking about both frames twice gave `unclear` all four times. So this is Spark being inconsistent
on a 50 px outlet with a plug in it, not the frame choice. "Unclear" is a fair answer for that view.

## Decision

Built (in `secondinspector/coverage.py`, tested in `tests/test_coverage.py`):

- **Every checklist item is searched in every clip.** `expected` still comes from the room type, so a detector in
  a kitchen is reported as seen but not required, and items that were neither expected nor seen are still
  dropped. This also helps other small fixtures: an exhaust fan or GFCI outlet in a room the narration labelled
  differently is now reported instead of silently skipped. Cost: at most one SAM call per item whose rooms were
  missing from the clip (SAM results are cached per phrase, so a re-run costs nothing).
- **The detector check accepts smoke, heat and CO detectors, residential or commercial**, and the mention
  keywords include "heat detector" and "fire alarm". `alarm.IDENTIFY_PROMPT` now says smoke, heat or CO, to
  match the `heat` kind it already allowed.
- **Each track is shown to Spark at its biggest box when confidences tie** (`coverage.top_tracks`), the same
  rule `alarm.best_views` already used for its crops. This matters most for small fixtures (detectors, outlets,
  fan grilles) that enter the frame at an edge.

Not built, because it was measured and gave no gain on these clips: phrase merging, zoomed re-checks, a higher
fps or resolution proxy, and SAM image/point fallback.

`scripts/detection_bench.py` reruns the phrase table from the SAM cache:

    uv run --env-file .env python scripts/detection_bench.py "smoke detector|smoke alarm" data/processed/*/

## Open

- **The narration disagrees with the picture.** The inspector called the detector a "sprinkler", so its status is
  `seen_not_mentioned`. Flagging when the narration's name contradicts what Spark saw would be worth adding.
- **Heat detector audits.** `alarm.audit_rooms` now runs for this clip. Commercial detector heads are usually tested
  from a fire panel, not a push button, so the manual lookup and audit may have little to work with.
- **Only four clips.** A clip where SAM really misses a small or distant detector would be needed to justify the
  Spark-locates, SAM-point-prompt fallback. The API pieces for it are confirmed above.
- **GFCI reads on small, plug-covered outlets are unstable** (see above). Showing Spark two or three frames of
  the track instead of one, or asking it to say `unclear` when the face is covered, would make the flag
  steadier.
- The original video was only available for the new clip, so the earlier clips were re-measured from their
  proxies and cached SAM runs, not re-run end to end.

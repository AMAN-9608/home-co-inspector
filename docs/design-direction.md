# Design direction: Second Inspector

Branch: `product-redesign`. The direction follows the plan → review → build → critique loop from Anthropic's
`frontend-design` skill. It applies the anti-pattern lists from Impeccable and `frontend-design`, and checks
interactions against Vercel's Web Interface Guidelines. None of these were installed: they are guidance, and
this app has no build step (see "Research" below).

## Brief

- **User:** a licensed home inspector back at a desk or in the truck, with a walkthrough they narrated on their phone.
- **One job:** turn that clip into a signed report by deciding on each finding. It should be quick, and the inspector has to trust what they sign.
- **Judge in 10 seconds:** what does the AI actually do, and who has the final say?

## Concept: a marked-up drawing set

Inspectors and builders already read drawings that carry three kinds of marks: graphite for the drawing, a
non-photo blue pencil for guides, and red pen for corrections. The interface uses the same three marks, and each
colour always means one thing:

| Mark | Colour | Means |
|------|--------|-------|
| Graphite | `#1C2328` ink, `#55606A` secondary | The inspector: their words, their decisions, all chrome |
| Blue pencil | `#1D6AAE` on `#E4EFF8` | The AI's second look: findings nobody mentioned, AI agreement |
| Red pen | `#C2302A` on `#FBE8E6` | A defect, which matches SAM's red box in the evidence frames |
| Approved | `#1F7A4D` on `#E2F2E8` | Accepted findings and sign-off |
| Paper | `#F3F5F4` page, `#FFFFFF` sheet, `#D3DADD` rule | Surfaces |

All text colours are at least 4.8:1 against the paper.

**Type.** One family, Archivo, used at different widths. Headings are semi-expanded (`font-stretch:118%`), which
recalls drawing title blocks. Body text is normal width at 16 px, and numbers are tabular. There are no all-caps
eyebrows, no serif display headline and no monospace labels.

**The memorable element.** The review screen's title block (Walkthrough / Property / Source clip / Status), as on a
drawing sheet, and the sign-off stamp. The stamp is the one orchestrated animation. Everything else is quiet.

## Layout

```
Home
┌ [⌂⌂ Second Inspector]   Home  Clips 1  Reports        [+ Upload a walkthrough] ┐
│ Turn a walkthrough video into a          ┌ real evidence frame ─┐ You said       │
│ signed inspection report.                │   (red SAM box)      │ SAM 3.1 found  │
│ [▶ Watch the demo]  [Upload a walkthrough]└─────────────────────┘ AI agrees     │
│ 1 clip to review ─────────────────────────────────────────────── All clips      │
│ [thumb] Garage & interior   2 from your narration, 1 flagged by AI  [Review]     │
│ How it works  ①──②──③──④                                                       │
└──────────────────────────────────────────────────────────────────────────────────┘

Review (master / detail)
┌ ← Clips ┌ Walkthrough ─┬ Property ─┬ Source clip ┬ Status ───┐                    ┐
│         └──────────────┴───────────┴─────────────┴───────────┘                    │
│ ▓▓▓░░ 2 of 5 reviewed      J K move · A accept · E edit · R reject  [Sign off]    │
│ ┌ findings ──────┐ ┌ selected finding ──────────────────────────────────────────┐ │
│ │ ○ Door   crack │ │ big evidence frame                                          │ │
│ │ ✓ Frame  crack │ │ crack   00:10–00:12                                         │ │
│ │ ○ Wall   scuff │ │ Door                                                        │ │
│ │ + Add finding  │ │ “cracks along the door”  (you, at 00:10)                    │ │
│ └────────────────┘ │ ✓ Found in the video (75% match)  ✓ A second AI pass agrees │ │
│                    │ [Accept A] [Edit E]                              [Reject R] │ │
│                    └─────────────────────────────────────────────────────────────┘ │
```

One decision at a time. After you accept, edit or reject, it moves to the next finding that still needs a
decision. When none are left, **Sign off** becomes the obvious next step.

## Rules applied

- **Plain copy.** Sentence case, active verbs, no slogans, no arrows in buttons, no middle-dot chains. An action
  keeps its name through the flow (Accept → Accepted, Sign off → Signed off).
- **Status never by colour alone.** Every state has an icon and words.
- **Surfaces are not a card kit.** Lists are rows on one sheet separated by rules. The how-it-works section is a real
  numbered sequence, the only place numbers are used. Radii vary by role: sheets 4 px, buttons 6 px, tags 3 px.
- **Motion.** One orchestrated moment (the stamp), the replay scan, and feedback on actions. No fade-up on every
  section. `prefers-reduced-motion` turns it all off.
- **Quality floor.** Visible focus, 44 px targets on touch, no horizontal scroll at 375 px, labelled controls,
  `aria-live` toasts, a page `<title>` per screen, and a recovery path on every error.

## Research

- [Anthropic `frontend-design` skill](https://github.com/anthropics/skills/tree/main/skills/frontend-design):
  the process, the "visual structure is information" rule, and its anti-patterns (eyebrows, arrows on buttons,
  middle-dot meta, the SaaS card kit, the cream background with serif look).
- [Impeccable](https://github.com/pbakaus/impeccable): its critique/polish/harden structure, plus anti-patterns
  such as cards in cards, grey text on colour, and the "tasteful default".
  It is not installed: `npx skills add` runs third-party code, and its listing passed only 1 of 3 security scanners.
- [Vercel Web Interface Guidelines](https://github.com/vercel-labs/web-interface-guidelines): interaction,
  feedback, form and accessibility checks.
- shadcn/ui was skipped. It is a React kit, and this app is dependency-free vanilla JS.

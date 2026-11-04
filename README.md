# Home Co-Inspector

Home Co-Inspector turns narrated home-inspection videos into findings with visual evidence. It combines Muse Spark for narration and evidence checks, Muse Wonder for an independent video review, and SAM 3.1 for localization. The inspector accepts, edits, or rejects findings, adds missing observations, and signs off before generating a report.

[About the product](https://aman-9608.github.io/home-co-inspector/about/) · [Interactive demo](https://aman-9608.github.io/home-co-inspector/demo/)

## Run locally

Install [Git](https://git-scm.com/downloads) and [uv](https://docs.astral.sh/uv/getting-started/installation/), then run from a terminal:

```sh
git clone https://github.com/AMAN-9608/home-co-inspector.git
cd home-co-inspector
uv sync --locked
```

The project requires Python 3.12 or newer; uv can provision Python when needed.

Install FFmpeg and ensure both `ffmpeg` and `ffprobe` are on PATH. Copy `.env.example` to `.env` in the repository root (or create `.env`) and set your Meta Model API key:

```dotenv
MODEL_API_KEY=your_model_api_key
```

Start the app from the repository root with live analysis enabled:

```sh
uv run --env-file .env python -m secondinspector.webapp
```

Open http://127.0.0.1:8000. The optional `base_url` environment variable overrides the default Meta API endpoint.

Raw videos belong in `data/raw/` under the repository root. Uploading through the app saves the video there automatically and starts analysis. The pipeline writes findings, transcripts, and evidence into `data/processed/<clip-name>/`. Placing a video in `data/raw/` alone does not start analysis; upload it through the app or run the pipeline explicitly.


## Checks

Run from the repository root. The test suite also requires Node.js for its browser-backend contract test:

```sh
uv run pytest -q
node --check web/app.js
```

The optional local-app browser check uses the installed Microsoft Edge browser, a temporary workspace, and port 8766. It does not change your recordings:

```sh
uv run --with playwright python scripts/check_showcase.py
```

The interface includes responsive layouts, keyboard focus and native modal focus management, reduced-motion support, 130 ms press feedback, and short transitions for cards, steps, and sign-off. Typography uses Google Fonts when available and system fallbacks otherwise.

The GitHub Pages browser check uses Microsoft Edge and temporary port 8767:

```sh
uv run --with playwright python scripts/check_pages.py
```

## Repository layout

- `secondinspector/`: analysis pipeline, review state, report rendering, and local web server.
- `web/`: app interface, landing page, static-demo adapter, and sample montage.
- `scripts/build_pages.py`: builds the static landing page and demo into `dist/`.
- `tests/`: unit, integration, and browser-backend contract checks.
- `data/processed/garage_door_video/`: tracked sample findings and evidence.

# Second Inspector showcase

Run from the repository root:

```sh
uv run --env-file .env python -m secondinspector.webapp
```

Open http://127.0.0.1:8000. If you only want to review existing clips and do not have an `.env`, omit `--env-file .env`.

The original Streamlit interface is still available with `uv run streamlit run app.py`. Both interfaces read the same processed recordings and save decisions in each recording's `review.json`.

## Run on another laptop

After the `packaging` branch has been pushed, install Git and uv, then run:

```sh
git clone --branch packaging https://github.com/AMAN-9608/second-inspector.git
cd second-inspector
uv sync --locked
uv run python -m secondinspector.webapp
```

Open http://127.0.0.1:8000. The project requires Python 3.12 or newer; uv can provision Python when needed. No Node.js, frontend build, Playwright, or PDF library is needed to run the app.

For **live analysis**, also install FFmpeg and ensure both `ffmpeg` and `ffprobe` are on PATH. Create a local `.env` in the repository root:

```dotenv
MODEL_API_KEY=your_model_api_key
```

Then start with `uv run --env-file .env python -m secondinspector.webapp`. The optional `base_url` environment variable overrides the default Meta API endpoint.

For **demo replay**, credentials and FFmpeg are not needed. Only `data/processed/garage_door_video/` is included in Git. Other local recordings must be copied separately into `data/processed/` to reproduce the same clip history. Copied reviews retain their saved decisions and signatures.

Neither `pyproject.toml` nor `uv.lock` received new dependencies for this interface. Uvicorn is already installed through Streamlit. The pypdf and Playwright packages used for development verification are not runtime requirements.

## Showcase flow

1. Choose **Watch the demo replay** on the overview, or **Analyze new clip**. Upload a new recording for live analysis, or choose **Replay a processed clip** for a short, explicitly labeled demo sequence using saved results.
2. Review the evidence. Click a finding (or its timestamp) to show its evidence frame, spoken quote and trust badges in the side panel. Accept a finding, edit and accept it, or reject it with an optional reason. Add your own observation with **Add missing finding**. Keyboard: J/K move, A accept, E edit, R reject.
3. Enter your inspector name and confirm the review to sign off. Every candidate finding must have a decision first.
4. Open **Reports** to view a signed-off inspection. Use **Print / Save as PDF** to print or save the report.

Live analysis uses the existing Spark/SAM pipeline and requires its existing credentials (`MODEL_API_KEY`) and media tools. Its duration depends on the recording and services. Upload names get unique suffixes so an existing recording is never overwritten. The demo replay does not run the models or reset reviews.

Report organization follows the supplied residential inspection reference: property and inspector details, contents, summary, findings grouped by system and room, evidence, coverage, and limitations. Severity is not invented for findings that lack a severity assessment. Generated reports use the fictional demo address 123 Jane Doe Street, Demo City, NY 100001.

## Floor level from a phone

In review, **Floor level → Measure with your phone** shows how to open the level page for that inspection. Phones only expose the tilt sensor over HTTPS, so start a tunnel to the workspace port:

```sh
cloudflared tunnel --url http://localhost:8000
```

On the phone, open the printed `https://….trycloudflare.com` link followed by `/level?clip=<clip id>`. Tap **Start sensor**, run **Flip calibrate** once, then lay the phone flat (top edge toward the same wall each time) and **Record** each spot. Every reading is saved to that clip's `level_readings.json` and analyzed at once; spots steeper than 0.45° become pending **Sensor measurement** findings with a slope map, and the review panel updates live. A new reading withdraws an earlier sign-off. The standalone `python -m secondinspector.level serve` still works.

This is a local, single-inspector workspace. Jobs run in memory and do not survive a server restart; saved review decisions do. Reload after making changes in another interface. Further edits invalidate a previous sign-off.

## Checks

```sh
uv run pytest -q
node --check web/app.js
```

The optional browser check uses the installed Microsoft Edge browser, a temporary workspace, and port 8766. It does not change your recordings:

```sh
uv run --with playwright python scripts/check_showcase.py
```

The interface includes responsive layouts, keyboard focus and native modal focus management, reduced-motion support, 130 ms press feedback, and short transitions for cards, steps, and sign-off. Typography uses Google Fonts when available and system fallbacks otherwise.

# Home Co-Inspector showcase

Run from the repository root:

```sh
uv run --env-file .env python -m secondinspector.webapp
```

Open http://127.0.0.1:8000. If you only want to review existing clips and do not have an `.env`, omit `--env-file .env`.

The original Streamlit interface is still available with `uv run streamlit run app.py`. Both interfaces read the same processed recordings and save decisions in each recording's `review.json`.

## GitHub Pages demo

This branch also builds a static demo that can be hosted on GitHub Pages. It uses the existing tracked garage findings and evidence images. The included 35-second silent video is a **montage of those evidence frames**, not the original walkthrough; the frame changes roughly match the findings' timestamps. It makes no model calls and has no real upload feature. Review decisions, added findings and signatures stay in the visitor's browser and can be removed by clearing site data. Reports are clearly marked as demos and are generated from the current browser-local decisions.

Build and preview locally:

```sh
uv run python scripts/build_pages.py dist
uv run python -m http.server 8767 --directory dist
```

Open http://localhost:8767/. The regular Python app continues to run with the command above. The build deliberately copies only the curated sample and selected evidence; it does not include `.env`, raw recordings, existing reviews, or other processed folders. The source material and generated Pages site are public when deployed, so review the sample images before publishing.

To publish: push `github-pages-demo`, then under the repository's **Settings → Pages → Build and deployment**, select **GitHub Actions** as the source. The `GitHub Pages demo` workflow runs on pushes to this branch and can also be run manually. If the first run happened before Pages was configured, run it again from the Actions tab. The expected project URL is `https://aman-9608.github.io/home-co-inspector/`. GitHub Pages hosting availability depends on the repository's visibility and GitHub plan.

## Run on another laptop

After the `github-pages-demo` branch has been pushed, install Git and uv, then run:

```sh
git clone --branch github-pages-demo https://github.com/AMAN-9608/home-co-inspector.git
cd home-co-inspector
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

1. On **Home** or **Clips**, open a saved clip to review it. In the local app, choose **Upload a walkthrough** to analyze a new recording. The home figure is a real evidence frame annotated with what the inspector said, what SAM 3.1 found and whether a second AI pass agrees.
2. Review one finding at a time. The list on the left shows each finding's status and source (your narration, AI only, level sensor). The selected finding shows its evidence frame, your spoken quote, the evidence checks and **Accept**, **Edit** and **Reject**. After each decision the next undecided finding opens. Keyboard: J/K move, A accept, E edit, R reject. Use **Add missing finding** for anything the AI missed.
3. When every finding has a decision, **Sign off on this clip** turns green. Enter your name and confirm.
4. Open **Reports** to view a signed inspection, then **Print / Save as PDF**.

The visual language is described in `docs/design-direction.md`: graphite for the inspector, blue pencil for the AI and red pen for defects.

Live analysis uses the existing Spark/SAM pipeline and requires its existing credentials (`MODEL_API_KEY`) and media tools. Its duration depends on the recording and services. Upload names get unique suffixes so an existing recording is never overwritten. The demo replay does not run the models or reset reviews.

Report organization follows the supplied residential inspection reference: property and inspector details, contents, summary, findings grouped by system and room, evidence, coverage, and limitations. Severity is not invented for findings that lack a severity assessment. Generated reports use the fictional demo address 123 Jane Doe Street, Demo City, NY 100001.

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

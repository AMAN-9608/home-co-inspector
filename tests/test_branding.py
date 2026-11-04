"""User-facing app and report names use the same product branding."""
import asyncio
from pathlib import Path

import httpx

from secondinspector import report
from secondinspector.webapp import Workspace

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/report_min'


def test_local_web_pages_use_home_co_inspector(tmp_path):
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=Workspace(tmp_path)), base_url='http://localhost') as client:
            home = (await client.get('/')).text
            app = (await client.get('/app.js')).text
            assert 'Home Co-Inspector' in home and 'Home Co-Inspector' in app
            assert 'Second Inspector' not in home and 'Second Inspector' not in app

    asyncio.run(run())


def test_web_entrypoint_labels_use_home_co_inspector():
    text = (ROOT / 'web/index.html').read_text(encoding='utf-8')
    assert 'Home Co-Inspector' in text
    assert 'Second Inspector' not in text


def test_generated_report_uses_home_co_inspector():
    html = report.render(FIXTURE, None)
    assert 'Home Co-Inspector' in html
    assert 'Second Inspector' not in html


def test_old_report_footer_is_rebranded_without_changing_inspector_text():
    html = ('<p>Inspector note: Second Inspector was mentioned here.</p>'
            '<footer>Prepared with Second Inspector, an AI assistant. AI-detected findings need review.</footer>')
    updated = report.rebrand_legacy_report(html)
    assert 'Inspector note: Second Inspector was mentioned here.' in updated
    assert '<footer>Prepared with Home Co-Inspector, an AI assistant.' in updated


def test_redundant_watch_demo_button_is_removed():
    app = (ROOT / 'web/app.js').read_text(encoding='utf-8')
    assert 'Watch the demo' not in app
    assert 'data-action="demo"' not in app

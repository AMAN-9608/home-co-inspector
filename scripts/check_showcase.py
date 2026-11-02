"""End-to-end check against an isolated workspace, using the installed Edge browser."""
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    folder = root / 'data/processed/demo-room'
    folder.mkdir(parents=True)
    (folder / 'findings.json').write_text(json.dumps({'clip': r'data\raw\original walkthrough.mp4', 'spoken': [{'room': 'garage', 'component_phrase': 'Door trim', 'defect_phrase': 'crack', 'description': 'A crack in the door trim.', 't_start': 2}], 'unspoken': [{'room': 'garage', 'component_phrase': 'Wall', 'defect_phrase': 'scuff', 'description': 'An unmentioned scuff.', 't_start': 6}]}))
    (folder / 'coverage.json').write_text(json.dumps([{'room': 'garage', 'items': [{'item': 'electrical_panel', 'label': 'Electrical panel', 'status': 'mentioned_not_seen'}]}]))
    server = subprocess.Popen([sys.executable, '-m', 'secondinspector.webapp', '--root', str(root), '--port', '8766'], cwd=ROOT, stdout=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                if httpx.get('http://127.0.0.1:8766/api/clips').status_code == 200:
                    break
            except httpx.ConnectError:
                pass
            time.sleep(.1)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            page = browser.new_page(viewport={'width': 1440, 'height': 1000}, reduced_motion='reduce')
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto('http://127.0.0.1:8766')
            page.get_by_role('heading', name='A second pair of eyes.').wait_for()
            assert page.locator('.top-meta').count() == 0, 'Top-bar status and date should be removed'
            assert page.locator('.profile').count() == 0, 'Sidebar profile should be removed'
            assert page.locator('#nav [data-page="signed"]').count() == 0, 'Use Reports instead of a duplicate signed-off tab'
            assert page.locator('.clip-card-meta > span').first.inner_text() == '1 from your inspection'
            assert page.locator('.clip-card .ai-text').inner_text().strip() == '1 flagged by AI'
            page.route('**/api/clips', lambda route: route.fulfill(json=[]))
            page.reload()
            page.get_by_role('heading', name='Your first walkthrough starts here.').wait_for()
            assert page.locator('.clip-card').count() == 0
            page.get_by_role('button', name='Analyze new clip').first.click()
            assert page.locator('.upload-choose').count() == 1, 'Provide a centered file picker button'
            for width in (1440, 390):
                page.set_viewport_size({'width': width, 'height': 1000})
                zone = page.locator('#drop-zone').bounding_box()
                choose = page.locator('.upload-choose').bounding_box()
                assert abs((choose['x'] + choose['width']/2) - (zone['x'] + zone['width']/2)) < 1
            page.set_viewport_size({'width': 1440, 'height': 1000})
            page.get_by_role('button', name='Analyze clip', exact=True).click()
            assert page.locator('#upload-error').inner_text() == 'Choose a walkthrough clip first.'
            with page.expect_file_chooser() as chooser:
                page.get_by_role('button', name='Choose file', exact=True).click()
            chooser.value.set_files({'name': 'test walkthrough.mp4', 'mimeType': 'video/mp4', 'buffer': b'test video'})
            assert page.locator('#upload-filename').inner_text() == 'test walkthrough.mp4'
            page.get_by_role('button', name='Replay a processed clip').click()
            assert page.get_by_role('button', name='Start demo analysis').is_disabled()
            page.keyboard.press('Escape')
            assert not page.locator('dialog').is_visible()
            page.unroute('**/api/clips')
            page.reload()
            page.get_by_role('heading', name='A second pair of eyes.').wait_for()
            page.locator('#nav [data-page="history"]').click()
            page.get_by_role('searchbox', name='Search clips').fill('no matching walkthrough')
            page.get_by_role('heading', name='No clips here yet.').wait_for()
            page.get_by_role('searchbox', name='Search clips').fill('')
            assert page.locator('.clip-card').count() == 1
            page.get_by_role('button', name='Signed off', exact=True).click()
            page.get_by_role('heading', name='No clips here yet.').wait_for()
            page.get_by_role('button', name='Needs review', exact=True).click()
            assert page.locator('.clip-card').count() == 1
            page.locator('#nav [data-page="reports"]').click()
            page.get_by_role('heading', name='The final word is yours.').wait_for()
            page.locator('#nav [data-page="overview"]').click()
            page.get_by_role('heading', name='A second pair of eyes.').wait_for()
            original_clip = httpx.get('http://127.0.0.1:8766/api/clips').json()[0]
            showcase_clips = [{**original_clip, 'id': f'pending-{i}'} for i in range(5)]
            showcase_clips.append({**original_clip, 'id': 'signed-clip', 'signed_by': 'Demo Inspector'})
            page.route('**/api/clips', lambda route: route.fulfill(json=showcase_clips))
            page.reload()
            page.get_by_role('heading', name='A second pair of eyes.').wait_for()
            assert page.locator('.property-strip').count() == 0, 'Property strip should be removed'
            assert page.locator('.stat').filter(has_text='Awaiting review').locator('strong').inner_text() == '05'
            assert page.locator('.clip-card').count() == 5, 'Show every unsigned clip counted in the dashboard'
            assert page.locator('.clip-card [data-id="signed-clip"]').count() == 0
            page.unroute('**/api/clips')
            page.reload()
            page.get_by_role('heading', name='A second pair of eyes.').wait_for()
            for height in (1000, 720, 600):
                page.set_viewport_size({'width': 1440, 'height': height})
                note = page.locator('.sidebar-note').bounding_box()
                assert height - note['y'] - note['height'] >= 40, f'Sidebar note needs bottom spacing at {height}px'
            page.set_viewport_size({'width': 1440, 'height': 1000})
            page.screenshot(path='/tmp/second-inspector-dashboard.png', full_page=True)
            page.get_by_role('button', name='Analyze new clip').first.click()
            page.get_by_role('button', name='Replay a processed clip').click()
            assert page.locator('#replay-clip option').inner_text() == 'original walkthrough.mp4 · 2 findings'
            page.get_by_role('button', name='Start demo analysis').click()
            page.get_by_role('heading', name='A closer look, frame by frame.').wait_for()
            page.get_by_role('heading', name='Review the details.').wait_for(timeout=15000)
            assert page.locator('.evidence-guide').count() == 0, 'Remove the explanatory note from clip review'
            assert page.locator('.coverage-row .badge').inner_text() == 'Mentioned, not seen'
            page.screenshot(path='/tmp/second-inspector-review.png', full_page=True)
            assert page.get_by_role('button', name='Sign off on this clip').is_disabled()
            page.get_by_role('button', name='Accept', exact=True).first.click()
            page.locator('.finding.accepted').wait_for()
            assert 'review needed' not in page.locator('.finding.accepted .finding-header').inner_text().lower()
            page.get_by_role('button', name='Accept', exact=True).last.click()
            page.locator('.finding.accepted').nth(1).wait_for()
            assert all('review needed' not in text.lower() for text in page.locator('.finding.accepted .finding-header').all_inner_texts())
            page.get_by_role('button', name='Reject', exact=True).last.click()
            page.get_by_role('button', name='Confirm rejection').click()
            page.get_by_text('Rejected', exact=True).wait_for()
            assert 'review needed' not in page.locator('.finding.rejected .finding-header').inner_text().lower()
            page.get_by_role('button', name='Edit', exact=True).last.click()
            page.get_by_label('Description').fill('Inspected and verified wall scuff.')
            page.get_by_role('button', name='Save changes').click()
            page.locator('.finding.edited').wait_for()
            assert 'review needed' not in page.locator('.finding.edited .finding-header').inner_text().lower()
            assert page.locator('.sign-area p').count() == 0, 'Remove the ready-for-sign-off message and icon'
            page.get_by_role('button', name='Add missing finding').click()
            page.get_by_label('Component').fill('Outlet')
            page.get_by_label('Description').fill('Missing outlet cover.')
            page.get_by_role('button', name='Add finding', exact=True).click()
            page.reload()
            page.get_by_role('button', name='Review findings', exact=False).last.click()
            page.get_by_text('Missing outlet cover.', exact=True).wait_for()
            page.get_by_role('button', name='Sign off on this clip').click()
            page.get_by_label('Inspector name').fill('Alex Inspector')
            page.get_by_label('I have reviewed every finding').check()
            page.get_by_role('button', name='Confirm sign-off').click()
            page.get_by_role('heading', name='Reviewed. Confirmed. Signed.').wait_for()
            assert page.locator('.signed-actions [data-page="reports"]').count() == 1
            page.screenshot(path='/tmp/second-inspector-signed.png', full_page=True)
            page.get_by_role('button', name='View report').click()
            page.get_by_role('heading', name='Ready for the next chapter.').wait_for()
            page.frame_locator('iframe').get_by_text('Alex Inspector').wait_for()
            assert page.locator('main .workflow-note').count() == 0, 'Remove the bottom report reassurance text'
            assert page.get_by_role('button', name='Download HTML').count() == 0
            assert page.get_by_role('button', name='Print / Save as PDF').is_visible()
            page.evaluate("document.querySelector('iframe').contentWindow.print = () => { window.reportPrintRequested = true; }")
            page.get_by_role('button', name='Print / Save as PDF').click()
            assert page.evaluate('window.reportPrintRequested === true')
            assert page.locator('.report-aside').get_by_text('Floor level measurements', exact=True).count() == 0
            assert page.locator('.report-aside').get_by_text('Evidence photographs', exact=True).count() == 0
            assert not errors, errors
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.locator('#nav [data-page="reports"]').click()
            page.get_by_role('heading', name='From findings to a finished report.').wait_for()
            assert page.locator('.signed-clip').count() == 1
            assert page.get_by_role('button', name='Review more clips').count() == 0
            (folder / 'level.json').write_text(json.dumps({'findings': [], 'rooms': {'garage': {'max_slope_deg': 0.1}}}))
            (folder / 'evidence').mkdir()
            evidence = folder / 'evidence/frame.svg'
            evidence.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"><rect width="20" height="20" fill="green"/></svg>')
            recording = json.loads((folder / 'findings.json').read_text())
            recording['spoken'][0]['evidence_path'] = str(evidence)
            (folder / 'findings.json').write_text(json.dumps(recording))
            page.get_by_role('button', name='View report', exact=True).click()
            page.get_by_role('heading', name='Ready for the next chapter.').wait_for()
            assert page.locator('.report-aside').get_by_text('Floor level measurements', exact=True).count() == 1
            assert page.locator('.report-aside').get_by_text('Evidence photographs', exact=True).count() == 1
            image = page.frame_locator('iframe').locator('.finding img').first
            image.wait_for()
            assert image.evaluate('(el) => el.complete && el.naturalWidth > 0'), 'Report evidence must render with its correct image type'

            page.get_by_role('button', name='Overview', exact=True).click()
            page.get_by_role('heading', name='All caught up.').wait_for()
            assert page.locator('.clip-card').count() == 0
            page.set_viewport_size({'width': 390, 'height': 844})
            page.locator('#toast').evaluate('(el) => el.classList.remove("visible")')
            page.screenshot(path='/tmp/second-inspector-mobile.png', full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            assert httpx.get('http://127.0.0.1:8766/api/clips').json()[0]['signed_by'] == 'Alex Inspector'
            browser.close()
        print('Edge browser checks passed: demo replay, edit, accept, add, sign, report, responsive layout.')
    finally:
        server.terminate()
        server.wait(timeout=10)

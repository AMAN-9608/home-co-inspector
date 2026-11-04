"""Exercise the built Pages demo at a GitHub-style subpath in Microsoft Edge."""
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as directory:
    site = Path(directory) / 'home-co-inspector'
    subprocess.run([sys.executable, str(ROOT / 'scripts/build_pages.py'), str(site)], cwd=ROOT, check=True)
    server = subprocess.Popen([sys.executable, '-m', 'http.server', '8767', '--bind', '127.0.0.1', '--directory', directory], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                if httpx.get('http://127.0.0.1:8767/home-co-inspector/').status_code == 200:
                    break
            except httpx.ConnectError:
                pass
            time.sleep(.1)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            page = browser.new_page(viewport={'width': 1440, 'height': 1000}, reduced_motion='reduce')
            errors, api_requests, failed = [], [], []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('request', lambda req: api_requests.append(req.url) if '/api/' in req.url else None)
            page.on('response', lambda res: failed.append(res.url) if res.status >= 400 and '127.0.0.1:8767' in res.url else None)
            page.goto('http://127.0.0.1:8767/home-co-inspector/')
            page.get_by_role('heading', name='A closer look at every walkthrough.').wait_for()
            typography = lambda selector: page.locator(selector).evaluate("el => { const s = getComputedStyle(el); return [s.fontFamily, s.fontStretch, s.fontWeight]; }")
            about_heading = typography('h1')
            about_brand = typography('.brand')
            header_style = lambda selector: page.locator(selector).evaluate("el => { const s = getComputedStyle(el); return [s.height, s.backgroundColor, s.borderBottomWidth, s.borderBottomColor, s.position]; }")
            about_header = header_style('header.nav')
            nav_text = lambda selector: page.locator(selector).first.evaluate("el => { const s = getComputedStyle(el); return [s.fontFamily, s.fontSize, s.fontWeight, s.color, s.lineHeight]; }")
            about_nav = nav_text('.navlinks a')
            assert '/about/' in page.url
            assert page.locator('.frame img').evaluate('(img) => img.complete && img.naturalWidth > 0')
            page.get_by_role('link', name='Try the interactive demo', exact=False).first.click()
            page.get_by_role('heading', name='Turn a walkthrough video into a signed inspection report.').wait_for()
            assert about_heading == typography('.home-copy h1'), (about_heading, typography('.home-copy h1'))
            assert about_brand == typography('.brand'), (about_brand, typography('.brand'))
            assert about_header == header_style('header.appbar'), (about_header, header_style('header.appbar'))
            assert about_nav == nav_text('#nav [data-page="history"]'), (about_nav, nav_text('#nav [data-page="history"]'))
            assert '/demo/' in page.url
            page.get_by_role('link', name='About the product').click()
            page.get_by_role('heading', name='A closer look at every walkthrough.').wait_for()
            page.get_by_role('link', name='Try the interactive demo', exact=False).first.click()
            page.get_by_role('heading', name='Turn a walkthrough video into a signed inspection report.').wait_for()
            assert page.get_by_role('link', name='Home Co-Inspector home').is_visible()
            assert page.get_by_role('button', name='Watch the demo', exact=False).count() == 0
            assert page.title().endswith('Home Co-Inspector')
            assert 'Second Inspector' not in page.locator('body').inner_text()
            assert page.get_by_text('Saved sample findings. The silent clip', exact=False).count() == 0
            assert page.locator('[data-action="analyze"]').count() == 0
            page.locator('#nav [data-page="history"]').click()
            page.get_by_role('searchbox', name='Search clips').fill('no matching clip')
            page.get_by_role('heading', name='No clips here yet.').wait_for()
            assert page.get_by_text('upload a new walkthrough', exact=False).count() == 0
            assert page.locator('[data-action="analyze"]').count() == 0
            page.get_by_role('searchbox', name='Search clips').fill('')
            page.locator('#nav [data-page="overview"]').click()
            page.get_by_role('heading', name='Turn a walkthrough video into a signed inspection report.').wait_for()
            page.screenshot(path='/tmp/second-inspector-pages-home.png', full_page=True)
            page.locator('#nav [data-page="history"]').click()
            page.get_by_role('button', name='Review findings', exact=True).click()
            page.locator('.review-layout').wait_for(timeout=15000)
            assert page.title().endswith('Home Co-Inspector')
            assert 'Second Inspector' not in page.locator('body').inner_text()
            page.wait_for_function("document.querySelector('#evidence-video')?.videoWidth > 0")
            assert page.locator('#evidence-video').evaluate('(v) => v.duration >= 34')
            page.screenshot(path='/tmp/second-inspector-pages-review.png', full_page=True)
            page.locator('#finding-spoken-0').click()
            page.get_by_role('button', name='Accept', exact=True).click()
            page.locator('#finding-spoken-1').click()
            page.get_by_role('button', name='Edit', exact=True).click()
            page.get_by_label('Description').fill('Edited verified detail.')
            page.get_by_role('button', name='Save changes').click()
            page.locator('#finding-spoken-1.edited').wait_for()
            page.locator('#finding-unspoken-0').click()
            page.get_by_role('button', name='Reject', exact=True).click()
            page.get_by_label('Reason (optional)').fill('Reflection')
            page.get_by_role('button', name='Reject finding').click()
            page.locator('#finding-unspoken-0.rejected').wait_for()
            page.reload()
            page.locator('.clip-card [data-action="review"]').click()
            page.locator('#finding-spoken-1.edited').wait_for()
            page.locator('#finding-unspoken-0.rejected').wait_for()
            while page.locator('.finding.pending').count():
                pending = page.locator('.finding.pending').count()
                page.locator('.finding.pending').first.click()
                page.get_by_role('button', name='Accept', exact=True).click()
                page.wait_for_function('(n) => document.querySelectorAll(".finding.pending").length < n', arg=pending)
            page.get_by_role('button', name='Add missing finding').click()
            page.get_by_label('Component').fill('Outlet')
            page.get_by_label('Description').fill('Missing outlet cover.')
            page.get_by_role('button', name='Add finding', exact=True).click()
            page.locator('.finding.inspector').wait_for()
            page.get_by_role('button', name='Sign off on this clip').click()
            page.get_by_label('Inspector name').fill('Alex Inspector')
            page.get_by_label('I have reviewed every finding').check()
            page.get_by_role('button', name='Confirm sign-off').click()
            page.get_by_role('heading', name='Signed off. The report is ready.').wait_for()
            assert page.title().endswith('Home Co-Inspector')
            page.get_by_role('button', name='View report').click()
            page.get_by_role('heading', name='Inspection report').wait_for()
            report = page.frame_locator('iframe')
            report.get_by_text('Demo only — not an actual inspection report.').wait_for()
            assert page.title().endswith('Home Co-Inspector')
            assert report.get_by_text('Prepared with Home Co-Inspector', exact=False).count() == 1
            assert 'Second Inspector' not in report.locator('body').inner_text()
            report.get_by_text('Alex Inspector', exact=False).first.wait_for()
            report.get_by_text('Edited verified detail.').wait_for()
            report.get_by_text('Missing outlet cover.').wait_for()
            assert report.get_by_text('very faint short diagonal linear mark', exact=False).count() == 0
            image = report.locator('.finding img').first
            image.wait_for()
            assert image.evaluate('(img) => img.complete && img.naturalWidth > 0')
            page.evaluate("document.querySelector('iframe').contentWindow.print = () => { window.reportPrintRequested = true; }")
            page.get_by_role('button', name='Print / Save as PDF').click()
            assert page.evaluate('window.reportPrintRequested === true')
            page.screenshot(path='/tmp/second-inspector-pages-report.png', full_page=True)
            page.reload()
            page.locator('#nav [data-page="reports"]').click()
            assert page.locator('.signed-clip').count() == 1
            page.locator('#nav [data-page="overview"]').click()
            page.set_viewport_size({'width': 390, 'height': 844})
            page.screenshot(path='/tmp/second-inspector-pages-mobile.png', full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            assert not errors, errors
            assert not api_requests, api_requests
            assert not failed, failed
            browser.close()
        print('Pages checks passed: subpath, sample video, review persistence, sign-off, report, and mobile.')
    finally:
        server.terminate()
        server.wait(timeout=10)

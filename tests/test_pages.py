"""Contract checks for the GitHub Pages demo build and browser-local review."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_pages_build_contains_only_curated_demo_data(tmp_path):
    # Arrange
    builder = ROOT / 'scripts/build_pages.py'
    assert builder.is_file(), 'The Pages build command should exist'
    output = tmp_path / 'site'

    # Act
    subprocess.run([sys.executable, str(builder), str(output)], cwd=ROOT, check=True)

    # Assert
    root = (output / 'index.html').read_text()
    about = (output / 'about/index.html').read_text()
    demo = output / 'demo'
    html = (demo / 'index.html').read_text()
    data = json.loads((demo / 'demo/sample.json').read_text())
    assert 'url=./about/' in root.lower()
    assert '../demo/' in about and '../demo/demo/evidence/spoken-1-f42.jpg' in about
    assert 'Archivo' in about and 'Manrope' not in about and 'DM+Sans' not in about
    assert 'Local preview' not in about
    assert 'href="../about/"' in html and 'About the product' in html
    assert './pages.js' in html and './app.js' in html and './styles.css' in html
    assert 'href="./" aria-label="Home Co-Inspector home"' in html
    assert 'Saved sample findings. The silent clip' not in html and '.env' not in html
    assert 'Home Co-Inspector' in html and 'Second Inspector' not in html
    assert 'Home Co-Inspector' in (demo / 'app.js').read_text()
    assert 'Second Inspector' not in (demo / 'app.js').read_text()
    assert data['signed_by'] is None and data['signed_at'] is None
    assert all(f['decision'] == 'pending' for f in data['findings'])
    assert data['video'] == 'demo/evidence-montage.mp4'
    assert (demo / data['video']).is_file()
    assert all((demo / f['image']).is_file() for f in data['findings'] if f.get('image'))
    assert 'Martha Brokaw' not in json.dumps(data)
    assert '/Users/' not in json.dumps(data) and 'data/raw/' not in json.dumps(data)
    assert not (output / '.env').exists() and not list(output.rglob('review.json'))


def test_pages_browser_review_contract():
    # Arrange
    contract = ROOT / 'tests/pages_contract.cjs'
    assert (ROOT / 'web/pages.js').is_file(), 'The browser-local demo backend should exist'

    # Act and assert
    subprocess.run(['node', str(contract)], cwd=ROOT, check=True)


def test_about_explains_impact_and_meta_pipeline():
    about = (ROOT / 'web/about.html').read_text()
    for text in ('Why this matters', 'USA', 'India', 'Muse Spark', 'SAM 3.1', 'angi.com', 'nemmadi.in'):
        assert text in about


def test_about_follows_product_audience_impact_workflow_order():
    about = (ROOT / 'web/about.html').read_text()
    sections = ['id="hero-title"', 'id="who"', 'id="impact"', 'id="impact-us"', 'id="impact-india"', 'id="meta"']
    positions = [about.index(section) for section in sections]
    assert positions == sorted(positions)
    audience = about[about.index('id="who"'):about.index('id="meta"')]
    assert 'USA' in audience and 'India' in audience


def test_about_uses_market_examples_and_housing_quality_without_workflow():
    about = (ROOT / 'web/about.html').read_text()
    assert 'Developed countries · e.g. USA' in about
    assert 'Developing countries · e.g. India' in about
    assert '41%' in about and '100+' in about
    us = about[about.index('id="impact-us"'):about.index('id="impact-india"')]
    india = about[about.index('id="impact-india"'):about.index('id="meta"')]
    assert '41%' in us and 'angi.com' in us
    assert '100+' in india and 'nemmadi.in' in india
    assert 'id="how"' not in about and 'href="#how"' not in about


def test_impact_keeps_two_data_points_per_market():
    about = (ROOT / 'web/about.html').read_text()
    us = about[about.index('id="impact-us"'):about.index('id="impact-india"')]
    india = about[about.index('id="impact-india"'):about.index('id="meta"')]
    assert us.count('<strong>') == 2
    assert india.count('<strong>') == 2
    assert 'href="#impact"' in about


def test_impact_removes_requested_copy_and_card_labels():
    import re
    about = (ROOT / 'web/about.html').read_text()
    for removed in ('Turn recorded walkthroughs into structured findings and visual evidence, with the reviewer in control.', 'Structural assessments, concealed defects', 'It is not an estimate of costs our product could prevent.', 'This is not a defect rate specific to new builds or rentals.', 'This is one published price for an on-site professional service, whose scope exceeds a video review.', 'This is one provider’s experience, rather than a national average.', '$611B', '12.2%'):
        assert removed not in about
    impact = about[about.index('id="impact"'):about.index('id="meta"')]
    cards = re.findall(r'<article>(.*?)</article>', impact, re.S)
    assert len(cards) == 4
    assert all('class="eyebrow"' not in card for card in cards)


def test_meta_section_omits_removed_explanatory_copy():
    about = (ROOT / 'web/about.html').read_text()
    for removed in ('The coverage checklist reuses SAM searches', 'Try the actual review experience below.', 'It can return uncertain or not visible.'):
        assert removed not in about


def test_about_navigation_matches_section_labels():
    about = (ROOT / 'web/about.html').read_text()
    assert '<a href="#impact">Why this matters</a>' in about
    assert '<a href="#meta">How It Works</a>' in about
    assert '<span class="eyebrow">How It Works</span>' in about
    assert 'Explore the AI' not in about


def test_hero_keeps_only_interactive_demo_action():
    about = (ROOT / 'web/about.html').read_text()
    actions = about.split('<div class="actions">', 1)[1].split('</div>', 1)[0]
    assert 'Try the interactive demo' in actions
    assert 'How It Works' not in actions


def test_landing_demo_links_share_label_without_closing_callout():
    import re
    about = (ROOT / 'web/about.html').read_text()
    labels = re.findall(r'<a[^>]*href="../demo/"[^>]*>(.*?)</a>', about, re.S)
    assert len(labels) == 2
    assert all(label.startswith('Try the interactive demo') for label in labels)
    assert 'See it in action' not in about
    assert 'Every detail, considered.' not in about

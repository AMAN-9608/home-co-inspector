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
    for text in ('Why this matters', 'United States', 'India', 'Muse Spark', 'SAM 3.1', 'jchs.harvard.edu', 'niua.in', 'first-pass'):
        assert text in about


def test_about_follows_product_audience_impact_workflow_order():
    about = (ROOT / 'web/about.html').read_text()
    sections = ['id="hero-title"', 'id="who"', 'id="impact"', 'id="meta"']
    positions = [about.index(section) for section in sections]
    assert positions == sorted(positions)
    audience = about[about.index('id="who"'):about.index('id="impact"')]
    assert 'USA' in audience and 'India' in audience


def test_about_uses_market_examples_and_housing_quality_without_workflow():
    about = (ROOT / 'web/about.html').read_text()
    assert 'Developed countries · e.g. USA' in about
    assert 'Developing countries · e.g. India' in about
    assert '12.2%' in about and '2018' in about
    assert 'id="how"' not in about and 'href="#how"' not in about

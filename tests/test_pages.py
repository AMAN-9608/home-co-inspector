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
    html = (output / 'index.html').read_text()
    data = json.loads((output / 'demo/sample.json').read_text())
    assert './pages.js' in html and './app.js' in html and './styles.css' in html
    assert 'href="./" aria-label="Home Co-Inspector home"' in html
    assert 'DEMO' in html and '.env' not in html
    assert 'Home Co-Inspector' in html and 'Second Inspector' not in html
    assert 'Home Co-Inspector' in (output / 'app.js').read_text()
    assert 'Second Inspector' not in (output / 'app.js').read_text()
    assert data['signed_by'] is None and data['signed_at'] is None
    assert all(f['decision'] == 'pending' for f in data['findings'])
    assert data['video'] == 'demo/evidence-montage.mp4'
    assert (output / data['video']).is_file()
    assert all((output / f['image']).is_file() for f in data['findings'] if f.get('image'))
    assert 'Martha Brokaw' not in json.dumps(data)
    assert '/Users/' not in json.dumps(data) and 'data/raw/' not in json.dumps(data)
    assert not (output / '.env').exists() and not list(output.rglob('review.json'))


def test_pages_browser_review_contract():
    # Arrange
    contract = ROOT / 'tests/pages_contract.cjs'
    assert (ROOT / 'web/pages.js').is_file(), 'The browser-local demo backend should exist'

    # Act and assert
    subprocess.run(['node', str(contract)], cwd=ROOT, check=True)

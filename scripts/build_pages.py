"""Build the static Pages demo from the repository's curated, tracked evidence."""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from secondinspector import report, review
from secondinspector.webapp import provenance

SOURCE = ROOT / 'data/processed/garage_door_video'


def build(output):
    output = Path(output)
    demo = output / 'demo'
    evidence = demo / 'evidence'
    evidence.mkdir(parents=True, exist_ok=True)
    for filename in ('app.js', 'pages.js', 'styles.css'):
        shutil.copyfile(ROOT / 'web' / filename, output / filename)
    shutil.copyfile(ROOT / 'web/demo/evidence-montage.mp4', demo / 'evidence-montage.mp4')
    html = (ROOT / 'web/index.html').read_text(encoding='utf-8')
    html = html.replace('href="/styles.css"', 'href="./styles.css"')
    html = html.replace('<script src="/app.js" defer></script>', '<script src="./pages.js" defer></script>\n  <script src="./app.js" defer></script>')
    html = html.replace('href="/" aria-label="Home Co-Inspector home"', 'href="./" aria-label="Home Co-Inspector home"')
    html = html.replace('<main id="main"', '<div class="demo-banner" role="note">DEMO · Saved sample findings. The silent clip is a montage of evidence frames; no new analysis runs. Your decisions stay in this browser.</div>\n  <main id="main"')
    (output / 'index.html').write_text(html, encoding='utf-8')
    (output / '.nojekyll').touch()

    raw = json.loads((SOURCE / 'findings.json').read_text(encoding='utf-8'))
    trust = provenance(raw)

    def image_path(path):
        if not path:
            return None
        name = Path(str(path).replace('\\', '/')).name
        src = SOURCE / 'evidence' / name
        if not src.is_file():
            src = SOURCE / name
        if not src.is_file() or src.suffix.lower() not in {'.jpg', '.jpeg', '.png', '.svg', '.webp'}:
            return None
        shutil.copyfile(src, evidence / name)
        return f'demo/evidence/{name}'

    findings = []
    for finding in review.candidates(SOURCE):
        image = image_path(finding.get('evidence_path'))
        findings.append({**finding, **trust.get(finding['id'], {}), 'evidence_path': image,
                         'image': image, 'decision': 'pending', 'note': ''})
    level = json.loads((SOURCE / 'level.json').read_text(encoding='utf-8'))
    rooms = {name: {'max_slope_deg': info.get('max_slope_deg'), 'image': image_path(info.get('svg'))}
             for name, info in (level.get('rooms') or {}).items()}
    sample = {'id': 'garage_door_video', 'title': 'Sample inspection', 'filename': 'Evidence montage (silent).mp4',
              'rooms': list(dict.fromkeys(f.get('room') or 'Unassigned' for f in findings)),
              'findings': findings, 'pending': len(findings), 'ai_count': sum(f['source'] == 'unspoken' for f in findings),
              'signed_by': None, 'signed_at': None, 'thumbnail': next((f['image'] for f in findings if f['image']), None),
              'video': 'demo/evidence-montage.mp4', 'coverage': {}, 'has_level': bool(rooms), 'level': rooms,
              'transcript': '', 'updated': 1793491200, 'report_css': report.CSS, 'limitations': report.LIMITATIONS}
    (demo / 'sample.json').write_text(json.dumps(sample, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Built static demo in {output}')


if __name__ == '__main__':
    build(sys.argv[1] if len(sys.argv) > 1 else ROOT / 'dist')

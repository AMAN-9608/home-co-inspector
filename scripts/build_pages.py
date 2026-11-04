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
    app = output / 'demo'
    demo = app / 'demo'
    evidence = demo / 'evidence'
    evidence.mkdir(parents=True, exist_ok=True)
    (output / 'about').mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / 'web/about.html', output / 'about/index.html')
    (output / 'index.html').write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=./about/"><title>Home Co-Inspector</title></head><body><a href="./about/">About Home Co-Inspector</a></body></html>', encoding='utf-8')
    for filename in ('app.js', 'pages.js', 'styles.css'):
        shutil.copyfile(ROOT / 'web' / filename, app / filename)
    shutil.copyfile(ROOT / 'web/demo/evidence-montage.mp4', demo / 'evidence-montage.mp4')
    html = (ROOT / 'web/index.html').read_text(encoding='utf-8')
    html = html.replace('href="/styles.css"', 'href="./styles.css"')
    html = html.replace('<script src="/app.js" defer></script>', '<script src="./pages.js" defer></script>\n  <script src="./app.js" defer></script>')
    html = html.replace('href="/" aria-label="Home Co-Inspector home"', 'href="./" aria-label="Home Co-Inspector home"')
    html = html.replace('<button class="primary appbar-cta"', '<a class="about-product" href="../about/">About the product</a>\n    <button class="primary appbar-cta"')
    html = html.replace('</head>', '<style>.about-product{display:inline-flex;align-items:center;justify-content:center;min-height:48px;padding:12px 19px;margin-left:auto;border:1px solid #1c2328;border-radius:4px;background:#1c2328;color:white;text-decoration:none;font-size:13px;font-weight:700;transition:background-color 160ms ease,transform 140ms ease}.about-product:hover{background:#33444f}.about-product:active{transform:scale(.97)}.appbar-cta{margin-left:0}@media(max-width:720px){.about-product{min-height:39px;padding:9px 12px;font-size:11px}}@media(prefers-reduced-motion:reduce){.about-product{transition:none}}</style>\n</head>')
    (app / 'index.html').write_text(html, encoding='utf-8')
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

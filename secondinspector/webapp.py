"""Local showcase: uv run python -m secondinspector.webapp (Streamlit remains available)."""
import argparse
import asyncio
import json
import logging
import mimetypes
import re
import threading
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from secondinspector import report, review, ui_helpers

WEB = Path(__file__).resolve().parent.parent / 'web'
MAX_UPLOAD = 512 * 1024 * 1024
logger = logging.getLogger(__name__)
MEDIA_TYPES = {'.jpg', '.jpeg', '.png', '.webp', '.svg', '.mp4', '.mov', '.m4v'}


class Workspace:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.processed = self.root / 'data/processed'
        # shortcut: jobs live in this process; use durable jobs before multi-user hosting.
        self.jobs = {}

    def folder(self, clip_id):
        folder = (self.processed / clip_id).resolve()
        if folder.parent != self.processed.resolve() or not (folder / 'findings.json').is_file():
            raise FileNotFoundError('Inspection not found')
        return folder

    def media_url(self, path, folder):
        if not path:
            return None
        normalized = Path(str(path).replace('\\', '/'))
        options = [normalized if normalized.is_absolute() else self.root / normalized,
                   folder / normalized.name, folder / 'evidence' / normalized.name]
        for candidate in options:
            candidate = candidate.resolve()
            if candidate.is_relative_to(self.root / 'data') and candidate.is_file() and candidate.suffix.lower() in MEDIA_TYPES:
                return '/media/' + quote(str(candidate.relative_to(self.root)))
        return None

    def detail(self, folder):
        state = review.load(folder)
        raw = report.read_json(folder / 'findings.json')
        findings = [{**finding, **state['items'][finding['id']].get('edits', {}),
                     'decision': state['items'][finding['id']]['decision'],
                     'note': state['items'][finding['id']].get('note', ''),
                     'image': self.media_url(finding.get('evidence_path'), folder)}
                    for finding in review.candidates(folder)]
        findings += [{**finding, 'decision': 'accepted', 'image': self.media_url(finding.get('evidence_path'), folder)}
                     for finding in state.get('added', [])]
        return {'id': folder.name, 'title': folder.name.replace('_', ' ').replace('-', ' ').title(),
                'filename': Path(str(raw.get('clip') or folder.name).replace('\\', '/')).name,
                'rooms': list(dict.fromkeys(f.get('room') or 'Unassigned' for f in findings)),
                'findings': findings, 'pending': len(review.pending(state)),
                'ai_count': sum(f['source'] == 'unspoken' for f in findings),
                'signed_by': state.get('signed_by'), 'signed_at': state.get('signed_at'),
                'thumbnail': next((f['image'] for f in findings if f.get('image')), None),
                'video': self.media_url(str(folder / 'proxy.mp4'), folder) or self.media_url(raw.get('clip'), folder),
                'coverage': report.coverage_rooms(report.read_json(folder / 'coverage.json')),
                'has_level': bool((report.read_json(folder / 'level.json') or {}).get('rooms')),
                'transcript': raw.get('transcript') or '',
                'updated': (folder / 'findings.json').stat().st_mtime}

    def start_job(self, clip):
        job_id = uuid4().hex
        self.jobs[job_id] = {'status': 'running', 'clip': clip.stem}

        def work():
            try:
                from secondinspector import pipeline
                asyncio.run(pipeline.run(str(clip), out_root=str(self.processed)))
                self.jobs[job_id]['status'] = 'complete'
            except Exception:
                logger.exception('Analysis failed')
                self.jobs[job_id].update(status='error', error='Analysis could not finish. Check the server log and model credentials, then try again.')

        threading.Thread(target=work, daemon=True).start()
        return job_id

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return
        headers = dict(scope.get('headers', []))
        method, path = scope['method'], scope['path']
        status, body, content_type = 200, b'', 'application/json'
        extra_headers = []
        try:
            if method == 'POST' and headers.get(b'sec-fetch-site') == b'cross-site':
                raise ValueError('Cross-site requests are not allowed')
            payload = bytearray()
            if method == 'POST':
                while True:
                    event = await receive()
                    if event['type'] == 'http.disconnect':
                        return
                    payload.extend(event.get('body', b''))
                    if len(payload) > (MAX_UPLOAD if path == '/api/analyze' else 1024 * 1024):
                        raise ValueError('Upload is too large (maximum 512 MB)')
                    if not event.get('more_body'):
                        break
            if method == 'GET' and path in ('/', '/app.js', '/styles.css'):
                asset = WEB / ('index.html' if path == '/' else path[1:])
                body = asset.read_bytes()
                content_type = mimetypes.guess_type(asset.name)[0] or 'text/plain'
            elif method == 'GET' and path.startswith('/media/'):
                asset = (self.root / path.removeprefix('/media/')).resolve()
                if not asset.is_relative_to(self.root / 'data') or asset.suffix.lower() not in MEDIA_TYPES or not asset.is_file():
                    raise FileNotFoundError('Media not found')
                size = asset.stat().st_size
                start, end = 0, size - 1
                if b'range' in headers:
                    match = re.fullmatch(rb'bytes=(\d+)-(\d*)', headers[b'range'])
                    if not match:
                        status, body = 416, {'error': 'Unsupported byte range'}
                    else:
                        start, end = int(match[1]), min(int(match[2]) if match[2] else end, end)
                        if start > end:
                            status, body = 416, {'error': 'Invalid byte range'}
                        else:
                            status = 206
                            extra_headers.append((b'content-range', f'bytes {start}-{end}/{size}'.encode()))
                if status != 416:
                    with asset.open('rb') as stream:
                        stream.seek(start)
                        body = stream.read(end - start + 1)
                    content_type = mimetypes.guess_type(asset.name)[0] or 'application/octet-stream'
                    extra_headers.append((b'accept-ranges', b'bytes'))
            elif method == 'GET' and path == '/api/clips':
                body = [self.detail(folder) for folder in ui_helpers.discover_processed(self.processed)]
            elif method == 'GET' and path.startswith('/api/jobs/'):
                job_id = path.rsplit('/', 1)[-1]
                if job_id not in self.jobs:
                    raise FileNotFoundError('Analysis job not found; the server may have restarted')
                job = self.jobs[job_id]
                output = self.processed / job['clip']
                stage = 2 if (output / 'observations.json').exists() else 1 if (output / 'asr.json').exists() else 0
                body = {**job, 'stage': stage}
            elif method == 'POST' and path == '/api/analyze':
                filename = headers.get(b'x-filename', b'').decode('utf-8')
                if Path(filename).suffix.lower() not in {'.mp4', '.mov', '.m4v'} or not payload:
                    raise ValueError('Choose a nonempty MP4, MOV, or M4V clip')
                raw = self.root / 'data/raw'
                raw.mkdir(parents=True, exist_ok=True)
                safe_name = re.sub(r'[^A-Za-z0-9_-]', '-', Path(filename).stem)[:80] or 'clip'
                clip = raw / f'{safe_name}-{uuid4().hex[:10]}{Path(filename).suffix.lower()}'
                clip.write_bytes(payload)
                status, body = 202, {'job': self.start_job(clip)}
            elif path.startswith('/api/clips/'):
                parts = path.strip('/').split('/')
                folder = self.folder(parts[2])
                action = parts[3] if len(parts) == 4 else ''
                state = review.load(folder)
                if method == 'GET' and not action:
                    body = self.detail(folder)
                elif method == 'GET' and action == 'report':
                    if not state.get('signed_by') or review.pending(state):
                        status, body = 409, {'error': 'Review every finding and sign off before generating a report'}
                    else:
                        body = report.render(folder, state, property_address='123 Jane Doe Street, Demo City, NY 100001').encode()
                        content_type = 'text/html; charset=utf-8'
                elif method == 'POST' and action in ('decision', 'add', 'sign'):
                    data = json.loads(payload)
                    if not isinstance(data, dict):
                        raise ValueError('Expected a JSON object')
                    if action == 'decision':
                        review.decide(state, data['id'], data['decision'], data.get('edits'), data.get('note', ''))
                    elif action == 'add':
                        if not isinstance(data.get('description'), str) or not data['description'].strip():
                            raise ValueError('Describe the finding before adding it')
                        review.add(state, {key: value for key, value in data.items() if key in review.EDITABLE})
                    else:
                        if not isinstance(data.get('name'), str):
                            raise ValueError('Inspector name required')
                        review.sign(state, data['name'])
                    review.save(folder, state)
                    body = self.detail(folder)
                else:
                    raise FileNotFoundError('Not found')
            else:
                raise FileNotFoundError('Not found')
        except FileNotFoundError:
            status, body = 404, {'error': 'Not found'}
        except (ValueError, KeyError, TypeError) as error:
            status, body = 400, {'error': str(error)}
        except Exception:
            logger.exception('Request failed')
            status, body = 500, {'error': 'Something went wrong. Your saved decisions are preserved; check the server log.'}
        if not isinstance(body, bytes):
            body = json.dumps(body).encode()
        await send({'type': 'http.response.start', 'status': status, 'headers': [
            (b'content-type', content_type.encode()), (b'content-length', str(len(body)).encode()),
            (b'x-content-type-options', b'nosniff'), (b'cache-control', b'no-store'), *extra_headers]})
        await send({'type': 'http.response.body', 'body': body})


def main():
    import uvicorn
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--root', type=Path, default=WEB.parent)
    args = parser.parse_args()
    uvicorn.run(Workspace(args.root), host='127.0.0.1', port=args.port, lifespan='off')


if __name__ == '__main__':
    main()

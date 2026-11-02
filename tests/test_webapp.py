"""The showcase UI must use the existing persisted inspection workflow."""
import asyncio
import importlib
import importlib.util
import json
from unittest.mock import patch

import httpx


def request(root, method, path, **kwargs):
    # Arrange: an isolated workspace; never alter the showcase recordings.
    assert importlib.util.find_spec('secondinspector.webapp'), 'The local showcase application is not implemented'
    module = importlib.import_module('secondinspector.webapp')

    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=module.Workspace(root)), base_url='http://test') as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(run())


def recording(tmp_path):
    folder = tmp_path / 'data/processed/garage'
    folder.mkdir(parents=True)
    (folder / 'findings.json').write_text(json.dumps({'spoken': [{'room': 'garage', 'component_phrase': 'door', 'description': 'Cracked trim', 'evidence_path': 'data/processed/garage/evidence/frame.jpg'}], 'unspoken': [{'room': 'garage', 'description': 'Missed scuff'}]}))
    (folder / 'evidence').mkdir()
    (folder / 'evidence/frame.jpg').write_bytes(b'picture')
    return folder


def test_landing_assets_are_served(tmp_path):
    # Act
    response = request(tmp_path, 'GET', '/')
    # Assert
    assert response.status_code == 200
    assert 'Second Inspector' in response.text
    script = request(tmp_path, 'GET', '/app.js')
    assert script.status_code == 200
    assert 'property-strip' not in script.text and '123 Jane Doe Street' not in script.text
    assert 'Martha Brokaw' not in script.text and 'Ewing Township' not in script.text
    assert request(tmp_path, 'GET', '/styles.css').status_code == 200


def test_history_and_review_use_existing_files(tmp_path):
    folder = recording(tmp_path)
    response = request(tmp_path, 'GET', '/api/clips')
    assert response.status_code == 200
    assert response.json()[0]['id'] == 'garage'
    assert response.json()[0]['pending'] == 2
    response = request(tmp_path, 'POST', '/api/clips/garage/decision', json={'id': 'spoken-0', 'decision': 'edited', 'edits': {'description': 'Verified crack'}})
    assert response.status_code == 200
    assert json.loads((folder / 'review.json').read_text())['items']['spoken-0']['edits']['description'] == 'Verified crack'
    assert request(tmp_path, 'GET', '/api/clips/garage').json()['findings'][0]['description'] == 'Verified crack'


def test_signoff_requires_decisions_and_report_uses_them(tmp_path):
    recording(tmp_path)
    assert request(tmp_path, 'GET', '/api/clips/garage/report').status_code == 409
    assert request(tmp_path, 'POST', '/api/clips/garage/sign', json={'name': 'Alex Inspector'}).status_code == 400
    request(tmp_path, 'POST', '/api/clips/garage/decision', json={'id': 'spoken-0', 'decision': 'accepted'})
    request(tmp_path, 'POST', '/api/clips/garage/decision', json={'id': 'unspoken-0', 'decision': 'rejected'})
    assert request(tmp_path, 'POST', '/api/clips/garage/add', json={'room': 'garage', 'component_phrase': 'outlet', 'description': 'Missing cover'}).status_code == 200
    assert request(tmp_path, 'POST', '/api/clips/garage/sign', json={'name': 'Alex Inspector'}).status_code == 200
    report = request(tmp_path, 'GET', '/api/clips/garage/report')
    assert report.status_code == 200
    assert '123 Jane Doe Street, Demo City, NY 100001' in report.text
    assert '(fictional demo property)' not in report.text
    assert 'Martha Brokaw' not in report.text and 'Ewing Township' not in report.text
    assert 'Alex Inspector' in report.text and 'Missing cover' in report.text and 'Missed scuff' not in report.text
    request(tmp_path, 'POST', '/api/clips/garage/decision', json={'id': 'spoken-0', 'decision': 'pending'})
    assert request(tmp_path, 'GET', '/api/clips/garage/report').status_code == 409


def test_invalid_input_and_private_paths_are_rejected(tmp_path):
    folder = recording(tmp_path)
    (tmp_path / '.env').write_text('secret')
    assert request(tmp_path, 'GET', '/media/.env').status_code == 404
    assert request(tmp_path, 'GET', '/media/data/processed/garage/../../../.env').status_code == 404
    assert request(tmp_path, 'GET', '/media/data/processed/garage/evidence/frame.jpg').content == b'picture'
    assert request(tmp_path, 'POST', '/api/clips/garage/add', json={'description': ' '}).status_code == 400
    assert request(tmp_path, 'POST', '/api/clips/garage/decision', json={'id': 'unknown', 'decision': 'accepted'}).status_code == 400
    assert request(tmp_path, 'POST', '/api/analyze', content=b'bad', headers={'x-filename': '../bad.txt'}).status_code == 400
    assert request(tmp_path, 'POST', '/api/clips/garage/sign', content='[1]').status_code == 400
    assert not (folder / 'review.json').exists()


def test_report_supports_current_pipeline_coverage(tmp_path):
    folder = recording(tmp_path)
    (folder / 'coverage.json').write_text(json.dumps([{'room': 'garage', 'items': [{'item': 'detector', 'label': 'Smoke detector', 'status': 'not_seen'}]}]))
    request(tmp_path, 'POST', '/api/clips/garage/decision', json={'id': 'spoken-0', 'decision': 'accepted'})
    request(tmp_path, 'POST', '/api/clips/garage/decision', json={'id': 'unspoken-0', 'decision': 'accepted'})
    request(tmp_path, 'POST', '/api/clips/garage/sign', json={'name': 'Alex'})
    response = request(tmp_path, 'GET', '/api/clips/garage/report')
    assert response.status_code == 200
    assert 'Smoke detector' in response.text and 'Items not inspected' in response.text
    assert isinstance(json.loads((folder / 'coverage.json').read_text()), list)


def test_upload_starts_pipeline_with_unique_safe_path(tmp_path):
    recording(tmp_path)
    assert importlib.util.find_spec('secondinspector.webapp'), 'The local showcase application is not implemented'
    module = importlib.import_module('secondinspector.webapp')
    with patch.object(module.Workspace, 'start_job', return_value='job-1') as start:
        response = request(tmp_path, 'POST', '/api/analyze', content=b'video', headers={'x-filename': 'garage.mp4'})
    assert response.status_code == 202 and response.json()['job'] == 'job-1'
    clip = start.call_args.args[0]
    assert clip.read_bytes() == b'video' and clip.stem != 'garage'
    assert clip.parent == tmp_path / 'data/raw'


def test_media_ranges_and_cross_site_writes(tmp_path):
    recording(tmp_path)
    response = request(tmp_path, 'GET', '/media/data/processed/garage/evidence/frame.jpg', headers={'range': 'bytes=1-3'})
    assert response.status_code == 206 and response.content == b'ict'
    assert response.headers['content-range'] == 'bytes 1-3/7'
    assert request(tmp_path, 'GET', '/media/data/processed/garage/evidence/frame.jpg', headers={'range': 'bytes=90-'}).status_code == 416
    assert request(tmp_path, 'POST', '/api/clips/garage/sign', json={'name': 'Alex'}, headers={'sec-fetch-site': 'cross-site'}).status_code == 400
    assert request(tmp_path, 'GET', '/api/jobs/missing').status_code == 404


def test_live_progress_tracks_pipeline_artifacts(tmp_path):
    recording(tmp_path)
    module = importlib.import_module('secondinspector.webapp')
    app = module.Workspace(tmp_path)
    app.jobs['active'] = {'status': 'running', 'clip': 'new-clip'}
    folder = tmp_path / 'data/processed/new-clip'
    folder.mkdir()

    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            assert (await client.get('/api/jobs/active')).json()['stage'] == 0
            (folder / 'asr.json').write_text('{}')
            assert (await client.get('/api/jobs/active')).json()['stage'] == 1
            (folder / 'observations.json').write_text('[]')
            assert (await client.get('/api/jobs/active')).json()['stage'] == 2

    asyncio.run(run())


def test_report_metadata_matches_available_floor_level_data(tmp_path):
    folder = recording(tmp_path)
    assert request(tmp_path, 'GET', '/api/clips/garage').json()['has_level'] is False
    (folder / 'level.json').write_text(json.dumps({'rooms': {'garage': {'max_slope_deg': 0.1}}, 'findings': []}))
    assert request(tmp_path, 'GET', '/api/clips/garage').json()['has_level'] is True


def test_replay_filename_comes_from_clip_path_not_room(tmp_path):
    folder = recording(tmp_path)
    data = json.loads((folder / 'findings.json').read_text())
    data['clip'] = r'data\raw\original walkthrough.mp4'
    (folder / 'findings.json').write_text(json.dumps(data))
    assert request(tmp_path, 'GET', '/api/clips/garage').json()['filename'] == 'original walkthrough.mp4'
    del data['clip']
    (folder / 'findings.json').write_text(json.dumps(data))
    assert request(tmp_path, 'GET', '/api/clips/garage').json()['filename'] == 'garage'

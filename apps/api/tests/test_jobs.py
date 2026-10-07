"""Real HTTP/job/persistence flow; only local model inference is substituted."""
import json
import time
from threading import Event

import pytest
from fastapi.testclient import TestClient
from app.ai_generator import AIGenerator, GenerationError
from app.config import Settings
from app.database import BuildRecord, BuildRepository
from app.jobs import JobRepository
from app.main import create_app
from app.schemas import Structure
from test_ai import response, options
from test_flow import picture, fixture
from test_optimization import envelope
from test_visual import study, plan, assessment


def wait_job(client, job_id):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        response = client.get('/api/generation-jobs/' + job_id)
        assert response.status_code == 200
        assert response.headers['cache-control'] == 'no-store'
        job = response.json()
        if job['status'] in {'succeeded', 'failed'}:
            return job
        time.sleep(.01)
    pytest.fail('Job did not finish')


@pytest.mark.parametrize('quality,image', [('quick', False), ('detailed', True), ('ultra', True)])
def test_job_to_saved_structure_and_restart(tmp_path, monkeypatch, quality, image):
    replies = iter([envelope(study()), envelope(plan()), envelope(assessment(96))] if image else [response()])
    monkeypatch.setattr(AIGenerator, '_request', lambda *args, **kwargs: next(replies))
    settings = Settings(data_dir=tmp_path, ai_context_tokens=32768, _env_file=None)
    with TestClient(create_app(settings)) as client:
        files = {'image': ('reference.webp', picture('WEBP'), 'image/webp')} if image else None
        result = client.post('/api/generation-jobs', files=files,
                             data={'options': options(quality=quality, depth_estimation=False).model_dump_json()})
        assert result.status_code == 202, result.text
        job_id = result.json()['id']
        job = wait_job(client, job_id)
        assert job['status'] == 'succeeded', job
        assert job['buildId'] == job_id
        build = client.get('/api/builds/' + job_id).json()
        assert build['importCommand'] == '/build import ' + job_id
        Structure.model_validate(client.get('/api/builds/' + job_id + '/structure').json())
        if image:
            assert client.get('/api/builds/' + job_id + '/render').status_code == 200
    with TestClient(create_app(settings)) as client:
        assert client.get('/api/generation-jobs/' + job_id).json()['status'] == 'succeeded'
        assert client.get('/api/builds/' + job_id + '/structure').status_code == 200


def test_slow_worker_does_not_block_health_and_rejects_duplicate_generation(tmp_path, monkeypatch):
    entered, release = Event(), Event()
    def model(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return response()
    monkeypatch.setattr(AIGenerator, '_request', model)
    with TestClient(create_app(Settings(data_dir=tmp_path, _env_file=None))) as client:
        try:
            result = client.post('/api/generation-jobs', data={'options': options().model_dump_json()})
            assert result.status_code == 202
            assert entered.wait(2)
            job_id = result.json()['id']
            job = client.get('/api/generation-jobs/' + job_id).json()
            assert job['status'] == 'running' and job['stage'] == 'quick.geometry'
            assert client.get('/api/health').status_code == 200
            assert client.get('/api/builds').json()['total'] == 0
            for endpoint in ['/api/generate', '/api/generation-jobs']:
                assert client.post(endpoint, data={'options': options().model_dump_json()}).status_code == 429
        finally:
            release.set()
        assert wait_job(client, job_id)['status'] == 'succeeded'


def test_error_is_persistent_and_slot_released(tmp_path, monkeypatch):
    def offline(*args, **kwargs):
        raise GenerationError('Abra o Ollama.', 503)
    monkeypatch.setattr(AIGenerator, '_request', offline)
    with TestClient(create_app(Settings(data_dir=tmp_path, _env_file=None))) as client:
        for _ in range(2):
            response_ = client.post('/api/generation-jobs', data={'options': options().model_dump_json()})
            assert response_.status_code == 202
            job = wait_job(client, response_.json()['id'])
            assert job['status'] == 'failed' and job['errorCode'] == 503
            assert job['error'] == 'Abra o Ollama.' and job['buildId'] is None
        assert client.get('/api/builds').json()['total'] == 0
        assert client.get('/api/generation-jobs/missing').status_code == 404


def test_invalid_submission_does_not_hold_slot(tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path, _env_file=None))) as client:
        assert client.post('/api/generation-jobs', data={'options': '{broken'}).status_code == 422
        assert client.post('/api/generation-jobs').status_code == 422
        result = client.post('/api/generation-jobs', files={'image': ('bad.png', b'invalid')})
        assert result.status_code == 202
        assert wait_job(client, result.json()['id'])['errorCode'] == 422
        result = client.post('/api/generation-jobs', files={'image': ('valid.png', picture())})
        assert wait_job(client, result.json()['id'])['status'] == 'succeeded'


def test_recover_interrupted_and_already_committed_jobs(tmp_path):
    settings = Settings(data_dir=tmp_path, _env_file=None)
    repository = BuildRepository(settings.db_url)
    repository.initialize()
    jobs = JobRepository(repository)
    jobs.create('interrupted')
    jobs.create('committed')
    data = fixture()
    data['id'] = 'committed'
    repository.save(BuildRecord(id='committed', structure=data, options={}))
    repository.engine.dispose()
    with TestClient(create_app(settings)) as client:
        interrupted = client.get('/api/generation-jobs/interrupted').json()
        assert interrupted['status'] == 'failed' and 'reiniciou' in interrupted['error']
        committed = client.get('/api/generation-jobs/committed').json()
        assert committed['status'] == 'succeeded' and committed['buildId'] == 'committed'

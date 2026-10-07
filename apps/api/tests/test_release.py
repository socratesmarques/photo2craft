import json
import httpx
import pytest
from fastapi.testclient import TestClient
from app.ai_generator import AIGenerator, GenerationError
from app.config import Settings
from app.main import create_app
from app.release import RELEASE, VERSION
from app.schemas import GenerateOptions
from app.verify_installation import verify


def test_legacy_openai_env_does_not_select_old_provider(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'obsolete-test-key')
    monkeypatch.setenv('OPENAI_MODEL', 'gpt-4.1-mini')
    config = Settings(data_dir=tmp_path, ai_provider='ollama', _env_file=None)
    with TestClient(create_app(config)) as client:
        response = client.get('/api/capabilities')
        result = response.json()
        assert result['release'] == RELEASE == 'ollama-local-0.5.0'
        assert result['version'] == VERSION == '0.5.0'
        assert result['aiProvider'] == 'ollama'
        assert result['aiModel'] == 'qwen3-vl:8b'
        assert result['aiConfigured'] is True
        assert response.headers['cache-control'] == 'no-store'
        assert 'obsolete-test-key' not in response.text
        assert client.get('/api/health').json()['release'] == RELEASE


@pytest.mark.parametrize('scenario', ['ready', 'old_api', 'missing_model', 'offline'])
def test_installed_version_and_model_check_without_generation(scenario):
    calls = []
    def handler(request):
        calls.append((request.method, str(request.url)))
        if request.url.path == '/api/capabilities':
            return httpx.Response(200, json={'release': RELEASE if scenario != 'old_api' else 'old', 'aiProvider': 'ollama', 'generationJobs': True})
        if scenario == 'offline':
            raise httpx.ConnectError('offline')
        assert request.url.path == '/api/tags'
        return httpx.Response(200, json={'models': [] if scenario == 'missing_model' else [{'name':'qwen3-vl:8b'}]})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        if scenario == 'ready':
            verify(client, Settings(_env_file=None))
        else:
            with pytest.raises((ValueError, httpx.ConnectError)):
                verify(client, Settings(_env_file=None))
    assert all(method == 'GET' for method, _ in calls)
    assert len(calls) == (1 if scenario == 'old_api' else 2)


def test_truncated_ollama_generation_never_saved(tmp_path):
    result = {'done': True, 'done_reason':'length','message':{'content':json.dumps({'summary':'partial'})}}
    gen = AIGenerator(Settings(data_dir=tmp_path, _env_file=None), httpx.MockTransport(lambda _:httpx.Response(200,json=result)))
    with pytest.raises(GenerationError, match='limite de saída'):
        gen.generate('test', GenerateOptions(mode='ai',description='Uma ponte'), [])


def test_connection_failure_explains_ollama(tmp_path):
    def handler(_):
        raise httpx.ConnectError('offline')
    gen = AIGenerator(Settings(data_dir=tmp_path, _env_file=None), httpx.MockTransport(handler))
    with pytest.raises(GenerationError, match='Abra o Ollama') as error:
        gen.generate('test', GenerateOptions(mode='ai',description='Uma ponte'), [])
    assert error.value.status_code == 503

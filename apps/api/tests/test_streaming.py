import json
import httpx
import pytest
from app.ai_generator import AIGenerator, GenerationError
from app.config import Settings
from app.progress import progress_callback
from test_ai import bridge, options


class Chunks(httpx.SyncByteStream):
    def __init__(self, raw): self.raw = raw
    def __iter__(self):
        # Splits JSON, UTF-8, and newline boundaries deliberately.
        for start in range(0, len(self.raw), 7): yield self.raw[start:start+7]


def streamed(events):
    raw = '\n'.join(json.dumps(item, ensure_ascii=False) for item in events).encode()
    return httpx.Response(200, headers={'content-type': 'application/x-ndjson'}, stream=Chunks(raw))


def test_stream_assembles_only_complete_json_and_retains_metrics(tmp_path):
    text = json.dumps(bridge(), ensure_ascii=False)
    events = [{'done': False, 'message': {'content': text[i:i+17]}} for i in range(0, len(text), 17)]
    events.append({'done': True, 'done_reason': 'stop', 'message': {'content': ''}, 'eval_count': 456})
    gen = AIGenerator(Settings(data_dir=tmp_path, _env_file=None), httpx.MockTransport(lambda _: streamed(events)))
    stages = []
    token = progress_callback.set(stages.append)
    try: result, info = gen.generate('stream', options(), [])
    finally: progress_callback.reset(token)
    assert result.blocks and info['calls'][0]['eval_count'] == 456
    assert stages == ['quick.geometry', 'quick.geometry.receiving']


@pytest.mark.parametrize('failure', ['disconnect', 'error', 'invalid_event', 'invalid_content', 'truncated'])
def test_stream_failure_never_saves_partial_structure(tmp_path, failure):
    events = [{'done': False, 'message': {'content': '{"summary":'}}]
    if failure == 'error': events.append({'error': 'private server error'})
    if failure == 'invalid_event': events.append([])
    if failure == 'invalid_content': events.append({'message': {'content': 123}})
    if failure == 'truncated': events.append({'done': True, 'done_reason': 'length'})
    gen = AIGenerator(Settings(data_dir=tmp_path, _env_file=None), httpx.MockTransport(lambda _: streamed(events)))
    with pytest.raises(GenerationError) as error:
        gen.generate('broken', options(), [])
    assert 'private server error' not in str(error.value)


def test_output_budget_compacts_schema_before_first_request(tmp_path):
    seen = []
    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={'done': True, 'message': {'content': json.dumps(bridge())}})
    gen = AIGenerator(Settings(data_dir=tmp_path, ai_max_output_tokens=1000, _env_file=None), httpx.MockTransport(handler))
    gen.generate('small-budget', options(), [])
    assert seen[0]['format']['properties']['parts']['maxItems'] == 3
    assert seen[0]['options']['num_predict'] == 1000

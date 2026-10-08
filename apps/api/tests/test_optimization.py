"""Regressions for bounded inference, image fidelity and geometry-first acceptance."""
import base64
from io import BytesIO
import json
import logging

import httpx
import numpy as np
from PIL import Image
import pytest

from app.ai_generator import AIGenerator, GenerationError
from app.config import Settings
from app.images import encode_reference
from app.ollama_session import GenerationSession
from app.schemas import GenerateOptions
from app.visual_score import improves_geometry
from test_ai import bridge
from test_detailed import study as text_study, body, details
from test_visual import study, plan, assessment


def envelope(value, reason="stop"):
    return {"done": True, "done_reason": reason, "prompt_eval_count": 1800,
            "eval_count": 900, "message": {"content": json.dumps(value)}}


def generator(tmp_path, replies, **settings):
    calls = []
    def respond(request):
        calls.append(json.loads(request.content))
        assert len(calls) <= len(replies), "Inference must remain bounded"
        return httpx.Response(200, json=replies[len(calls)-1])
    config = Settings(generation_mode="legacy", ai_provider="ollama", data_dir=tmp_path, ollama_model="qwen3-vl:8b",
                      ai_context_tokens=32768, ai_max_output_tokens=24000,
                      _env_file=None, **settings)
    return AIGenerator(config, httpx.MockTransport(respond)), calls


def test_quick_length_retries_compact_without_increasing_context(tmp_path, caplog):
    gen, calls = generator(tmp_path, [envelope({"partial": True}, "length"), envelope(bridge())])
    with caplog.at_level(logging.INFO, logger="photo2craft.ollama"):
        result, info = gen.generate("retry", GenerateOptions(mode="ai", description="Ponte"), [])
    assert result.blocks and len(calls) == 2
    assert [c['format']['properties']['parts']['maxItems'] for c in calls] == [32, 16]
    assert all(c['options']['num_ctx'] == 32768 for c in calls)
    assert calls[0]['options']['num_predict'] == calls[1]['options']['num_predict'] == 8000
    assert "partial" not in calls[1]['messages'][1]['content']
    metrics = [json.loads(r.message) for r in caplog.records if r.message.startswith('{')]
    assert [r['done_reason'] for r in metrics] == ['length', 'stop']
    for entry in metrics:
        assert entry['build_id'] == 'retry' and entry['model'] == 'qwen3-vl:8b'
        assert {'stage', 'seconds', 'prompt_eval_count', 'eval_count', 'num_ctx', 'num_predict'} <= entry.keys()
    assert info['warnings'] and len(info['calls']) == 2


def test_repeated_length_is_bounded_and_never_compiles_partial_json(tmp_path):
    gen, calls = generator(tmp_path, [envelope(bridge(), "length")] * 2)
    with pytest.raises(GenerationError, match="compactação"):
        gen.generate("partial", GenerateOptions(mode="ai", description="Ponte"), [])
    assert len(calls) == 2


@pytest.mark.parametrize("cut_stage", [0, 1, 2])
def test_visual_analysis_geometry_and_assessment_recover_length(tmp_path, cut_stage):
    replies = [envelope(study()), envelope(plan()), envelope(assessment(96))]
    replies.insert(cut_stage, envelope({"partial": True}, "length"))
    gen, calls = generator(tmp_path, replies)
    result, info = gen.generate("visual", GenerateOptions(mode="ai", quality="detailed"),
                                [Image.new("RGB", (1800, 900), "gray")])
    assert result.blocks and len(calls) == 4 and info['score']['total'] == 96
    with Image.open(BytesIO(base64.b64decode(calls[0]['messages'][1]['images'][0]))) as image:
        assert image.size == (1280, 640) and image.format == 'PNG'
    assert len(info['warnings']) == 2  # uncertain segmentation and compact retry


@pytest.mark.parametrize("quality,edge,components", [("detailed",1280,32),("ultra",1536,48)])
def test_visual_quality_has_explicit_image_and_geometry_budgets(tmp_path, quality, edge, components):
    gen, calls = generator(tmp_path, [envelope(study()), envelope(plan()), envelope(assessment(96))])
    _, info = gen.generate("quality", GenerateOptions(mode="ai", quality=quality, depth_estimation=False),
                           [Image.new("RGB", (2000, 1000), "gray")])
    with Image.open(BytesIO(base64.b64decode(calls[0]['messages'][1]['images'][0]))) as image:
        assert max(image.size) == edge
    assert calls[1]['format']['properties']['components']['maxItems'] == components
    assert info['quality'] == quality


@pytest.mark.parametrize("quality,base_limit,detail_limit", [("detailed",28,12),("ultra",40,24)])
def test_text_quality_modes_have_useful_distinct_budgets(tmp_path, quality, base_limit, detail_limit):
    gen, calls = generator(tmp_path, [envelope(text_study()), envelope(body()), envelope(details())])
    _, info = gen.generate("text", GenerateOptions(mode="ai", quality=quality, size="large", description="Carro"), [])
    assert len(calls) == 3 and info['quality'] == quality
    assert calls[1]['format']['properties']['parts']['maxItems'] == base_limit
    assert calls[2]['format']['properties']['parts']['maxItems'] == detail_limit
    assert all(c['messages'][1]['images'] == [] for c in calls)


def test_prompt_reservation_scales_with_input_and_keeps_output_bounded(tmp_path):
    gen, calls = generator(tmp_path, [envelope(bridge())] * 2)
    gen.settings.ai_context_tokens = 8192
    session = GenerationSession(gen, "budget")
    schema = {'type': 'object', 'properties': {'title': {'type': 'string'}}, 'required': ['title']}
    session.ask(schema, "JSON", {'request': 'x'}, [], 24000, 'small')
    session.ask(schema, "JSON", {'request': 'x' * 6000}, ['image'], 24000, 'large')
    assert 512 <= calls[1]['options']['num_predict'] < calls[0]['options']['num_predict'] < 8192
    assert 'title' in calls[0]['format']['properties']


def test_http_failure_logs_metrics_without_response_or_prompt(tmp_path, caplog):
    settings = Settings(generation_mode="legacy", ai_provider="ollama", data_dir=tmp_path, _env_file=None)
    gen = AIGenerator(settings, httpx.MockTransport(lambda _: httpx.Response(500, text="private data")))
    with caplog.at_level(logging.WARNING, logger='photo2craft.ollama'), pytest.raises(GenerationError):
        gen.generate('http-error', GenerateOptions(mode='ai', description='private prompt'), [])
    assert '"http_status": 500' in caplog.text
    assert 'private data' not in caplog.text and 'private prompt' not in caplog.text


def test_lossless_image_encoding_preserves_colors_and_does_not_upscale():
    pixels = np.zeros((20, 30, 3), dtype=np.uint8)
    pixels[:, ::2] = [255, 0, 0]
    pixels[:, 1::2] = [0, 0, 255]
    raw = base64.b64decode(encode_reference(Image.fromarray(pixels)))
    with Image.open(BytesIO(raw)) as image:
        assert image.size == (30, 20) and np.array_equal(np.asarray(image), pixels)


def test_api_persists_lossless_reference_and_reads_legacy_jpeg(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    data = BytesIO()
    image = Image.new('RGB', (30, 20), (250, 10, 40))
    exif = Image.Exif()
    exif[270] = 'private image metadata'
    image.save(data, 'PNG', exif=exif)
    with TestClient(create_app(Settings(generation_mode="legacy", ai_provider="ollama", data_dir=tmp_path, _env_file=None))) as client:
        response = client.post('/api/generate', files={'image': ('ref.png', data.getvalue(), 'image/png')})
        assert response.status_code == 201
        build_id = response.json()['id']
        path = tmp_path/'images'/build_id
        response = client.get(f'/api/builds/{build_id}/image')
        assert response.headers['content-type'] == 'image/png'
        with Image.open(BytesIO(response.content)) as saved:
            assert np.array_equal(np.asarray(saved), np.asarray(image))
            assert not saved.getexif()
        image.save(path/'source.jpg', 'JPEG')
        (path/'source.png').unlink()
        assert client.get(f'/api/builds/{build_id}/image').headers['content-type'] == 'image/jpeg'


def test_color_and_detail_gains_cannot_hide_geometry_regression():
    before = {'total': 60, 'components': dict(silhouette=75, proportion=75, structure=75, color=10, detail=10)}
    after = {'total': 80, 'components': dict(silhouette=60, proportion=75, structure=75, color=100, detail=100)}
    assert not improves_geometry(before, after)
    after['components']['silhouette'] = 75
    assert improves_geometry(before, after)


def test_compact_retry_shares_total_deadline(tmp_path, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr('app.ollama_session.time.monotonic', lambda: clock[0])
    gen, _ = generator(tmp_path, [])
    seen = []
    def request(payload, **kwargs):
        seen.append(kwargs['timeout_seconds'])
        clock[0] += 6
        return envelope(bridge(), 'length' if len(seen) == 1 else 'stop')
    gen._request = request
    session = GenerationSession(gen, 'deadline', deadline=10)
    with pytest.raises(GenerationError, match='Tempo total'):
        session.ask({'type':'object'}, 'JSON', {}, [], 8000, 'test')
    assert seen == [10, 4]

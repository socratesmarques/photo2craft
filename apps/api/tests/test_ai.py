import json
from io import BytesIO
import httpx
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from pydantic import ValidationError
from app.ai_generator import AIGenerator, GenerationError
from app.blueprint import Blueprint, blueprint_schema, compile_blueprint
from app.config import Settings
from app.main import create_app
from app.schemas import GenerateOptions, Structure


def part(shape="box", start=(0, 0, 0), end=(8, 0, 4), block="minecraft:stone_bricks", **kwargs):
    return {"shape": shape, "start": dict(zip("xyz", start)), "end": dict(zip("xyz", end)),
            "block": block, "axis": "y", "hollow": False, "thickness": 1, **kwargs}


def bridge():
    return {"summary": "Ponte de pedra com tabuleiro e dois pilares.",
            "assumptions": ["A parte traseira foi inferida por simetria."],
            "size": {"width": 9, "height": 7, "depth": 5},
            "parts": [part(start=(0, 4, 0), end=(8, 4, 4)),
                      part(start=(0, 0, 0), end=(1, 3, 4)),
                      part(start=(7, 0, 0), end=(8, 3, 4)),
                      part("line", (0, 5, 0), (8, 5, 0)),
                      part("line", (0, 5, 4), (8, 5, 4))]}


def response(plan=None):
    return {"model": "test-model", "done": True,
            "message": {"role": "assistant", "content": json.dumps(bridge() if plan is None else plan)}}


@pytest.fixture
def settings(tmp_path):
    return Settings(data_dir=tmp_path, ai_provider="ollama", generation_mode="legacy", ollama_url="http://ollama.test:11434",
                    ollama_model="test-model", _env_file=None)


def options(**kwargs):
    return GenerateOptions(mode="ai", name="Ponte", description="Uma ponte de pedra", **kwargs)


def test_compiles_bridge_with_open_space():
    result = compile_blueprint(Blueprint.model_validate(bridge()), "bridge", options(), 50000, (16, 16, 16))
    blocks = {(c.x, c.y, c.z): c.block for c in result.blocks}
    assert blocks[4, 4, 2] == "minecraft:stone_bricks"
    assert (4, 0, 2) not in blocks
    assert blocks[0, 0, 2] == "minecraft:stone_bricks"
    assert len(blocks) == len(result.blocks)
    Structure.model_validate(result.model_dump())


@pytest.mark.parametrize("shape", ["box", "ellipsoid", "cylinder", "pyramid", "gable", "line"])
def test_all_shapes_generate_bounded_cells(shape):
    data = bridge()
    data["parts"] = [part(shape, (0, 0, 0), (8, 6, 4), axis="z")]
    result = compile_blueprint(Blueprint.model_validate(data), "shape", options(), 50000, (16, 16, 16))
    Structure.model_validate(result.model_dump())
    assert result.blocks
    assert all(0 <= c.x < 9 and 0 <= c.y < 7 and 0 <= c.z < 5 for c in result.blocks)


def test_hollow_shapes_and_air_override():
    data = bridge()
    data["parts"] = [part(start=(0, 0, 0), end=(8, 6, 4), hollow=True),
                     part(start=(4, 1, 0), end=(4, 2, 0), block="minecraft:air")]
    result = compile_blueprint(Blueprint.model_validate(data), "hollow", options(), 50000, (16, 16, 16))
    cells = {(b.x, b.y, b.z): b.block for b in result.blocks}
    assert cells[4, 3, 2] == "minecraft:air"
    assert cells[4, 1, 0] == "minecraft:air"
    assert cells[0, 3, 2] == "minecraft:stone_bricks"


def test_diagonal_line_preserves_endpoints():
    data = bridge()
    data["parts"] = [part("line", (8, 6, 4), (0, 0, 0))]
    result = compile_blueprint(Blueprint.model_validate(data), "line", options(), 50000, (16, 16, 16))
    positions = {(b.x, b.y, b.z) for b in result.blocks}
    assert (8, 6, 4) in positions and (0, 0, 0) in positions


@pytest.mark.parametrize("mutation", ["unsafe_block", "negative", "float", "unknown_shape", "extra", "outside", "budget", "empty", "big_size", "work"])
def test_rejects_untrusted_plans(mutation):
    data = bridge()
    budget = 50000
    if mutation == "unsafe_block": data["parts"][0]["block"] = "minecraft:command_block"
    if mutation == "negative": data["parts"][0]["start"]["x"] = -1
    if mutation == "float": data["parts"][0]["start"]["x"] = 0.3
    if mutation == "unknown_shape": data["parts"][0]["shape"] = "execute"
    if mutation == "extra": data["parts"][0]["code"] = "print('unsafe')"
    if mutation == "outside": data["parts"][0]["end"]["x"] = 10
    if mutation == "budget": budget = 5
    if mutation == "empty": data["parts"] = [part(block="minecraft:air")]
    if mutation == "big_size": data["size"]["height"] = 32
    bounds = (16, 16, 16)
    if mutation == "work":
        data["size"] = {"width": 64, "height": 64, "depth": 64}
        data["parts"] = [part(end=(63, 63, 63))] * 128
        bounds = (64, 64, 64)
    with pytest.raises((ValueError, ValidationError)):
        compile_blueprint(Blueprint.model_validate(data), "bad", options(), budget, bounds)


def test_ollama_wire_contract_includes_image_prompt_and_schema(settings):
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=response())
    gen = AIGenerator(settings, httpx.MockTransport(handler))
    result, info = gen.generate("bridge", options(type="ponte"), [Image.new("RGB", (2000, 500), "green")])
    assert len(seen) == 1 and result.id == "bridge" and info["mode"] == "ai"
    request = seen[0]
    payload = json.loads(request.content)
    assert request.url == "http://ollama.test:11434/api/chat"
    assert "authorization" not in request.headers
    assert payload["stream"] is False and payload["think"] is False
    assert payload["options"]["temperature"] == 0
    assert payload["format"]["additionalProperties"] is False
    user = payload["messages"][1]
    assert json.loads(user["content"])["subject"] == "ponte"
    assert len(user["images"]) == 1
    import base64
    with Image.open(BytesIO(base64.b64decode(user["images"][0]))) as image:
        assert max(image.size) <= 1280


def test_text_only_and_strict_schema(settings):
    seen = []
    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=response())
    AIGenerator(settings, httpx.MockTransport(handler)).generate("text", options(), [])
    assert seen[0]["messages"][1]["images"] == []
    schema = blueprint_schema()
    assert schema["properties"]["parts"]["maxItems"] == 64
    for obj in [schema, *schema["$defs"].values()]:
        assert obj["additionalProperties"] is False
        assert set(obj["required"]) == set(obj["properties"])


@pytest.mark.parametrize("status", [400, 403, 404, 429, 500, 302])
def test_ollama_errors_do_not_retry(settings, status):
    count = 0
    def handler(request):
        nonlocal count
        count += 1
        return httpx.Response(status, text="private debug")
    with pytest.raises(GenerationError) as exc:
        AIGenerator(settings, httpx.MockTransport(handler)).generate("fail", options(), [])
    assert count == 1 and "private debug" not in str(exc.value)


@pytest.mark.parametrize("kind", ["empty", "incomplete", "invalid_json", "bad_plan", "oversized", "timeout"])
def test_invalid_responses_do_not_generate_a_template(settings, kind):
    def handler(request):
        if kind == "timeout": raise httpx.ReadTimeout("timeout")
        if kind == "oversized": return httpx.Response(200, content=b"x" * (2 * 1024 * 1024 + 1))
        if kind == "invalid_json": return httpx.Response(200, text="invalid")
        if kind == "bad_plan": return httpx.Response(200, json=response({"name": "wrong"}))
        if kind == "incomplete": return httpx.Response(200, json={"done": False, "message": {"content": ""}})
        return httpx.Response(200, json={"done": True, "message": {"content": ""}})
    with pytest.raises(GenerationError):
        AIGenerator(settings, httpx.MockTransport(handler)).generate("fail", options(), [])


def test_api_ai_requires_configuration_and_no_silent_fallback(tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path, ai_provider="disabled", _env_file=None))) as client:
        cap = client.get("/api/capabilities").json()
        assert cap["aiConfigured"] is False
        r = client.post("/api/generate", data={"options": options().model_dump_json()})
        assert r.status_code == 503 and "AI_PROVIDER" in r.json()["detail"]
        assert client.get("/api/builds").json()["total"] == 0


def test_api_text_to_ai_structure_and_persistence(settings, monkeypatch):
    monkeypatch.setattr(AIGenerator, "_request", lambda self, payload, **kwargs: response())
    with TestClient(create_app(settings)) as client:
        cap = client.get("/api/capabilities").json()
        assert cap["aiConfigured"] is True and cap["aiProvider"] == "ollama"
        r = client.post("/api/generate", data={"options": options(type="ponte com arcos").model_dump_json()})
        assert r.status_code == 201, r.text
        build = r.json()
        assert build["generator"] == "vision-blueprint-v1"
        assert build["generationInfo"]["summary"].startswith("Ponte")
        assert build["sourceImages"] == [] and build["thumbnail"] is None
        data = client.get(f"/api/builds/{build['id']}/structure").json()
        assert data["formatVersion"] == "1.0" and data["minecraftVersion"] == "1.21.1"
        assert data["size"] == bridge()["size"]
        Structure.model_validate(data)
        assert client.delete(f"/api/builds/{build['id']}").status_code == 204


def test_full_quota_prevents_paid_request(settings, monkeypatch):
    settings.max_projects = 1
    calls = []
    def fake_request(self, payload, **kwargs):
        calls.append(payload)
        return response()
    monkeypatch.setattr(AIGenerator, "_request", fake_request)
    with TestClient(create_app(settings)) as client:
        payload = {"options": options().model_dump_json()}
        assert client.post("/api/generate", data=payload).status_code == 201
        assert client.post("/api/generate", data=payload).status_code == 409
        assert len(calls) == 1

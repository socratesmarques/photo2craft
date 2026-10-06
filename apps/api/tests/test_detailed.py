import json
import time

import httpx
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.ai_generator import AIGenerator, GenerationError
from app.config import Settings
from app.detailed_generator import (ReferenceStudy, DetailPart, PartBatch, Assembly,
                                    batch_schema, fit_proportions, expand_parts, generate_detailed)
from app.main import create_app
from app.schemas import GenerateOptions, Size, Structure, PALETTE


def study():
    return dict(subject="Carro azul", proportions=dict(width=10, height=4, depth=20),
                silhouette="Baixo e comprido", landmarks=["Quatro rodas pretas", "Cabine central"],
                symmetry="x", material_notes="Azul e vidro", assumptions=["Traseira inferida"])


def part(start=(2, 2, 2), end=(20, 6, 40), **kwargs):
    return dict(shape="box", start=dict(zip("xyz", start)), end=dict(zip("xyz", end)),
                block="minecraft:blue_concrete", axis="y", hollow=False, thickness=1,
                label="Carroceria", mirror="none", **kwargs)


def body():
    return dict(summary="Carro azul com volumes proporcionais.", parts=[part()])


def details():
    item = part((2, 7, 12), (2, 7, 13))
    item.update(block="minecraft:glass", mirror="x", label="Janela lateral")
    return dict(summary="Janelas", parts=[item])


def envelope(value):
    return dict(done=True, message=dict(content=json.dumps(value)))


def run(tmp_path, replies, **kwargs):
    seen = []
    def handler(request):
        seen.append(json.loads(request.content))
        value = replies[len(seen)-1]
        if isinstance(value, int):
            return httpx.Response(value)
        return httpx.Response(200, json=envelope(value))
    opts = GenerateOptions(mode="ai", quality="detailed", size="large", description="Carro azul", **kwargs)
    # Preserve regression coverage of the legacy planner retained for text-only generation.
    result = generate_detailed(AIGenerator(Settings(data_dir=tmp_path, _env_file=None), httpx.MockTransport(handler)),
        "car", opts, [Image.new("RGB", (100, 100), "blue")], (48,48,48))
    return result, seen


def test_three_stages_share_reference_preserve_proportions_and_add_details(tmp_path):
    (result, info), calls = run(tmp_path, [study(), body(), details()], fidelity=95, style="medieval")
    assert len(calls) == 3
    assert result.size == Size(width=24, height=10, depth=48)
    assert all(call["think"] is False and call["stream"] is False for call in calls)
    assert all(call["options"]["num_ctx"] == 16384 for call in calls)
    assert all(len(call["messages"][1]["images"]) == 1 for call in calls)
    assert json.loads(calls[1]["messages"][1]["content"])["style"] == "preserve reference colors and shape"
    assert json.loads(calls[1]["messages"][1]["content"])["fixed_size"] == result.size.model_dump()
    assert "base_parts" in json.loads(calls[2]["messages"][1]["content"])
    cells = {(b.x, b.y, b.z): b.block for b in result.blocks}
    assert cells[2, 7, 12] == cells[21, 7, 12] == "minecraft:glass"
    assert info["stagesCompleted"] == ["analysis", "geometry", "details"]
    assert info["partCount"] == 3 and not info["warnings"]
    assert info["minimumModVersion"] == "0.3.0"
    Structure.model_validate(result.model_dump())


def test_image_priority_always_overrides_style(tmp_path):
    (_, _), calls = run(tmp_path, [study(), body(), details()], fidelity=30, style="medieval")
    assert json.loads(calls[1]["messages"][1]["content"])["style"] == "preserve reference colors and shape"


@pytest.mark.parametrize("axis,expected", [("x", (21, 7, 12)), ("z", (2, 7, 34))])
def test_reflection_preserves_extent(axis, expected):
    value = part((2, 7, 12), (2, 7, 13))
    value["mirror"] = axis
    expanded = expand_parts([DetailPart.model_validate(value)], Size(width=24, height=10, depth=48))
    assert len(expanded) == 2
    assert expanded[1].start.xyz() == expected


def test_reflection_handles_reversed_lines():
    value = part((2, 2, 3), (0, 0, 0))
    value.update(shape="line", mirror="x")
    expanded = expand_parts([DetailPart.model_validate(value)], Size(width=10, height=8, depth=12))
    assert expanded[1].start.xyz() == (7, 2, 3)
    assert expanded[1].end.xyz() == (9, 0, 0)


def test_centered_piece_does_not_duplicate():
    value = part((2, 0, 0), (7, 1, 1))
    value["mirror"] = "x"
    assert len(expand_parts([DetailPart.model_validate(value)], Size(width=10, height=8, depth=12))) == 1


def test_invalid_directional_reflection_rejected():
    value = part()
    value.update(shape="pyramid", axis="x", mirror="x")
    with pytest.raises(ValidationError):
        DetailPart.model_validate(value)


def test_geometry_repair_is_bounded(tmp_path):
    invalid = body()
    invalid["parts"][0]["end"]["x"] = 80
    (result, info), calls = run(tmp_path, [study(), invalid, body(), details()])
    assert len(calls) == 4 and result.blocks
    assert "repair" in json.loads(calls[2]["messages"][1]["content"])
    with pytest.raises(GenerationError, match="após uma correção"):
        run(tmp_path, [study(), invalid, invalid])


@pytest.mark.parametrize("refinement", [500, {}, {"summary":"bad", "parts":[]}])
def test_failed_refinement_preserves_base_and_warns(tmp_path, refinement):
    (result, info), calls = run(tmp_path, [study(), body(), refinement])
    assert len(calls) == 3 and result.blocks
    assert info["stagesCompleted"] == ["analysis", "geometry"]
    assert info["warnings"] and info["partCount"] == 1


def test_destructive_refinement_rejected(tmp_path):
    cut = body()
    cut["parts"][0]["block"] = "minecraft:air"
    (result, info), _ = run(tmp_path, [study(), body(), cut])
    assert all(b.block == "minecraft:blue_concrete" for b in result.blocks)
    assert info["warnings"]


def test_repainting_most_of_model_rejected(tmp_path):
    recolor = body()
    recolor["parts"][0]["block"] = "minecraft:red_concrete"
    (result, info), _ = run(tmp_path, [study(), body(), recolor])
    assert all(b.block == "minecraft:blue_concrete" for b in result.blocks)
    assert info["stagesCompleted"] == ["analysis", "geometry"]


def test_large_unrelated_overlay_rejected(tmp_path):
    addition = {"summary":"Volume excessivo", "parts":[part((0, 7, 0), (23, 9, 47))]}
    (result, info), _ = run(tmp_path, [study(), body(), addition])
    assert info["stagesCompleted"] == ["analysis", "geometry"]
    assert info["warnings"]


def test_no_fallback_for_invalid_study(tmp_path):
    with pytest.raises(GenerationError, match="análise"):
        run(tmp_path, [{}])


def test_schema_palette_and_bounds():
    schema = batch_schema()
    assert schema["properties"]["parts"]["maxItems"] == 48
    for obj in [schema, *schema["$defs"].values()]:
        assert obj["additionalProperties"] is False
        assert set(obj["required"]) == set(obj["properties"])
    assert "minecraft:blue_concrete" in schema["$defs"]["DetailPart"]["properties"]["block"]["enum"]
    value = part()
    value["block"] = "minecraft:command_block"
    with pytest.raises(ValidationError):
        DetailPart.model_validate(value)
    with pytest.raises(ValidationError):
        PartBatch.model_validate(dict(summary="excess", parts=[part()] * 49))


@pytest.mark.parametrize("bounds", [(16,16,16),(32,32,32),(48,48,48),(12,64,64)])
def test_fit_proportions_no_stretch(bounds):
    size = fit_proportions(Size(width=10, height=4, depth=20), bounds)
    assert all(1 <= n <= b for n, b in zip(size.model_dump().values(), bounds))
    assert abs(size.width / size.depth - .5) <= .07


def test_context_budget_and_total_deadline(tmp_path, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr("app.detailed_generator.time.monotonic", lambda: clock[0])
    calls = []
    def fake(self, payload, timeout_seconds=None):
        calls.append(timeout_seconds)
        clock[0] += 4
        return envelope([study(), body(), details()][len(calls)-1])
    monkeypatch.setattr(AIGenerator, "_request", fake)
    settings = Settings(data_dir=tmp_path, ai_timeout_seconds=10, _env_file=None)
    _, info = AIGenerator(settings).generate("car", GenerateOptions(mode="ai", quality="detailed", size="large"), [])
    assert calls == [10,6,2]
    assert info["stagesCompleted"] == ["analysis", "geometry"]
    assert info["warnings"]


def test_detailed_api_persistence_and_old_projects(tmp_path, monkeypatch):
    replies = iter([study(), body(), details()])
    monkeypatch.setattr(AIGenerator, "_request", lambda self, payload, timeout_seconds=None: envelope(next(replies)))
    with TestClient(create_app(Settings(data_dir=tmp_path, _env_file=None))) as client:
        cap = client.get("/api/capabilities").json()
        assert cap["minimumModVersion"] == "0.3.0" and "detailed" in cap["qualityModes"]
        result = client.post("/api/generate", data={"options":json.dumps(dict(mode="ai", quality="detailed", size="large", description="Carro"))})
        assert result.status_code == 201, result.text
        data = result.json()
        assert data["generator"] == "vision-detailed-v2"
        assert data["generationInfo"]["referenceStudy"]["subject"] == "Carro azul"
        assert client.get("/api/builds").json()["items"][0]["generationInfo"] == data["generationInfo"]


def test_all_concrete_colors_available():
    colors = "white orange magenta light_blue yellow lime pink gray light_gray cyan purple blue brown green red black".split()
    assert all("minecraft:" + color + "_concrete" in PALETTE for color in colors)

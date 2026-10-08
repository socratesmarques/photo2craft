import json
from io import BytesIO
from pathlib import Path
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from app.main import create_app
from app.config import Settings, ROOT
from app.schemas import GenerateOptions, Structure
from app.generator import ProceduralGenerator

@pytest.fixture
def config(tmp_path): return Settings(generation_mode="legacy", ai_provider="ollama", data_dir=tmp_path)

@pytest.fixture
def client(config):
    with TestClient(create_app(config)) as c: yield c

def picture(format="PNG"):
    output=BytesIO(); Image.new("RGB",(24,20),"orange").save(output,format=format)
    return output.getvalue()

def generate(client,options=None,raw=None):
    return client.post("/api/generate",data={"options":json.dumps(options or {})},
                       files={"image":("../../unsafe.png",picture() if raw is None else raw,"image/png")})

def test_image_to_import_delete(client,config):
    r=generate(client,{"name":"Castelo do Sócrates","type":"castle","style":"medieval"})
    assert r.status_code==201,r.text
    result=r.json(); ident=result["id"]
    assert result["status"]=="ready" and result["importCommand"]==f"/build import {ident}"
    assert result["sourceImages"][0]["view"]=="reference"
    assert client.get("/api/builds").json()["total"]==1
    assert client.get(f"/api/builds/{ident}").json()["name"]=="Castelo do Sócrates"
    s=Structure.model_validate(client.get(f"/api/builds/{ident}/structure").json())
    assert len(s.blocks)==s.size.width*s.size.height*s.size.depth
    assert client.get(result["thumbnail"]).headers["content-type"]=="image/jpeg"
    assert not (config.data_dir.parent/"unsafe.png").exists()
    assert client.delete(f"/api/builds/{ident}").status_code==204
    assert client.get(f"/api/builds/{ident}/structure").status_code==404
    assert not (config.data_dir/"images"/ident).exists()

@pytest.mark.parametrize("format",["JPEG","PNG","WEBP"])
def test_image_formats(client,format): assert generate(client,raw=picture(format)).status_code==201

def test_invalid_image_and_options(client):
    assert generate(client,raw=b"not a picture").status_code==422
    assert generate(client,raw=b"").status_code==422
    assert generate(client,{"interior":"complete"}).status_code==422
    assert generate(client,{"size":"custom","width":64,"height":64,"depth":64}).status_code==422
    assert client.get("/api/builds/unknown").status_code==404
    assert client.get("/api/builds/a!b/structure").status_code==422

@pytest.mark.parametrize("kind",["automatic","house","castle","building","monument","other"])
@pytest.mark.parametrize("style",["minecraft","medieval","modern","fantasy","cyberpunk"])
def test_generated_structures(kind,style):
    g=ProceduralGenerator()
    s=g.generate("sample",GenerateOptions(type=kind,style=style,interior="simple"),[])
    Structure.model_validate(s.model_dump())
    blocks={b.block for b in s.blocks}
    assert len(blocks)>2 and "minecraft:air" in blocks
    assert all(b.y>=0 for b in s.blocks)

def fixture(): return json.loads((ROOT/"shared/test-house.json").read_text())

def test_json_import_reassigns_identity(client):
    data=fixture()
    r=client.post("/api/builds",json=data)
    assert r.status_code==201,r.text
    assert r.json()["id"]!=data["id"]
    assert r.json()["sourceImages"]==[]

@pytest.mark.parametrize("mutation",["unknown","command","state","bounds","duplicate","fraction","version"])
def test_untrusted_json(client,mutation):
    data=fixture()
    if mutation=="unknown":data["blocks"][0]["block"]="minecraft:missing"
    if mutation=="command":data["blocks"][0]["block"]="minecraft:command_block"
    if mutation=="state":data["blocks"][0]["states"]={"axis":"wrong"}
    if mutation=="bounds":data["blocks"][0]["x"]=data["size"]["width"]
    if mutation=="duplicate":data["blocks"].append(data["blocks"][0])
    if mutation=="fraction":data["blocks"][0]["x"]=0.5
    if mutation=="version":data["formatVersion"]="2.0"
    assert client.post("/api/builds",json=data).status_code==422

def test_limits(config):
    config.max_upload_bytes=1024
    config.max_request_bytes=2048
    config.max_image_pixels=100
    with TestClient(create_app(config)) as c:
        assert generate(c,raw=b"x"*1100).status_code==413
        assert generate(c).status_code==413
        assert c.post("/api/builds",content=(b"x"*5000)).status_code==413
        def chunks():
            for _ in range(5): yield b"x"*1000
        assert c.post("/api/builds",content=chunks()).status_code==413

def test_persistence_and_project_limit(config):
    config.max_projects=1
    with TestClient(create_app(config)) as c:
        ident=generate(c).json()["id"]
        assert generate(c).status_code==409
    with TestClient(create_app(config)) as c:
        assert c.get(f"/api/builds/{ident}/structure").status_code==200
        assert c.get("/api/health").json()["status"]=="ok"
        capabilities=c.get("/api/capabilities").json()
        assert capabilities["imageInterpretation"] is True
        assert capabilities["aiProvider"] == "ollama"

def test_cors(client):
    r=client.options("/api/generate",headers={"Origin":"http://localhost:5173","Access-Control-Request-Method":"POST"})
    assert r.headers["access-control-allow-origin"]=="http://localhost:5173"
    r=client.options("/api/generate",headers={"Origin":"https://untrusted.example","Access-Control-Request-Method":"POST"})
    assert r.status_code==400

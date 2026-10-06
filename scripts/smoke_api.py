"""Create, fetch and delete a temporary project against a running Photo2Craft API."""
import argparse
import json
from pathlib import Path
import httpx

parser=argparse.ArgumentParser()
parser.add_argument("--url",default="http://localhost:8000")
parser.add_argument("--image",required=True,type=Path)
args=parser.parse_args()
with httpx.Client(base_url=args.url,timeout=60) as client:
    with args.image.open("rb") as stream:
        response=client.post("/api/generate",files={"image":(args.image.name,stream)},
                             data={"options":json.dumps({"name":"Smoke test temporário","type":"house"})})
    response.raise_for_status()
    project=response.json();build_id=project["id"]
    try:
        response=client.get(f"/api/builds/{build_id}/structure");response.raise_for_status()
        structure=response.json()
        assert structure["id"]==build_id and structure["blocks"]
        print(f"OK: {len(structure['blocks'])} células. {project['importCommand']}")
    finally:
        client.delete(f"/api/builds/{build_id}").raise_for_status()
        print("Projeto temporário excluído.")

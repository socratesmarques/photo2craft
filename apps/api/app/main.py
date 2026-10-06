from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import logging
import re
import shutil
from threading import BoundedSemaphore, Lock
from uuid import uuid4
from fastapi import FastAPI, File, Form, HTTPException, Query, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from .config import Settings
from .database import BuildRecord, BuildRepository
from .generator import ProceduralGenerator
from .images import decode_image, save_images
from .limits import RequestSizeLimit
from .schemas import Structure, GenerateOptions
from .ai_generator import AIGenerator, GenerationError
from .release import VERSION, RELEASE

logger=logging.getLogger("photo2craft")

def create_app(settings: Settings | None = None) -> FastAPI:
    settings=settings or Settings()
    settings.data_dir.mkdir(parents=True,exist_ok=True)
    repository=BuildRepository(settings.db_url)
    generator=ProceduralGenerator()
    ai_generator=AIGenerator(settings)
    generation_slots=BoundedSemaphore(1)
    mutation_lock=Lock()

    @asynccontextmanager
    async def lifespan(app):
        repository.initialize()
        yield
        repository.engine.dispose()

    app=FastAPI(title="Photo2Craft",version=VERSION,lifespan=lifespan)
    app.state.repository=repository
    app.state.settings=settings
    app.add_middleware(RequestSizeLimit,max_bytes=settings.max_request_bytes)
    app.add_middleware(CORSMiddleware,allow_origins=[x.strip() for x in settings.cors_origins.split(",") if x.strip()],
                       allow_methods=["GET","POST","DELETE"],allow_headers=["Content-Type"])

    def get_record(build_id):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}",build_id): raise HTTPException(422,"ID inválido.")
        record=repository.get(build_id)
        if record is None: raise HTTPException(404,"Construção não encontrada.")
        return record

    def metadata(record):
        s=record.structure
        return {"id":record.id,"name":s["name"],"description":s["description"],"author":s["author"],
                "createdAt":s["createdAt"],"size":s["size"],"blockCount":len(s["blocks"]),
                "solidBlockCount":sum(b["block"]!="minecraft:air" for b in s["blocks"]),
                "status":"ready","generator":record.options.get("_generator","procedural-v1" if record.options else "json-import"),
                "generationInfo":record.options.get("_generation",{}),
                "thumbnail":f"/api/builds/{record.id}/thumbnail" if record.has_image else None,
                "sourceImages":[{"view":"reference","url":f"/api/builds/{record.id}/image"}] if record.has_image else [],
                "options":record.options,"importCommand":f"/build import {record.id}"}

    def enforce_limits(structure):
        if len(structure.blocks)>settings.max_blocks or max(structure.size.model_dump().values())>settings.max_dimension:
            raise HTTPException(422,"Construção excede os limites de blocos ou dimensões.")
        if len(structure.model_dump_json().encode())>settings.max_request_bytes:
            raise HTTPException(422,"Estrutura excede o limite de JSON.")

    def ensure_capacity():
        if repository.count()>=settings.max_projects: raise HTTPException(409,"Limite de projetos atingido. Exclua um projeto.")

    @app.get("/api/health")
    def health():
        repository.count()
        return {"status":"ok","version":VERSION,"release":RELEASE}

    @app.get("/api/capabilities")
    def capabilities(response: Response):
        response.headers["Cache-Control"] = "no-store"
        return {"version":VERSION,"release":RELEASE,
                "maxUploadBytes":settings.max_upload_bytes,"maxBlocks":settings.max_blocks,
                "maxDimension":settings.max_dimension,"maxProjects":settings.max_projects,
                "generationMode":"ai" if ai_generator.configured else "procedural",
                "aiConfigured":ai_generator.configured,"aiProvider":settings.ai_provider,
                "aiModel":settings.ollama_model,
                "imageInterpretation":ai_generator.configured,"fullInterior":False,
                "qualityModes":["quick","detailed"],"minimumModVersion":"0.2.0"}

    @app.get("/api/builds")
    def list_builds(offset: int=Query(0,ge=0),limit: int=Query(30,ge=1,le=100)):
        return {"items":[metadata(r) for r in repository.list(offset,limit)],"total":repository.count(),"offset":offset,"limit":limit}

    @app.post("/api/builds",status_code=201)
    def create_build(structure: Structure):
        enforce_limits(structure)
        structure=structure.model_copy(update={"id":uuid4().hex,"createdAt":datetime.now(timezone.utc),"thumbnail":None})
        with mutation_lock:
            ensure_capacity()
            record=repository.save(BuildRecord(id=structure.id,structure=structure.model_dump(mode="json"),options={}))
        return metadata(record)

    @app.get("/api/builds/{build_id}")
    def get_build(build_id: str): return metadata(get_record(build_id))

    @app.get("/api/builds/{build_id}/structure")
    def get_structure(build_id: str): return get_record(build_id).structure

    def image_response(build_id,filename):
        record=get_record(build_id)
        if not record.has_image: raise HTTPException(404,"Projeto sem imagem.")
        path=settings.data_dir/"images"/record.id/filename
        if not path.is_file(): raise HTTPException(404,"Imagem indisponível.")
        return FileResponse(path,media_type="image/jpeg",headers={"X-Content-Type-Options":"nosniff"})

    @app.get("/api/builds/{build_id}/image")
    def source_image(build_id: str): return image_response(build_id,"source.jpg")

    @app.get("/api/builds/{build_id}/thumbnail")
    def thumbnail(build_id: str): return image_response(build_id,"thumbnail.jpg")

    @app.delete("/api/builds/{build_id}",status_code=204)
    def delete_build(build_id: str):
        with mutation_lock:
            record=get_record(build_id)
            repository.delete(record.id)
            shutil.rmtree(settings.data_dir/"images"/record.id,ignore_errors=True)

    def generate(raw,options):
        image=decode_image(raw,settings.max_image_pixels) if raw else None
        build_id=uuid4().hex
        with mutation_lock:
            ensure_capacity()
        if options.mode=="ai":
            structure, info=ai_generator.generate(build_id,options,[image] if image else [])
            engine="vision-detailed-v2" if options.quality=="detailed" else "vision-blueprint-v1"
        else:
            if options.type not in {"automatic","house","castle","building","monument","other"}:
                raise HTTPException(422,"Esse tipo livre precisa do modo IA. O modo demo usa apenas modelos prontos.")
            size={"small":(11,11,13),"medium":(17,16,19),"large":(25,24,27)}.get(options.size,(options.width,options.height,options.depth))
            if max(size)>settings.max_dimension or size[0]*size[1]*size[2]>settings.max_blocks:
                raise HTTPException(422,"Diminua as dimensões: o volume excede os limites.")
            structure=generator.generate(build_id,options,[image])
            info={"mode":"procedural","summary":"Modelo pronto de demonstração. Imagem e descrição não interpretadas.","assumptions":[]}
            engine="procedural-v1"
        structure.thumbnail=f"/api/builds/{build_id}/thumbnail" if image else None
        enforce_limits(structure)
        directory=settings.data_dir/"images"/build_id
        with mutation_lock:
            ensure_capacity()
            try:
                if image:
                    save_images(image,directory)
                record=repository.save(BuildRecord(id=build_id,structure=structure.model_dump(mode="json"),
                                                   options={**options.model_dump(),"_generator":engine,"_generation":info},has_image=image is not None))
            except Exception:
                shutil.rmtree(directory,ignore_errors=True)
                raise
        return metadata(record)

    @app.post("/api/generate",status_code=201)
    async def generate_build(image: UploadFile | None=File(None),options: str=Form("{}")):
        if not generation_slots.acquire(blocking=False):
            if image:
                await image.close()
            raise HTTPException(429,"Gerador ocupado. Tente novamente em instantes.")
        try:
            try: parsed=GenerateOptions.model_validate_json(options)
            except ValidationError: raise HTTPException(422,"Configurações inválidas. Confira tipo, tamanho e dimensões.")
            raw=await image.read(settings.max_upload_bytes+1) if image else b""
            if image and not raw: raise HTTPException(422,"O arquivo está vazio.")
            if not raw and (parsed.mode=="procedural" or not parsed.description.strip()):
                raise HTTPException(422,"Envie uma imagem ou, no modo IA, descreva a estrutura desejada.")
            if len(raw)>settings.max_upload_bytes: raise HTTPException(413,"Imagem excede o limite de upload.")
            return await run_in_threadpool(generate,raw,parsed)
        except HTTPException: raise
        except GenerationError as exc:
            raise HTTPException(exc.status_code,str(exc)) from exc
        except Exception:
            logger.exception("Falha na geração")
            raise HTTPException(500,"Não foi possível gerar a construção.")
        finally:
            if image:
                await image.close()
            generation_slots.release()

    return app

app=create_app()

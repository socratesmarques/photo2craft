from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import logging
import re
import shutil
import time
import cv2
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
from .jobs import JobRepository
from .progress import progress_callback, report_progress

logger=logging.getLogger("photo2craft")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

def create_app(settings: Settings | None = None) -> FastAPI:
    settings=settings or Settings()
    settings.data_dir.mkdir(parents=True,exist_ok=True)
    repository=BuildRepository(settings.db_url)
    generator=ProceduralGenerator()
    ai_generator=AIGenerator(settings)
    generation_slots=BoundedSemaphore(1)
    mutation_lock=Lock()
    jobs=JobRepository(repository)
    worker=ThreadPoolExecutor(max_workers=1, thread_name_prefix="photo2craft-generation")

    @asynccontextmanager
    async def lifespan(app):
        repository.initialize()
        jobs.recover()
        try:
            yield
        finally:
            await run_in_threadpool(worker.shutdown, wait=True)
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
                "qualityModes":["quick","detailed","ultra"],"minimumModVersion":"0.3.0",
                "visualRefinement":True,"multiViewUpload":False,"depthConfigured":bool(settings.depth_model_path),
                "generationJobs":True,"aiTimeoutSeconds":settings.ai_timeout_seconds}

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
        return FileResponse(path,media_type="image/png" if filename.endswith(".png") else "image/jpeg",headers={"X-Content-Type-Options":"nosniff"})

    @app.get("/api/builds/{build_id}/image")
    def source_image(build_id: str):
        record = get_record(build_id)
        filename = "source.png" if (settings.data_dir/"images"/record.id/"source.png").is_file() else "source.jpg"
        return image_response(build_id, filename)

    @app.get("/api/builds/{build_id}/thumbnail")
    def thumbnail(build_id: str): return image_response(build_id,"thumbnail.jpg")

    @app.get("/api/builds/{build_id}/render")
    def reference_render(build_id: str): return image_response(build_id,"render.png")

    @app.delete("/api/builds/{build_id}",status_code=204)
    def delete_build(build_id: str):
        with mutation_lock:
            record=get_record(build_id)
            repository.delete(record.id)
            shutil.rmtree(settings.data_dir/"debug"/record.id,ignore_errors=True)
            shutil.rmtree(settings.data_dir/"images"/record.id,ignore_errors=True)

    def generate(raw,options,build_id=None):
        started = time.monotonic()
        report_progress("preprocessing")
        image=decode_image(raw,settings.max_image_pixels) if raw else None
        build_id=build_id or uuid4().hex
        with mutation_lock:
            ensure_capacity()
        if options.mode=="ai":
            structure, info=ai_generator.generate(build_id,options,[image] if image else [])
            engine="vision-refinement-v3" if image and options.quality in {"detailed","ultra"} else "vision-detailed-v2" if options.quality in {"detailed","ultra"} else "vision-blueprint-v1"
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
        report_progress("saving")
        directory=settings.data_dir/"images"/build_id
        with mutation_lock:
            ensure_capacity()
            try:
                if image:
                    save_images(image,directory)
                    if info.get("camera"):
                        from .voxel_render import render_structure
                        from .scene_plan import Camera
                        try:
                            rendered, _ = render_structure(structure, Camera.model_validate(info["camera"]))
                            rendered.save(directory/"render.png")
                            info["renderAvailable"] = True
                        except (ValueError, RuntimeError, OSError, cv2.error):
                            info.setdefault("warnings", []).append("Render de comparação indisponível; use o preview 3D.")
                if "timings" in info:
                    info["timings"]["total"] = round(time.monotonic() - started, 3)
                record=repository.save(BuildRecord(id=build_id,structure=structure.model_dump(mode="json"),
                                                   options={**options.model_dump(),"_generator":engine,"_generation":info},has_image=image is not None))
            except Exception:
                shutil.rmtree(directory,ignore_errors=True)
                raise
        return metadata(record)

    async def read_generation(image, options):
        try: parsed=GenerateOptions.model_validate_json(options)
        except ValidationError: raise HTTPException(422,"Configurações inválidas. Confira tipo, tamanho e dimensões.")
        raw=await image.read(settings.max_upload_bytes+1) if image else b""
        if image and not raw: raise HTTPException(422,"O arquivo está vazio.")
        if not raw and (parsed.mode=="procedural" or not parsed.description.strip()):
            raise HTTPException(422,"Envie uma imagem ou, no modo IA, descreva a estrutura desejada.")
        if len(raw)>settings.max_upload_bytes: raise HTTPException(413,"Imagem excede o limite de upload.")
        return raw,parsed

    def run_job(job_id, raw, options):
        token=progress_callback.set(lambda stage: jobs.update(job_id, stage=stage))
        try:
            jobs.update(job_id,status="running",stage="preprocessing")
            generate(raw,options,job_id)
            jobs.update(job_id,status="succeeded",stage="final")
        except (GenerationError,HTTPException) as exc:
            detail=exc.detail if isinstance(exc,HTTPException) else str(exc)
            logger.warning("build_id=%s generation failed: %s",job_id,detail)
            jobs.update(job_id,status="failed",error=str(detail)[:1000],error_code=exc.status_code)
        except Exception:
            logger.exception("build_id=%s generation failed",job_id)
            jobs.update(job_id,status="failed",error="Falha interna na geração. Consulte os logs da API com este ID: "+job_id,error_code=500)
        finally:
            progress_callback.reset(token)
            generation_slots.release()

    @app.post("/api/generation-jobs",status_code=202)
    async def start_generation(image: UploadFile | None=File(None),options: str=Form("{}")):
        acquired=False
        submitted=False
        try:
            acquired=generation_slots.acquire(blocking=False)
            if not acquired: raise HTTPException(429,"Gerador ocupado. Tente novamente em instantes.")
            raw,parsed=await read_generation(image,options)
            with mutation_lock:
                ensure_capacity()
            job_id=uuid4().hex
            job=jobs.create(job_id)
            try:
                worker.submit(run_job,job_id,raw,parsed)
            except RuntimeError as exc:
                jobs.update(job_id,status="failed",error="A API está encerrando. Tente novamente.",error_code=503)
                raise HTTPException(503,"A API está encerrando. Tente novamente.") from exc
            submitted=True
            return job
        finally:
            if acquired and not submitted: generation_slots.release()
            if image: await image.close()

    @app.get("/api/generation-jobs/{job_id}")
    def generation_status(job_id: str,response: Response):
        response.headers["Cache-Control"]="no-store"
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}",job_id): raise HTTPException(422,"ID inválido.")
        job=jobs.get(job_id)
        if job is None: raise HTTPException(404,"Geração não encontrada ou histórico expirado. Confira Minhas construções.")
        return job

    @app.post("/api/generate",status_code=201)
    async def generate_build(image: UploadFile | None=File(None),options: str=Form("{}")):
        if not generation_slots.acquire(blocking=False):
            if image:
                await image.close()
            raise HTTPException(429,"Gerador ocupado. Tente novamente em instantes.")
        try:
            raw,parsed=await read_generation(image,options)
            return await run_in_threadpool(generate,raw,parsed)
        except HTTPException: raise
        except GenerationError as exc:
            raise HTTPException(exc.status_code,str(exc)) from exc
        except Exception:
            logger.exception("Falha na geração")
            raise HTTPException(500,"Não foi possível gerar a construção.")
        finally:
            generation_slots.release()
            if image:
                await image.close()

    return app

app=create_app()

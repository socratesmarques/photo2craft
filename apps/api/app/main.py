from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import hashlib
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
from pydantic import ValidationError, Field
from .schemas import StrictModel
from starlette.concurrency import run_in_threadpool
from .config import Settings
from .database import BuildRecord, BuildRepository
from .generator import ProceduralGenerator
from .images import decode_image, save_images
from .limits import RequestSizeLimit
from .schemas import Structure, GenerateOptions
from .ai_generator import AIGenerator, GenerationError
from .release import VERSION, RELEASE
from .jobs import JobManager
from .architectural_generator import progress, generate_architectural
from .blueprint import target_size

class Approval(StrictModel):
    approved: bool
    content_hash: str = Field(pattern=r'^[a-f0-9]{64}$')

class RefinementRequest(StrictModel):
    instruction: str = Field(min_length=1,max_length=2000)

class MaterialChange(StrictModel):
    material_id: str = Field(max_length=48)
    block: str = Field(max_length=80)
    states: dict[str,str] = Field(default_factory=dict,max_length=8)

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
    jobs=JobManager(repository)

    @asynccontextmanager
    async def lifespan(app):
        repository.initialize()
        jobs.initialize()
        yield
        jobs.close()
        repository.engine.dispose()

    app=FastAPI(title="Photo2Craft",version=VERSION,lifespan=lifespan)
    app.state.repository=repository
    app.state.settings=settings
    app.state.jobs=jobs
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
                "architectureAvailable":bool(record.options.get("_generation",{}).get("architecturalPlan")),
                "status":record.options.get("_approval","ready"),"contentHash":content_hash(s),"generator":record.options.get("_generator","procedural-v1" if record.options else "json-import"),
                "generationInfo":{k:v for k,v in record.options.get("_generation",{}).items() if k!="architecturalPlan"},
                "thumbnail":f"/api/builds/{record.id}/thumbnail" if record.has_image else None,
                "sourceImages":[{"view":"reference" if i==0 else f"reference-{i+1}","url":f"/api/builds/{record.id}/image" if i==0 else f"/api/builds/{record.id}/references/{i}"} for i in range(record.options.get("_reference_count",1))] if record.has_image else [],
                "options":{k:v for k,v in record.options.items() if not k.startswith("_")},"importCommand":f"/build import {record.id}"}

    def content_hash(structure):
        return hashlib.sha256(json.dumps(structure,sort_keys=True,separators=(",",":")).encode()).hexdigest()

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
                "aiModel":settings.gemini_model if settings.ai_provider=="gemini" else settings.ollama_model,
                "configurationIssue":None if ai_generator.configured else "Configure GEMINI_API_KEY e confirme projeto Free Tier sem faturamento no backend.",
                "architecturalPipeline":settings.generation_mode=="architectural","generationJobs":True,
                "maxRequestBytes":settings.max_request_bytes,"maxReferenceImages":settings.max_reference_images,
                "imageInterpretation":ai_generator.configured,"fullInterior":False,
                "qualityModes":["quick","detailed","ultra"],"minimumModVersion":"0.3.0",
                "visualRefinement":settings.enable_visual_refinement,"multiViewUpload":True,"depthConfigured":bool(settings.depth_model_path)}

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
    def get_structure(build_id: str,response: Response):
        response.headers["Cache-Control"]="no-store"
        record=get_record(build_id)
        if record.options.get('_approval','ready') != 'ready':
            raise HTTPException(409,'Confira a prévia e aprove a construção no site antes de importar.')
        return record.structure

    @app.get('/api/builds/{build_id}/preview')
    def get_preview(build_id: str,response: Response):
        response.headers["Cache-Control"]="no-store"
        return get_record(build_id).structure

    @app.get('/api/builds/{build_id}/architecture')
    def get_architecture(build_id: str):
        plan=get_record(build_id).options.get('_generation',{}).get('architecturalPlan')
        if plan is None: raise HTTPException(404,'Projeto legado sem plano arquitetônico.')
        return plan

    @app.post('/api/builds/{build_id}/approval')
    def approve(build_id: str, decision: Approval):
        with mutation_lock:
            record=get_record(build_id)
            if decision.content_hash != content_hash(record.structure):
                raise HTTPException(409,'A construção mudou; recarregue a prévia antes de aprovar.')
            record.options={**record.options,'_approval':'ready' if decision.approved else 'rejected'}
            repository.save(record)
            return metadata(record)


    def image_response(build_id,filename,record=None):
        record=record or get_record(build_id)
        if not record.has_image and filename not in {"render.png",record.options.get('_render_file')}: raise HTTPException(404,"Projeto sem imagem.")
        path=settings.data_dir/"images"/record.id/filename
        if not path.is_file(): raise HTTPException(404,"Imagem indisponível.")
        return FileResponse(path,media_type="image/png" if filename.endswith(".png") else "image/jpeg",headers={"X-Content-Type-Options":"nosniff","Cache-Control":"no-store"})

    @app.get("/api/builds/{build_id}/image")
    def source_image(build_id: str):
        record = get_record(build_id)
        filename = "source.png" if (settings.data_dir/"images"/record.id/"source.png").is_file() else "source.jpg"
        return image_response(build_id, filename)

    @app.get('/api/builds/{build_id}/references/{index}')
    def extra_reference(build_id: str,index: int):
        record=get_record(build_id)
        if index<1 or index>=record.options.get('_reference_count',1):
            raise HTTPException(404,'Referência não encontrada.')
        return image_response(build_id,f'reference-{index}.png')

    @app.get("/api/builds/{build_id}/thumbnail")
    def thumbnail(build_id: str): return image_response(build_id,"thumbnail.jpg")

    @app.get("/api/builds/{build_id}/render")
    def reference_render(build_id: str):
        record=get_record(build_id)
        return image_response(build_id,record.options.get('_render_file','render.png'),record)

    @app.delete("/api/builds/{build_id}",status_code=204)
    def delete_build(build_id: str):
        with mutation_lock:
            record=get_record(build_id)
            repository.delete(record.id)
            shutil.rmtree(settings.data_dir/"debug"/record.id,ignore_errors=True)
            shutil.rmtree(settings.data_dir/"images"/record.id,ignore_errors=True)

    def generate(raw,options,extra_raws=None,seed=None):
        started = time.monotonic()
        image=decode_image(raw,settings.max_image_pixels) if raw else None
        images=([image] if image else [])+[decode_image(r,settings.max_image_pixels) for r in (extra_raws or [])]
        build_id=uuid4().hex
        with mutation_lock:
            ensure_capacity()
        if options.mode=="ai":
            if seed:
                structure,info=generate_architectural(ai_generator,build_id,options,images,target_size(options,settings.max_dimension),seed)
            else:
                structure, info=ai_generator.generate(build_id,options,images)
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
        if options.mode=='ai' and settings.generation_mode=='architectural': engine='architectural-2.0'
        progress('validation')
        structure.thumbnail=f"/api/builds/{build_id}/thumbnail" if image else None
        enforce_limits(structure)
        directory=settings.data_dir/"images"/build_id
        with mutation_lock:
            ensure_capacity()
            try:
                if image:
                    save_images(image,directory)
                    for index,reference in enumerate(images[1:],1): reference.save(directory/f'reference-{index}.png')
                if info.get("camera"):
                    progress("preview_render")
                    directory.mkdir(parents=True,exist_ok=True)
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
                                                   options={**options.model_dump(),"_generator":engine,"_generation":info,"_reference_count":len(images),
                                                            "_approval":"pending" if engine=="architectural-2.0" else "ready"},has_image=image is not None))
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

    async def read_uploads(image,references,options):
        uploads=([image] if image else [])+list(references or [])
        try:
            if len(uploads)>settings.max_reference_images:
                raise HTTPException(422,'Máximo de referências excedido.')
            try: parsed=GenerateOptions.model_validate_json(options)
            except ValidationError: raise HTTPException(422,'Opções inválidas.')
            raws=[]
            for upload in uploads:
                raw=await upload.read(settings.max_upload_bytes+1)
                if not raw: raise HTTPException(422,'Arquivo vazio.')
                if len(raw)>settings.max_upload_bytes: raise HTTPException(413,'Imagem excede limite de upload.')
                await run_in_threadpool(decode_image,raw,settings.max_image_pixels)
                raws.append(raw)
            if not raws and (parsed.mode=='procedural' or not parsed.description.strip()):
                raise HTTPException(422,'Envie imagem ou uma descrição no modo IA.')
            if parsed.mode=='ai' and not ai_generator.configured:
                raise HTTPException(503,'Configure a chave Gemini Free Tier no backend ou selecione Ollama opcional.')
            ensure_capacity()
            return raws,parsed
        finally:
            for upload in uploads: await upload.close()

    def queued_work(raws,parsed,seed=None):
        def work():
            with generation_slots:
                return generate(raws[0] if raws else b'',parsed,raws[1:],seed)
        return work

    @app.post('/api/generations',status_code=202)
    async def start_generation(image: UploadFile | None=File(None),references: list[UploadFile] | None=File(None),options: str=Form('{}')):
        raws,parsed=await read_uploads(image,references,options)
        return jobs.submit(queued_work(raws,parsed))

    @app.get('/api/generations/{job_id}')
    def get_generation(job_id: str): return jobs.get(job_id)

    @app.post('/api/builds/{build_id}/refine',status_code=202)
    def refine_build(build_id: str,request: RefinementRequest):
        if not ai_generator.configured: raise HTTPException(503,'IA não configurada.')
        if not settings.enable_visual_refinement or settings.max_refinement_passes<1:
            raise HTTPException(409,'Refinamento visual desativado na configuração.')
        record=get_record(build_id)
        info=record.options.get('_generation',{})
        if not info.get('architecturalPlan') or not record.has_image:
            raise HTTPException(422,'Refinamento exige plano arquitetônico e referência visual.')
        opts={k:v for k,v in record.options.items() if not k.startswith('_')}
        opts.update(description=request.instruction,quality='detailed',max_refinements=settings.max_refinement_passes)
        parsed=GenerateOptions.model_validate(opts)
        directory=settings.data_dir/'images'/record.id
        try:
            raws=[(directory/'source.png').read_bytes()]+[(directory/f'reference-{i}.png').read_bytes() for i in range(1,record.options.get('_reference_count',1))]
        except OSError:
            raise HTTPException(409,'Referências indisponíveis. Reenvie as imagens antes de refinar.')
        ensure_capacity()
        return jobs.submit(queued_work(raws,parsed,{'plan':info['architecturalPlan'],'study':info['referenceStudy']}))

    @app.post('/api/builds/{build_id}/materials')
    def replace_material(build_id: str,request: MaterialChange):
        from .architecture import ArchitecturalPlan,compile_architecture
        from .scene_plan import Camera
        from .voxel_render import render_structure
        with mutation_lock:
            record=get_record(build_id)
            info=dict(record.options.get('_generation',{}))
            if not info.get('architecturalPlan'): raise HTTPException(422,'Projeto sem plano arquitetônico.')
            data=json.loads(json.dumps(info['architecturalPlan']))
            target=next((m for m in data['palette'] if m['id']==request.material_id),None)
            if target is None: raise HTTPException(422,'Material inexistente.')
            target['block']=request.block;target['states']=request.states
            try:
                plan=ArchitecturalPlan.model_validate(data)
                opts=GenerateOptions.model_validate({k:v for k,v in record.options.items() if not k.startswith('_')})
                structure=compile_architecture(plan,build_id,opts,settings.max_blocks,target_size(opts,settings.max_dimension))
                structure.createdAt=Structure.model_validate(record.structure).createdAt
                structure.thumbnail=record.structure.get('thumbnail')
                enforce_limits(structure)
                rendered,_=render_structure(structure,Camera.model_validate(info['camera']))
            except ValueError: raise HTTPException(422,'Material ou geometria inválidos.')
            info.update(architecturalPlan=plan.model_dump(),score=None,scoreHistory=[],cacheHit=False)
            info.setdefault('warnings',[]).append('Materiais alterados manualmente; avaliação visual anterior invalidada.')
            record.structure=structure.model_dump(mode='json')
            render_file=f'render-{content_hash(record.structure)}.png'
            record.options={**record.options,'_generation':info,'_approval':'pending','_render_file':render_file}
            directory=settings.data_dir/'images'/record.id
            directory.mkdir(parents=True,exist_ok=True)
            rendered.save(directory/'render.tmp.png')
            (directory/'render.tmp.png').replace(directory/render_file)
            # Publish structure and immutable render pointer in the same DB commit.
            # Failed commits leave an unreferenced file, never a stale preview.
            repository.save(record)
            return metadata(record)

    return app

app=create_app()

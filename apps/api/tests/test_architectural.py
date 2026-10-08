import copy
import json
import time
from io import BytesIO
import httpx
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from pydantic import ValidationError
from app.ai_generator import AIGenerator
from app.architecture import (ArchitecturalPlan,ArchitecturalStudy,ArchitecturalCorrections,compile_architecture,
                              apply_edits,migrate_scene,architecture_schema)
from app.config import Settings
from app.main import create_app
from app.providers import GeminiProvider,QuotaError,QuotaGate
from app.ollama_session import GenerationError
from app.schemas import GenerateOptions,Structure

KEY='test-key-never-real-01234567890'


def settings(tmp_path,**changes):
    return Settings(**{'data_dir':tmp_path,'gemini_api_key':KEY,'gemini_free_tier_confirmed':True,
                    'enable_generation_cache':False,'_env_file':None,**changes})


def element(id='body',start=(0,0,0),end=(15,7,15),**changes):
    return dict(id=id,kind='wall',shape='box',start=dict(zip('xyz',start)),end=dict(zip('xyz',end)),
                axis='y',hollow=True,thickness=1,operation='add',material='wall',overlaps=[],
                evidence=dict(kind='visible',confidence=.8,references=[0],note='Fachada visível; profundidade aproximada.'),**changes)


def plan():
    return dict(schema_version='2.0',coordinate_system='x-east_y-up_z-south_blocks',orientation='north',
                structure_type='house',summary='Casa com telhado de duas águas',size=dict(width=16,height=16,depth=16),
                palette=[dict(id='wall',block='minecraft:white_concrete',states={}),dict(id='roof',block='minecraft:red_concrete',states={})],
                elements=[element(),{**element('roof',(0,8,0),(15,12,15)),'hollow':False,'shape':'gable','axis':'z','material':'roof','kind':'roof'}],relations=[])


def study():
    return dict(subject='Casa',proportions=dict(width=16,height=16,depth=16),silhouette='Retangular com telhado triangular',
                landmarks=['Telhado vermelho'],symmetry='x',material_notes='Parede branca e telhado vermelho',assumptions=['Traseira inferida'],
                camera=dict(yaw=0,pitch=0),architectural_style='simples',apparent_floors=1,preserve=['telhado'],unknown=['interior'],orthographic_comparable=True)


def score(n=95,**changes):
    return dict(structure=n,detail=n,silhouette=n,proportion=n,color=n,issues=[],comparable=True,perspective_note='Vista frontal aproximada',**changes)


def options(**changes):
    return GenerateOptions(mode='ai',quality='detailed',size='custom',width=16,height=16,depth=16,**changes)


def image():
    data=BytesIO();Image.new('RGB',(64,64),'gray').save(data,'PNG');return data.getvalue()


def envelope(value,reason='STOP'):
    return {'candidates':[{'finishReason':reason,'content':{'parts':[{'text':json.dumps(value)}]}}],
            'usageMetadata':{'promptTokenCount':200,'candidatesTokenCount':100,'totalTokenCount':300}}


def provider(tmp_path,replies,**changes):
    seen=[]
    def handler(request):
        seen.append(request)
        result=replies[len(seen)-1]
        if isinstance(result,Exception): raise result
        if isinstance(result,httpx.Response): return result
        return httpx.Response(200,json=result)
    p=GeminiProvider(settings(tmp_path,**changes),httpx.MockTransport(handler))
    return p,seen


def ask(p): return p.ask({'type':'object'},'system',{},[],12000,'test',time.monotonic()+30)


def test_gemini_contract_and_no_secrets_in_logs(tmp_path,caplog):
    p,seen=provider(tmp_path,[envelope({'ok':True})])
    with caplog.at_level('INFO',logger='photo2craft.providers'):
        assert json.loads(ask(p))=={'ok':True}
    req=seen[0];payload=json.loads(req.content)
    assert req.url.host=='generativelanguage.googleapis.com' and req.headers['x-goog-api-key']==KEY
    assert KEY not in str(req.url) and KEY not in caplog.text
    assert payload['generationConfig']['responseMimeType']=='application/json'
    assert 'responseJsonSchema' in payload['generationConfig'] and 'tools' not in payload
    assert p.calls[0]['tokens']['totalTokenCount']==300


@pytest.mark.parametrize('changes',[{'gemini_api_key':''},{'gemini_free_tier_confirmed':False},{'gemini_api_key':'bad key'}])
def test_missing_invalid_key_or_unconfirmed_free_project_never_calls(tmp_path,changes):
    p,seen=provider(tmp_path,[],**changes)
    with pytest.raises(GenerationError): ask(p)
    assert not seen


def test_paid_unknown_models_and_providers_rejected():
    for config in ({'gemini_model':'gemini-pro-paid'},{'ai_provider':'openai'},{'fallback_provider':'paid'},{'ai_provider':'ollama','ollama_url':'file:///etc/passwd'}):
        with pytest.raises(ValidationError): Settings(_env_file=None,**config)


@pytest.mark.parametrize('status',[400,401,403,404,302])
def test_non_retryable_http(tmp_path,status):
    p,seen=provider(tmp_path,[httpx.Response(status,text='sensitive upstream body')])
    with pytest.raises(GenerationError) as exc: ask(p)
    assert len(seen)==1 and 'sensitive' not in str(exc.value)


def test_network_and_server_retry_bounded(tmp_path,monkeypatch):
    monkeypatch.setattr('app.providers.time.sleep',lambda _:None)
    p,seen=provider(tmp_path,[httpx.ConnectError('private'),httpx.Response(503),envelope({'ok':1})])
    assert json.loads(ask(p))=={'ok':1} and len(seen)==3
    p,seen=provider(tmp_path/'failed',[httpx.ReadTimeout('x')]*3)
    with pytest.raises(GenerationError): ask(p)
    assert len(seen)==3


def test_429_blocks_across_restart_and_other_models(tmp_path):
    p,seen=provider(tmp_path,[httpx.Response(429,json={'error':{'message':'quota'}})])
    with pytest.raises(QuotaError): ask(p)
    p2,seen2=provider(tmp_path,[],gemini_model='gemini-3.7-flash')
    with pytest.raises(QuotaError): ask(p2)
    assert len(seen)==1 and seen2==[]


def test_daily_local_limit_and_rollover(tmp_path,monkeypatch):
    p,seen=provider(tmp_path,[envelope({})],ai_daily_call_limit=1)
    ask(p)
    with pytest.raises(QuotaError): ask(p)
    assert len(seen)==1
    monkeypatch.setattr(QuotaGate,'window',staticmethod(lambda:('2099-01-01',time.time()+1000)))
    p2,_=provider(tmp_path,[envelope({})],ai_daily_call_limit=1)
    ask(p2)


@pytest.mark.parametrize('response',[envelope({'partial':1},'MAX_TOKENS'),envelope({},'SAFETY'),{'candidates':[]},
                                    {'candidates':[{'finishReason':'STOP','content':{'parts':[]}}]},[],httpx.Response(200,content=b'x'*(2097153))])
def test_incomplete_malformed_or_oversized_not_accepted(tmp_path,response):
    p,_=provider(tmp_path,[response])
    with pytest.raises(GenerationError): ask(p)


def test_geometry_roof_openings_stairs_states_and_determinism():
    data=plan()
    door={**element('door',(6,1,0),(7,3,0)),'hollow':False,'operation':'cut','material':None,'overlaps':['body'],'kind':'door'}
    data['elements'].append(door)
    result=compile_architecture(ArchitecturalPlan.model_validate(data),'house',options(),50000,(16,16,16),1)
    blocks={(b.x,b.y,b.z):b.block for b in result.blocks}
    assert blocks[6,1,0]=='minecraft:air' and blocks[0,1,0]=='minecraft:white_concrete'
    assert blocks[7,12,0]=='minecraft:red_concrete'
    assert len(blocks)==len(result.blocks)
    Structure.model_validate(result.model_dump())
    data=plan();data['elements']=[{**element('stairs',(0,0,0),(7,7,3)),'hollow':False,'shape':'stairs','axis':'x'}]
    data['palette'][0]=dict(id='wall',block='minecraft:oak_log',states={'axis':'x'})
    result=compile_architecture(ArchitecturalPlan.model_validate(data),'stairs',options(),50000,(16,16,16),1)
    assert max(b.y for b in result.blocks if b.x==0)==0
    assert max(b.y for b in result.blocks if b.x==7)==7
    assert all(b.states=={'axis':'x'} for b in result.blocks)


@pytest.mark.parametrize('mutation',['bounds','duplicate','material','state','collision','floating','empty_cut','relation','reference','version','unknown_confidence'])
def test_bad_architecture_rejected(mutation):
    data=plan()
    if mutation=='bounds': data['elements'][0]['end']['x']=16
    if mutation=='duplicate': data['elements'][1]['id']='body'
    if mutation=='material': data['palette'][0]['block']='minecraft:missing'
    if mutation=='state': data['palette'][0]['states']={'facing':'upward'}
    if mutation=='collision': data['elements'].append({**element('overlap'),'material':'roof'})
    if mutation=='floating': data['elements']=[{**element('floating',(0,2,0),(3,3,3)),'hollow':False}]
    if mutation=='empty_cut': data['elements'].append({**element('cut',(0,15,0),(1,15,1)),'operation':'cut','material':None,'hollow':False,'overlaps':['body']})
    if mutation=='relation': data['relations']=[dict(source='body',target='roof',relation='above')]
    if mutation=='reference': data['elements'][0]['evidence']['references']=[3]
    if mutation=='version': data['schema_version']='3.0'
    if mutation=='unknown_confidence': data['elements'][0]['evidence']['kind']='unknown'
    with pytest.raises(ValueError): compile_architecture(ArchitecturalPlan.model_validate(data),'bad',options(),50000,(16,16,16),1)


def test_geometry_limits_and_transactional_edits():
    original=ArchitecturalPlan.model_validate(plan());before=original.model_dump()
    with pytest.raises(ValueError): compile_architecture(original,'a',options(),4,(16,16,16),1)
    with pytest.raises(ValueError): compile_architecture(original,'a',options(),50000,(10,10,10),1)
    edits=ArchitecturalCorrections.model_validate({'corrections':[{'action':'remove','target':'missing','element':None}]})
    with pytest.raises(ValueError): apply_edits(original,edits)
    assert original.model_dump()==before


def install_mock(monkeypatch,replies,seen):
    original=GeminiProvider.__init__
    def init(self,settings,transport=None):
        def handler(request):
            seen.append(json.loads(request.content))
            value=replies.pop(0)
            return value if isinstance(value,httpx.Response) else httpx.Response(200,json=envelope(value))
        original(self,settings,httpx.MockTransport(handler))
    monkeypatch.setattr(GeminiProvider,'__init__',init)


def wait_job(client,id):
    for _ in range(300):
        value=client.get('/api/generations/'+id).json()
        if value['status'] in {'ready','failed'}: return value
        time.sleep(.01)
    pytest.fail('Job exceeded test deadline')


def test_full_job_multiview_approval_materials_export_and_persistence(tmp_path,monkeypatch):
    seen=[];install_mock(monkeypatch,[study(),plan(),score()],seen)
    config=settings(tmp_path)
    with TestClient(create_app(config)) as c:
        cap=c.get('/api/capabilities').json()
        assert cap['aiProvider']=='gemini' and cap['multiViewUpload'] and KEY not in json.dumps(cap)
        response=c.post('/api/generations',data={'options':options().model_dump_json()},files=[('image',('front.png',image())),('references',('side.png',image()))])
        assert response.status_code==202,response.text
        job=wait_job(c,response.json()['id']);assert job['status']=='ready',job
        bid=job['buildId'];build=c.get('/api/builds/'+bid).json()
        assert build['status']=='pending' and len(build['sourceImages'])==2
        assert 'architecturalPlan' not in build['generationInfo']
        assert c.get(f'/api/builds/{bid}/structure').status_code==409
        preview=c.get(f'/api/builds/{bid}/preview').json();Structure.model_validate(preview)
        assert c.get(f'/api/builds/{bid}/render').status_code==200
        assert c.get(f'/api/builds/{bid}/references/1').status_code==200
        assert c.get(f'/api/builds/{bid}/references/4').status_code==404
        assert c.post(f'/api/builds/{bid}/approval',json={'approved':True,'content_hash':'0'*64}).status_code==409
        assert c.post(f'/api/builds/{bid}/approval',json={'approved':True,'content_hash':build['contentHash']}).status_code==200
        assert c.get(f'/api/builds/{bid}/structure').json()==preview
        changed=c.post(f'/api/builds/{bid}/materials',json={'material_id':'roof','block':'minecraft:blue_concrete'}).json()
        assert changed['status']=='pending' and changed['generationInfo']['score'] is None
        assert changed['contentHash']!=build['contentHash']
        assert c.post(f'/api/builds/{bid}/approval',json={'approved':False,'content_hash':changed['contentHash']}).json()['status']=='rejected'
        assert c.get(f'/api/builds/{bid}/structure').status_code==409
        assert len(seen)==3 and len(seen[0]['contents'][0]['parts'])==3
        assert {'architectural_plan','validation','block_generation','preview_render'}<={e['stage'] for e in job['events']}
    with TestClient(create_app(config)) as c:
        assert c.get('/api/generations/'+job['id']).json()['status']=='ready'
        assert c.get(f'/api/builds/{bid}').json()['status']=='rejected'


def test_job_errors_and_restart_recovery(tmp_path,monkeypatch):
    seen=[];install_mock(monkeypatch,[httpx.Response(429)],seen)
    config=settings(tmp_path)
    app=create_app(config)
    with TestClient(app) as c:
        response=c.post('/api/generations',data={'options':options(description='Casa').model_dump_json()})
        job=wait_job(c,response.json()['id']);assert job['status']=='failed' and job['httpStatus']==429
        assert c.get('/api/builds').json()['total']==0
        from app.database import JobRecord
        with app.state.repository.sessions() as db:
            db.add(JobRecord(id='interrupted',data={'status':'running','stage':'analysis'}));db.commit()
    with TestClient(create_app(config)) as c:
        assert c.get('/api/generations/interrupted').json()['status']=='failed'


def test_cache_avoids_external_calls_and_changes_identity(tmp_path,monkeypatch):
    seen=[];install_mock(monkeypatch,[study(),plan(),score()],seen)
    config=settings(tmp_path);config.enable_generation_cache=True
    gen=AIGenerator(config)
    first,info=gen.generate('first',options(),[Image.new('RGB',(64,64),'gray')])
    second,cached=gen.generate('second',options(name='Outro'),[Image.new('RGB',(64,64),'gray')])
    assert len(seen)==3 and cached['cacheHit'] and cached['calls']==[]
    assert second.id=='second' and second.name=='Outro' and first.blocks==second.blocks


def test_uncertain_camera_disables_comparison_and_refinements(tmp_path,monkeypatch):
    seen=[];s=study();s['orthographic_comparable']=False
    install_mock(monkeypatch,[s,plan(),score()],seen)
    result,info=AIGenerator(settings(tmp_path)).generate('perspective',options(),[Image.new('RGB',(64,64),'gray')])
    assert result.blocks and info['score'] is None and info['warnings'] and len(seen)==2


def test_quota_during_refinement_keeps_reviewable_geometry(tmp_path,monkeypatch):
    seen=[];install_mock(monkeypatch,[study(),plan(),httpx.Response(429)],seen)
    result,info=AIGenerator(settings(tmp_path)).generate('quota',options(),[Image.new('RGB',(64,64),'gray')])
    assert result.blocks and info['score'] is None and any('Cota' in w for w in info['warnings'])
    with pytest.raises(QuotaError):
        AIGenerator(settings(tmp_path)).generate('again',options(),[Image.new('RGB',(64,64),'gray')])
    assert len(seen)==3


def test_plan_repair_invalid_schema_bounded(tmp_path,monkeypatch):
    seen=[];invalid=plan();invalid['elements'][0]['end']['x']=90
    install_mock(monkeypatch,[study(),invalid,invalid],seen)
    with pytest.raises(GenerationError,match='após uma correção'):
        AIGenerator(settings(tmp_path)).generate('repair',options(),[Image.new('RGB',(64,64),'gray')])
    assert len(seen)==3


def test_explicit_local_fallback_on_quota(tmp_path,monkeypatch):
    seen=[];install_mock(monkeypatch,[httpx.Response(429)],seen)
    replies=iter([study(),plan(),score()])
    monkeypatch.setattr(AIGenerator,'_request',lambda *a,**k:{'done':True,'message':{'content':json.dumps(next(replies))}})
    result,info=AIGenerator(settings(tmp_path,fallback_provider='ollama',ai_context_tokens=32768)).generate('local',options(),[Image.new('RGB',(64,64),'gray')])
    assert result.blocks and info['provider']=='ollama' and info['warnings'] and len(seen)==1


def test_legacy_scene_migration():
    from test_visual import plan as old_plan
    migrated=migrate_scene(old_plan())
    assert migrated.schema_version=='2.0' and migrated.elements[0].evidence.kind=='unknown'
    compile_architecture(migrated,'old',options(),50000,(32,32,32))


def test_default_api_boots_without_key_or_ollama(tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path,_env_file=None))) as c:
        assert c.get('/api/health').status_code==200
        assert c.get('/api/capabilities').json()['aiConfigured'] is False
        assert c.post('/api/generations',data={'options':options(description='Casa').model_dump_json()}).status_code==503


def test_arch_has_grounded_jambs_and_open_center():
    data=plan();data['elements']=[{**element('arch',(0,0,0),(15,15,2)),'shape':'arch','kind':'arch','axis':'z','hollow':False,'thickness':2}]
    result=compile_architecture(ArchitecturalPlan.model_validate(data),'arch',options(),50000,(16,16,16),1)
    positions={(b.x,b.y,b.z) for b in result.blocks}
    assert (0,0,0) in positions and (15,0,0) in positions and (7,0,0) not in positions
    assert (7,15,0) in positions


def test_glass_window_collision_and_transparency_opt_out():
    data=plan();data['palette'].append(dict(id='glass',block='minecraft:glass',states={}))
    data['elements'].append({**element('window',(3,2,0),(4,3,0)),'hollow':False,'material':'glass','overlaps':['body'],'kind':'window'})
    result=compile_architecture(ArchitecturalPlan.model_validate(data),'glass',options(),50000,(16,16,16),1)
    assert any(b.block=='minecraft:glass' for b in result.blocks)
    with pytest.raises(ValueError,match='transparência'):
        compile_architecture(ArchitecturalPlan.model_validate(data),'glass',options(allow_transparent=False),50000,(16,16,16),1)


def test_refinement_accepts_improvement_and_rejects_regression(tmp_path,monkeypatch):
    seen=[]
    def assessment(n):
        result=score(n);result['issues']=['Corrigir o telhado'];return result
    e=plan()['elements'][1];e['end']['y']=13
    edits={'corrections':[dict(action='replace',target='roof',element=e)]}
    e2=copy.deepcopy(e);e2['end']['y']=14
    edits2={'corrections':[dict(action='replace',target='roof',element=e2)]}
    install_mock(monkeypatch,[study(),plan(),assessment(40),edits,assessment(70),edits2,assessment(60)],seen)
    result,info=AIGenerator(settings(tmp_path)).generate('refine',options(),[Image.new('RGB',(64,64),'gray')])
    assert info['refinementsAttempted']==2 and info['refinementsAccepted']==1
    assert [h['accepted'] for h in info['scoreHistory']]==[True,True,False]
    assert info['architecturalPlan']['elements'][1]['end']['y']==13
    assert len(seen)==7


def test_multiview_limits_rejected_before_inference(tmp_path):
    with TestClient(create_app(settings(tmp_path))) as c:
        files=[('references',(str(i)+'.png',image())) for i in range(5)]
        assert c.post('/api/generations',files=files).status_code==422
        assert c.post('/api/generations',files={'image':('x.png',b'notimage')}).status_code==422


def test_refine_endpoint_preserves_old_project(tmp_path,monkeypatch):
    seen=[];initial=score(70);initial['issues']=['Corrigir janela']
    install_mock(monkeypatch,[study(),plan(),score(),initial,{'corrections':[]}],seen)
    with TestClient(create_app(settings(tmp_path))) as c:
        r=c.post('/api/generations',data={'options':options().model_dump_json()},files={'image':('x.png',image())})
        job=wait_job(c,r.json()['id']);bid=job['buildId']
        old=c.get(f'/api/builds/{bid}/preview').json()
        r=c.post(f'/api/builds/{bid}/refine',json={'instruction':'Confira a janela'})
        assert r.status_code==202
        second=wait_job(c,r.json()['id']);assert second['status']=='ready',second
        assert second['buildId']!=bid and c.get(f'/api/builds/{bid}/preview').json()==old


def test_minute_quota_reset_and_shared_deadline(tmp_path,monkeypatch):
    response=httpx.Response(429,json={'error':{'details':[{'violations':[{'quotaId':'GenerateRequestsPerMinutePerProjectPerModel-FreeTier'}]}, {'retryDelay':'10s'}]}})
    p,seen=provider(tmp_path,[response])
    with pytest.raises(QuotaError) as exc: ask(p)
    assert 50 <= exc.value.until-time.time() <= 61
    with pytest.raises(GenerationError,match='Tempo total'):
        p.ask({},'',{},[],1000,'test',time.monotonic()-1)
    assert len(seen)==1


@pytest.mark.parametrize('name',['simple_house','modern_house','castle','asymmetric'])
def test_reference_fixture_schema_geometry_and_render(name):
    from app.config import ROOT
    from app.scene_plan import Camera
    from app.voxel_render import render_structure
    path=ROOT/'benchmarks/references/architectural'
    data=ArchitecturalPlan.model_validate_json((path/(name+'.json')).read_text())
    built=compile_architecture(data,name,options(),50000,(16,16,16),1)
    rendered,mask=render_structure(built,Camera(yaw=25,pitch=15))
    assert mask.any()
    import numpy as np
    with Image.open(path/(name+'.png')) as expected:
        assert np.array_equal(np.asarray(rendered),np.asarray(expected))


def test_configuration_errors_do_not_echo_secret():
    with pytest.raises(ValidationError) as exc:
        Settings(gemini_api_key=KEY,gemini_model='unknown',_env_file=None)
    assert KEY not in str(exc.value)


def test_job_admission_is_bounded(tmp_path):
    from threading import Event
    from app.database import BuildRepository
    from app.jobs import JobManager
    repository=BuildRepository(f'sqlite:///{tmp_path}/jobs.db');repository.initialize()
    manager=JobManager(repository);manager.initialize();release=Event()
    def work():
        release.wait(3)
        return {'id':'test','status':'pending'}
    try:
        for _ in range(4): manager.submit(work)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc: manager.submit(work)
        assert exc.value.status_code==429
    finally:
        release.set();manager.close();repository.engine.dispose()


def test_versioned_schema_matches_file():
    from app.config import ROOT
    assert json.loads((ROOT/'shared/architecture.schema.json').read_text())==architecture_schema()

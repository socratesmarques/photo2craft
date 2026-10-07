import copy
import json
from io import BytesIO
import subprocess
import time
import httpx
import numpy as np
import pytest
from PIL import Image, ImageDraw
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from app.ai_generator import AIGenerator, GenerationError
from app.config import Settings
from app.schemas import GenerateOptions, PALETTE, Structure
from app.scene_plan import Study, ScenePlan, Corrections, Component, Assessment, Camera, apply_corrections, compile_scene
from app.visual_analysis import preprocess
from app.visual_score import evaluate
from app.materials import match_material, VISUALS, lab
from app.voxel_render import render_structure
from app.images import decode_image
from app.depth import estimate_depth
from app.main import create_app


def study():
    return dict(subject='Torre',proportions=dict(width=1,height=2,depth=1),silhouette='Torre alta',landmarks=['Corpo alto vermelho'],symmetry='none',material_notes='Vermelho',assumptions=['Traseira inferida'],camera=dict(yaw=0,pitch=0))

def component(**kwargs):
    return dict(id='tower',label='Corpo',shape='box',start=dict(x=0,y=0,z=0),end=dict(x=5,y=7,z=5),axis='y',hollow=False,thickness=1,mirror='none',block='minecraft:red_concrete',color=[142,32,32],material='paint',role='wall',**kwargs)

def plan(): return dict(summary='Torre vermelha',size=dict(width=16,height=32,depth=16),components=[component()])
def assessment(value=40): return dict(silhouette=value,proportion=value,color=value,structure=value,detail=value,issues=['Aumentar a altura'])
def edit(height=12):
    c=component();c['end']['y']=height
    return dict(size=None,corrections=[dict(target='tower',action='replace',component=c)])

def generate(tmp_path,replies,**kwargs):
    calls=[]
    def handler(request):
        calls.append(json.loads(request.content))
        assert len(calls)<=len(replies),'Unbounded inference loop'
        result=replies[len(calls)-1]
        if isinstance(result,Exception): raise result
        return httpx.Response(200,json={'done':True,'message':{'content':result if isinstance(result,str) else json.dumps(result)}})
    generator=AIGenerator(Settings(data_dir=tmp_path,_env_file=None),httpx.MockTransport(handler))
    options=GenerateOptions(mode='ai',quality=kwargs.pop('quality','detailed'),size='small',**kwargs)
    # Uniform source deliberately triggers uncertain segmentation and model-only scores.
    output=generator.generate('visualtest',options,[Image.new('RGB',(64,64),'gray')])
    return output,calls


def test_accepts_improvement_then_rolls_back_regression(tmp_path):
    (structure,info),calls=generate(tmp_path,[study(),plan(),assessment(40),edit(12),assessment(75),edit(20),assessment(30)])
    assert max(c.y for c in structure.blocks)==12
    assert info['score']['total']==75
    assert [h['accepted'] for h in info['scoreHistory']]==[True,True,False]
    assert info['refinementsAttempted']==2 and info['refinementsAccepted']==1
    assert len(calls)==7
    assert len(calls[2]['messages'][1]['images'])==2
    assert len(calls[0]['messages'][1]['images'])==1
    assert all(c['options']['num_ctx']==16384 for c in calls)
    assert all('IMAGE > observed geometry' in c['messages'][0]['content'] for c in calls)
    assert info['timings']['total']>0

@pytest.mark.parametrize('failure',[httpx.ReadTimeout('timeout'),'{broken',{'corrections':[]},dict(size=None,corrections=[dict(target='missing',action='remove',component=None)])])
def test_refinement_failure_preserves_best(tmp_path,failure):
    (structure,info),_=generate(tmp_path,[study(),plan(),assessment(40),edit(12),assessment(70),failure])
    assert max(c.y for c in structure.blocks)==12 and info['score']['total']==70
    assert info['warnings']


def test_initial_comparison_failure_preserves_initial_structure(tmp_path):
    (structure,info),_=generate(tmp_path,[study(),plan(),httpx.ConnectError('offline')])
    assert structure.blocks and info['score'] is None
    assert info['refinementsAttempted']==0

@pytest.mark.parametrize('quality,limit',[('detailed',2),('ultra',3)])
def test_cycles_are_bounded(tmp_path,quality,limit):
    replies=[study(),plan(),assessment(10)]
    for i in range(limit): replies += [edit(10+i),assessment(20+i*10)]
    (_,info),calls=generate(tmp_path,replies,quality=quality,depth_estimation=False,max_refinements=3)
    assert info['refinementsAttempted']==limit
    assert len(calls)==3+limit*2


def test_zero_refinements_still_measures_initial(tmp_path):
    (_,info),calls=generate(tmp_path,[study(),plan(),assessment()],max_refinements=0)
    assert len(calls)==3 and info['refinementsAttempted']==0


def test_ultra_without_depth_model_continues(tmp_path):
    (_,info),_=generate(tmp_path,[study(),plan(),assessment(96)],quality='ultra')
    assert info['score']['total']==96 and info['depthUsed'] is False
    assert any('modelo local' in w for w in info['warnings'])


def test_invalid_plan_repaired_once(tmp_path):
    invalid=plan();invalid['components'][0]['end']['x']=100
    (structure,_),calls=generate(tmp_path,[study(),invalid,plan(),assessment(96)])
    assert structure.blocks and len(calls)==4
    with pytest.raises(GenerationError,match='reparo'):
        generate(tmp_path,[study(),invalid,invalid])


def test_invalid_study_never_falls_back(tmp_path):
    with pytest.raises(GenerationError,match='genérica'):
        generate(tmp_path,[{}])


def test_fenced_json_safe_repair(tmp_path):
    (_,info),_=generate(tmp_path,['```json\n'+json.dumps(study())+'\n```',plan(),assessment(96)])
    assert info['score']['total']==96

@pytest.mark.parametrize('change',[{'color':[True,0,0]},{'color':[0,0,300]},{'block':'minecraft:command_block'},{'id':'../escape'}])
def test_component_rejects_untrusted_fields(change):
    with pytest.raises(ValidationError): Component.model_validate({**component(),**change})


def test_transactional_edits_and_global_scaling():
    original=ScenePlan.model_validate(plan());before=original.model_dump()
    changed=apply_corrections(original,Corrections.model_validate(edit(12)))
    assert changed.components[0].end.y==12 and original.model_dump()==before
    scaled=apply_corrections(original,Corrections(size=dict(width=8,height=16,depth=8),corrections=[]))
    assert scaled.size.height==16 and scaled.components[0].end.y==3
    with pytest.raises(ValueError):
        apply_corrections(original,Corrections.model_validate(dict(size=None,corrections=[dict(target='unknown',action='remove',component=None)])))
    assert original.model_dump()==before


def test_palette_semantics_and_perceptual_distance():
    assert set(PALETTE)==set(VISUALS) and len(PALETTE)>150
    assert match_material([30,70,150],'glass','window').endswith(('glass','glass_pane'))
    assert VISUALS[match_material([160,130,80],'wood','wall')]['category']=='wood'
    assert VISUALS[match_material([255,255,255],'glass','window',False)]['category']!='glass'
    assert all(not VISUALS[match_material([n,n,n])]['gravity'] for n in (0,50,100,200,255))
    assert np.linalg.norm(lab((100,100,100))-lab((100,100,100)))==0


def test_preprocessing_simple_foreground_and_empty():
    image=Image.new('RGB',(200,160),'white');ImageDraw.Draw(image).rectangle((60,20,139,139),fill='red')
    evidence=preprocess(image)
    assert evidence.data['segmentationConfident']
    assert evidence.data['boundingBox']==dict(x=60,y=20,width=80,height=120)
    assert evidence.data['projectedAspectRatio']==pytest.approx(2/3,abs=.001)
    assert evidence.edges.max()>0 and evidence.data['horizontalSymmetry']==1
    assert not preprocess(Image.new('RGB',(100,100),'white')).data['segmentationConfident']
    assert preprocess(image,'scene').mask.all()
    assert max(preprocess(Image.new('RGB',(4000,3000))).image.size)<=768


def test_alpha_composited_and_pixel_limit():
    image=Image.new('RGBA',(20,20),(255,0,0,0));ImageDraw.Draw(image).rectangle((5,5,14,14),fill=(0,0,255,255))
    data=BytesIO();image.save(data,'PNG');raw=data.getvalue()
    decoded=decode_image(raw,1000)
    assert decoded.getpixel((0,0))==(255,255,255) and decoded.getpixel((10,10))==(0,0,255)
    with pytest.raises(HTTPException) as error: decode_image(raw,100)
    assert error.value.status_code==413


def test_render_geometry_and_score_recognize_improvement():
    options=GenerateOptions(mode='ai')
    original=ScenePlan.model_validate(plan());s=Study.model_validate(study())
    wrong=compile_scene(original,s,'wrong',options,50000,(32,32,32))
    improved_plan=apply_corrections(original,Corrections.model_validate(edit(12)))
    target=compile_scene(improved_plan,s,'target',options,50000,(32,32,32))
    image,mask=render_structure(target,s.camera)
    evidence=preprocess(image)
    wrong_image,wrong_mask=render_structure(wrong,s.camera)
    evaluation=Assessment.model_validate(assessment(60))
    good=evaluate(evidence,image,mask,evaluation);bad=evaluate(evidence,wrong_image,wrong_mask,evaluation)
    assert good['components']['silhouette']==100
    assert good['total']>bad['total']+5
    again,_=render_structure(target,s.camera)
    assert np.array_equal(np.asarray(image),np.asarray(again))
    assert render_structure(target,Camera(yaw=90,pitch=20))[1].sum()>0


def test_limits_reject_candidate():
    scene=ScenePlan.model_validate(plan());s=Study.model_validate(study())
    with pytest.raises(ValueError): compile_scene(scene,s,'limit',GenerateOptions(),4,(32,32,32))
    with pytest.raises(ValueError): compile_scene(scene,s,'limit',GenerateOptions(),50000,(8,8,8))

@pytest.mark.parametrize('failure',[subprocess.TimeoutExpired('depth',1),subprocess.CalledProcessError(1,'depth'),OSError('missing')])
def test_depth_failure_fallback(tmp_path,monkeypatch,failure):
    def fail(*args,**kwargs): raise failure
    monkeypatch.setattr('app.depth.subprocess.run',fail)
    depth,warning=estimate_depth(Image.new('RGB',(32,32)),Settings(depth_model_path=str(tmp_path),_env_file=None),1)
    assert depth is None and 'preservado' in warning


def test_visual_api_persists_and_old_fixture_imports(tmp_path,monkeypatch):
    replies=iter([study(),plan(),assessment(96)])
    monkeypatch.setattr(AIGenerator,'_request',lambda self,payload,timeout_seconds=None, **kwargs:{'done':True,'message':{'content':json.dumps(next(replies))}})
    image=BytesIO();Image.new('RGB',(64,64),'gray').save(image,'PNG')
    with TestClient(create_app(Settings(data_dir=tmp_path,_env_file=None))) as client:
        result=client.post('/api/generate',data={'options':json.dumps(dict(mode='ai',quality='detailed',size='small'))},files={'image':('ref.png',image.getvalue(),'image/png')})
        assert result.status_code==201,result.text
        build=result.json();assert build['generator']=='vision-refinement-v3'
        assert build['generationInfo']['renderAvailable']
        assert client.get(f"/api/builds/{build['id']}/render").headers['content-type']=='image/png'
        assert client.get(f"/api/builds/{build['id']}").json()['generationInfo']==build['generationInfo']
        from app.config import ROOT
        fixture=json.loads((ROOT/'shared/test-house.json').read_text())
        assert client.post('/api/builds',json=fixture).status_code==201
        assert not (tmp_path/'debug').exists()
        assert client.delete(f"/api/builds/{build['id']}").status_code==204
        assert client.get(f"/api/builds/{build['id']}/render").status_code==404


def test_visual_shared_deadline_keeps_initial_geometry(tmp_path,monkeypatch):
    clock=[0.0];replies=iter([study(),plan(),assessment()]);timeouts=[]
    monkeypatch.setattr('app.visual_generator.time.monotonic',lambda:clock[0])
    def fake(self,payload,timeout_seconds=None, **kwargs):
        timeouts.append(timeout_seconds);clock[0]+=4
        return {'done':True,'message':{'content':json.dumps(next(replies))}}
    monkeypatch.setattr(AIGenerator,'_request',fake)
    structure,info=AIGenerator(Settings(data_dir=tmp_path,ai_timeout_seconds=10,_env_file=None)).generate(
        'deadline',GenerateOptions(mode='ai',quality='detailed',size='small'),[Image.new('RGB',(32,32),'gray')])
    assert timeouts==[10,6,2]
    assert structure.blocks and info['score'] is None and info['warnings']


def test_bad_ollama_message_preserves_base(tmp_path,monkeypatch):
    replies=iter([{'done':True,'message':{'content':json.dumps(study())}},
                  {'done':True,'message':{'content':json.dumps(plan())}},
                  {'done':True,'message':None}])
    monkeypatch.setattr(AIGenerator,'_request',lambda *args,**kwargs:next(replies))
    structure,info=AIGenerator(Settings(data_dir=tmp_path,_env_file=None)).generate(
        'nullmessage',GenerateOptions(mode='ai',quality='detailed',size='small'),[Image.new('RGB',(32,32),'gray')])
    assert structure.blocks and info['score'] is None


def test_debug_saves_evidence_only_when_enabled(tmp_path,monkeypatch):
    replies=iter([study(),plan(),assessment(96)])
    monkeypatch.setattr(AIGenerator,'_request',lambda *args,**kwargs:{'done':True,'message':{'content':json.dumps(next(replies))}})
    _,info=AIGenerator(Settings(data_dir=tmp_path,visual_debug=True,_env_file=None)).generate(
        'debug',GenerateOptions(mode='ai',quality='detailed',size='small'),[Image.new('RGB',(32,32),'gray')])
    assert (tmp_path/'debug/debug/initial-plan.json').is_file()
    assert (tmp_path/'debug/debug/render-0.png').is_file()
    assert (tmp_path/'debug/debug/final-structure.json').is_file()
    assert (tmp_path/'debug/debug/scores.json').is_file()


def test_automatic_palette_avoids_stateful_partial_blocks():
    for material,role,rgb in [('wood','roof',[114,84,48]),('glass','window',[30,70,150])]:
        selected=match_material(rgb,material,role)
        assert not selected.endswith(('_stairs','_pane'))
        assert VISUALS[selected].get('automatic',True)


def test_grabcut_can_be_confident_only_for_isolated_subject():
    array=np.zeros((180,240,3),dtype=np.uint8)
    for y in range(180):
        array[y,:,0]=np.linspace(20,180,240,dtype=np.uint8)
        array[y,:,1]=80+y//3
        array[y,:,2]=120
    array[35:155,75:165]=[220,35,25]
    evidence=preprocess(Image.fromarray(array))
    assert evidence.data['segmentationMethod']=='grabcut_rectangle'
    assert evidence.data['segmentationConfident']
    assert evidence.data['segmentationQuality']['boundaryFraction']<.03

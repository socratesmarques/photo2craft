"""Controlled synthetic benchmark: hand-authored plans, NOT real Gemini inference.

References are created from known geometry. Compare reference-derived plans against
old generic procedural templates under the SAME camera and resource limits.
This tests engine capacity/metrics, not inference quality or photographic fidelity.
"""
import copy
import json
from pathlib import Path
import sys
import time
import tracemalloc
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps/api'))
from app.architecture import ArchitecturalPlan,compile_architecture
from app.schemas import GenerateOptions
from app.generator import ProceduralGenerator
from app.scene_plan import Camera
from app.voxel_render import render_structure
from app.visual_analysis import preprocess
from app.visual_score import normalized_mask
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'benchmarks/references/architectural'


def part(id,lo,hi,**changes):
    data=dict(id=id,kind='volume',shape='box',start=dict(zip('xyz',lo)),end=dict(zip('xyz',hi)),axis='y',
              hollow=False,thickness=1,operation='add',material='wall',overlaps=[],
              evidence=dict(kind='visible',confidence=1,references=[0],note='Referência sintética conhecida, não inferência.'))
    data.update(changes);return data


def fixtures():
    base=dict(schema_version='2.0',coordinate_system='x-east_y-up_z-south_blocks',orientation='north',
              structure_type='synthetic',summary='Referência sintética de geometria conhecida',size=dict(width=16,height=16,depth=16),
              palette=[dict(id='wall',block='minecraft:white_concrete',states={}),dict(id='roof',block='minecraft:red_concrete',states={})],relations=[])
    house=[part('body',(0,0,0),(15,7,15),hollow=True),part('roof',(0,8,0),(15,12,15),shape='gable',axis='z',material='roof',kind='roof')]
    modern=[part('base',(0,0,0),(15,0,15),kind='foundation'),part('left',(0,1,0),(5,10,15)),part('right',(6,1,7),(15,5,15)),part('canopy',(6,6,7),(15,6,15),material='roof')]
    castle=[part('base',(0,0,0),(15,0,15),kind='foundation'),part('wall_front',(4,1,2),(10,6,3)),
            part('tower_left',(0,1,0),(4,11,5),shape='cylinder',kind='tower'),part('tower_right',(11,1,0),(15,11,5),shape='cylinder',kind='tower'),
            part('spire_left',(0,12,0),(4,15,5),shape='pyramid',material='roof'),part('spire_right',(11,12,0),(15,15,5),shape='pyramid',material='roof')]
    asymmetric=[part('base',(0,0,0),(15,0,15),kind='foundation'),part('tall',(0,1,3),(5,14,9)),part('wing',(6,1,5),(15,4,13)),
                part('stairs',(6,1,1),(14,5,4),shape='stairs',axis='x',kind='stairs')]
    return {name:ArchitecturalPlan.model_validate({**copy.deepcopy(base),'structure_type':name,'elements':parts})
            for name,parts in [('simple_house',house),('modern_house',modern),('castle',castle),('asymmetric',asymmetric)]}


def main():
    DEST.mkdir(parents=True,exist_ok=True)
    camera=Camera(yaw=25,pitch=15)
    options=GenerateOptions(size='custom',width=16,height=16,depth=16,style='modern')
    results=[]
    for name,plan in fixtures().items():
        tracemalloc.start();started=time.monotonic()
        result=compile_architecture(plan,name,options,50000,(16,16,16),1)
        rendered,mask=render_structure(result,camera)
        seconds=time.monotonic()-started;_,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
        rendered.save(DEST/(name+'.png'))
        (DEST/(name+'.json')).write_text(plan.model_dump_json(indent=2))
        old_options=options.model_copy(update={'type':'castle' if name=='castle' else 'house'})
        old=ProceduralGenerator().generate('old',old_options,[])
        old_render,old_mask=render_structure(old,camera)
        target,_=normalized_mask(mask);a,_=normalized_mask(old_mask)
        iou=100*float(np.logical_and(target,a).sum()/np.logical_or(target,a).sum())
        results.append(dict(reference=name,source='hand-authored plan; no AI',blocksBefore=len(old.blocks),blocksAfter=len(result.blocks),
                            silhouetteIoU_genericTemplate=round(iou,2),silhouetteIoU_knownPlan=100,
                            geometryAndRenderSeconds=round(seconds,4),pythonPeakMiB=round(peak/1048576,3),
                            tokens=None,minecraftResult='not tested',camera=camera.model_dump()))
    destination=ROOT/'docs/architectural-synthetic-results.json'
    destination.write_text(json.dumps(results,indent=2)+'\n')
    print(destination)

if __name__=='__main__':main()

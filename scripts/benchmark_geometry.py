"""CPU and wire-size benchmarks, no model inference. Keeps the current limits."""
import json
from pathlib import Path
import sys
import time
import tracemalloc
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps/api'))
from app.blueprint import Blueprint, compile_blueprint
from app.schemas import GenerateOptions
from app.voxel_render import render_structure
from app.scene_plan import Camera


def main():
    results=[]
    for size in (32,48,64):
        data=dict(summary='Benchmark shell',assumptions=[],size=dict(width=size,height=size,depth=size),parts=[])
        # Six independent panels: sparse shell instead of a volume filled with air.
        for axis in range(3):
            for position in (0,size-1):
                start=[0]*3;end=[size-1]*3;start[axis]=end[axis]=position
                data['parts'].append(dict(shape='box',start=dict(zip('xyz',start)),end=dict(zip('xyz',end)),block='minecraft:stone_bricks',axis='y',hollow=False,thickness=1))
        tracemalloc.start();start=time.monotonic()
        structure=compile_blueprint(Blueprint.model_validate(data),'benchmark',GenerateOptions(),50000,(64,64,64))
        geometry=time.monotonic()-start;start=time.monotonic()
        render_structure(structure,Camera(yaw=35,pitch=20))
        render=time.monotonic()-start;_,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
        results.append(dict(size=size,blocks=len(structure.blocks),jsonBytes=len(structure.model_dump_json().encode()),geometrySeconds=round(geometry,3),renderSeconds=round(render,3),pythonPeakMiB=round(peak/1048576,2)))
    print(json.dumps(results,indent=2))

if __name__=='__main__':main()

"""Headless deterministic orthographic surface renderer. No GPU or browser needed.
Colors are approximate; panes/stairs use cube envelopes, as in the old preview.
"""
import math
import cv2
import numpy as np
from PIL import Image
from .materials import VISUALS


def render_structure(structure,camera,resolution=384):
    if not 64<=resolution<=768: raise ValueError('Resolução fora do limite')
    yaw,pitch=math.radians(camera.yaw),math.radians(camera.pitch)
    eye=np.array([math.sin(yaw)*math.cos(pitch),math.sin(pitch),-math.cos(yaw)*math.cos(pitch)])
    right=np.array([math.cos(yaw),0,math.sin(yaw)])
    up=np.cross(right,eye)
    projection=np.stack([right,-up,eye])
    dims=np.array(list(structure.size.model_dump().values()),dtype=float)
    center=(dims-1)/2
    corners=np.array([[x,y,z] for x in (-.5,dims[0]-.5) for y in (-.5,dims[1]-.5) for z in (-.5,dims[2]-.5)])
    projected=(corners-center)@projection.T
    span=np.ptp(projected[:,:2],axis=0)
    scale=(resolution-32)/max(float(span.max()),1)
    offset=np.array([resolution/2,resolution/2])
    cells={(b.x,b.y,b.z):b.block for b in structure.blocks if b.block!='minecraft:air'}
    faces=[]
    for axis in range(3):
        sign=1 if eye[axis]>0 else -1
        if abs(eye[axis])<1e-6: continue
        normal=np.zeros(3); normal[axis]=sign
        other=[a for a in range(3) if a!=axis]
        template=[]
        for u,v in [(-.5,-.5),(.5,-.5),(.5,.5),(-.5,.5)]:
            vertex=normal*.5;vertex[other[0]]=u;vertex[other[1]]=v;template.append(vertex)
        template=np.array(template)
        for position,block in cells.items():
            neighbor=list(position);neighbor[axis]+=sign
            if tuple(neighbor) in cells: continue
            vertices=(template+position-center)@projection.T
            xy=np.rint(vertices[:,:2]*scale+offset).astype(np.int32)
            rgb=np.array(VISUALS[block]['rgb'],dtype=float)
            # Modest fixed face shading preserves color better than photorealistic lighting.
            factor=1 if axis==1 else .93 if axis==2 else .86
            color=tuple(int(c) for c in np.clip(rgb*factor,0,255))
            faces.append((float(vertices[:,2].mean()),xy,color))
    canvas=np.full((resolution,resolution,3),245,np.uint8)
    mask=np.zeros((resolution,resolution),np.uint8)
    for _,xy,color in sorted(faces,key=lambda face:face[0]):
        cv2.fillConvexPoly(canvas,xy,color,lineType=cv2.LINE_8)
        cv2.fillConvexPoly(mask,xy,1)
    return Image.fromarray(canvas),mask

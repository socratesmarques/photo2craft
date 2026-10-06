"""Approximate evaluation; fixed camera and same scoring rule across candidates."""
import math
import cv2
import numpy as np
from .materials import lab


def normalized_mask(mask):
    y,x=np.where(mask)
    if not len(x): raise ValueError('Render sem silhueta')
    crop=mask[y.min():y.max()+1,x.min():x.max()+1]
    h,w=crop.shape
    scale=112/max(h,w)
    resized=cv2.resize(crop,(max(1,round(w*scale)),max(1,round(h*scale))),interpolation=cv2.INTER_NEAREST)
    result=np.zeros((128,128),np.uint8)
    y0=(128-resized.shape[0])//2;x0=(128-resized.shape[1])//2
    result[y0:y0+resized.shape[0],x0:x0+resized.shape[1]]=resized
    return result,w/h


def evaluate(evidence,render,mask,assessment):
    scores=assessment.model_dump(exclude={'issues'})
    source='vision_model_estimate'
    if evidence.data['segmentationConfident']:
        a,ratio_a=normalized_mask(evidence.mask)
        b,ratio_b=normalized_mask(mask)
        scores['silhouette']=100*float(np.logical_and(a,b).sum()/max(1,np.logical_or(a,b).sum()))
        scores['proportion']=100*math.exp(-abs(math.log(ratio_a/ratio_b)))
        # Compare distributions via nearest palette bins, not only mean color.
        pixels=np.asarray(render)[mask.astype(bool)]
        unique,counts=np.unique((pixels//32)*32+16,axis=0,return_counts=True)
        order=np.argsort(-counts)[:8]
        references=evidence.data['dominantColors']
        def nearest(rgb,candidates): return min(float(np.linalg.norm(lab(tuple(rgb))-lab(tuple(c)))) for c in candidates)
        render_colors=[unique[i] for i in order]
        reference_colors=[r['rgb'] for r in references]
        ref_error=sum(r['fraction']*nearest(r['rgb'],render_colors) for r in references)/max(.001,sum(r['fraction'] for r in references))
        render_error=sum(float(counts[i])*nearest(unique[i],reference_colors) for i in order)/max(1,sum(counts[i] for i in order))
        scores['color']=100*math.exp(-(ref_error+render_error)/60)
        source='foreground_heuristics_and_vision_model'
    weights={'silhouette':.35,'proportion':.30,'structure':.20,'color':.10,'detail':.05}
    return {'total':round(sum(weights[k]*scores[k] for k in weights),2),
            'components':{k:round(v,2) for k,v in scores.items()},'source':source,
            'label':'Estimativa heurística, não porcentagem científica de semelhança'}


def improves_geometry(previous, candidate):
    """Color/detail gains must not hide a loss of silhouette, proportions or parts."""
    before, after = previous['components'], candidate['components']
    if any(after[key] < before[key] - 2 for key in ('silhouette', 'proportion', 'structure')):
        return False
    geometry = lambda scores: .4*scores['silhouette'] + .35*scores['proportion'] + .25*scores['structure']
    return geometry(after) >= geometry(before) - .25 and candidate['total'] > previous['total'] + .25

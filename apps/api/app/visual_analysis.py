"""Bounded, non-semantic foreground heuristics. Never present these as object recognition."""
from dataclasses import dataclass
import cv2
import numpy as np
from PIL import Image

@dataclass
class VisualEvidence:
    image: Image.Image
    mask: np.ndarray
    edges: np.ndarray
    data: dict


def preprocess(original, scope='object'):
    image = original.copy()
    image.thumbnail((768, 768))
    array = np.array(image.convert('RGB'))
    h, w = array.shape[:2]
    gray = cv2.cvtColor(array, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 70, 150)
    border = np.concatenate((array[0], array[-1], array[:, 0], array[:, -1]))
    background = np.median(border, axis=0)
    distance = np.linalg.norm(array.astype(np.float32) - background, axis=2)
    mask = (distance > 35).astype(np.uint8)
    method = 'border_color'
    if scope == 'scene':
        mask[:] = 1
        method = 'full_scene'
    elif min(w, h) >= 20 and np.mean(np.linalg.norm(border-background, axis=1)) > 22:
        # Rectangle seed is only an approximation, confidence remains conservative.
        labels = np.zeros((h,w),np.uint8)
        try:
            cv2.setRNGSeed(0)
            cv2.grabCut(array, labels, (max(1,w//20),max(1,h//20),w-2*max(1,w//20),h-2*max(1,h//20)),
                        np.zeros((1,65)),np.zeros((1,65)),2,cv2.GC_INIT_WITH_RECT)
            mask = np.isin(labels,[cv2.GC_FGD,cv2.GC_PR_FGD]).astype(np.uint8)
            method = 'grabcut_rectangle'
        except cv2.error:
            pass
    occupancy = float(mask.mean())
    # Confidence is deliberately conservative. GrabCut may be useful on photos,
    # but only when one connected subject dominates and barely touches the frame.
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    areas = stats[1:, cv2.CC_STAT_AREA] if count > 1 else np.array([], dtype=int)
    largest_fraction = float(areas.max() / max(1, mask.sum())) if len(areas) else 0.0
    boundary = np.concatenate((mask[0], mask[-1], mask[:, 0], mask[:, -1]))
    boundary_fraction = float(boundary.mean())
    border_dispersion = float(np.mean(np.linalg.norm(border-background,axis=1)))
    confident = scope == 'object' and .02 < occupancy < .92 and (
        (method == 'border_color' and border_dispersion < 16 and largest_fraction > .5)
        or (method == 'grabcut_rectangle' and occupancy < .88
            and largest_fraction > .6 and boundary_fraction < .03)
    )
    if occupancy < .005 or occupancy > .98:
        mask[:] = 1
        confident = False
        method = 'uncertain_full_frame'
    ys,xs = np.where(mask)
    x0,x1,y0,y1=int(xs.min()),int(xs.max()+1),int(ys.min()),int(ys.max()+1)
    cropped = mask[y0:y1,x0:x1]
    pixels = array[mask.astype(bool)]
    # Quantized histogram has deterministic order and bounded memory, no random clustering.
    quantized = (pixels // 32).astype(np.int32)
    codes = quantized[:, 0] * 64 + quantized[:, 1] * 8 + quantized[:, 2]
    counts = np.bincount(codes, minlength=512)
    indices = np.arange(512)
    unique = np.stack((indices // 64, (indices // 8) % 8, indices % 8), axis=1) * 32 + 16
    order = np.argsort(-counts, kind='stable')[:6]
    order = order[counts[order] > 0]
    lines = cv2.HoughLinesP(edges,1,np.pi/180,threshold=40,minLineLength=max(10,min(w,h)//5),maxLineGap=8)
    line_data=[] if lines is None else [[int(n) for n in line[0]] for line in lines[:12]]
    return VisualEvidence(image,mask,edges,{
        'originalResolution':list(original.size),'processedResolution':[w,h],
        'boundingBox':{'x':x0,'y':y0,'width':x1-x0,'height':y1-y0},
        'projectedAspectRatio':round((x1-x0)/(y1-y0),4), 'occupancy':round(float(mask.mean()),4),
        'center':[round(float(xs.mean())/w,4),round(float(ys.mean())/h,4)],
        'horizontalSymmetry':round(float((cropped==cropped[:,::-1]).mean()),4),
        'dominantColors':[{'rgb':unique[i].tolist(),'fraction':round(float(counts[i]/len(pixels)),4)} for i in order],
        'brightFraction':round(float((gray[mask.astype(bool)]>200).mean()),4),
        'darkFraction':round(float((gray[mask.astype(bool)]<60).mean()),4),
        'dominantLines':line_data,'segmentationMethod':method,'segmentationConfident':confident,
        'segmentationQuality':{'largestComponentFraction':round(largest_fraction,4),
                               'boundaryFraction':round(boundary_fraction,4)},
        'perspective':'not calibrated; projected ratio is NOT the real 3D width/height',
    })

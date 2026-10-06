"""One shared visual catalog for deterministic Lab matching and both renderers."""
import json
from functools import lru_cache
import cv2
import numpy as np
from .config import ROOT

VISUALS = json.loads((ROOT / 'shared/block-visuals.json').read_text())

@lru_cache(maxsize=4096)
def lab(rgb):
    return cv2.cvtColor(np.array([[rgb]], dtype=np.float32) / 255, cv2.COLOR_RGB2LAB)[0, 0]


def match_material(rgb, material='paint', role='wall', allow_transparent=True):
    candidates = [(key, value) for key, value in VISUALS.items()
                  if value['category'] == material and role in value['roles']
                  and value.get('automatic', True) and not value['gravity']
                  and (allow_transparent or not value['transparent'])]
    if not candidates:
        candidates = [(key, value) for key, value in VISUALS.items()
                      if value['category'] in ('paint', 'stone')
                      and value.get('automatic', True) and not value['gravity']]
    target = lab(tuple(rgb))
    # CIE76 Delta E plus a small texture penalty. Semantic filtering comes first.
    return min(candidates, key=lambda item: (float(np.linalg.norm(target - lab(tuple(item[1]['rgb']))))
                                           + item[1]['texture'] * 4, item[0]))[0]

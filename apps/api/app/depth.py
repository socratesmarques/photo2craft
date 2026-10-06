"""Optional offline CPU worker, isolated with a hard timeout and no persistent model."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import numpy as np
from PIL import Image


def estimate_depth(image,settings,timeout):
    if not settings.depth_model_path:
        return None,'Profundidade opcional indisponível: modelo local não configurado.'
    try:
        with tempfile.TemporaryDirectory(prefix='photo2craft-depth-') as temp:
            source=Path(temp)/'input.png'; output=Path(temp)/'depth.npy'
            small=image.copy();small.thumbnail((518,518));small.save(source)
            env={**os.environ,'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','OMP_NUM_THREADS':'2','PYTHONPATH':str(Path(__file__).resolve().parents[1])}
            subprocess.run([sys.executable,'-m','app.depth_worker',str(source),str(output),str(settings.depth_model_path)],
                           check=True,timeout=max(1,min(timeout,settings.depth_timeout_seconds)),
                           stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=env)
            depth=np.load(output,allow_pickle=False)
            if depth.ndim!=2 or not np.isfinite(depth).all() or depth.size>518*518:
                raise ValueError('Invalid depth map')
            low,high=np.percentile(depth,[2,98])
            if high-low<1e-6: raise ValueError('Flat depth map')
            depth=np.clip((depth-low)/(high-low),0,1)
            grid=np.asarray(Image.fromarray(depth).resize((8,8)))
            return {'map':depth,'summary':{'model':'Depth-Anything-V2-Small-hf','relativeInverseDepth8x8':grid.round(3).tolist(),
                                         'meaning':'larger is nearer; relative only, NOT meters or hidden surfaces'}},None
    except (OSError,ValueError,subprocess.SubprocessError):
        return None,'A estimativa de profundidade falhou ou excedeu o tempo; o planejamento visual foi preservado.'

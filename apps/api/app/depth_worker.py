"""Executed only by the optional isolated depth provider."""
import sys
import numpy as np
from PIL import Image

def main():
    import torch
    from transformers import AutoImageProcessor, AutoModelForDepthEstimation
    source,output,model_path=sys.argv[1:]
    torch.set_num_threads(2)
    processor=AutoImageProcessor.from_pretrained(model_path,local_files_only=True,trust_remote_code=False)
    model=AutoModelForDepthEstimation.from_pretrained(model_path,local_files_only=True,trust_remote_code=False,use_safetensors=True).eval()
    image=Image.open(source).convert('RGB')
    with torch.inference_mode():
        prediction=model(**processor(images=image,return_tensors='pt')).predicted_depth
        depth=torch.nn.functional.interpolate(prediction.unsqueeze(1),size=(image.height,image.width),mode='bicubic',align_corners=False)
    np.save(output,depth.squeeze().cpu().numpy(),allow_pickle=False)

if __name__=='__main__': main()

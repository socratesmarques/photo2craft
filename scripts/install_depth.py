"""Optional, explicit model installation. Never run automatically during generation."""
import argparse
from pathlib import Path

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--directory',type=Path,default=Path('models/depth-anything-v2-small'))
    args=parser.parse_args()
    from huggingface_hub import snapshot_download
    snapshot_download('depth-anything/Depth-Anything-V2-Small-hf',local_dir=str(args.directory),
                      allow_patterns=['*.json','*.safetensors'])
    print('DEPTH_MODEL_PATH='+str(args.directory.resolve()))
    print('Restart the API after setting this value. Inference will use CPU and local files only.')

if __name__=='__main__':main()

"""Repeatable local benchmark through the actual API; no fabricated model scores."""
import argparse
import hashlib
import html
import json
import mimetypes
from pathlib import Path
import time
import httpx


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--references',type=Path,default=Path('benchmarks/references'))
    parser.add_argument('--output',type=Path,default=Path('benchmark-results'))
    parser.add_argument('--url',default='http://127.0.0.1:8000')
    parser.add_argument('--quality',choices=['quick','detailed','ultra'],default='detailed')
    parser.add_argument('--refinements',type=int,choices=range(4),default=None)
    parser.add_argument('--size',choices=['small','medium','large'],default='medium')
    parser.add_argument('--keep-projects',action='store_true')
    args=parser.parse_args()
    paths=sorted(p for p in args.references.iterdir() if p.suffix.lower() in {'.png','.jpg','.jpeg','.webp'})
    if not paths: parser.error('Adicione suas imagens em '+str(args.references))
    output=args.output/time.strftime('%Y%m%d-%H%M%S');output.mkdir(parents=True,exist_ok=False)
    results=[];cards=[]
    with httpx.Client(base_url=args.url,timeout=920) as client:
        response=client.get('/api/capabilities');response.raise_for_status();cap=response.json()
        for i,path in enumerate(paths):
            start=time.monotonic();project_id=None
            raw=path.read_bytes();options=dict(name=path.stem[:100],mode='ai',quality=args.quality,size=args.size,max_refinements=args.refinements)
            entry=dict(reference=path.name,sha256=hashlib.sha256(raw).hexdigest(),version=cap.get('version'),model=cap.get('aiModel'),options=options)
            folder=output/str(i);folder.mkdir();reference='reference'+path.suffix.lower();(folder/reference).write_bytes(raw)
            try:
                response=client.post('/api/generate',data={'options':json.dumps(options)},files={'image':(path.name,raw,mimetypes.guess_type(path.name)[0] or 'application/octet-stream')})
                response.raise_for_status();build=response.json();project_id=build['id']
                entry.update(dimensions=build['size'],blocks=build['blockCount'],generation=build['generationInfo'])
                response=client.get('/api/builds/'+project_id+'/preview')
                if response.status_code == 404:  # Original backend predates approval/preview.
                    response=client.get('/api/builds/'+project_id+'/structure')
                response.raise_for_status();(folder/'structure.json').write_text(json.dumps(response.json()))
                if build['generationInfo'].get('renderAvailable'):
                    response=client.get('/api/builds/'+project_id+'/render');response.raise_for_status();(folder/'render.png').write_bytes(response.content)
                cards.append(f'<article><h2>{html.escape(path.name)}</h2><img src="{i}/{html.escape(reference,quote=True)}"><img src="{i}/render.png"><pre>{html.escape(json.dumps(entry,ensure_ascii=False,indent=2))}</pre></article>')
            except (httpx.HTTPError,ValueError,KeyError) as exc:
                entry['error']=str(exc);cards.append(f'<article><h2>{html.escape(path.name)}</h2><p>Falha: {html.escape(str(exc))}</p></article>')
            finally:
                entry['wallSeconds']=round(time.monotonic()-start,3);results.append(entry)
                (output/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
                if project_id and not args.keep_projects:
                    cleanup=client.delete('/api/builds/'+project_id)
                    if not cleanup.is_success: print('Não foi possível excluir projeto temporário',project_id)
    (output/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Photo2Craft benchmark</title><style>body{font-family:system-ui;background:#152920;color:#eef;padding:24px}article{margin:32px 0}img{width:40%;max-height:400px;object-fit:contain;background:#fff}pre{white-space:pre-wrap}</style><h1>Referência × construção</h1><p>Compare visualmente as mesmas referências entre versões. Scores são estimativas, não prova de fidelidade.</p>'+''.join(cards))
    print(output.resolve())

if __name__=='__main__':main()

"""Create, validate, fetch and delete a temporary project via the running API."""
import argparse
import json
import time
from pathlib import Path
import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://localhost:8000')
    parser.add_argument('--image', type=Path)
    parser.add_argument('--description', default='')
    parser.add_argument('--mode', choices=['procedural', 'ai'], default='procedural')
    parser.add_argument('--quality', choices=['quick', 'detailed', 'ultra'], default='detailed')
    parser.add_argument('--size', choices=['small', 'medium', 'large'], default='medium')
    parser.add_argument('--timeout', type=float, default=960)
    args = parser.parse_args()
    if not args.image and (args.mode == 'procedural' or not args.description.strip()):
        parser.error('Envie --image ou use --mode ai --description "...".')
    options = dict(name='Smoke test temporário', mode=args.mode, quality=args.quality,
                   size=args.size, description=args.description,
                   type='automatic' if args.mode == 'ai' else 'house')
    files = {'image': (args.image.name, args.image.read_bytes())} if args.image else None
    with httpx.Client(base_url=args.url, timeout=30) as client:
        deadline = time.monotonic() + args.timeout
        response = client.post('/api/generation-jobs', files=files, data={'options': json.dumps(options)})
        response.raise_for_status()
        job_id = response.json()['id']
        print(f'Geração recebida: {job_id}', flush=True)
        previous_stage = None
        while True:
            response = client.get(f'/api/generation-jobs/{job_id}')
            response.raise_for_status()
            job = response.json()
            if job['stage'] != previous_stage:
                print(f"{job['elapsedSeconds']}s: {job['stage']}", flush=True)
                previous_stage = job['stage']
            if job['status'] == 'failed':
                raise RuntimeError(f"Geração falhou (HTTP {job['errorCode']}): {job['error']}")
            if job['status'] == 'succeeded':
                build_id = job['buildId']
                break
            if time.monotonic() >= deadline:
                raise TimeoutError(f'Acompanhamento expirou; o job {job_id} pode continuar. Consulte /api/generation-jobs/{job_id}.')
            time.sleep(1)
        try:
            response = client.get(f'/api/builds/{build_id}')
            response.raise_for_status()
            project = response.json()
            response = client.get(f'/api/builds/{build_id}/structure')
            response.raise_for_status()
            structure = response.json()
            assert structure['id'] == build_id and structure['blocks']
            size = structure['size']
            positions = [(b['x'], b['y'], b['z']) for b in structure['blocks']]
            assert len(positions) == len(set(positions))
            assert all(0 <= x < size['width'] and 0 <= y < size['height'] and 0 <= z < size['depth']
                       for x, y, z in positions)
            print(json.dumps({'id': build_id, 'blocks': len(positions),
                              'generationInfo': project.get('generationInfo')}, ensure_ascii=False, indent=2))
        finally:
            client.delete(f'/api/builds/{build_id}').raise_for_status()
            print('Projeto temporário excluído.')


if __name__ == '__main__':
    main()

"""Package sources without local data, secrets, dependencies or build output."""
from pathlib import Path
import argparse
import json
import zipfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    excluded = {
        "node_modules", "dist", "data", ".gradle", "build", "run",
        "__pycache__", ".pytest_cache", ".e2e-data", "test-results",
        "playwright-report", ".git", ".venv", "models", "benchmark-results",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root)
            if (not path.is_file() or path.is_symlink() or path == output
                    or any(part in excluded for part in relative.parts)
                    or (path.name.startswith(".env") and path.name != ".env.example")
                    or path.suffix in {".pyc", ".tsbuildinfo", ".log"}):
                continue
            archive.write(path, Path("photo2craft") / relative)
        count = len(archive.namelist())
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        assert "photo2craft/ATUALIZAR-IA.md" in archive.namelist()
        assert "photo2craft/ATUALIZAR-OLLAMA.ps1" in archive.namelist()
        assert "photo2craft/.env" not in archive.namelist()
        for name in ['apps/api/app/release.py', 'apps/web/src/App.tsx', 'RELEASE.txt']:
            assert 'architectural-2.0' in archive.read('photo2craft/' + name).decode('utf-8'), name
        backend = archive.read('photo2craft/apps/api/app/ai_generator.py').decode('utf-8')
        assert '/api/chat' in backend and 'api.openai.com' not in backend
        assert 'photo2craft/apps/api/app/detailed_generator.py' in archive.namelist()
        package = json.loads(archive.read('photo2craft/apps/web/package.json'))
        lock = json.loads(archive.read('photo2craft/apps/web/package-lock.json'))
        assert lock['version'] == lock['packages']['']['version'] == package['version']
        assert lock['packages']['node_modules/@jridgewell/gen-mapping']['version'] == '0.3.13'
        assert 'mod_version=0.3.0' in archive.read('photo2craft/minecraft/mod/gradle.properties').decode()
        palette = json.loads(archive.read('photo2craft/shared/block-palette.json'))
        assert 'minecraft:blue_concrete' in palette and 'minecraft:red_concrete' in palette
    print(f"{output}: {count} files, {output.stat().st_size} bytes; ZIP verified")


if __name__ == "__main__":
    main()

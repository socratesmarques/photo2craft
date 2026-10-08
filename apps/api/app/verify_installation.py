"""Read-only checks executed inside the installed API container."""
import sys
import httpx
from .config import Settings
from .release import RELEASE


def verify(client, settings):
    response = client.get("http://127.0.0.1:8000/api/capabilities")
    response.raise_for_status()
    cap = response.json()
    if cap.get("release") != RELEASE:
        raise ValueError("A API em execucao nao corresponde a esta versao Photo2Craft.")
    print(f"API confirmada: {RELEASE}")
    if settings.ai_provider == 'gemini':
        if not cap.get('aiConfigured'):
            raise ValueError('Configure GEMINI_API_KEY e confirme o projeto Free Tier sem faturamento.')
        print('Gemini configurado. Chave/cota/fidelidade reais ainda exigem uma geração de teste.')
        return
    if settings.ai_provider == 'disabled':
        print('Modo demo; inferência desativada.')
        return
    response = client.get(settings.ollama_url.rstrip("/") + "/api/tags")
    response.raise_for_status()
    models = response.json().get("models", [])
    if not any(isinstance(item, dict) and settings.ollama_model in (item.get("name"), item.get("model")) for item in models):
        raise ValueError(f"Ollama conectado, mas falta o modelo. Execute: ollama pull {settings.ollama_model}")
    print(f"Ollama conectado. Modelo instalado: {settings.ollama_model}. Nenhuma geracao executada.")


def main():
    try:
        with httpx.Client(timeout=10, trust_env=False, follow_redirects=False) as client:
            verify(client, Settings())
    except (httpx.HTTPError, ValueError, TypeError, AttributeError) as exc:
        if isinstance(exc, httpx.HTTPError):
            print("Falha ao acessar API/provedor configurado. Confira endereço, rede e os logs do container.", file=sys.stderr)
        else:
            print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

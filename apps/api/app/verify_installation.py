"""Read-only checks executed inside the installed API container."""
import sys
import httpx
from .config import Settings
from .release import RELEASE


def verify(client, settings):
    response = client.get("http://127.0.0.1:8000/api/capabilities")
    response.raise_for_status()
    cap = response.json()
    if cap.get("release") != RELEASE or cap.get("aiProvider") != "ollama":
        raise ValueError("A API em execucao nao corresponde a esta versao Ollama.")
    if not cap.get("generationJobs"):
        raise ValueError("A API ainda nao suporta geracao em segundo plano. Reconstrua api e web juntos.")
    print(f"API confirmada: {RELEASE}")
    print(f"Contexto: {settings.ai_context_tokens}; teto de saida: {settings.ai_max_output_tokens}; prazo: {settings.ai_timeout_seconds}s")
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
            print("Falha ao acessar API/Ollama. Abra o Ollama, confira OLLAMA_HOST=0.0.0.0:11434 e reinicie o Ollama.", file=sys.stderr)
        else:
            print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

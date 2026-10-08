# Migrar a instalação para Photo2Craft 2.0

Preserve `.env`, volume photo2craft-data, mundos, configuração do mod e nome do
projeto Docker. Não use `docker compose down -v`. Faça backup antes da atualização.

```bash
git fetch origin
git switch feat/photo2craft-2-architectural
```

O PR ainda depende de aceitação real; consulte docs/photo2craft-2-validation.md.
Não é necessário sobrescrever todo o `.env`. Substitua/adicione estas entradas:

```dotenv
AI_PROVIDER=gemini
GEMINI_API_KEY=sua_chave_do_projeto_free_tier
GEMINI_MODEL=gemini-3.8-flash
GEMINI_FREE_TIER_CONFIRMED=true
FALLBACK_PROVIDER=none
GENERATION_MODE=architectural
ENABLE_VISUAL_REFINEMENT=true
MAX_REFINEMENT_PASSES=2
ENABLE_GENERATION_CACHE=true
AI_DAILY_CALL_LIMIT=20
```

Confirme primeiro que o projeto Google AI Studio está no Free Tier sem billing/cartão.
Não coloque a chave no frontend. Detalhes: docs/gemini-free-tier.md.
Preserve portas, DATA_DIR, DATABASE_URL, limites e demais configurações necessárias.

```bash
docker compose up -d --build
docker compose exec -T api python -m app.verify_installation
```

A verificação não faz inferência. No site, confira `architectural-2.0` e Gemini em
/api/capabilities. Envie uma imagem clara, acompanhe as etapas, examine a prévia,
altere materiais se necessário e aprove. Depois use o comando mostrado no jogo.
A mesma versão do mod 0.3.0/Minecraft1.21.1/Fabric/Java21 permanece compatível.
Se você já tem o JAR 0.3.0 funcional, esta migração não exige novo JAR.

Windows: ATUALIZAR-OLLAMA.ps1 é mantido como nome de entrada por compatibilidade.
Preserva valores existentes, portanto não migra um AI_PROVIDER=ollama sozinho:
edite as entradas acima primeiro. Pode ser executado sem Ollama quando usa Gemini.
Sem Docker, reinstale requirements.txt (inclui tzdata), compile web e reinicie API/site.

Para voltar ao pipeline local anterior, explicitamente:

```dotenv
AI_PROVIDER=ollama
GENERATION_MODE=legacy
OLLAMA_URL=http://host.docker.internal:11434
OLLAMA_MODEL=qwen3-vl:8b
```

GENERATION_MODE=architectural com Ollama também é suportado, mas pode exigir mais
contexto. Fallback local opcional é desligado por padrão. Não há fallback para nuvem paga.

# Validação — 0.5.0 Visual Refinement

## Executado nesta entrega

- **144 testes Python aprovados** (API, modo demo, gerador textual anterior, plano, geometria, limites,
  paleta/semântica/Lab, correções transacionais, ciclos limitados, rollback da melhor estrutura,
  JSON inválido, timeout, falha do Ollama, falha do worker depth, transparência, imagem grande,
  segmentação incerta, render determinístico, score, persistência, projetos antigos e debug).
- **Build TypeScript/Vite aprovado**. Aviso de tamanho do chunk Three.js permanece, sem erro de compilação.
- ZIP de fontes validado pelo script de empacotamento, sem dados/configurações/modelos/dependências locais.
- Benchmark de geometria/render CPU executado. Valores abaixo incluem overhead de `tracemalloc`:

| Eixo máximo | Células | JSON bytes | Geometria | Render | Pico Python rastreado |
| --- | ---: | ---: | ---: | ---: | ---: |
| 32 | 5.768 | 386.069 | 0,186 s | 0,844 s | 6,21 MiB |
| 48 | 13.256 | 889.685 | 0,359 s | 1,891 s | 13,27 MiB |
| 64 | 23.816 | 1.600.661 | 0,665 s | 3,292 s | 23,44 MiB |

Caso: casca de seis painéis, sem Ollama. Pico Python não inclui toda memória nativa/VRAM nem é medição de RSS.
Esses tempos não estimam o tempo do Gemma em seu computador. Não foram habilitadas dimensões 96/128.
O teste de score mostra que uma correção geométrica controlada melhora a silhueta de referência sintética;
isso **não comprova** melhor fidelidade em fotografias arbitrárias.

## Bloqueios de ambiente / pendências

- **E2E Chromium:** tentativa feita; navegador foi bloqueado na inicialização de sockets (`Operation not permitted`).
  Nenhum fluxo E2E desta entrega é declarado aprovado. Testes existentes foram adaptados e há novo teste
  de comparação/sobreposição/câmeras. Execute no PC com navegador permitido.
- **Mod Fabric:** tentou-se `gradlew test build`, inclusive com JDK 21 disponível; download do Gradle
  foi bloqueado por conectividade do processo Java (`Network is unreachable`). JAR final não compilado aqui.
  Novo teste Java percorre toda a allowlist e mantém fixture antiga. A colocação no jogo precisa de teste real.
- **Docker:** CLI/daemon indisponíveis. Dockerfiles/Compose foram revisados, incluindo o caminho do catálogo
  compartilhado e a instalação opcional de depth, mas não houve `docker compose build/up` real aqui.
- **Ollama/Gemma e Depth Anything reais:** ausentes. Testes automáticos usam mocks; depth tem testes de fallback.
  Não há alegação de score ou melhoria de fotografias produzidos pelo modelo real.

## Repetir testes

Na venv, da raiz:

```bash
pip install -r apps/api/requirements-dev.txt
PYTHONPATH=apps/api pytest -q apps/api/tests
python scripts/benchmark_geometry.py
```

Windows: `cd apps/api; python -m pytest -q` (o `pytest.ini` configura o caminho).
Frontend: `cd apps/web; npm ci; npm run build`.
E2E, com Python da venv no PATH: `npx playwright install chromium; npm run test:e2e`.
Mod, com Java 21: `cd minecraft/mod; ./gradlew test build` (Windows: `gradlew.bat`).
Docker: `docker compose up -d --build`, depois confira `/api/health` e `/api/capabilities`.

## Aceitação visual obrigatória antes de considerar a melhoria confirmada

1. Fixe seis referências: casa, igreja, carro, castelo, personagem e objeto. Use arquivos próprios/autorizados.
2. Registre resultados da versão anterior e 0.5.0 com as mesmas imagens, modelo, tamanho e instrução.
3. Na 0.5.0, compare também `--refinements 0` com Detalhado/Ultra. Guarde os HTMLs e hashes.
4. Avalie manualmente silhueta, proporções, profundidade aparente, componentes, materiais e posições.
5. Veja se a nota concorda com essa avaliação. Se não concordar, registre o caso, preserve a referência
   e use `VISUAL_DEBUG=true` para identificar câmera/máscara/material/alteração responsável.
6. Instale o mod 0.3.0 em mundo de teste; importe projeto novo e antigo, gire 90/180/270, cancele/desfaça.
7. Confira os materiais realmente colocados, transparência, telhado e aberturas. O render cúbico é aproximado.
8. Só aceite a atualização como melhoria de fidelidade se a comparação visual real for positiva.

Comandos do benchmark e limitações: [Visual Refinement](visual-refinement.md).

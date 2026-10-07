# Revisão de fidelidade e eficiência — 2026-10-06

Base revisada: `1f21e6b` (main). Foram mapeados os 88 arquivos versionados e revisados backend, frontend,
testes, Docker, configurações/atualizador, schemas/paleta, scripts/documentação e integração Fabric.
A arquitetura React/FastAPI/SQLite/Ollama/Fabric e o contrato de blocos 1.0 foram preservados.

## Problemas encontrados e correções

- `quick` não enviava `num_ctx`; agora todos os modos usam `AI_CONTEXT_TOKENS` explicitamente.
- Cada pipeline duplicava payloads, parse e limites de saída. `ollama_session.py` centraliza
  orçamento, prazo total, JSON compacto e recuperação de truncamento. A paleta duplicada foi
  retirada dos dados do prompt; continua no schema e na validação Python.
- `done_reason=length` antes encerrava a etapa. Agora permite uma tentativa compacta:
  reduz limites dos arrays pela metade, encurta instruções de saída e prioriza partes principais.
  Não aumenta contexto/saída, não aplica JSON parcial e não reenvia um fragmento cortado como plano válido.
  Persistindo a falha na base, a geração falha; em refinamento, conserva a melhor construção válida.
  Falhas HTTP não provocam novas tentativas automáticas.
- Os limites internos existiam sem transparência. O teto do `.env` continua sendo um teto;
  cada etapa tem um orçamento menor e registra o `num_predict` efetivamente enviado.
- A visão detalhada recebia a cópia OpenCV de 768 px. Agora o OpenCV continua leve em 768 px,
  mas o modelo recebe a imagem original reduzida uma única vez, em PNG sem perda e sem ampliação.
  Limites do lado maior: Rápido 1024, Detalhado 1280, Ultra 1536 px.
- Referências novas são persistidas em PNG sem perda adicional; projetos antigos em JPEG continuam
  acessíveis pelo mesmo endpoint. Miniaturas continuam JPEG. PNG pode ocupar mais disco, sobretudo
  em fotos grandes; os limites de upload/pixels permanecem iguais.
- O estudo pede posições e extensões relativas das partes, contato/sobreposição, ordem frente/fundo
  e distinção entre evidência e inferência. O plano transforma essas relações em coordenadas fixas.
  Máscaras do OpenCV são pistas falíveis, nunca autoridade sobre o objeto pedido pelo usuário.
- A ordem dos prompts é silhueta, proporções, posição das partes, profundidade, cores, materiais,
  aberturas e detalhes. Cascas grandes devem usar painéis, evitando milhares de células de ar.
- A avaliação passou a pesar silhueta 35%, proporção 30%, estrutura 20%, cor 10%, detalhe 5%.
  Ganhos de cor/detalhe não compensam uma regressão geométrica: rejeita perda acima de 2 pontos
  em silhueta/proporção/estrutura ou perda ponderada geométrica acima de 0,25 ponto.
  Esses valores são tolerâncias heurísticas, não medidas físicas ou garantia perceptual.
- Ultra por texto antes era igual a Detalhado, inclusive no metadado. Agora permite mais componentes
  e detalhes, mantendo três etapas e identificando corretamente a qualidade utilizada.
- Texto detalhado passa a respeitar as opções de transparência e espelhamento.
- Cuboides sólidos têm compilação direta; projeções de faces expostas são processadas em lotes;
  histograma de cores usa 512 contadores em vez de ordenar todos os pixels.
- A prévia Three.js renderiza em mudanças de câmera/tamanho e durante amortecimento, sem um loop
  permanente quando está parada. Corrigida a identificação acessível dos seletores de qualidade/refinamento.
- Compose ganhou `host.docker.internal:host-gateway` para Linux. Nginx aguarda 960 s, acima do teto
  de 900 s da IA. A conexão ao Ollama tem timeout de conexão separado de até 10 s.
- Docker ignora modelos, resultados e backups de `.env` no contexto de build. O atualizador deixa
  de descartar o cache de build e continua preservando valores existentes no `.env`.

## Configuração para a instalação informada

```dotenv
OLLAMA_MODEL=qwen3-vl:8b
AI_CONTEXT_TOKENS=32768
AI_MAX_OUTPUT_TOKENS=24000
AI_TIMEOUT_SECONDS=900
```

O código não altera o `.env` existente nem instala/troca o modelo. Esses valores estão no exemplo.
Sem `.env`, os padrões de contexto/saída/timeout continuam conservadores: 16384/16000/600;
o modelo padrão passa a `qwen3-vl:8b`. O teto de timeout aceito é 900 s.

`num_ctx` inclui entrada, imagens e saída. `num_predict` é o menor entre o orçamento da etapa,
`AI_MAX_OUTPUT_TOKENS` e o espaço estimado restante. A reserva considera texto/schema e dimensões
visuais; é uma estimativa conservadora de orçamento, não um tokenizer exato nem garantia contra
truncamento interno pelo Ollama. `prompt_eval_count` permite conferir o uso real no computador local.

| Caminho | Estudo | Geometria | Detalhes ou correção | Avaliação |
| --- | ---: | ---: | ---: | ---: |
| Rápido | junto da geometria | 8000; até 32 partes | — | — |
| Texto detalhado | 2400 | 9000; até 28 partes | 4500; até 12 partes | — |
| Texto ultra | 2400 | 12000; até 40 partes | 7500; até 24 partes | — |
| Imagem detalhada | 2600 | 11000; até 32 componentes | 6500; até 6 edições por rodada | 2200 |
| Imagem ultra | 2600 | 14000; até 48 componentes | 6500; até 6 edições por rodada | 2200 |

Os números são tetos de tokens, não metas de consumo. Arrays também são limitados no schema enviado.
Detalhado permite até duas rodadas visuais; Ultra até três e profundidade opcional. Pode encerrar antes.
Sem reparos: rápido 1 chamada; texto 3; imagem detalhada até 7; imagem ultra até 9.
Cada chamada lógica admite no máximo uma repetição compacta. O plano inicial detalhado admite também
um reparo de validação. Todas as chamadas e repetições compartilham o prazo total.

O aplicativo solicita `think=false`. Isso depende do modelo/versão: não se deve afirmar que todo
modelo desliga raciocínio. Se vier `message.thinking`, o log orienta conferir `qwen3-vl:8b-instruct`;
o sistema não muda silenciosamente a tag. O conteúdo de raciocínio não é interpretado como JSON.
Fontes: [API chat](https://docs.ollama.com/api/chat),
[saída estruturada](https://docs.ollama.com/capabilities/structured-outputs),
[controles de raciocínio](https://docs.ollama.com/capabilities/thinking),
[variante Instruct](https://ollama.com/library/qwen3-vl:8b-instruct).

## Logs

Cada requisição registra um evento JSON `ollama_call` com `build_id`, `model`, `stage`, `seconds`,
`prompt_eval_count`, `eval_count`, `done_reason`, `num_ctx`, `num_predict`, `http_status` e `error`.
Não registra imagem, prompt, resposta completa nem raciocínio. Em falhas sem resposta, métricas ausentes
ficam `null`. Chamadas concluídas também ficam nos metadados `generationInfo.calls`.

```bash
docker compose logs -f api
```

## Validação executada

- 159 testes Python aprovados, incluindo APIs, upload PNG/JPEG/WEBP, texto/imagem com Ollama simulado,
  modos de qualidade, compactação em estudo/geometria/avaliação, prazo compartilhado, logs, rollback,
  referência sem perda, leitura de JPEG antigo e limites de contratos.
- Build TypeScript/Vite aprovado. Permanece o aviso do chunk Three.js de aproximadamente 529 kB,
  carregado sob demanda; não é erro de compilação.
- 4 testes E2E Chromium aprovados: geração demo real, fluxo IA por texto com API simulada,
  comparação/sobreposição/câmeras com API simulada, API incompatível e layout móvel.
- 24 comparações de render, seis formas e quatro câmeras: pixels e máscaras idênticos à base.
- Compose YAML, caminhos de Dockerfiles, dependência de saúde, host gateway e timeout do proxy
  verificados estaticamente. **Não houve build/up Docker:** CLI e daemon não estão disponíveis.
- Tentativa de `gradlew test build`: download do Gradle falhou com `Network is unreachable`;
  ambiente oferece Java 17, enquanto o mod requer 21. Código e contrato do mod não foram alterados.
- **Não há Ollama local/GPU do usuário neste ambiente.** Inferência real, consumo de RAM/VRAM e
  fidelidade em fotos reais não estão certificados. Os testes simulados comprovam controle do pipeline,
  não a qualidade artística de resultados que o modelo ainda não produziu.

Benchmark CPU no mesmo ambiente, casca de seis painéis, com overhead de `tracemalloc`:

| Eixo | Células | Geometria antes → depois | Render antes → depois | Pico Python antes → depois |
| --- | ---: | ---: | ---: | ---: |
| 32 | 5768 | 0,227 → 0,095 s | 1,007 → 0,207 s | 6,21 → 6,07 MiB |
| 48 | 13256 | 0,428 → 0,238 s | 2,429 → 0,423 s | 13,27 → 12,98 MiB |
| 64 | 23816 | 0,733 → 0,469 s | 3,385 → 0,798 s | 23,44 → 23,02 MiB |

Quantidade de blocos e bytes de JSON permaneceram iguais. Uma medição sintética por tamanho;
não representa inferência do Qwen, uso total de memória nativa nem desempenho garantido no PC do usuário.

## Verificação local com o modelo real

Na pasta atual do projeto, após obter esta branch:

```bash
docker compose up -d --build
docker compose ps
docker compose exec -T api python -m app.verify_installation
```

Com Python e `httpx` instalados, o smoke test agora cobre texto e imagem, e exclui somente o projeto
que ele próprio criou:

```bash
python scripts/smoke_api.py --mode ai --quality quick --description "Ponte de pedra com dois pilares e vão central"
python scripts/smoke_api.py --mode ai --quality detailed --image sua-referencia.png
python scripts/smoke_api.py --mode ai --quality ultra --image sua-referencia.png
```

Para guardar referência/render/JSON comparáveis, use `scripts/benchmark_visual.py` com as mesmas imagens,
modelo, tamanho e opções antes/depois. Avalie primeiro silhueta/proporções/partes/profundidade.
As mudanças de maior impacto esperado são a referência mais bem preservada, o planejamento espacial
mais explícito, a recuperação de truncamento e o bloqueio de regressões geométricas no refinamento.

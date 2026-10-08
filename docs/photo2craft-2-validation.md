# Photo2Craft 2.0 — relatório de implementação e validação

Data: 2026-10-08. Base: `4317a5f`. Branch: `feat/photo2craft-2-architectural`.
**Não certificado ponta a ponta.** O PR deve permanecer em rascunho até validar
inferência Gemini real, containers e colocação no Minecraft. Não há métricas de
fidelidade de inferência real nesta entrega, nem promessa de reprodução exata.

## Diagnóstico e mudanças

A [auditoria](photo2craft-2-audit.md) foi feita antes das alterações. A versão anterior
já possuía plano compacto, render CPU, validação e refinamento: esses componentes foram
reutilizados. Os problemas identificados incluem dependência de inferência local,
requisições síncronas longas, colisões por ordem de escrita, ausência de fila durável,
aprovação e incerteza explícita, além da comparação de perspectivas não calibradas.
Não atribuímos toda falha visual ao modelo sem executar inferência comparativa.

Alterações por responsabilidade:

| Arquivos | Resultado |
| --- | --- |
| `apps/api/app/providers.py`, `config.py` | Gemini configurável, Ollama opcional, segredo no backend, deadlines, retries limitados, cotas persistentes e bloqueio gratuito |
| `architecture.py`, `shared/architecture.schema.json` | Schema 2.0, paleta real, evidências, relações, limites, colisões explícitas e compilação determinística |
| `architectural_generator.py`, `ai_generator.py` | Estudo → plano → validação → blocos → render → revisões limitadas; cache; preservação do legado |
| `jobs.py`, `database.py`, `main.py` | Jobs persistidos, múltiplas referências, edição de materiais, aprovação por hash, exportação protegida |
| `apps/web/src/App.tsx`, `api.ts`, `ArchitectureReview.tsx` e estilos | Progresso real, recuperação de job, comparação, incerteza, refinamento e aprovação; prévia Three preservada |
| `apps/api/tests/`, `apps/web/e2e/` | Regressões, falhas dos provedores, geometria e fluxos de navegador |
| `benchmarks/references/architectural/`, `scripts/benchmark_architectural.py` | Quatro referências sintéticas próprias CC0 e benchmark reproduzível |
| `.env.example`, `docker-compose.yml`, dependências, scripts e documentação | Configuração gratuita, atualização, instalação e limitações explícitas |

Mod Fabric 0.3.0, Minecraft 1.21.1, Java 21, schema final 1.0 e protocolo de download
foram preservados. Não houve mudança dos fontes do mod. O plano arquitetônico 2.0 é
intermediário: o mod continua recebendo a estrutura 1.0 em uma única requisição.
Lista exata de arquivos: `git diff --name-status 4317a5f..HEAD`.

## Testes executados

| Verificação | Antes | Depois / evidência |
| --- | --- | --- |
| Pytest backend | 159 aprovados | 214 aprovados; 1 aviso de depreciação de dependência |
| TypeScript + Vite | Compilação aprovada | Compilação aprovada |
| Playwright Chromium | Fluxos existentes preservados | 6 testes aprovados, incluindo upload, múltiplas referências, recuperação de job, aprovação e cota |
| API sem Ollama/chave | Não era o fluxo principal | Inicialização/demo testadas; chamadas Gemini sem chave/confirmação são bloqueadas |
| Compose | — | YAML, Dockerfiles, dependências e segredo somente no backend verificados estaticamente |
| Pacote fonte | — | ZIP gerado e integridade verificada; sem `.env`, dados locais ou dependências instaladas |
| Build/execução Docker | — | NÃO executados: Docker ausente neste ambiente |
| Gradle/mod | — | Tentativa bloqueada no download Gradle 8.12 por rede indisponível; ambiente possui Java 17, não 21 |
| Gemini real | — | NÃO executado: nenhuma chave real disponível; mocks não consomem cota |
| Minecraft | — | NÃO executado: jogo/servidor indisponível |

Testes cobrem chave ausente/inválida, confirmação gratuita, modelo/provedor proibido,
JSON estruturado, saída incompleta, timeouts, rede/5xx, 429 persistido/reinício/reset,
contagem local, limites, coordenadas, materiais/estados, colisões, sustentação,
paredes/telhados/aberturas/arcos/escadas, migração, cache, exportação, edição de
materiais (incluindo falha de commit sem render divergente), rejeição/aprovação por hash, refinamento com regressão/cota e perspectiva
incomparável. E2E exercita frontend/API reais com inferência simulada, não a nuvem.

Comandos reproduzíveis, com dependências instaladas e ambiente Python ativo:

```bash
cd apps/api
python -m pytest -q
cd ../web
npm ci
npm run build
npx playwright install chromium
npm run test:e2e
cd ../..
python scripts/benchmark_architectural.py --help
```

## Comparação medida e limites da evidência

[Dados brutos](architectural-synthetic-results.json). As referências abaixo foram
renderizadas de planos manuais conhecidos. A nova compilação reproduz o mesmo plano;
portanto IoU 100% é esperado por construção. Isso verifica representação/geometria,
**não** capacidade de Gemini reconstruir uma foto nem melhoria sobre o Ollama antigo.
O comparador antigo é o gerador procedural genérico, não a inferência multimodal.

| Referência | Blocos genéricos → plano | IoU genérico → plano conhecido | Compilação do plano | Pico Python |
| --- | --- | --- | --- | --- |
| Casa simples | 4096 → 2816 | 72,18% → 100% | 0,2503 s | 4,131 MiB |
| Casa moderna | 4096 → 1756 | 65,36% → 100% | 0,1291 s | 2,757 MiB |
| Castelo | 4096 → 1012 | 58,90% → 100% | 0,0851 s | 1,805 MiB |
| Assimétrica | 4096 → 1304 | 58,05% → 100% | 0,0952 s | 2,216 MiB |

Microbenchmark do motor/render reutilizado, caixas ocas 32/48/64: 5.768/13.256/23.816
células e JSON 386.069/889.685/1.600.661 bytes, iguais antes/depois. Geometria antes
0,080/0,197/0,436 s e depois 0,081/0,196/0,437 s; render antes 0,173/0,408/0,749 s
e depois 0,171/0,398/0,679 s. Pico de alocação Python aproximadamente
6,07/12,98/23,02 MiB, sem mudança relevante. Medição única, sujeita a ruído; não é
benchmark de GPU, memória RSS do processo ou pipeline completo. Nenhum ganho de
velocidade é reivindicado. Tokens reais e resultados no Minecraft: não medidos.

Melhorias concretas verificadas: estruturas distintas/assimétricas representáveis,
aberturas determinísticas, colisões rejeitadas, referências incertas identificadas,
refinamento que não aceita regressão geométrica, exportação vinculada à prévia
aprovada. A magnitude da melhoria de fidelidade fotográfica permanece desconhecida.

## Configuração gratuita e teste real pendente

Modelo padrão `gemini-3.8-flash`: imagens e JSON estruturado documentados, entrada e
saída listadas no nível gratuito na data de consulta. Comparação e fontes em
[Gemini gratuito](gemini-free-tier.md). É configurável; não há fallback pago.

1. Preserve `.env`/volumes existentes. Para instalação nova, copie `.env.example`.
2. Crie/use chave em projeto Free Tier **sem Cloud Billing/cartão**. Não envie a chave
   por chat nem a grave no Git/frontend. A aplicação não detecta faturamento da chave.
3. Configure somente no `.env` do backend:

```dotenv
AI_PROVIDER=gemini
GEMINI_API_KEY=sua_chave_local
GEMINI_MODEL=gemini-3.8-flash
GEMINI_FREE_TIER_CONFIRMED=true
FALLBACK_PROVIDER=none
GENERATION_MODE=architectural
MAX_REFINEMENT_PASSES=2
```

Confirme `true` somente após conferir a gratuidade no AI Studio. Cota local padrão
20 tentativas/dia não é oferta de 20 chamadas garantidas pelo Google. Quota real
esgotada bloqueia chamadas, inclusive após reinício; não trocar chave para contornar.

```bash
docker compose up -d --build
docker compose ps
docker compose exec -T api python -m app.verify_installation
docker compose logs --tail=100 api
```

Abra http://localhost:8081. Verifique upload de 1–4 referências, progresso, prévia,
edição de materiais, aprovação/rejeição e recuperação após recarregar. Gere as mesmas
referências com a versão antiga isolada e com a nova, sem compartilhar banco de teste.
Use `scripts/benchmark_visual.py` para registrar tempo, chamadas/tokens disponíveis,
blocos, dimensões, avisos e render. Respeite as cotas: não rode lotes grandes.
Avalie silhueta, proporções, volumes, telhado, aberturas e materiais na mesma câmera;
registre resultado não comparável quando a perspectiva não permitir avaliação.

## Validação manual no Minecraft

1. Use JDK 21, compile `cd minecraft/mod && ./gradlew test build`, instale Fabric
   1.21.1/Fabric API compatível e Photo2Craft 0.3.0. Faça backup do mundo.
2. Em mundo descartável criativo, configure a URL da API na máquina do servidor.
3. Execute `/build test`; teste download de projeto legado e da nova estrutura aprovada.
4. Antes de aprovar, `/build import ID` deve falhar com 409 sem colocar blocos.
5. Após aprovar, importe em área plana/carregada, nos ângulos 0/90/180/270.
6. Confira dimensões, origem, orientação dos estados, janelas/portas, telhados e cores
   contra o JSON da prévia. Capture screenshots na câmera da referência.
7. Teste `/build cancel`, `/build undo`, área ocupada, chunks ausentes, limites do
   mundo, indisponibilidade da API e usuário sem permissão.
8. Registre confirmações/erros no jogo. Não há confirmação de conclusão enviada ao site.

## Pendências e limitações conhecidas

- Bloqueadores de aceitação: Gemini real, comparação fotográfica antes/depois, Docker
  real e execução Java21/Minecraft. Não marcar PR como pronto antes de verificá-los.
- Câmera estimada ortográfica, sem calibração multiview. Múltiplas fotos entram na
  inferência; avaliação automática usa a referência primária comparável.
- Render/Three usam cores/envelopes aproximados, sem texturas/iluminação do Minecraft.
  Estados especiais, vidro e escadas podem não parecer idênticos no jogo.
- Schema restringe primitivas, exige ligação à base e rejeita gravidade/flutuação.
  Não reconstrói malha arbitrária, detalhes invisíveis ou interiores comprovados.
- API local sem autenticação; uma instância/um worker. Job interrompido falha em vez
  de reiniciar chamadas externas. Nenhuma promessa de fila distribuída.
- Limites maiores precisam ser compatibilizados com o mod e ensaiados em memória real.
- Aprovação valida conteúdo, não fidelidade; qualidade ainda exige revisão humana.
- Planos legados com mirror exigem expansão antes de migração; estruturas prontas
  legadas continuam sendo lidas/exportadas sem migração.

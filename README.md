# Photo2Craft 2.0 — reconstrução arquitetônica

Referência(s) → análise multimodal → projeto arquitetônico validado → geometria
Minecraft → prévia → refinamentos limitados → aprovação → importação.

**Gemini API é o provedor principal; Ollama/GPU local não são necessários.**
Modo demo, pipeline Ollama legado, projetos existentes e mod Fabric permanecem.
O JSON final continua no formato 1.0 para Minecraft 1.21.1/Java21/Fabric0.3.0.

Implementados: múltiplas referências, estudo com incerteza por elemento, materiais
reais, colisões explícitas, aberturas/escadas/arcos, conectividade, jobs persistidos,
progresso por etapas, cache, revisão de materiais, aprovação/rejeição e cotas duráveis.
Render/cores são aproximados; uma foto não revela laterais/interior/traseira.

**Estado de aceitação:** testes locais/mocks e frontend verificados; inferência real
Gemini, comparação em fotos reais, Docker e colocação no Minecraft ainda precisam
ser validados no ambiente do usuário. A migração não está certificada ponta a ponta.
[Resultados e pendências](docs/photo2craft-2-validation.md).

## Iniciar com Docker e custo zero

Na instalação existente, preserve `.env`, volume, mundos e nome do projeto Compose.
Para uma instalação nova:

```bash
cp .env.example .env
```

No Windows PowerShell: `Copy-Item .env.example .env`.
Obtenha a chave em https://aistudio.google.com/apikey em um projeto **Free Tier sem
faturamento/cartão**. Não ative Cloud Billing. Edite `.env` somente no backend:

```dotenv
AI_PROVIDER=gemini
GEMINI_API_KEY=sua_chave_aqui
GEMINI_MODEL=gemini-3.8-flash
GEMINI_FREE_TIER_CONFIRMED=true
FALLBACK_PROVIDER=none
GENERATION_MODE=architectural
ENABLE_VISUAL_REFINEMENT=true
MAX_REFINEMENT_PASSES=2
```

A confirmação deve ser feita somente após verificar o nível gratuito do projeto.
O aplicativo não consegue detectar uma chave paga e não torna uma chave paga gratuita.
Nunca coloque a chave em `VITE_*`, frontend, Git ou mensagens.
Sem chave/confirmação, API e demo iniciam normalmente; geração Gemini fica indisponível.

```bash
docker compose up -d --build
docker compose ps
docker compose exec -T api python -m app.verify_installation
docker compose logs --tail=100 api
```

Site: http://localhost:8081 · Saúde: http://localhost:8000/api/health.
Swagger: http://localhost:8081/docs. Portas existentes do `.env` prevalecem.
Dados em `photo2craft-data`; `docker compose down` preserva, **down -v apaga**.
Quota esgotada pausa chamadas, inclusive após reiniciar. Não há acesso ilimitado nem
fallback pago. [Modelos, evidências oficiais e limites](docs/gemini-free-tier.md).

Documentação: [migração](ATUALIZAR-IA.md), [arquitetura 2.0](docs/photo2craft-2-architecture.md),
[auditoria](docs/photo2craft-2-audit.md), [testes](docs/photo2craft-2-validation.md).

## Instalar o mod

1. Instale **JDK 21** e confira `java -version`.
2. Compile o mod:

```bash
cd minecraft/mod
# Linux/macOS
chmod +x gradlew
./gradlew build
# Windows PowerShell
.\gradlew.bat build
```

3. Instale [Fabric Loader](https://fabricmc.net/use/installer/) para **Minecraft 1.21.1**, versão 0.16.14 ou posterior compatível.
4. Com o jogo/servidor fechado, substitua o mod antigo por `minecraft/mod/build/libs/photo2craft-0.3.0.jar` na pasta `mods` da sua instalação. Preserve uma cópia do JAR antigo fora de `mods`. Mantenha [Fabric API](https://modrinth.com/mod/fabric-api) **0.116.6+1.21.1**. Não use o JAR `-sources` nem deixe as duas versões do Photo2Craft juntas.
5. Inicie Minecraft no perfil Fabric. Use um mundo de teste criativo com comandos habilitados. Em servidor dedicado, instale o mod e Fabric API no servidor; os comandos exigem nível de operador 2. Não precisa instalar o mod no cliente para esta versão sem holograma.

O mod cria `config/photo2craft.json` ao iniciar o mundo/servidor. Por padrão, consulta `http://127.0.0.1:8000` **a partir da máquina do servidor Minecraft**. Se servidor e API estão em máquinas diferentes, configure o endereço da API e reinicie o servidor/mundo.

### Teste independente da API

```text
/build test
```

Uma casa local de exemplo é validada e construída a 3 blocos no sentido +X e +Z da posição atual, com base na altura dos pés. Fique em uma área plana, livre e carregada. O mod não altera automaticamente o terreno.

### Fluxo completo

1. Abra o site.
2. Escolha o modo IA e envie JPG, PNG ou WEBP (até 5 MiB por padrão), ou escreva um pedido sem imagem.
3. Informe o tipo livre, tamanho, estilo e detalhes na descrição.
4. Clique em **Gerar construção**.
5. Confira a prévia 3D e as referências. Clique **Aprovar para Minecraft**; só então copie o comando. Rejeitados/pendentes retornam HTTP 409 no mod.
6. No Minecraft, digite `/build import ID`, substituindo `ID` pelo código real.
7. Aguarde validação e construção. O progresso aparece na barra de ação.

```text
/build import SEU_ID
/build import SEU_ID 90
/build cancel
/build undo
```

Rotação: 0, 90, 180 ou 270 graus, em torno do eixo vertical. A caixa é reposicionada para manter a origem no canto mínimo. Estados orientáveis também giram.

`cancel` interrompe download ou fila; os blocos já colocados permanecem. `undo` desfaz a última colocação desta sessão em lotes, preservando blocos que foram alterados depois. O histórico não é salvo em disco; guarda até oito jogadores e uma construção por jogador. Não há comando de refazer.

## O que funciona

- Upload validado pelo conteúdo real, normalização da imagem e miniatura da referência.
- Projetos persistentes, listagem paginada, detalhes, exclusão e download do JSON.
- Geração por IA: imagem e/ou descrição → plano geométrico validado → blocos. Tipo livre, fidelidade orientativa e explicação das simplificações.
- Demo: modelos procedurais de casa, castelo, prédio e monumento; clientes antigos que enviam automático/outro continuam usando casa somente nesse modo.
- Cinco estilos e catálogo de materiais semânticos; dimensões pequenas, médias, grandes ou personalizadas.
- Interior simples: bancada e iluminação nas casas/prédios; lajes com abertura técnica em prédios. Não inclui escadas internas completas. Castelo e monumento mantêm o modelo básico.
- Prévia 3D no navegador com orbit, zoom, pan, reset e vistas frente/trás/laterais/topo/perspectiva. Cores aproximadas, sem texturas do jogo; blocos especiais, como escadas importadas por JSON, aparecem como cubos.
- Mod com validação, download assíncrono limitado, orçamento global de blocos por tick, cancelamento, rotação e desfazer.
- Docker, Swagger, contrato JSON compartilhado e testes.

Ainda não implementado: reconstrução 3D precisa, interiores completos, holograma dentro do jogo, contas e permissões por projeto. A nota de fidelidade visual é estimada, sem garantia científica de semelhança.

## Arquitetura

```text
apps/web        Interface e prévia 3D (React / Three.js)
apps/api/app    Rotas, modelos, repositório, imagens e gerador
apps/api/tests  Testes de API, persistência e validação
minecraft/mod   Mod Fabric, wrapper Gradle, testes Java
shared          JSON Schema, paleta permitida e casa de teste
docker          Dockerfiles e proxy Nginx
docs            Contrato, arquitetura e validação
scripts         Teste HTTP do fluxo
```

O gerador implementa uma interface que recebe opções e uma lista de imagens e devolve `Structure`. A API persiste o contrato sem depender da lógica de colocação do mod. O visualizador lê o mesmo JSON; não inventa uma prévia independente.

## Desenvolvimento sem Docker

Requisitos: Python 3.12, Node 22 LTS, JDK 21. A primeira instalação e a primeira compilação do mod precisam de internet.

Na raiz, Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r apps/api/requirements-dev.txt
# Execute da raiz para carregar o .env, se você criou o arquivo.
uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 8000
```

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r apps/api/requirements-dev.txt
uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 8000
```

Em outro terminal:

```bash
cd apps/web
npm ci
npm run dev
```

Abra http://localhost:5173. O Vite encaminha `/api`, `/docs` e `/openapi.json` à API. Em desenvolvimento o banco padrão fica em `photo2craft/data/`. `.env` é lido a partir do diretório em que a API foi iniciada.

## Configuração

| Variável | Padrão | Efeito |
| --- | --- | --- |
| `BIND_ADDRESS` | `127.0.0.1` | Interface publicada pelo Docker |
| `WEB_PORT` / `API_PORT` | `8081` / `8000` | Portas externas |
| `DATA_DIR` | `photo2craft/data` | Dados fora do Docker; Compose usa caminho interno fixo |
| `DATABASE_URL` | vazio | SQLite automático; veja guia de PostgreSQL |
| `CORS_ORIGINS` | localhost 5173/8080 | Origens separadas por vírgula |
| `MAX_UPLOAD_BYTES` | 5242880 | Imagem enviada, até 5 MiB |
| `MAX_REQUEST_BYTES` | 8388608 | Corpo HTTP total e JSON gerado |
| `MAX_IMAGE_PIXELS` | 16000000 | Limite de pixels; animações são rejeitadas |
| `MAX_BLOCKS` | 50000 | Células, incluindo ar |
| `MAX_DIMENSION` | 64 | Limite de cada eixo |
| `MAX_PROJECTS` | 200 | Quota de projetos locais |
| `AI_PROVIDER` | gemini | gemini, ollama ou disabled |
| `GEMINI_MODEL` | gemini-3.8-flash | Modelo da allowlist gratuita revisada |
| `GEMINI_API_KEY` | vazio | Segredo somente no backend |
| `GEMINI_FREE_TIER_CONFIRMED` | false | Confirmação de projeto sem billing |
| `FALLBACK_PROVIDER` | none | Alternativa local ollama, explicitamente habilitada |
| `GENERATION_MODE` | architectural | legacy preserva o pipeline Ollama anterior |
| `MAX_REFINEMENT_PASSES` | 2 | Máximo global; opção da qualidade só reduz |
| `AI_DAILY_CALL_LIMIT` | 20 | Limite local de chamadas, não cota prometida pelo Google |
| `OLLAMA_URL` | localhost fora do Docker | Compose usa `http://host.docker.internal:11434` |
| `OLLAMA_MODEL` | qwen3-vl:8b | Modelo local com visão e saída estruturada |
| `AI_TIMEOUT_SECONDS` | 600 | Prazo total de inferência |
| `AI_MAX_OUTPUT_TOKENS` | 16000 | Teto de saída; cada etapa usa orçamento próprio; think=false somente no Ollama |
| `AI_CONTEXT_TOKENS` | 16384 | Contexto somente do Ollama; exemplo .env usa 32768. Mais contexto local consome RAM/VRAM |

Na demo, o volume inteiro da caixa conta em `MAX_BLOCKS`. No modo IA, apenas posições emitidas contam (incluindo ar explícito), permitindo estruturas esparsas. IA pequena/média/grande usa caixas máximas de 32³/48³/64³; a IA escolhe proporções dentro delas. Personalizado aceita 9–64 por eixo. A API e o mod têm limites independentes: se aumentar um, revise o outro.

Mod, arquivo `config/photo2craft.json`:

```json
{
  "apiBaseUrl": "http://127.0.0.1:8000",
  "blocksPerTick": 500,
  "maxBlocks": 50000,
  "maxDimension": 64,
  "maxResponseBytes": 8388608,
  "maxJobs": 4,
  "replaceExisting": false
}
```

A área precisa estar carregada, dentro da borda e da altura do mundo. Por padrão, só ar e blocos substituíveis (como vegetação) são aceitos. `replaceExisting: true` permite substituir o terreno e estruturas; blocos com inventário/dados continuam protegidos. O mod exige operador, mas não integra sistemas de claims de outros mods.

## Endpoints

| Método | Caminho | Uso |
| --- | --- | --- |
| GET | `/api/health` | Saúde com acesso ao banco |
| GET | `/api/capabilities` | Limites e capacidades reais |
| POST | `/api/generations` | Multipart image + references[] + options; retorna job 202 |
| GET | `/api/generations/{id}` | Progresso/status persistidos, sem porcentagem inventada |
| POST | `/api/generate` | Endpoint síncrono legado; projeto novo exige revisão |
| GET | `/api/builds/{id}/preview` | Blocos exatos para revisão antes da aprovação |
| GET | `/api/builds/{id}/architecture` | Plano arquitetônico versionado |
| POST | `/api/builds/{id}/approval` | Aprovar/rejeitar vinculando content_hash |
| POST | `/api/builds/{id}/materials` | Alterar material e invalidar aprovação/score |
| POST | `/api/builds/{id}/refine` | Novo job/versão, sem apagar a anterior |
| POST | `/api/builds` | Importa um JSON de construção validado; cria ID/data novos |
| GET | `/api/builds?offset=0&limit=30` | Lista metadados, até 100 por página |
| GET | `/api/builds/{id}` | Metadados |
| GET | `/api/builds/{id}/structure` | Contrato para mod/visualizador |
| GET | `/api/builds/{id}/image` | Referência PNG sem perda; JPEG em projetos antigos |
| GET | `/api/builds/{id}/render` | Render final na câmera estimada, quando disponível |
| GET | `/api/builds/{id}/thumbnail` | Miniatura da referência |
| DELETE | `/api/builds/{id}` | Exclui banco e imagens; não altera o mundo Minecraft |

Exemplo Linux/macOS:

```bash
curl -F 'image=@casa.png' \
  -F 'options={"name":"Minha casa","type":"house","style":"medieval","size":"small","interior":"simple"}' \
  http://localhost:8000/api/generate
```

A interface usa `/api/generations`: resposta `202`, fila limitada e progresso persistido consultado pelo ID. O endpoint síncrono acima permanece compatível e retorna `201`; projetos arquitetônicos novos ficam pendentes de aprovação. Erros incluem `413` para tamanho, `422` para validação, `409` para conflito de aprovação/limite de projetos e `429` para fila/cota de inferência esgotada. Falhas de jobs aparecem no status consultado, com código e mensagem.

Clientes antigos que omitem `mode` continuam em `procedural`. Para IA, envie `"mode":"ai"` e uma imagem ou `description` não vazia. `quality` aceita `quick` (padrão da API), `detailed` ou `ultra`. `type` aceita texto livre de até 120 caracteres; `fidelity` vai de 0 a 100. Ollama indisponível retorna 503; plano inválido 502; timeout 504. Falhas na análise/base não criam projetos e não são convertidas em casas. Falha de comparação/refinamento preserva a melhor estrutura válida com aviso. O Nginx aguarda até 960 segundos; a IA tem prazo total de até 900 segundos.

## Testes

```bash
# Raiz, com ambiente Python ativo
cd apps/api
pytest -q
# Em outro terminal/da raiz
cd apps/web
npm run build
# Em outro terminal/da raiz
cd minecraft/mod
./gradlew test build
```

Para repetir o fluxo no navegador (com o ambiente Python ativo e portas 8000/5173 livres):

```bash
cd apps/web
npx playwright install chromium
npm run test:e2e
```

O teste inicia API e Vite, usa dados separados em `.e2e-data`, faz upload, confere o JSON e a prévia, valida a largura de 390 px e exclui o projeto temporário.

Com API em execução:

```bash
python scripts/smoke_api.py --url http://localhost:8000 --image sua-imagem.png
```

O teste cria, consulta, aprova quando necessário e exclui seu próprio projeto temporário. Essa aprovação automatizada testa o contrato, não a fidelidade. O checklist completo e a evidência desta entrega estão em [docs/photo2craft-2-validation.md](docs/photo2craft-2-validation.md).

## Uso local e próximos passos

Esta versão tem um único espaço compartilhado, sem autenticação. O Docker publica apenas em localhost por padrão. Para uso entre máquinas confiáveis na LAN, configure `BIND_ADDRESS=0.0.0.0`, firewall e `apiBaseUrl` com o IP correto; adicione a origem do navegador ao CORS quando necessário. Não exponha diretamente esta API à internet antes de implementar contas e autorização.

Evolução planejada:

1. Validar a colocação no mundo com o checklist e diferentes terrenos.
2. Adicionar sessão de posicionamento: mover, girar, confirmar e cancelar antes da fila.
3. Implementar holograma cliente/servidor.
4. Avaliar gerações reais e calibrar o novo refinamento visual iterativo.
5. Calibrar câmeras entre múltiplas referências e validar reconstrução multiview real.
6. Contas, autorização, migrações versionadas e PostgreSQL.

Detalhes: [contrato](docs/structure-format.md), [arquitetura](docs/architecture.md).

Novos parâmetros de geração/configuração e dependências de profundidade: [Visual Refinement](docs/visual-refinement.md).

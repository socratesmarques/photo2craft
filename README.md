# Photo2Craft 0.5.0 — Visual Refinement

Revisão de fidelidade/Ollama: [mudanças, limites por etapa, benchmarks e validação](docs/ollama-fidelity-review.md).

Transforme imagem ou descrição em uma estrutura de blocos para Minecraft Java 1.21.1.
React/Vite/Three.js, FastAPI/SQLite, IA local via Ollama e mod Fabric (Java 21).

O novo fluxo detalhado com imagem é **OpenCV → estudo → componentes → geometria → render → comparação → correções → melhor estrutura**.
Correções que pioram a avaliação são descartadas. Imagem sempre prevalece sobre estilo/texto complementar.
A interface inclui Rápido/Detalhado/Ultra, objeto principal/cena completa, comparação lado a lado/sobreposição,
vistas da câmera, tempo, etapas concluídas e nota estimada. A paleta passou a 166 IDs com seleção perceptual e semântica.

- **Rápido:** uma análise e geração, sem refinamento visual.
- **Detalhado:** até duas rodadas de correção/avaliação.
- **Ultra:** até três rodadas e profundidade CPU opcional quando instalada; demora mais.
- Sem imagem, preserva o planejamento textual anterior, sem nota de semelhança inventada.
- Limites preservados: 64 por eixo / 50 mil células. Novos presets IA: 32, 48 e 64; proporções são preservadas dentro da caixa.

**O código foi testado com Ollama simulado; melhoria perceptual em fotos reais ainda precisa ser validada no seu PC.**
A nota é uma heurística, não porcentagem científica. Uma única foto não mostra lados ocultos.
Não há modelo adicional obrigatório: o depth model é opcional. Todos os modos respeitam o contexto configurado; o exemplo para Qwen usa 32k.

**Atualização:** veja [ATUALIZAR-IA.md](ATUALIZAR-IA.md). Recompile e instale o mod **0.3.0** para a nova paleta.
Contrato JSON 1.0 e projetos antigos preservados. Não é necessário apagar banco, projetos nem `.env`.

Documentação: [pipeline, arquivos, materiais e limitações](docs/visual-refinement.md),
[arquitetura](docs/architecture.md), [validação e benchmarks](docs/testing.md).

## Começar com Docker

Instale Docker com Compose v2 (no Windows, Docker Desktop com contêineres Linux). Na pasta que contém este README:

```bash
docker compose up -d --build
```

Depois da primeira compilação, `docker compose up -d` é suficiente.

- Site: http://localhost:8080
- API e saúde: http://localhost:8000/api/health
- Swagger: http://localhost:8000/docs (também http://localhost:8080/docs)

Os dados ficam no volume `photo2craft-data`. `docker compose down` preserva os projetos. **`docker compose down -v` apaga os dados.**

Para configurar limites e portas, copie `.env.example` para `.env` antes de iniciar. Sem `.env`, os padrões funcionam. Para atualizar código: `docker compose up -d --build`.

```bash
docker compose ps
docker compose logs --tail=100 api web
```

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
5. Confira os blocos na prévia 3D e copie o comando exibido.
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

Ainda não implementado: reconstrução 3D precisa, interiores completos, holograma dentro do jogo, contas, permissões por projeto e múltiplas vistas na interface. A nota de fidelidade visual é estimada, sem garantia científica de semelhança.

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
| `WEB_PORT` / `API_PORT` | `8080` / `8000` | Portas externas |
| `DATA_DIR` | `photo2craft/data` | Dados fora do Docker; Compose usa caminho interno fixo |
| `DATABASE_URL` | vazio | SQLite automático; veja guia de PostgreSQL |
| `CORS_ORIGINS` | localhost 5173/8080 | Origens separadas por vírgula |
| `MAX_UPLOAD_BYTES` | 5242880 | Imagem enviada, até 5 MiB |
| `MAX_REQUEST_BYTES` | 8388608 | Corpo HTTP total e JSON gerado |
| `MAX_IMAGE_PIXELS` | 16000000 | Limite de pixels; animações são rejeitadas |
| `MAX_BLOCKS` | 50000 | Células, incluindo ar |
| `MAX_DIMENSION` | 64 | Limite de cada eixo |
| `MAX_PROJECTS` | 200 | Quota de projetos locais |
| `AI_PROVIDER` | ollama | Provedor local de IA |
| `OLLAMA_URL` | localhost fora do Docker | Compose usa `http://host.docker.internal:11434` |
| `OLLAMA_MODEL` | qwen3-vl:8b | Modelo local com visão e saída estruturada |
| `AI_TIMEOUT_SECONDS` | 600 | Tempo limite da geração local |
| `AI_MAX_OUTPUT_TOKENS` | 16000 | Teto de saída; cada etapa usa orçamento próprio e solicita think=false |
| `AI_CONTEXT_TOKENS` | 16384 | Contexto de todos os modos; exemplo .env usa 32768. Mais contexto consome RAM/VRAM |

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
| POST | `/api/generate` | Multipart: `options` JSON + `image` opcional no modo IA; retorna projeto pronto |
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

O MVP gera de forma síncrona e permite uma geração local por vez para não sobrecarregar GPU/RAM; resposta de sucesso é `201` com status `ready`. Não há fila persistente ou status fictício. Erros são `4xx` com `detail`, incluindo `413` para tamanho, `422` para validação, `409` para quota e `429` para gerador ocupado.

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

O teste cria, consulta e exclui um projeto temporário. O checklist completo e a evidência desta entrega estão em [docs/testing.md](docs/testing.md).

## Uso local e próximos passos

Esta versão tem um único espaço compartilhado, sem autenticação. O Docker publica apenas em localhost por padrão. Para uso entre máquinas confiáveis na LAN, configure `BIND_ADDRESS=0.0.0.0`, firewall e `apiBaseUrl` com o IP correto; adicione a origem do navegador ao CORS quando necessário. Não exponha diretamente esta API à internet antes de implementar contas e autorização.

Evolução planejada:

1. Validar a colocação no mundo com o checklist e diferentes terrenos.
2. Adicionar sessão de posicionamento: mover, girar, confirmar e cancelar antes da fila.
3. Implementar holograma cliente/servidor.
4. Avaliar gerações reais e calibrar o novo refinamento visual iterativo.
5. Adicionar upload/armazenamento multiview completo e calibração de câmera.
6. Contas, autorização, migrações versionadas e PostgreSQL.

Detalhes: [contrato](docs/structure-format.md), [arquitetura](docs/architecture.md).

Novos parâmetros de geração/configuração e dependências de profundidade: [Visual Refinement](docs/visual-refinement.md).

# Photo2Craft

Transforme uma imagem ou descrição em uma estrutura em blocos e importe para Minecraft Java.

**MVP 0.4.0:** React + Vite + TypeScript, FastAPI + SQLite, planejador visual local Ollama/Gemma 4 e um mod Fabric para **Minecraft Java 1.21.1 / Java 21**. O mod passa a **0.2.0** para aceitar a paleta ampliada; o contrato JSON continua 1.0. Projetos anteriores continuam legíveis.

**Validação da entrega:** testes de API com Ollama simulado e build do site. O Gemma real não está instalado neste ambiente: não foi medida a melhora visual. O núcleo Java foi testado em revisão anterior; o teste novo da paleta e a compilação do mod 0.2.0 precisam ser executados com Java 21 no seu PC. Veja [docs/testing.md](docs/testing.md).

Há dois modos explícitos: **IA local**, que envia imagem/descrição ao Gemma 4 executado pelo Ollama no próprio PC; e **Demo local**, que conserva os modelos prontos. A IA aceita tipo livre e pode trabalhar só com texto. O resultado continua aproximado, não uma reconstrução 3D perfeita.

### Planejamento detalhado (novo)

- Analisa assunto, proporções tridimensionais estimadas, silhueta, cores e características importantes antes de construir.
- Ajusta as dimensões preservando a razão estimada: um carro não deve virar um cubo só porque a caixa máxima é cúbica.
- Gera a forma principal e depois um lote separado de detalhes, olhando a referência em ambas as etapas.
- Calcula cópias espelhadas de peças no código, úteis para rodas, janelas, asas e membros.
- Usa as 16 cores de concreto. O preview também reconhece essas cores.
- Até 48 peças por lote e 192 formas após espelhamento; o limite total continua 50 mil células e 64 por eixo.
- Na interface, o padrão é Detalhado + Grande (48 por eixo). Personalizado permite uma caixa máxima de até 64 por eixo. A forma usa proporções estimadas dentro dessa caixa, não preenche necessariamente todos os eixos.
- A prioridade da referência não é uma porcentagem de semelhança. Com imagem e prioridade ≥75, o detalhado prioriza cores/forma da referência sobre o estilo escolhido.

O detalhado faz três consultas sequenciais, ou quatro se a geometria precisar de uma correção, compartilhando o tempo de `AI_TIMEOUT_SECONDS`. Quando os detalhes falham ou alteram volume demais, conserva a forma principal e exibe um aviso. O rápido continua disponível. As verificações são geométricas, não uma avaliação visual; não há comparação automática de um render com a foto. Uma foto não revela os lados ocultos, que ainda são inferidos. Para avaliar fidelidade, gere novamente uma mesma referência e compare os resultados; projetos antigos não são modificados.

**Já instalou a versão anterior? Siga [ATUALIZAR-IA.md](ATUALIZAR-IA.md).** Preserve seu `.env`, porta e volume de dados. **Nesta atualização, recompile e instale o mod 0.2.0 antes de importar as novas cores.**

A versão 0.4.0 inclui `ATUALIZAR-OLLAMA.ps1`: verifica os arquivos, salva backup do `.env`, configura Ollama, recompila e confirma a versão real através do site. O marcador `ollama-local-0.4.0` aparece em `RELEASE.txt`, `/api/health` e `/api/capabilities`. O site identifica uma API antiga e informa como atualizar. A consulta ao Ollama confirma instalação/conexão, não qualidade das gerações. O lockfile do frontend também foi regenerado somente com pacotes realmente publicados no npm, permitindo que o `npm ci` do Docker seja reproduzido do zero.

Para ativar a IA, instale o Ollama no Windows, baixe `gemma4:e2b` e siga [ATUALIZAR-IA.md](ATUALIZAR-IA.md). Não há chave nem cobrança por geração. O Ollama precisa permanecer aberto; não há fallback silencioso para casas.

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
4. Com o jogo/servidor fechado, substitua o mod antigo por `minecraft/mod/build/libs/photo2craft-0.2.0.jar` na pasta `mods` da sua instalação. Preserve uma cópia do JAR antigo fora de `mods`. Mantenha [Fabric API](https://modrinth.com/mod/fabric-api) **0.116.6+1.21.1**. Não use o JAR `-sources` nem deixe as duas versões do Photo2Craft juntas.
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
- Cinco paletas de estilo e dimensões pequenas, médias, grandes ou personalizadas.
- Interior simples: bancada e iluminação nas casas/prédios; lajes com abertura técnica em prédios. Não inclui escadas internas completas. Castelo e monumento mantêm o modelo básico.
- Prévia 3D no navegador com orbit e zoom. Cores aproximadas, sem texturas do jogo; blocos especiais, como escadas importadas por JSON, aparecem como cubos.
- Mod com validação, download assíncrono limitado, orçamento global de blocos por tick, cancelamento, rotação e desfazer.
- Docker, Swagger, contrato JSON compartilhado e testes.

Ainda não implementado: reconstrução 3D precisa, interiores completos, holograma dentro do jogo, contas, permissões por projeto e múltiplas vistas na interface. A fidelidade é uma instrução ao modelo, não uma medida garantida de semelhança.

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
| `OLLAMA_MODEL` | gemma4:e2b | Modelo local com visão e saída estruturada |
| `AI_TIMEOUT_SECONDS` | 600 | Tempo limite da geração local |
| `AI_MAX_OUTPUT_TOKENS` | 16000 | Limite de saída do modelo; o raciocínio interno é desativado |
| `AI_CONTEXT_TOKENS` | 16384 | Contexto do modo detalhado; consome mais RAM/VRAM. O rápido usa o padrão do Ollama |

Na demo, o volume inteiro da caixa conta em `MAX_BLOCKS`. No modo IA, apenas posições emitidas contam (incluindo ar explícito), permitindo estruturas esparsas. IA pequena/média/grande usa caixas máximas de 16³/32³/48³; a IA escolhe proporções dentro delas. Personalizado aceita 9–64 por eixo. A API e o mod têm limites independentes: se aumentar um, revise o outro.

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
| GET | `/api/builds/{id}/image` | Referência normalizada em JPEG |
| GET | `/api/builds/{id}/thumbnail` | Miniatura da referência |
| DELETE | `/api/builds/{id}` | Exclui banco e imagens; não altera o mundo Minecraft |

Exemplo Linux/macOS:

```bash
curl -F 'image=@casa.png' \
  -F 'options={"name":"Minha casa","type":"house","style":"medieval","size":"small","interior":"simple"}' \
  http://localhost:8000/api/generate
```

O MVP gera de forma síncrona e permite uma geração local por vez para não sobrecarregar GPU/RAM; resposta de sucesso é `201` com status `ready`. Não há fila persistente ou status fictício. Erros são `4xx` com `detail`, incluindo `413` para tamanho, `422` para validação, `409` para quota e `429` para gerador ocupado.

Clientes antigos que omitem `mode` continuam em `procedural`. Para IA, envie `"mode":"ai"` e uma imagem ou `description` não vazia. O novo `quality` aceita `quick` (padrão da API) ou `detailed`. `type` aceita texto livre de até 120 caracteres; `fidelity` vai de 0 a 100. Ollama indisponível retorna 503; plano inválido 502; timeout 504. Falhas na análise/base não criam projetos e não são convertidas em casas. Falha apenas nos detalhes devolve a base validada com aviso. O Nginx aguarda até 900 segundos.

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
4. Avaliar gerações reais, melhorar proporções e adicionar refinamento visual iterativo.
5. Adicionar vistas frente/trás/laterais e proveniência da interpretação.
6. Contas, autorização, migrações versionadas e PostgreSQL.

Detalhes: [contrato](docs/structure-format.md), [arquitetura](docs/architecture.md).

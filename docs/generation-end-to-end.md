# Revisão de geração ponta a ponta — 2026-10-07

Base revisada: `4317a5f`, depois dos PRs #1 e #2. Foram examinados backend,
frontend, imagens, geometria, schemas, persistência, renderização, Docker,
atualizador, testes e o fluxo de importação Fabric.

## Problemas confirmados e correções

- A geração prendia o navegador em uma requisição longa. Erros HTML de proxy
  apareciam apenas como “Não foi possível acessar a API”, sem estado recuperável.
  O site agora submete um job e acompanha estado/etapa em chamadas curtas.
- Recarregar a página perdia o acompanhamento. O ID fica no navegador; sucesso
  e falha ficam no SQLite. Reconexões não disparam outra inferência.
- Reinício da API podia deixar o usuário sem saber se o projeto foi salvo.
  Jobs interrompidos recebem erro explícito; um projeto já gravado recupera sucesso.
- A resposta inteira do Ollama só era recebida ao final. Agora são lidos eventos
  NDJSON, com indicação de que a IA começou a responder e validação somente após
  conclusão. Truncamento continua com uma tentativa compacta, sem usar JSON parcial.
- O teto de componentes era independente dos tokens realmente disponíveis.
  Ele agora diminui antes da primeira chamada quando o orçamento não comporta
  a quantidade original. O modo rápido também tem um reparo limitado para planos inválidos.
- Falhas opcionais preservavam a estrutura, mas ocultavam o motivo na interface.
  Agora avisos incluem a causa conhecida do Ollama. Falhas obrigatórias continuam
  sem fallback para uma casa ou outro assunto.
- `.env` com timeout acima de 900 impedia a API de iniciar. O limite agora é 7200,
  padrão 900. Isso permite mais espera em CPU lenta, sem prometer mais velocidade.
- API antiga e site novo com o mesmo número de versão não eram distinguidos.
  A capacidade `generationJobs` é verificada pela interface e pelo atualizador.

O JSON 1.0, Minecraft 1.21.1, mod Fabric 0.3.0, a paleta e os projetos existentes
permanecem compatíveis. Não foram alterados código Java nem algoritmos de colocação.

## Validação

- Baseline: 159 testes Python aprovados antes das alterações.
- Revisão: testes de jobs reais na API com inferência substituída cobrem texto,
  imagem Detalhado/Ultra, persistência, reinício, concorrência, erro e upload inválido.
- Testes NDJSON dividem bytes inclusive no meio de UTF-8/JSON; verificam conclusão,
  truncamento, eventos inválidos, erro de servidor e métricas.
- Chromium cobre demo real do upload à exclusão, preview, IA simulada,
  recarga da página, reconexão e apresentação de erro persistido.
- TypeScript/Vite compila a interface. O workflow `Photo2Craft checks` executa
  testes API/web, build Java 21 e smoke demo através de Docker/Nginx.

O ambiente de revisão não tem daemon Docker nem JDK 21. O download de JDK 21
foi bloqueado pela conexão; esses gates são executados pelo workflow no GitHub,
quando Actions está disponível. Consulte o resultado do commit, sem presumir aprovação.

**Não há acesso ao Ollama/GPU do usuário nem ao Minecraft em execução.** Os testes
simulados verificam o pipeline e seus erros, não a fidelidade visual do Qwen real,
o tempo de inferência no PC ou a colocação dentro de um mundo. É necessário executar
o smoke abaixo com o mesmo modelo e referência para fechar essa validação local.

## Atualizar e verificar

Obtenha a branch do PR (ou atualize `main` depois da integração). Não sobrescreva
seu `.env`. Na pasta do projeto:

```bash
docker compose up -d --build
docker compose ps
docker compose exec -T api python -m app.verify_installation
docker compose logs --tail=100 api
```

Abra a porta configurada em `WEB_PORT` e pressione Ctrl+F5. O site deve mostrar
etapas durante a geração e retomá-las após recarregar. O verificador confirma
API, suporte a jobs, configuração e presença do modelo; ele não executa inferência.

Com Python e `httpx` no computador:

```bash
python scripts/smoke_api.py --url http://localhost:8081 --mode ai --quality quick --description "Uma ponte de pedra com dois pilares e vão central"
python scripts/smoke_api.py --url http://localhost:8081 --mode ai --quality detailed --image sua-referencia.png
```

Adapte `8081` à sua porta. O script mostra o ID e as etapas, valida o JSON e exclui
somente a construção temporária que ele criou. Se `AI_TIMEOUT_SECONDS` for maior
que 900, passe também `--timeout` compatível. Depois gere uma construção pelo site
e use seu `/build import <id>` no Minecraft. Compare silhueta, proporções e partes
principais com a mesma referência; a nota heurística não substitui essa inspeção.

## Limites operacionais

Um processo Uvicorn e uma geração por vez. Jobs armazenam estados, não uma fila
distribuída ou checkpoint do modelo. Reiniciar o backend interrompe a geração;
recarregar apenas o navegador não interrompe. O endpoint síncrono legado continua
disponível, mas tem o limite de 960 s do Nginx. O novo frontend usa jobs.

Se a conexão cair durante o POST inicial antes de receber seu ID, a geração pode
continuar: confira a galeria. Nenhuma tentativa automática repete o POST. O sistema
recusa outro pedido enquanto o worker está ocupado.

Referências técnicas: [Ollama Chat](https://docs.ollama.com/api/chat) e
[Ollama Streaming](https://docs.ollama.com/api/streaming).

# Atualizar para Photo2Craft 0.5.0

Preserve a pasta e o projeto Docker da instalação atual. Banco e imagens continuam no mesmo volume.
Não use `docker compose down -v`. O contrato antigo continua aceito.

## Obter o código

Use o pacote `Photo2Craft-Ollama-0.5.0.zip` entregue nesta conversa. Extraia para uma pasta temporária
e copie o conteúdo de `photo2craft` para a pasta atual, preservando `.env`, dados, modelos e configuração local.
O pacote não inclui `.env`, banco, dependências nem pesos de modelos. Guarde uma cópia da versão anterior.
Não crie outro projeto Docker por engano: execute o atualizador na pasta usada pela instalação existente.

A branch de revisão é `feat/visual-refinement-0.5`. Se preferir instalar pelo Git:

```bash
git fetch origin
git switch feat/visual-refinement-0.5
```

## Atualizar API e site

Com Docker Desktop e Ollama abertos, no PowerShell da pasta do projeto:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\ATUALIZAR-OLLAMA.ps1
```

O script salva backup do `.env`, adiciona somente valores ausentes, preserva valores existentes,
recompila e verifica versão/modelo. Mantém o nome Docker `photo2craft`; se você usa outro, passe `-ProjectName NOME`.
A mensagem de sucesso indica Photo2Craft 0.5.0. Confira `release: ollama-local-0.5.0` em `/api/capabilities`.
Se o modelo indicado no `.env` não estiver instalado, a verificação informa o comando `ollama pull` correto.
Não troca silenciosamente seu modelo.

Linux/macOS, ou atualização manual na mesma pasta/projeto:

```bash
docker compose up -d --build
docker compose exec -T api python -m app.verify_installation
```

Sem Docker, ative sua venv, instale `apps/api/requirements.txt`, execute `npm ci` e `npm run build`
em `apps/web` e reinicie os processos. Há duas dependências novas obrigatórias: NumPy e OpenCV headless.
O backend permanece Python 3.12. Atualize a página com Ctrl+F5.

## Atualizar o mod

Use JDK 21, mantendo Fabric Loader/Fabric API para Minecraft 1.21.1:

```powershell
cd minecraft\mod
.\gradlew.bat test build
```

Linux/macOS: `./gradlew test build`. Com o jogo fechado, substitua o JAR antigo por
`build/libs/photo2craft-0.3.0.jar` na pasta `mods` (não use `-sources`). Guarde o antigo fora de `mods`.
Preserve mundos e `config/photo2craft.json`. A nova paleta exige esse mod; os projetos antigos continuam válidos.

## Primeiro teste

1. Gere uma referência clara em Detalhado + Médio.
2. Confira proporções, silhueta, portas/janelas/partes principais na comparação lado a lado.
3. Veja se houve correções aceitas e examine os avisos. Score indisponível significa comparação não concluída.
4. Importe em um mundo de teste com o comando exibido; confira rotação e `/build undo`.
5. Repita a mesma imagem com zero refinamentos para comparar antes/depois. Não aceite apenas a nota como prova.

Ultra não exige outro modelo. O depth model local é opcional, com instalação separada:
[dependências, pesos, Docker e fallback](docs/visual-refinement.md#profundidade-local-opcional).

# Instalar o Photo2Craft com Ollama — Windows

O Photo2Craft 0.4.0 usa **Ollama + Gemma 4 no seu computador**. Não precisa de chave, créditos ou assinatura de API. Com a configuração local indicada neste guia, a imagem permanece no PC. **As novas cores exigem atualizar o mod para 0.2.0.** O JAR anterior rejeita esses blocos.

## Atualização da versão anterior

Baixe **Photo2Craft-Ollama-0.4.0.zip**. Salve em Downloads com esse nome exato. Com Docker Desktop e Ollama abertos, execute no PowerShell:

```powershell
Expand-Archive -LiteralPath "$env:USERPROFILE\Downloads\Photo2Craft-Ollama-0.4.0.zip" -DestinationPath "$env:USERPROFILE\Documents" -Force
cd "$env:USERPROFILE\Documents\photo2craft"
Get-Content .\RELEASE.txt
powershell -NoProfile -ExecutionPolicy Bypass -File .\ATUALIZAR-OLLAMA.ps1
```

O script usa o projeto Docker `photo2craft`, o mesmo da instalação anterior. Se seu projeto tiver outro nome, passe `-ProjectName nome` para preservar seu volume. Ele verifica os arquivos da versão, faz backup do `.env`, atualiza apenas os parâmetros do Ollama e conserva as portas existentes. Sem `.env`, cria um novo a partir de `.env.example` com porta 8081.

Depois recompila sem cache, recria os contêineres, verifica a versão realmente executada, consulta os modelos instalados no Ollama e confirma a resposta através da porta do site. Falhas interrompem o script; não há mensagem de sucesso caso a instalação esteja errada. O script não apaga volumes, não gera construções e não recompila o mod.

O final esperado é `CONFIRMADO: Photo2Craft 0.4.0 / Ollama / gemma4:e2b`. Abra o endereço indicado e pressione Ctrl+F5. Em `/api/capabilities`, confira `"release":"ollama-local-0.4.0"`.

Se a conexão com Ollama falhar, configure `OLLAMA_HOST` e reinicie o Ollama conforme o passo 2 abaixo. Rode novamente o script após corrigir.

### Atualizar o mod (obrigatório para novas cores)

Feche o Minecraft/servidor. No PowerShell:

```powershell
cd "$env:USERPROFILE\Documents\photo2craft\minecraft\mod"
.\gradlew.bat --version
.\gradlew.bat clean build --no-daemon
```

O Gradle deve indicar **Java 21**, como na instalação que já funcionava. Após `BUILD SUCCESSFUL`, use `build\libs\photo2craft-0.2.0.jar` (não `-sources`). Mova o JAR antigo para uma pasta de backup fora de `mods` e coloque o novo em `mods` do perfil Fabric 1.21.1 ou do servidor. Não mantenha ambos. Preserve Fabric API, `config/photo2craft.json` e seus mundos.

Se só quiser avaliar a prévia no site, pode testar antes de atualizar o mod; não importe cores novas com o JAR antigo.

### Comparar fidelidade

1. Abra o site e pressione Ctrl+F5; confira 0.4.0.
2. Escolha **IA → Detalhado → Grande**, prioridade da referência 95, sem interior para objetos/veículos.
3. Envie uma referência nítida, com o objeto grande e pouco fundo. Descreva as características que não podem sumir, sem exigir dimensões cúbicas para um objeto comprido.
4. Aguarde. Há 3 consultas locais, até 4 com correção; o relógio mostra tempo, não progresso.
5. Veja a prévia e abra **O que a IA identificou na referência**. Se a análise estiver errada, esclareça o assunto/proporções no texto e gere outra construção.
6. Confira se aparece **Forma + detalhes aplicados** ou um aviso de refinamento incompleto. O resultado anterior continua salvo, permitindo comparação.

Não é prometida uma porcentagem de semelhança. O código foi testado com respostas simuladas; a qualidade real do Gemma e a velocidade precisam ser avaliadas no seu computador. Para mais definição, teste Personalizado com 64 por eixo, respeitando o teto de 50 mil células. Isso aumenta resolução, mas não corrige uma interpretação errada da foto.

## Instalação manual ou primeira instalação

## 1. Atualizar o projeto sem perder dados

Extraia o novo ZIP e copie o conteúdo da pasta `photo2craft` para:

```text
C:\Users\Usuario\Documents\photo2craft
```

Aceite substituir o código, mas preserve seu arquivo `.env`. O ZIP não contém `.env`, banco nem imagens de projetos. Continue usando a mesma pasta/nome do projeto Compose para manter o volume `photo2craft_photo2craft-data`. Nunca execute `docker compose down -v`.

## 2. Instalar e liberar o Ollama para o Docker

1. Baixe e instale o Ollama para Windows em <https://ollama.com/download/windows>.
2. Feche o Ollama pelo ícone próximo ao relógio, se ele tiver aberto sozinho.
3. Abra o PowerShell normal e execute:

```powershell
setx OLLAMA_HOST "0.0.0.0:11434"
```

4. Abra o Ollama novamente pelo menu Iniciar. Se o Firewall do Windows perguntar, permita somente em **redes privadas**. Essa configuração é necessária para o contêiner Docker alcançar o Ollama no Windows.
5. Abra um novo PowerShell e confira:

```powershell
ollama --version
Invoke-RestMethod http://localhost:11434/api/tags
```

## 3. Baixar o Gemma 4

O download é feito uma única vez e ocupa vários gigabytes:

```powershell
ollama pull gemma4:e2b
ollama run gemma4:e2b "Responda somente: OK"
```

Na primeira execução o modelo pode demorar para carregar. O modelo `e2b` foi escolhido por ser visual e menor; na RX 6600, o Ollama pode usar Vulkan e também compartilhar trabalho com a RAM/CPU.

## 4. Configurar o Photo2Craft

Abra seu `.env`:

```powershell
cd C:\Users\Usuario\Documents\photo2craft
notepad .env
```

Mantenha `WEB_PORT=8081` se essa é sua porta atual. Remova as linhas antigas `OPENAI_API_KEY` e `OPENAI_MODEL`, ou deixe-as — esta versão as ignora. Adicione:

```dotenv
AI_PROVIDER=ollama
OLLAMA_URL=http://host.docker.internal:11434
OLLAMA_MODEL=gemma4:e2b
AI_TIMEOUT_SECONDS=600
AI_MAX_OUTPUT_TOKENS=16000
AI_CONTEXT_TOKENS=16384
```

Salve e feche.

## 5. Recriar o site e a API

```powershell
docker compose up -d --build
docker compose ps
```

Teste se o contêiner alcança o Ollama:

```powershell
docker compose exec api python -c "import urllib.request; print(urllib.request.urlopen('http://host.docker.internal:11434/api/tags').status)"
```

O resultado esperado é `200`. Depois abra <http://localhost:8000/api/capabilities>; deve aparecer `"aiProvider":"ollama"` e `"aiModel":"gemma4:e2b"`.

## 6. Fazer o primeiro teste

Abra <http://localhost:8081> (ou sua `WEB_PORT`) e pressione **Ctrl+F5**. Escolha **IA**, tamanho pequeno e teste primeiro somente com texto:

```text
Uma ponte medieval de pedra com dois arcos abertos, pilares grossos e piso de madeira. Não crie casas nem terreno.
```

A primeira geração é a mais lenta porque o modelo entra na memória. Aguarde sem clicar várias vezes. Depois confira a prévia e use `/build import ID` no Minecraft.

## Problemas comuns

- **Não conecta ao Ollama:** confirme que ele está aberto, repita o passo `OLLAMA_HOST`, feche e abra o Ollama e teste `/api/tags`.
- **Modelo não instalado:** execute `ollama pull gemma4:e2b`.
- **Muito lento:** feche jogos e programas pesados, use tamanho pequeno e descrição objetiva. Confira `ollama ps` durante a geração.
- **Erro de memória:** feche jogos e programas pesados. O detalhado solicita 16.384 tokens de contexto e pode consumir mais memória/usar CPU. Tente o modo Rápido. Também pode reduzir `AI_CONTEXT_TOKENS=8192` no `.env` e executar `docker compose up -d --force-recreate api`; isso reduz a margem para manter os detalhes no contexto.
- **Plano fora dos limites:** peça menos detalhes ou use tamanho maior. Não existe fallback automático para uma casa.
- **Firewall:** permita a porta somente na rede privada; não exponha a porta 11434 na internet.

## Limites reais

O Gemma 4 local é gratuito, mas tende a ser menos preciso que modelos pagos. A saída continua sendo uma aproximação geométrica em blocos e uma imagem não revela os lados ocultos. O compilador valida paleta, dimensões, quantidade de blocos e formas antes de salvar qualquer projeto.

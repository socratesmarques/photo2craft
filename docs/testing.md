# Validação desta entrega

## Executado no ambiente de desenvolvimento

- **API: 112 testes aprovados.** Incluem os casos anteriores e o fluxo detalhado: análise → proporções → base → detalhes, espelhamento, novas cores, prioridade da referência, correção limitada, prazo global, preservação da base e avisos de refinamento rejeitado. O Ollama é simulado. Não foi realizado benchmark de semelhança, nem demonstrada melhora visual com o Gemma real neste ambiente.
- **Frontend:** `npm ci` executado do zero contra o registro oficial, seguido de TypeScript e `vite build`, todos aprovados. O lockfile usa apenas versões publicadas. Prévia Three.js separada em um chunk carregado sob demanda.
- **Navegador: 3 testes Playwright incluídos, não concluídos nesta revisão.** O Chromium local está incompleto e encerrou antes de abrir as páginas; nenhuma asserção de interface foi executada nesta revisão. O fluxo demo usa a API real: upload → geração → prévia WebGL → JSON com 1.573 células → galeria → exclusão. O fluxo IA usa a API simulada e verifica pedido por texto, tipo livre, prévia e simplificações. O terceiro reproduz a resposta da API antiga enviada pelo usuário e verifica a mensagem de atualização. Desktop 1440 px e celular 390 px.
- **Núcleo Java: 5 testes JUnit aprovados em revisão anterior**. Foi acrescentado um sexto teste para as novas cores; os 6 testes e o build do mod 0.2.0 ainda precisam ser executados com Java 21 no PC Windows. O runtime Java padrão deste ambiente é 17. A alteração do mod nesta entrega é a versão e a paleta empacotada; o código de colocação não mudou.
- **Compose:** configuração revisada; contêineres não executados neste ambiente.
- **Gradle Wrapper:** gerado com Gradle 8.12, scripts Unix/Windows e wrapper JAR incluídos.

## Limitações de validação

A compilação completa pelo Fabric Loom não pôde ser concluída neste ambiente. Após resolver dependências localmente, Loom 1.9.2 falhou em `CurrentPlatform.isUnixDomainSocketsSupported` com `java.net.SocketException: Operation not permitted`. Isso acontece durante a configuração da ferramenta, antes da compilação do código do mod. O ambiente também não permitiu a conexão de rede direta do Gradle.

**Não há JAR final de mod compilado nesta entrega.** O código-fonte, dependências e wrapper estão incluídos para executar `./gradlew build` ou `.\gradlew.bat build` com Java 21 e internet em uma máquina local. O funcionamento dentro do mundo Minecraft ainda precisa de validação. Não foi iniciado servidor nem aceito EULA automaticamente.

Docker e PowerShell não estão instalados no ambiente de geração; os Dockerfiles, Compose e script Windows foram revisados, mas o build dos contêineres e a execução do script precisam ser validados no PC Windows. Os testes Python verificam a lógica de diagnóstico usada dentro do contêiner com respostas simuladas.

## Checklist local obrigatório

1. Na raiz, executar `docker compose up -d --build`.
2. Verificar `docker compose ps`, abrir site e Swagger; API deve ficar saudável.
3. Criar uma construção e reiniciar os contêineres: projeto e imagem devem permanecer.
4. Com Java 21, executar `./gradlew test build` na pasta `minecraft/mod`.
5. Instalar o JAR e Fabric API para 1.21.1 em um perfil Fabric. Abrir mundo criativo novo, com comandos.
6. Em terreno plano e área livre, testar `/build test`. O piso nasce na altura dos pés, deslocado +3 em X/Z.
7. Gerar uma casa no site e executar `/build import ID`. Conferir nome, dimensões, materiais e progresso.
8. Desfazer e testar importação com rotações 90/180/270. Conferir orientação de estados usando JSON com `oak_log` ou `spruce_stairs`.
9. Executar `/build cancel` durante uma estrutura grande, depois `/build undo`. Confirmar interrupção e restauração.
10. Alterar um bloco manualmente após construir e executar undo: alteração posterior deve ser preservada.
11. Testar área ocupada, inventário/baú, chunk não carregado, borda e limite vertical. Deve rejeitar ou parar com mensagem sem forçar chunks.
12. Desligar API e testar importação; testar ID inexistente, JSON inválido e versão incompatível. O servidor deve continuar respondendo.
13. Em servidor de teste, jogador sem OP não deve poder executar comandos. Conferir orçamento global com dois operadores e `blocksPerTick=50`.
14. Em mundo descartável, habilitar `replaceExisting` e conferir substituição/undo; nunca começar esse teste em um mundo importante.

## Repetir os testes automatizados

Consulte os comandos do README. O teste de navegador inicia serviços nas portas 8000 e 5173 e precisa dessas portas livres. Os dados dele ficam separados em `apps/web/.e2e-data` e o projeto temporário é removido ao terminar. A imagem de teste é uma cor sólida: testa transporte/geração em modo demo. O Ollama é desativado no teste do fluxo real e simulado no teste da interface de IA; a validação final do modelo exige instalar o Gemma 4 localmente.

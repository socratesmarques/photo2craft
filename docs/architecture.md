# Decisões de arquitetura

## Limites de responsabilidade

A interface envia `multipart/form-data` com opções e imagem opcional no modo IA. `RequestSizeLimit` limita inclusive uploads sem Content-Length. Pillow verifica formato, pixels e animação, orienta pelo EXIF e reencoda em JPEG sem metadados. O nome original do arquivo nunca compõe um caminho.

`ProceduralGenerator` implementa `StructureGenerator`. A assinatura recebe uma lista de imagens para permitir múltiplas vistas no futuro; o endpoint atual aceita somente uma. O modelo da API já devolve `sourceImages` com o papel `reference`.

`BuildRepository` isola SQLAlchemy. O JSON é armazenado transacionalmente no banco. Imagens ficam em `data/images/{uuid}/`. Há limpeza compensatória se falhar a gravação no banco. A lista retorna metadados; a estrutura é obtida sob demanda. Exclusão é limitada ao UUID resolvido pelo repositório.

O limite de gerações e o lock de quota são por processo. Use **um processo Uvicorn** neste MVP. Não escale múltiplos workers antes de mover quota e jobs para coordenação no banco/fila. Listagem ainda lê JSON dos registros; em grande escala, mova os metadados para colunas próprias.

## Mod

- `StructureCodec`: contrato, limites, coordenadas, paleta e estados.
- `ApiClient`: HTTP fora do tick, timeout, sem redirects e limite enquanto recebe bytes.
- `BuildQueue`: somente thread do servidor; orçamento global compartilhado entre jobs, validação prévia incremental e colocação incremental. Não força carregamento de chunks.
- `Photo2Craft`: comandos, autorização, ciclo do servidor e importações pendentes.
- `ModConfig`: configuração validada com limites máximos defensivos.

Antes de colocar qualquer bloco, a fila verifica toda a região declarada célula por célula. Na colocação verifica novamente se o bloco original mudou. Se a área mudar durante a execução, pode haver colocação parcial; o histórico permite desfazer. A fila é FIFO e pode priorizar o primeiro job até concluir. Não há promessa de 500 blocos por tick se há falha ou validação; 500 é o teto global.

As notificações de vizinhos são limitadas para evitar cascatas de atualização. A paleta usa predominantemente blocos estáticos; adicionar física, redstone, água ou blocos com NBT exige rever essa estratégia e os testes.

## Futuro preview no Minecraft

Introduzir uma `PlacementSession` com estrutura validada, origem e rotação. O comando de importação preencherá essa sessão; somente confirmar enviará um job à fila. O cliente renderizará um holograma a partir da sessão e enviará solicitações de movimento/rotação. A autoridade continuará no servidor, que deverá revalidar dimensão, distância, área e permissão ao confirmar. Nenhum protocolo ou holograma está implementado nesta versão.

## Visão e geração livre — versão 0.4.0 / Ollama

`AIGenerator` envia a referência normalizada (máximo 1280 px por lado), o pedido e os limites para a API local `/api/chat` do Ollama com JSON Schema. O Gemma 4 recebe texto e imagem e produz somente dados. O rápido usa uma tentativa, timeout e limite de 2 MiB por resposta.

`quality=detailed` delega a `detailed_generator`: `ReferenceStudy` estima proporções e características, depois `PartBatch` gera a forma principal em uma caixa dimensionada no código, e outro `PartBatch` adiciona detalhes. Cada lote tem até 48 peças nomeadas, com espelhamento opcional X/Z. `Assembly` permite até 192 peças expandidas, mantendo limites de trabalho/blocos. Pirâmides não podem ser espelhadas no eixo da ponta; linhas refletem os extremos sem reordenar. Geometria inválida pode ser corrigida uma única vez. São até quatro consultas, sob um prazo global compartilhado; não há reenvio infinito. Saída usa `think=false` e até 2.400/12.000/10.000 tokens por etapa, sempre limitada também pela configuração do usuário.

O refinamento só é aplicado se compilar nos limites e não substituir/apagar mais que max(32,35% dos sólidos existentes), nem adicionar mais que max(256,60% dos sólidos existentes). Caso contrário, retorna a base com aviso explícito. Esses limiares são heurísticas de preservação, não métricas de semelhança. A análise, etapas concluídas e avisos são guardados junto dos metadados do projeto. O frontend começa em Detalhado/Grande; o default da API é rápido para manter compatibilidade com clientes antigos. A prioridade ≥75 com imagem sobrepõe o estilo no modo detalhado.

`Blueprint` descreve dimensões, resumo, suposições e até 64 formas ordenadas: caixa, elipsoide, cilindro, pirâmide, telhado triangular e linha. O Gemma recebe `think=false` para dedicar a saída ao JSON e é orientado a usar 8–48 peças maiores. O compilador `compile_blueprint` preenche as formas, aplica recortes de ar e emite o mesmo `Structure` 1.0 consumido pelo mod. Limita o trabalho a 6 milhões de posições candidatas e o resultado a `MAX_BLOCKS`. Não aceita blocos fora da paleta, coordenadas inválidas ou dados executáveis.

Posições omitidas são preservadas. Formas ocas emitem ar dentro da casca; partes posteriores sobrescrevem as anteriores. Isso permite vãos de ponte, cascos, torres, silhuetas orgânicas aproximadas e combinações livres, mas há limitações de geometria, paleta, detalhes e qualidade do modelo. Não há reconstrução multivista nem otimização por comparação de render.

O modo IA nunca cai automaticamente no procedural quando o Ollama falha. A demo é uma escolha explícita. O endpoint de capacidades informa provedor e modelo configurados; a conexão real é validada na geração.

Proveniência, resumo e suposições são guardados em `BuildRecord.options`, evitando migração de banco. Projetos antigos continuam legíveis. O contrato continua 1.0; a paleta passa a conter todos os concretos coloridos e exige mod 0.2.0. O Gradle inclui `shared/block-palette.json` no JAR. O registro mantém os blocos finais e os metadados da análise, não o plano geométrico completo.

Referências de implementação: [visão no Ollama](https://docs.ollama.com/capabilities/vision), [saídas estruturadas](https://docs.ollama.com/capabilities/structured-outputs), [Gemma 4](https://ollama.com/library/gemma4) e [suporte de hardware](https://docs.ollama.com/gpu).

## Contas e PostgreSQL

`owner_id` já existe como coluna anulável, mas não é usado como autorização. Para contas reais: adicionar usuários/sessões, preencher owner_id e filtrar todas as consultas, imagens, downloads e exclusões por propriedade/visibilidade. O mod precisará de um token revogável por usuário ou projeto. O ID não deve virar mecanismo de autenticação.

Para PostgreSQL: instalar `psycopg[binary]`, configurar `DATABASE_URL=postgresql+psycopg://...`, introduzir Alembic e migrar os registros e arquivos. Os modelos evitam SQL específico de SQLite; `create_all` só inicializa esquema novo, não é um sistema de migrações. O Compose entregue usa apenas SQLite.

## Operação

Manter cópia conjunta do banco e das imagens. Para uma cópia consistente de SQLite, pare a API antes de copiar o volume ou use a API de backup SQLite, considerando WAL. Restaurar os dois juntos evita referências a imagens ausentes. Não versionar `data`, `.env` ou tokens.

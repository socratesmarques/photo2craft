# Decisões de arquitetura

## Limites de responsabilidade

A interface envia `multipart/form-data` com opções e imagem opcional no modo IA. `RequestSizeLimit` limita inclusive uploads sem Content-Length. Pillow verifica formato, pixels e animação, orienta pelo EXIF e salva referência PNG sem perda adicional, sem metadados do upload (miniatura JPEG). O nome original do arquivo nunca compõe um caminho.

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

## Visão e geração livre — versão 0.5.0

O roteador `AIGenerator` preserva o modo rápido (`ai_generator.py`) e o planejador textual legado
(`detailed_generator.py`). Imagem + Detalhado/Ultra usa `visual_generator.py`.
O processamento e os renderizadores usam o mesmo catálogo visual; o contrato final e o mod usam a mesma allowlist.

Plano e correções possuem schemas próprios (`scene_plan.py`) e nunca são usados como código.
Cada candidato é compilado e validado antes de renderizar. Cada render é avaliado independentemente;
regressão ou falha conserva a versão com maior nota. Sem nota válida, preserva a geometria inicial validada.
Os metadados novos ficam em `BuildRecord.options._generation`, sem migração destrutiva de banco.
O render final fica junto à referência e tem endpoint próprio. Planos intermediários completos só são salvos em debug.
O frontend continua lendo o mesmo JSON de blocos que o Fabric importa.

Mapeamento dos arquivos, pesos da avaliação, limites e casos de fallback: [Visual Refinement](visual-refinement.md).

Os orçamentos, compactação, logging e recuperação compartilhados estão em `ollama_session.py`.
Detalhes da revisão: [fidelidade/Ollama](ollama-fidelity-review.md).

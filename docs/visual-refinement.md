# Photo2Craft 0.5.0 — Visual Refinement

Implementação incremental sobre 0.4.0. O contrato exportado permanece **1.0**;
SQLite, projetos anteriores, demo, JSON importado e comandos Fabric são preservados.
A aceitação visual em fotografias reais ainda exige teste com Ollama no computador do usuário.

## Pipeline e arquivos

| Etapa | Implementação | Resultado |
| --- | --- | --- |
| Upload | `images.py`, `main.py` | Limites de bytes/pixels, EXIF removido, transparência sobre branco |
| Evidência objetiva | `visual_analysis.py` | OpenCV: bbox, proporção projetada, centro, bordas, linhas, simetria, cores e luminosidade |
| Análise e plano | `visual_generator.py`, `scene_plan.py` | Assunto, dimensões relativas, câmera estimada e componentes identificados |
| Materiais | `materials.py`, `shared/block-visuals.json` | Filtro semântico + CIE76 Delta E em Lab + penalidade de textura |
| Geometria | `blueprint.py`, `scene_plan.py` | Primitivas determinísticas, espelhamento condicionado, limites existentes |
| Render | `voxel_render.py` | Render ortográfico em CPU, 384×384, somente faces expostas |
| Comparação | `visual_score.py`, Ollama | Referência e render enviados juntos; avaliação independente da proposta de correção |
| Correção | `apply_corrections` | Até 12 alterações locais por rodada; adição, substituição, remoção, redimensionamento global |
| Escolha | `generate_visual` | Guarda plano/estrutura/score melhores; regressão, JSON inválido ou falha mantém a versão anterior |
| Interface | `App.tsx`, `Preview.tsx`, `Comparison.tsx` | Comparação, sobreposição, câmera, etapas concluídas, tempo e nota |

Uma imagem sempre prevalece sobre texto e estilo. O texto pode selecionar o assunto e excluir o fundo.
Os números geométricos são produzidos pelo planejador, mas cada bloco é calculado por código.
O modelo nunca escreve código nem milhares de células individuais. Partes não observadas são estimadas.

## Qualidade

| Modo | Com imagem | Limite de correções | Chamadas normais máximas* |
| --- | --- | --- | --- |
| Rápido | Evidência OpenCV + blueprint simples | 0 | 1 |
| Detalhado | Estudo, plano, render, avaliação, correção e nova avaliação | 2 | 7 |
| Ultra | Mesmo fluxo + profundidade opcional | 3 | 9 |

\* Pode ocorrer **uma** consulta extra para reparar o plano inicial. O ciclo termina antes se não houver
problemas, atingir nota 93, receber correção vazia, regredir ou esgotar o tempo. Número máximo configurado
pelo usuário só reduz o limite do modo. Sem imagem, Detalhado/Ultra preservam o planejador textual em etapas
anterior, sem inventar nota de fidelidade visual. O rápido não usa o novo ScenePlan de materiais por componente.

O contexto permanece em 16.384 tokens para o pipeline detalhado. Não foi aumentado.
Todas as chamadas compartilham `AI_TIMEOUT_SECONDS` (600 por padrão). Uma rodada usa
uma chamada para corrigir e outra para avaliar: não é repetir o mesmo prompt.
A referência é redimensionada e codificada uma vez por geração; a melhor avaliação e render são reutilizados.
Não existe cache persistente de inferências entre projetos nesta versão.

## Avaliação e rollback

Com máscara de primeiro plano confiável, usa IoU da silhueta centralizada, proporção projetada e
comparação de distribuições de cores em Lab. Com máscara incerta, usa estimativas do modelo também
nesses três itens. Presença/posição dos componentes e detalhes são sempre avaliações do modelo.
Pesos: silhueta 35%, proporção 25%, cor 15%, estrutura 15%, detalhes 10%.
A câmera permanece fixa entre candidatos. Aceita melhoria maior que 0,25 ponto; caso contrário mantém
`best_structure`/`best_score` e encerra para evitar gasto repetitivo. Sem avaliação válida, score é `null`.
Não há porcentagem científica, garantia de melhoria humana nem reconstrução perfeita.

A segmentação utiliza cor do contorno ou GrabCut com retângulo; **não é segmentação semântica**.
Fundos complexos, sombras, reflexos e objetos encostando nas bordas podem confundir essa estimativa.
O modo Cena completa preserva a imagem inteira como referência, sem alegar segmentação de objeto.
A proporção 2D observada auxilia o modelo, mas não é imposta como proporção 3D.

## Paleta e mod

166 IDs permitidos, contando ar. Concretos, pós, terracotas, lã, madeiras, pedras, cobre encerado,
vidros e painéis, além de musgo. A seleção automática evita blocos sujeitos à gravidade e reserva
terracota esmaltada para detalhes cerâmicos. Escadas e painéis permanecem na allowlist para projetos
importados, mas a seleção automática usa blocos inteiros até o render representar seus estados reais.
Pós continuam disponíveis no contrato para uso explícito.
Água corrente não é adicionada automaticamente; superfícies de água podem ser aproximadas com vidro.
RGBs são **aproximações curadas**, não medidas de todas as texturas do jogo; essa é uma limitação conhecida.
O render CPU mostra vidro/escadas/painéis pela caixa cúbica; o preview 3D usa transparência aproximada.
Texturas e estados especiais ainda podem diferir do jogo.

`block-palette.json` é a allowlist de estados compartilhada com o JAR; `block-visuals.json` é o catálogo
visual compartilhado entre backend e navegador. Recompile e instale **mod 0.3.0** antes de importar os novos blocos.
O contrato 1.0 anterior continua aceito. Não houve alteração do protocolo de download/colocação.

## Profundidade local opcional

Escolha: [Depth Anything V2 Small](https://github.com/DepthAnything/Depth-Anything-V2), variante
[Small-hf](https://huggingface.co/depth-anything/Depth-Anything-V2-Small-hf), modelo Small sob Apache-2.0.
O mapa é **profundidade inversa relativa**, não metros; não revela partes ocultas.
A malha 8×8 normalizada auxilia o estudo de volumes/recuos, sem criar geometria 3D métrica automaticamente.

Instalação sem Docker, na venv do projeto:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r apps/api/requirements-depth.txt
python scripts/install_depth.py
```

Copie o `DEPTH_MODEL_PATH` exibido para `.env` e reinicie a API. O download só ocorre nesse comando
explícito. Geração usa arquivos locais, sem código remoto, processo CPU separado e timeout de 45 segundos;
a memória do modelo é liberada antes das consultas ao Ollama. Dependências e pesos não são obrigatórios.

Docker: baixe o modelo em `models/depth-anything-v2-small` com o script acima, configure
`INSTALL_DEPTH=true` e `DEPTH_MODEL_PATH=/srv/photo2craft/models/depth-anything-v2-small` no `.env`,
então recompile. O diretório `models` é montado somente para leitura. Desativar é deixar o caminho vazio.
Se não houver modelo/dependências, falhar ou expirar, o Ultra continua com planejamento visual e aviso.
A execução do modelo real não foi validada neste ambiente.

## Múltiplas vistas

O gerador aceita uma lista de imagens, marca a primeira como vista principal e envia as demais como
restrições adicionais. A câmera e a avaliação automática se referem à primeira. A API/interface ainda
aceitam **uma imagem por projeto**; armazenamento/UI multiview completo fica para uma próxima versão.
Não há triangulação, calibração de câmeras ou fusão de profundidades nesta versão.

## Diagnóstico e benchmark

`VISUAL_DEBUG=true` salva arquivos em `DATA_DIR/debug/<id>`: referência reduzida, máscara, bordas,
mapa de profundidade quando disponível, estudo, planos, estrutura inicial/final, renders, correções e scores.
O padrão é desligado. Excluir um projeto exclui também seus arquivos de debug; tentativas que falham
antes de salvar um projeto podem deixar diagnóstico para inspeção manual.

```bash
python scripts/benchmark_visual.py --references benchmarks/references --quality detailed --size medium
python scripts/benchmark_visual.py --references benchmarks/references --quality detailed --refinements 0 --size medium
python scripts/benchmark_geometry.py
```

Coloque suas imagens fixas em `benchmarks/references`. Cada execução produz `results.json`, HTML comparativo,
referências, renders e estruturas. Registra hash da referência, versão/modelo, opções, dimensões, tempos e notas.
O script exclui os projetos temporários da API ao terminar; use `--keep-projects` para preservá-los.
Compare também com os resultados anteriores: scores sozinhos não satisfazem a aceitação visual.

## Limites e próxima etapa

32/48/64 são os limites dos novos presets IA, não cubos obrigatórios. Demo conserva seus tamanhos antigos.
Nenhum limite de API/mod foi ampliado: 64 por eixo e 50.000 células, 8 MiB de JSON, por padrão.
O usuário ainda precisa importar com `/build import ID`; envio automático ao mundo não foi acrescentado.
Status são etapas realmente concluídas no resultado; durante a geração síncrona há somente o contador de tempo.
Próxima etapa prioritária: benchmark humano com casa/igreja/carro/castelo/personagem/objeto reais,
calibração do score, recorte manual/segmentação semântica e render com texturas/estados reais do Minecraft.
Só depois reavaliar 96/128, múltiplas vistas completas e reconstrução mais precisa.

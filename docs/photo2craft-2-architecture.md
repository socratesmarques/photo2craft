# Arquitetura Photo2Craft 2.0

## Fluxo principal

1. `POST /api/generations`: valida uploads/opções, admite até 4 trabalhos em espera/execução
   e retorna 202 com ID. Até 4 referências, 5 MiB por imagem e 8 MiB por requisição por padrão.
2. `jobs.py`: worker único fora do loop ASGI; status/eventos no SQLite, consultados por
   `GET /api/generations/{id}`. Recarregar a página recupera o ID via localStorage.
3. Pillow normaliza orientação/remove metadados. PNG sem perda para inferência, lado
   maior 1280 (1536 Ultra); OpenCV usa cópia de até 768. Imagens originais normalizadas
   são guardadas para comparação. A primeira referência determina a câmera.
4. `GeminiProvider` solicita `ArchitecturalStudy`: proporções reais estimadas, estilo,
   pavimentos, silhueta, câmera, elementos a preservar e desconhecidos. Sem imagem,
   gera planejamento textual e não atribui fidelidade visual.
5. `ArchitecturalPlan` 2.0: paleta curta + elementos + relações espaciais + evidência por
   elemento. Dimensões vêm das proporções normalizadas uniformemente, nunca do bbox 2D.
6. Validação Pydantic e compilador: bounds, materiais/estados, referências, colisões
   declaradas, operações, orçamento de trabalho/células e conectividade com a base.
7. Render CPU; avaliação só se câmera/perspectiva forem consideradas comparáveis.
   Compara referência primária e render da mesma câmera, sem supor calibração exata.
8. Até `MAX_REFINEMENT_PASSES` (2 padrão), máximo 6 alterações locais por rodada.
   Cada candidato passa por validação, compilação e avaliação. Mantém melhor geometria;
   regressão ou ausência de melhora encerra. Quota/falha no refinamento guarda geometria
   válida com aviso, pendente de revisão; nunca apresenta score ausente como sucesso visual.
9. Site recebe prévia em `/preview`, altera materiais ou solicita nova versão refinada.
   Aprovação é vinculada ao SHA-256 exato da estrutura. Rejeição bloqueia exportação.
10. `/structure` serve somente projetos aprovados (ou legados prontos). Mod recebe
    **uma** estrutura 1.0 em uma requisição, valida e constrói por tick. Nenhum novo
    protocolo ou lista de chamadas por bloco foi introduzido.

## Schema e geometria

Schema gerado: `shared/architecture.schema.json`. Não confundir schema arquitetônico
2.0 com o contrato final Minecraft 1.0, que continua intacto. API para consultar plano:
`GET /api/builds/{id}/architecture`. Planos novos são sempre persistidos no banco, sem
precisar de debug. `migrate_scene` converte ScenePlan sem espelhamento explícito;
se houver mirror, exige expansão antes da migração. Dados antigos de blocos são lidos
sem conversão/destruição; projetos sem plano não permitem edição arquitetônica.

Elementos: volumes, fundações, paredes, pisos, telhados, torres, colunas, arcos,
sacadas, escadas, portas/janelas, cercas e detalhes. Primitivas: cuboide, elipsoide,
cilindro, pirâmide, gable, linha, arco e escada. Volumes irregulares são combinações
explícitas. Telhado plano = painel; inclinado = gable; quatro águas = pirâmide.
`axis` determina orientação da primitiva; degraus ascendem no eixo positivo x/z.
Curvas são discretizadas. Não há reconstrução arbitrária de meshes ou spline.

Operações: add, cut (ar explícito), paint (sólidos existentes). `overlaps` aponta
IDs anteriores que podem ser alterados; conflito de material não declarado é erro.
Conectividade por faces a y=0 rejeita componentes flutuantes; balanços ligados ao
corpo são aceitos. Estruturas flutuantes intencionais não são aceitas nesse pipeline.
Relações de caixas são validadas; não substituem análise estrutural de engenharia.

Paleta usa allowlist Minecraft 1.21.1 compartilhada com o mod; não escolhe blocos de
gravidade. Respeita transparência desativada. Estados explícitos são validados e
exportados, e o mod aplica rotação nativa. Render/Three.js ainda mostram envelopes
cúbicos aproximados para estados especiais/escadas/painéis. Para a geração, o prompt
prefere blocos completos e geometria de degraus; sem texturas ou iluminação do jogo.

## Persistência, cache e concorrência

Mantido BuildRecord/SQLite; estado novo em options, sem alteração destrutiva de coluna.
Render de material editado é salvo com nome por hash antes de publicar estrutura e
ponteiro no mesmo commit do banco. Falha de commit preserva prévia anterior; versões
de PNG não referenciadas ficam na pasta até excluir o projeto (sem coletor dedicado).
Tabela aditiva generation_jobs guarda eventos/status. Crash/restart marca jobs em
execução/espera como interrompidos; não reinicia chamadas que podem ter consumido cota.
Não é fila distribuída: mantenha **um worker Uvicorn e uma instância da API**.
Admissão limitada evita uploads ilimitados em memória. Histórico limitado a 200 jobs.

Cache em DATA_DIR/cache: SHA-256 de imagens normalizadas, opções, provedor/modelo,
limites e versão do pipeline. Nome não altera geometria. Reutilização recebe outro
ID/data e exige aprovação novamente. Falhas/avisos não são cacheados. Até MAX_PROJECTS
entradas; não armazena credenciais. Tokens históricos de um cache não são contabilizados
como nova chamada. Limpeza de cache é permitida sem apagar projetos.

Geração síncrona `/api/generate` permanece para scripts antigos, ainda sujeita ao timeout
HTTP do cliente. UI nova utiliza jobs. `/api/builds` com JSON importado mantém contrato
legado; não oferece garantia de autenticidade/assinatura nem de aprovação externa.

## Limites e segurança

Máximos iniciais: 50.000 células incluindo ar, dimensão 64, trabalho geométrico
6.000.000 operações estimadas. Configuração permite até 100.000 células/dimensão128;
tamanho custom de frontend/options ainda limita 64 para preservar contratos. Planos
não executam código, comandos, NBT, URLs ou entidades. API continua local, sem contas/
autenticação. Bind padrão 127.0.0.1; uma instalação compartilhada/pública precisa de
controle de acesso externo. Aprovação é um controle de fluxo local, não autenticação.

O mod mantém Minecraft 1.21.1, Fabric, Java21 e versão0.3.0; sem mudanças de fontes.
Download limitado, sem redirects, ID validado, coordenadas/estados checados, permissão
nível2, área/chunks/limites do mundo verificados, cancel/undo preservados. Confirmação
de recebimento/construção aparece no jogo; não há telemetria de conclusão de volta ao site.

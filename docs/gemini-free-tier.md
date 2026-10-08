# Gemini gratuito — verificação em 2026-10-08

Modelo padrão escolhido: **gemini-3.8-flash**, configurável por `GEMINI_MODEL`.
A página oficial o descreve como o Flash mais inteligente e informa entrada de
texto/imagem/vídeo/áudio/PDF, saída de texto, JSON estruturado, contexto de 1.048.576
 tokens e saída de até 65.536. O aplicativo usa limites bem menores por etapa.
Isso fundamenta a escolha; não prova que é o melhor reconstrutor de arquitetura.

| Modelo revisado | Nível gratuito de entrada/saída | Escolha |
| --- | --- | --- |
| gemini-3.8-flash | Listado oficialmente como gratuito | Padrão; prioridade à qualidade |
| gemini-3.7-flash | Listado oficialmente como gratuito | Alternativa configurável, sem troca automática |
| gemini-3.5-flash-lite | Listado oficialmente como gratuito | Alternativa econômica; sem evidência local de fidelidade equivalente |

Fontes oficiais consultadas:
- https://ai.google.dev/gemini-api/docs/pricing
- https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash
- https://ai.google.dev/gemini-api/docs/models/gemini-3.7-flash
- https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite
- https://ai.google.dev/gemini-api/docs/structured-output
- https://ai.google.dev/api/generate-content
- https://ai.google.dev/gemini-api/docs/rate-limits
- https://ai.google.dev/gemini-api/docs/billing

## O que garante custo zero

Use uma chave de projeto **Free Tier sem Cloud Billing**, sem cartão e sem créditos
comprados. A API permite níveis gratuitos e pagos; não há um parâmetro de inferência
que torne gratuita uma chave paga. O Photo2Craft não consegue consultar o faturamento
com uma API key e não promete detectar uma chave paga. Por isso chamadas externas
ficam desativadas até `GEMINI_FREE_TIER_CONFIRMED=true`: é uma confirmação do operador
após verificar o projeto no AI Studio, não uma comprovação automática de billing.
Nunca marque a confirmação para um projeto pago. Não habilite faturamento.

A allowlist de modelos é explícita, revisada em código. Não aceita `latest`, modelos
pagos/desconhecidos, Batch, Search grounding, ferramentas ou serviços extras.
O endpoint Google é fixo; chave vai somente no cabeçalho do backend, nunca no URL,
frontend, capabilities ou logs. Respostas/prompt/imagens não são registrados no log
normal. O nível gratuito pode usar conteúdo para melhoria dos produtos do Google;
verifique os termos antes de enviar referências privadas.

## Cotas e falhas

Limites reais dependem de projeto/modelo e devem ser conferidos no AI Studio. Não
fixamos números de RPM/TPM/RPD como uma promessa. As cotas diárias do Google reiniciam
à meia-noite do Pacífico, com horário de verão respeitado. `AI_DAILY_CALL_LIMIT=20`
é um limite LOCAL conservador, por instalação, incluindo tentativas; não representa
uma oferta do Google. Dois Photo2Craft em instalações diferentes não compartilham
esse contador, mas continuam sujeitos à cota real do projeto.

HTTP 429 não é repetido imediatamente. Bloqueio persistido em
`DATA_DIR/provider-quota.sqlite`, compartilhado por modelos/chaves na instalação.
Se a resposta identificar explicitamente quota por minuto e RetryInfo, aguarda pelo
menos 60 s; quota diária ou desconhecida bloqueia até a próxima meia-noite do Pacífico.
Reiniciar o container não limpa o bloqueio. Alterar modelo/chave não o contorna.
Erros transitórios de rede/5xx admitem até 3 tentativas com backoff 1/2 s, dentro do
prazo total. Erros 400/401/403/404, bloqueios de conteúdo e saída truncada encerram
a etapa; JSON parcial nunca é construído. Correção de schema/geometria inicial:
no máximo uma nova chamada, com erro de validação e sem relaxar limites.

Fallback padrão `none`. `FALLBACK_PROVIDER=ollama` habilita alternativa local
explicitamente, em quota/timeout. Nunca seleciona outra nuvem ou serviço pago.
Sem Ollama configurado, uma falha nele continua sendo uma falha real.

**Credenciais reais não estavam disponíveis durante a implementação.** A existência,
capacidades e preços foram verificados na documentação; acesso da conta, quotas e
qualidade de inferência ainda exigem um teste real com a chave do usuário.

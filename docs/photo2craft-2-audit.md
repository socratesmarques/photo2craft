# Auditoria Photo2Craft 2.0 — 2026-10-08

Base: 4317a5f. Inspecionados backend, React/Three.js, contratos/paletas, Fabric/Java,
testes, Docker, configurações e scripts/documentação antes de alterar implementação.

- A base já tem geometria compacta, render CPU e refinamento. Serão reutilizados.
- AIGenerator/GenerationSession acoplam inferência ao Ollama. Reserva conservadora
  de contexto reduz saída efetiva abaixo do teto do .env; inferência local pode
  gastar tempo em raciocínio e truncar. Hardware real não disponível para medição.
- /api/generate mantém uma requisição aberta por toda a geração. Nginx tolera 960 s,
  mas outros proxies/clientes podem encerrar antes. Não há jobs/progresso persistidos.
- ScenePlan só é salvo em debug; falta versão, incerteza por elemento, relações
  verificáveis e intenção explícita de sobreposição. Última peça vence.
- Segmentação/câmera são heurísticas; falta gate para perspectiva não comparável.
- Material automático substitui escolha de bloco por RGB. Render usa envelopes
  cúbicos para escadas/vidro; cores aproximadas, sem texturas reais.
- Upload aceita uma referência; preview já possui órbita/zoom/comparação.
  Faltam aprovação/rejeição, materiais alternativos e recuperação após reload.
- Mod: Fabric 0.3.0, Minecraft 1.21.1, Java 21, contrato 1.0. Download único limitado,
  rotação nativa de BlockState, fila por tick, cancel/undo e permissão nível 2 existem.
- API local sem autenticação: exposição pública exige proteção externa.
- Testes com mocks não comprovam fidelidade fotográfica.

Estratégia: provedores independentes; schema arquitetônico versionado; compilação com
colisões explícitas e conectividade; jobs persistidos; múltiplas referências; aprovação;
cache por conteúdo; bloqueio persistente de cotas. Preservar demo, caminho Ollama legado
selecionável, dados existentes e contrato do mod. Nenhum fallback procedural silencioso.

A referência inicial executada e os limites do ambiente constam no relatório de validação.

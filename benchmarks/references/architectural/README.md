# Referências sintéticas de teste (CC0)

Casa simples, casa moderna, castelo e estrutura assimétrica. Geradas pelo renderer
CPU a partir dos planos manuais JSON, por `python scripts/benchmark_architectural.py`.
São fixtures reproduzíveis para testar o motor, não exemplos produzidos pelo Gemini.
Os renders usam cores aproximadas próprias, sem texturas proprietárias do jogo.

O benchmark compara o template procedural genérico antigo com o plano conhecido.
IoU=100 do plano conhecido é esperado por construção e NÃO prova evolução da IA.
Uma comparação real exige submeter as MESMAS imagens à inferência antiga/nova e
avaliar fotos próprias separadamente com `scripts/benchmark_visual.py`.

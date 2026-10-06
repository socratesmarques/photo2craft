# Contrato Photo2Craft 1.0

`shared/structure.schema.json` é o JSON Schema gerado dos modelos Pydantic. `shared/block-palette.json` define os identificadores e valores de estados permitidos. Validadores Python e Java também conferem unicidade, limites e nomes — JSON Schema sozinho não cobre essas regras entre campos.

```json
{
  "formatVersion": "1.0",
  "minecraftVersion": "1.21.1",
  "id": "exemplo",
  "name": "Exemplo mínimo",
  "description": "Demonstração do contrato",
  "author": "local",
  "createdAt": "2026-10-05T00:00:00Z",
  "thumbnail": null,
  "orientation": "north",
  "size": {"width": 2, "height": 1, "depth": 1},
  "blocks": [
    {"x": 0, "y": 0, "z": 0, "block": "minecraft:oak_log", "states": {"axis": "y"}},
    {"x": 1, "y": 0, "z": 0, "block": "minecraft:stone_bricks", "states": {}}
  ]
}
```

- Origem `(0,0,0)` no canto inferior mínimo da caixa. X aumenta para leste, Y para cima e Z para sul. Frente canônica: norte, face `z=0`.
- `size` é a caixa completa, não apenas a extensão dos blocos sólidos. Todos os eixos são inteiros positivos.
- Cada posição aparece no máximo uma vez, sempre `0 <= coordenada < tamanho`.
- Posição omitida significa **preservar o mundo**. `minecraft:air` explícito significa **limpar a posição**, sujeito à política de substituição. Ar conta no limite e na fila.
- O gerador procedural preenche toda a caixa com células, inclusive ar, para que interiores sejam determinísticos.
- O gerador por IA emite apenas posições tocadas pelas formas do plano, incluindo seus recortes e interiores de ar. O restante da caixa é preservado. O JSON final continua na versão 1.0 e usa a mesma paleta.
- `states` contém strings, não números/booleanos. Estados omitidos usam o padrão do registro Minecraft. Estado ou valor desconhecido é rejeitado, sem fallback silencioso.
- NBT, entidades, comandos, fluidos, explosivos e blocos com inventário não fazem parte deste MVP. A paleta é uma lista positiva compartilhada.
- A API aceita somente os campos documentados. O mod usa os campos necessários para construção e ignora metadados adicionais, mas rejeita versão incompatível.
- IDs têm 1–64 caracteres ASCII: letras, números, `_` e `-`. Novos IDs da API são UUID4 hex com 32 caracteres. Diferenciam maiúsculas/minúsculas.
- `thumbnail` é uma rota local de imagem, não um URL a ser buscado pelo mod.
- `author` é apenas metadado local; não prova identidade. `createdAt` é UTC nos projetos gerados.

## Rotação

Para a célula `(x,y,z)` em largura `W` e profundidade `D`:

| Ângulo | Posição |
| --- | --- |
| 0° | `(x,y,z)` |
| 90° | `(D-1-z,y,x)` |
| 180° | `(W-1-x,y,D-1-z)` |
| 270° | `(z,y,W-1-x)` |

90° e 270° trocam largura e profundidade da caixa. O mod aplica a mesma rotação aos `BlockState` usando a API nativa de Minecraft.

## Evolução

Uma mudança incompatível requer nova `formatVersion` e suporte explícito nos consumidores. Não introduzir transformações implícitas ou baixar recursos externos a partir do JSON. Uma representação por paleta/RLE pode reduzir payload no futuro, mas a versão 1.0 privilegia depuração e interoperabilidade.

"""Shared bounded structured calls. No generated code or partial JSON is executed."""
from copy import deepcopy
import base64
from io import BytesIO
import json
import logging
import math
import time
from PIL import Image

logger = logging.getLogger("photo2craft.ollama")


class GenerationError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def compact_schema(schema):
    """Remove presentation metadata, retaining every validation constraint."""
    if isinstance(schema, list):
        return [compact_schema(value) for value in schema]
    if isinstance(schema, dict):
        return {key: ({name: compact_schema(child) for name, child in value.items()}
                      if key in {"properties", "$defs", "definitions"} else compact_schema(value))
                for key, value in schema.items()
                if key not in {"title", "description"}}
    return schema


def parse_json(model, content):
    text = content.strip()
    if text.startswith("```") and text.endswith("```"):
        text = "\n".join(text.splitlines()[1:-1])
    return model.model_validate_json(text)


class GenerationSession:
    def __init__(self, generator, build_id, deadline=None):
        self.generator = generator
        self.build_id = build_id
        self.deadline = deadline or time.monotonic() + generator.settings.ai_timeout_seconds
        self.calls = []
        self.warnings = []
        self.image_reserves = {}

    def image_reserve(self, encoded):
        if encoded not in self.image_reserves:
            try:
                with Image.open(BytesIO(base64.b64decode(encoded))) as image:
                    # Qwen-style 28px visual patches plus template margin. Other models
                    # may tokenize differently: this remains a budget estimate.
                    tokens = math.ceil(image.width / 28) * math.ceil(image.height / 28) + 256
            except (ValueError, OSError):
                tokens = 1536
            self.image_reserves[encoded] = max(512, tokens)
        return self.image_reserves[encoded]

    def ask(self, schema, instruction, data, images, budget, stage):
        settings = self.generator.settings
        schema = compact_schema(schema)
        for attempt in range(2):
            remaining = self.deadline - time.monotonic()
            if remaining <= 1:
                raise GenerationError("Tempo total de geração esgotado.", 504)
            user = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
            # Conservative estimate, not a tokenizer: reserve schema, text, template and
            # visual tokens. Actual prompt_eval_count is retained for local calibration.
            prompt_reserve = max(2048, math.ceil((len(instruction) + len(user) +
                                 len(json.dumps(schema, separators=(",", ":")))) / 2)
                                 + 512 + sum(self.image_reserve(image) for image in images))
            available = settings.ai_context_tokens - prompt_reserve
            if available < 512:
                raise GenerationError("O contexto não comporta esta etapa. Reduza os componentes ou use AI_CONTEXT_TOKENS=32768.")
            predict = min(budget, settings.ai_max_output_tokens, available)
            limits = {key: value["maxItems"] for key, value in schema.get("properties", {}).items()
                      if "maxItems" in value}
            payload = {
                "model": settings.ollama_model,
                "messages": [
                    {"role": "system", "content": instruction +
                     "\nReturn compact JSON only, no Markdown or commentary. Array limits: " + json.dumps(limits)},
                    {"role": "user", "content": user, "images": images},
                ],
                "format": schema, "stream": False, "think": False, "keep_alive": "10m",
                "options": {"temperature": 0, "num_ctx": settings.ai_context_tokens, "num_predict": predict},
            }
            name = stage + (".compact" if attempt else "")
            started = time.monotonic()
            response = self.generator._request(payload, timeout_seconds=remaining,
                                               stage=name, build_id=self.build_id)
            self.calls.append({"stage": name, "model": settings.ollama_model,
                               "seconds": round(time.monotonic() - started, 3),
                               "num_ctx": settings.ai_context_tokens, "num_predict": predict,
                               **{key: response.get(key) for key in
                                  ("prompt_eval_count", "eval_count", "done_reason")}})
            if time.monotonic() > self.deadline:
                raise GenerationError("Tempo total de geração esgotado.", 504)
            if response.get("done_reason") == "length":
                if attempt:
                    raise GenerationError("A etapa atingiu o limite de saída mesmo após compactação; nenhum JSON parcial foi aplicado.")
                schema = deepcopy(schema)
                for key, value in schema.get("properties", {}).items():
                    if "maxItems" in value:
                        value["maxItems"] = max(value.get("minItems", 0), value["maxItems"] // 2, 1)
                instruction += ("\nCOMPACT RETRY: previous output exceeded its budget. Ignore previous target counts. "
                                "Use the smaller array limits, short labels and prose. Merge adjacent same-material "
                                "geometry; retain silhouette, proportions and defining parts before tiny details. "
                                "Return a COMPLETE smaller result; never continue a cut JSON.")
                self.warnings.append(f"Etapa {stage}: saída truncada; nova tentativa compacta, sem aumentar o contexto.")
                continue
            message = response.get("message")
            if response.get("done") is not True or not isinstance(message, dict):
                raise GenerationError("O Ollama não concluiu a etapa " + stage + ".")
            content = message.get("content")
            if not isinstance(content, str) or not content.strip():
                hint = " O modelo retornou somente raciocínio; confira a variante Instruct do Qwen3-VL." if message.get("thinking") else ""
                raise GenerationError("O Ollama retornou conteúdo vazio na etapa " + stage + "." + hint)
            return content

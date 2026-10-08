"""Bounded JSON providers. Network runs in the job worker, never on the ASGI loop."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import logging
import sqlite3
import time
from zoneinfo import ZoneInfo
import httpx
from .ollama_session import GenerationError, GenerationSession, compact_schema

log = logging.getLogger('photo2craft.providers')


class QuotaError(GenerationError):
    def __init__(self, until):
        self.until = until
        super().__init__('Cota gratuita/limite local atingido. Chamadas Gemini suspensas até ' +
                         datetime.fromtimestamp(until, timezone.utc).isoformat() + '.', 429)


class QuotaGate:
    """One durable gate across models/keys: do not evade a project's quota by rotation."""
    def __init__(self, settings):
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.path = settings.data_dir / 'provider-quota.sqlite'
        self.limit = settings.ai_daily_call_limit
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS quota (id INTEGER PRIMARY KEY, day TEXT, calls INTEGER, blocked REAL)')
            db.execute("INSERT OR IGNORE INTO quota VALUES (1, '', 0, 0)")

    def connect(self):
        return sqlite3.connect(self.path, timeout=20)

    @staticmethod
    def window():
        now = datetime.now(ZoneInfo('America/Los_Angeles'))
        reset = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return now.date().isoformat(), reset.timestamp()

    def reserve(self):
        day, reset = self.window()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            previous, calls, blocked = db.execute('SELECT day,calls,blocked FROM quota WHERE id=1').fetchone()
            if blocked > time.time():
                raise QuotaError(blocked)
            if previous != day:
                calls = 0
            if calls >= self.limit:
                raise QuotaError(reset)
            db.execute('UPDATE quota SET day=?,calls=?,blocked=0 WHERE id=1', (day, calls+1))

    def block(self, response):
        # Only explicit short-window quota identifiers authorize an early retry.
        until = self.window()[1]
        try:
            details = response.json().get('error', {}).get('details', [])
            ids = [v.get('quotaId', '').lower() for d in details for v in d.get('violations', [])]
            delays = [float(d['retryDelay'].removesuffix('s')) for d in details if 'retryDelay' in d]
            if ids and all('perminute' in q for q in ids) and delays:
                until = time.time() + max(60, min(max(delays), 86400))
        except (ValueError, TypeError, AttributeError):
            pass
        with self.connect() as db:
            db.execute('UPDATE quota SET blocked=MAX(blocked,?) WHERE id=1', (until,))
        return QuotaError(until)


class GeminiProvider:
    name = 'gemini'
    def __init__(self, settings, transport=None):
        self.settings, self.transport = settings, transport
        self.model = settings.gemini_model
        self.gate = QuotaGate(settings)
        self.calls = []

    @property
    def configured(self):
        return bool(self.settings.gemini_api_key.get_secret_value().strip()) and self.settings.gemini_free_tier_confirmed

    def ask(self, schema, instruction, data, images, budget, stage, deadline):
        if not self.configured:
            raise GenerationError('Configure GEMINI_API_KEY no backend e GEMINI_FREE_TIER_CONFIRMED=true somente para um projeto Free Tier sem faturamento.', 503)
        key = self.settings.gemini_api_key.get_secret_value().strip()
        if any(c.isspace() for c in key) or len(key) < 20:
            raise GenerationError('GEMINI_API_KEY inválida. Copie a chave completa do Google AI Studio.', 503)
        schema = compact_schema(deepcopy(schema))
        endpoint = f'https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent'
        payload = {'systemInstruction': {'parts': [{'text': instruction}]},
                   'contents': [{'role': 'user', 'parts': [{'text': json.dumps(data, ensure_ascii=False, separators=(',', ':'))}] +
                                [{'inlineData': {'mimeType': 'image/png', 'data': image}} for image in images]}],
                   'generationConfig': {'responseMimeType': 'application/json', 'responseJsonSchema': schema,
                                        'maxOutputTokens': min(budget, self.settings.ai_max_output_tokens)}}
        for attempt in range(self.settings.ai_max_attempts):
            remaining = deadline - time.monotonic()
            if remaining <= 1:
                raise GenerationError('Tempo total da geração esgotado.', 504)
            self.gate.reserve()
            started = time.monotonic()
            metric = {'provider': self.name, 'model': self.model, 'stage': stage, 'attempt': attempt+1}
            retry = False
            try:
                with httpx.Client(transport=self.transport, timeout=httpx.Timeout(remaining, connect=min(10, remaining)),
                                  trust_env=False, follow_redirects=False) as client:
                    with client.stream('POST', endpoint, headers={'x-goog-api-key': key}, json=payload) as response:
                        metric['httpStatus'] = response.status_code
                        body = bytearray()
                        for chunk in response.iter_bytes():
                            if time.monotonic() >= deadline:
                                raise GenerationError('Tempo total da geração esgotado.', 504)
                            body.extend(chunk)
                            if len(body) > 2*1024*1024:
                                raise GenerationError('Resposta Gemini excedeu o limite de bytes.')
                        bounded = httpx.Response(response.status_code, content=bytes(body))
                status = bounded.status_code
                if status == 429:
                    raise self.gate.block(bounded)
                if status in {401, 403}:
                    raise GenerationError('Gemini recusou a chave ou o acesso ao modelo/região. Confira o projeto Free Tier no AI Studio.', 503)
                if status == 404:
                    raise GenerationError('Modelo Gemini indisponível para esta chave. Confira GEMINI_MODEL e a documentação oficial.', 503)
                if status in {500, 502, 503, 504}:
                    retry = True
                    raise GenerationError('Gemini temporariamente indisponível.', 503)
                if status != 200:
                    raise GenerationError(f'Gemini recusou a solicitação (HTTP {status}); confira a configuração e o schema.', 502)
                result = bounded.json()
                usage = result.get('usageMetadata', {})
                metric['tokens'] = {k: usage[k] for k in ('promptTokenCount', 'candidatesTokenCount', 'thoughtsTokenCount', 'totalTokenCount') if isinstance(usage.get(k), int)}
                candidates = result.get('candidates', [])
                if len(candidates) != 1:
                    raise GenerationError('Gemini não retornou um candidato; a referência pode ter sido bloqueada.')
                candidate = candidates[0]
                metric['finishReason'] = candidate.get('finishReason')
                if candidate.get('finishReason') != 'STOP':
                    reason = 'limite de saída' if candidate.get('finishReason') == 'MAX_TOKENS' else 'interrupção ou bloqueio'
                    raise GenerationError(f'Gemini encerrou por {reason}. Nenhum JSON parcial foi aplicado.')
                text = ''.join(p.get('text', '') for p in candidate.get('content', {}).get('parts', []) if not p.get('thought'))
                if not text.strip():
                    raise GenerationError('Gemini retornou conteúdo vazio.')
                return text
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                metric['error'] = type(exc).__name__
                retry = True
                failure = GenerationError('Falha de rede/timeout ao consultar Gemini.', 504 if isinstance(exc, httpx.TimeoutException) else 503)
            except GenerationError as exc:
                metric['error'] = type(exc).__name__
                if not retry:
                    raise
                failure = exc
            except (ValueError, TypeError, AttributeError, httpx.HTTPError) as exc:
                metric['error'] = type(exc).__name__
                raise GenerationError('Resposta Gemini inválida; nenhuma estrutura foi criada.') from exc
            finally:
                metric['seconds'] = round(time.monotonic()-started, 3)
                self.calls.append(metric)
                log.info('%s', json.dumps(metric))
            if attempt+1 == self.settings.ai_max_attempts:
                raise failure
            delay = min(2**attempt, 4)
            if deadline-time.monotonic() <= delay+1:
                raise failure
            time.sleep(delay)


class OllamaProvider:
    name = 'ollama'
    def __init__(self, generator, build_id, deadline):
        self.session = GenerationSession(generator, build_id, deadline)
        self.model = generator.settings.ollama_model
        self.calls = self.session.calls

    def ask(self, schema, instruction, data, images, budget, stage, deadline):
        return self.session.ask(schema, instruction, data, images, budget, stage)


class AIProviderFactory:
    @staticmethod
    def create(generator, build_id, deadline, name=None):
        provider = name or generator.settings.ai_provider
        if provider == 'gemini':
            return GeminiProvider(generator.settings, generator.transport)
        if provider == 'ollama':
            return OllamaProvider(generator, build_id, deadline)
        raise GenerationError('Configure AI_PROVIDER=gemini ou ollama.', 503)

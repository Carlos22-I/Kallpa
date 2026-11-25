"""Adaptadores de modelos de lenguaje multimodales (Claude u OpenAI-compatible).

Separación de responsabilidades:
- *Clientes* (ClaudeClient, OpenAICompatibleClient): solo saben hablar HTTP con un proveedor.
- *Adaptadores* (LLMPlateAnalyzer, LLMAssistant): implementan los puertos con un cliente cualquiera.
Llamadas con urllib (biblioteca estándar): sin SDKs que mantener.
"""
from __future__ import annotations

import base64
import json
import re
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod

from ...application.ports import FamilyAssistant, PlateAnalyzer
from ...domain.models import DetectedFood, Food, PlateAnalysis


class LLMError(RuntimeError):
    pass


def post_json(url: str, payload: dict, headers: dict, timeout: float) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"content-type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise LLMError(f"HTTP {e.code}: {e.read().decode(errors='ignore')[:300]}") from e
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        raise LLMError(str(e)) from e


def extract_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise LLMError("La respuesta del modelo no contiene JSON")
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise LLMError(f"JSON inválido: {e}") from e


# Precios de referencia en USD por 1M de tokens (entrada, salida), verificados en noviembre de 2026.
# Se pueden sobrescribir con AI_PRICE_IN / AI_PRICE_OUT si el proveedor cambia sus tarifas.
PRICES_USD_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "gemini-3.1-flash-lite": (0.25, 1.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-3-flash-preview": (0.50, 3.00),
    "gpt-4o-mini": (0.15, 0.60),
}


class UsageMeter:
    """Cuenta llamadas, tokens y costo estimado por proveedor (en memoria, se reinicia al reiniciar)."""

    def __init__(self) -> None:
        self.by_provider: dict[str, dict] = {}

    def add(self, provider: str, model: str, tokens_in: int, tokens_out: int, ok: bool, latency_s: float,
            price: tuple[float, float] | None) -> None:
        p = self.by_provider.setdefault(provider, {"llamadas": 0, "errores": 0, "tokens_entrada": 0,
                                                   "tokens_salida": 0, "costo_usd": 0.0, "latencia_total_s": 0.0})
        p["llamadas"] += 1
        p["errores"] += 0 if ok else 1
        p["tokens_entrada"] += tokens_in
        p["tokens_salida"] += tokens_out
        p["latencia_total_s"] += latency_s
        if price:
            p["costo_usd"] += tokens_in * price[0] / 1e6 + tokens_out * price[1] / 1e6

    def snapshot(self) -> dict:
        out = {}
        for k, v in self.by_provider.items():
            ok_calls = max(1, v["llamadas"] - v["errores"])
            out[k] = {**v, "costo_usd": round(v["costo_usd"], 5),
                      "costo_promedio_por_llamada_usd": round(v["costo_usd"] / ok_calls, 6),
                      "latencia_promedio_s": round(v["latencia_total_s"] / max(1, v["llamadas"]), 2)}
            out[k].pop("latencia_total_s")
        return out


def price_for(model: str, override: tuple[float, float] | None = None) -> tuple[float, float] | None:
    if override:
        return override
    for prefix in sorted(PRICES_USD_PER_MTOK, key=len, reverse=True):
        if model.startswith(prefix):
            return PRICES_USD_PER_MTOK[prefix]
    return None


class LLMClient(ABC):
    name = "llm"

    def __init__(self, model: str, timeout: float, meter: UsageMeter | None, price: tuple[float, float] | None):
        self.model, self.timeout = model, timeout
        self.meter = meter or UsageMeter()
        self.price = price_for(model, price)
        self.last_usage: tuple[int, int] = (0, 0)

    def complete(self, system: str, text: str, image: bytes | None = None, mime: str | None = None,
                 max_tokens: int = 800) -> str:
        t0 = time.monotonic()
        try:
            out, tin, tout = self._call(system, text, image, mime, max_tokens)
        except Exception:
            self.meter.add(self.name, self.model, 0, 0, False, time.monotonic() - t0, self.price)
            raise
        self.last_usage = (tin, tout)
        self.meter.add(self.name, self.model, tin, tout, True, time.monotonic() - t0, self.price)
        if not out or not out.strip():
            raise LLMError("Respuesta vacía del modelo")
        return out

    @abstractmethod
    def _call(self, system: str, text: str, image: bytes | None, mime: str | None,
              max_tokens: int) -> tuple[str, int, int]:
        """Devuelve (texto, tokens_entrada, tokens_salida)."""


class ClaudeClient(LLMClient):
    URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key: str, model: str, timeout: float = 20.0, meter: UsageMeter | None = None,
                 price: tuple[float, float] | None = None):
        if not api_key:
            raise ValueError("Falta ANTHROPIC_API_KEY")
        super().__init__(model, timeout, meter, price)
        self.api_key = api_key
        self.name = f"claude:{model}"

    def _call(self, system, text, image, mime, max_tokens):
        content: list = []
        if image:
            content.append({"type": "image", "source": {"type": "base64", "media_type": mime or "image/jpeg",
                                                         "data": base64.b64encode(image).decode()}})
        content.append({"type": "text", "text": text})
        data = post_json(self.URL, {"model": self.model, "max_tokens": max_tokens, "system": system,
                                    "messages": [{"role": "user", "content": content}]},
                         {"x-api-key": self.api_key, "anthropic-version": "2023-06-01"}, self.timeout)
        out = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        u = data.get("usage") or {}
        tin = int(u.get("input_tokens", 0)) + int(u.get("cache_read_input_tokens", 0) or 0) \
            + int(u.get("cache_creation_input_tokens", 0) or 0)
        return out, tin, int(u.get("output_tokens", 0))


class OpenAICompatibleClient(LLMClient):
    """OpenAI, Gemini (endpoint compatible), Groq, OpenRouter u Ollama."""

    def __init__(self, api_key: str, model: str, base_url: str, timeout: float = 20.0,
                 meter: UsageMeter | None = None, price: tuple[float, float] | None = None,
                 reasoning_effort: str = ""):
        if not api_key:
            raise ValueError("Falta OPENAI_API_KEY")
        super().__init__(model, timeout, meter, price)
        self.api_key, self.base_url = api_key, base_url.rstrip("/")
        self.reasoning_effort = reasoning_effort
        host = "gemini" if "generativelanguage" in self.base_url else "openai"
        self.name = f"{host}:{model}"

    def _call(self, system, text, image, mime, max_tokens):
        user: list | str = text
        if image:
            user = [{"type": "text", "text": text}, {"type": "image_url", "image_url": {
                "url": f"data:{mime or 'image/jpeg'};base64,{base64.b64encode(image).decode()}"}}]
        payload: dict = {"model": self.model,
                         "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        # Los modelos nuevos de OpenAI usan max_completion_tokens; Gemini y otros aceptan max_tokens.
        payload["max_completion_tokens" if "api.openai.com" in self.base_url else "max_tokens"] = max_tokens
        if self.reasoning_effort:
            payload["reasoning_effort"] = self.reasoning_effort
        data = post_json(f"{self.base_url}/chat/completions", payload,
                         {"authorization": f"Bearer {self.api_key}"}, self.timeout)
        try:
            out = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as e:
            raise LLMError("Respuesta inesperada del proveedor") from e
        u = data.get("usage") or {}
        return out, int(u.get("prompt_tokens", 0)), int(u.get("completion_tokens", 0))


PLATE_PROMPT = """Eres el módulo de visión de Kallpa, una app que ayuda a familias de Abancay (Apurímac, Perú) a prevenir la anemia infantil.
Te llega la foto del plato de un niño o niña pequeño y/o una descripción (español, quechua chanka o mezcla).
Identifica SOLO alimentos del CATÁLOGO (usa su id) y estima los gramos servidos AL NIÑO (porciones infantiles; 1 cucharada ≈ 15 g).
Responde ÚNICAMENTE un JSON:
{
  "is_food_photo": boolean,                     // false si la imagen no es comida
  "foods": [{"id": "<id del catálogo>", "grams": número, "confidence": 0-1}],
  "consistency": "espesa|sopa|desconocida",     // segundo/papilla vs sopa/caldo
  "privacy_flags": ["persona_visible"] si aparece una cara o persona identificable, si no [],
  "confidence": 0-1,                            // honesta: baja si la foto es borrosa o ambigua
  "language": "es|qu|mixto",
  "note": "frase corta en español para la familia si la foto no sirve; si no, vacío"
}
No calcules hierro ni des consejos médicos. No inventes alimentos que no se ven.

CATÁLOGO (id: nombre):
{catalog}"""

ASSISTANT_PROMPT = """Eres Kallpa, asistente para familias de Abancay sobre alimentación rica en hierro y prevención de la anemia infantil.
Responde en el idioma de la persona (español o quechua chanka), en máximo 4 frases, cálido y práctico, con alimentos de la zona.
Usa SOLO la información del CONTEXTO. NUNCA indiques dosis de medicamentos ni suplementos: di que siga la indicación del establecimiento de salud.
NO diagnostiques. Ante signos de alarma, indica acudir de inmediato al establecimiento de salud.

CONTEXTO:
{context}"""


def _clamp(x, lo, hi, default):
    try:
        return max(lo, min(hi, float(x)))
    except (TypeError, ValueError):
        return default


def to_plate_analysis(data: dict, valid_ids: set[str], provider: str) -> PlateAnalysis:
    """Valida la salida del modelo: ids fuera del catálogo se descartan, valores se acotan."""
    foods = []
    for f in data.get("foods", []) or []:
        if isinstance(f, dict) and f.get("id") in valid_ids:
            foods.append(DetectedFood(f["id"], _clamp(f.get("grams"), 1, 400, 30), _clamp(f.get("confidence"), 0, 1, 0.6)))
    cons = data.get("consistency", "desconocida")
    return PlateAnalysis(
        foods=tuple(foods),
        confidence=round(_clamp(data.get("confidence"), 0, 1, 0.5), 2),
        is_food_photo=bool(data.get("is_food_photo", True)),
        privacy_flags=tuple(p for p in data.get("privacy_flags", []) or [] if p == "persona_visible"),
        consistency=cons if cons in ("espesa", "sopa", "desconocida") else "desconocida",
        note=str(data.get("note", ""))[:200],
        provider=provider,
        language=str(data.get("language", "es"))[:6],
    )


class LLMPlateAnalyzer(PlateAnalyzer):
    def __init__(self, client: LLMClient):
        self.client = client
        self.name = client.name

    def analyze(self, description, image, mime, catalog: list[Food]) -> PlateAnalysis:
        cat_txt = "\n".join(f"{f.id}: {f.name}" for f in catalog)
        text = self.client.complete(PLATE_PROMPT.replace("{catalog}", cat_txt),
                                    f"Descripción de la familia: {description or '(sin descripción)'}", image, mime,
                                    max_tokens=1500)
        return to_plate_analysis(extract_json(text), {f.id for f in catalog}, self.client.name)


class LLMAssistant(FamilyAssistant):
    def __init__(self, client: LLMClient):
        self.client = client

    def answer(self, question, context):
        return self.client.complete(ASSISTANT_PROMPT.format(context=context), question, max_tokens=800).strip(), self.client.name

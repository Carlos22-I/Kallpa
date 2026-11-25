from pathlib import Path

import pytest

from app.infrastructure.adapters import JsonFoodCatalog
from app.infrastructure.ai.llm import LLMError, LLMPlateAnalyzer, extract_json, to_plate_analysis
from app.infrastructure.ai.local import LocalAssistant, LocalPlateAnalyzer
from app.infrastructure.ai.resilient import ResilientAnalyzer

DATA = Path(__file__).resolve().parent.parent / "data"
CATALOG = JsonFoodCatalog(DATA / "alimentos.json", DATA / "recetas.json")
FOODS = CATALOG.all()


@pytest.fixture(scope="module")
def local():
    return LocalPlateAnalyzer()


def ids(a):
    return {f.food_id for f in a.foods}


def test_reconoce_alimentos_y_cantidades(local):
    a = local.analyze("puré de papa con 2 cucharadas de hígado de pollo y jugo de naranja", None, None, FOODS)
    assert ids(a) == {"papa", "higado_pollo", "naranja"}
    hig = next(f for f in a.foods if f.food_id == "higado_pollo")
    assert hig.grams == 30
    assert a.consistency == "espesa"


def test_sinonimo_largo_gana_al_corto(local):
    a = local.analyze("higado de res", None, None, FOODS)
    assert ids(a) == {"higado_res"}


def test_quechua_con_sufijos(local):
    a = local.analyze("huk tortilla runtu yawarwan, kinwa", None, None, FOODS)
    assert {"huevo", "sangrecita", "quinua"} <= ids(a)
    assert a.language in ("qu", "mixto")


def test_sopa_e_infusion(local):
    a = local.analyze("sopa de fideos con té", None, None, FOODS)
    assert a.consistency == "sopa" and "infusion" in ids(a)


def test_solo_foto_confianza_baja(local):
    a = local.analyze("", b"x", "image/jpeg", FOODS)
    assert a.confidence < 0.5 and not a.foods


def test_to_plate_analysis_valida_salida_del_llm():
    a = to_plate_analysis({"foods": [{"id": "bazo", "grams": 9999}, {"id": "pizza", "grams": 50}, "basura"],
                           "confidence": 5, "privacy_flags": ["persona_visible", "otro"], "consistency": "rara"},
                          {f.id for f in FOODS}, "test")
    assert [f.food_id for f in a.foods] == ["bazo"] and a.foods[0].grams == 400
    assert a.confidence == 1 and a.privacy_flags == ("persona_visible",) and a.consistency == "desconocida"


def test_extract_json():
    assert extract_json('```json\n{"a":1}\n```') == {"a": 1}
    with pytest.raises(LLMError):
        extract_json("nada")


class FakeClient:
    name = "fake"

    def __init__(self, reply=None, fail=False):
        self.reply, self.fail, self.calls = reply, fail, 0

    def complete(self, system, text, image=None, mime=None, max_tokens=600):
        self.calls += 1
        assert "sangrecita: Sangrecita de pollo" in system  # el catálogo va en el prompt
        if self.fail:
            raise LLMError("caído")
        return self.reply


def test_adaptador_llm_con_cliente_falso():
    a = LLMPlateAnalyzer(FakeClient('{"foods":[{"id":"sangrecita","grams":30}],"confidence":0.9,"consistency":"espesa"}'))
    r = a.analyze("", b"img", "image/jpeg", FOODS)
    assert ids(r) == {"sangrecita"} and r.provider == "fake"


def test_fallback_y_circuit_breaker(local):
    fake = FakeClient(fail=True)
    chain = ResilientAnalyzer([LLMPlateAnalyzer(fake), local])
    for _ in range(5):
        r = chain.analyze("arroz con huevo", None, None, FOODS)
        assert r.provider == "local-texto"
    assert fake.calls == 3 and chain.status()[0]["circuito"] == "abierto"


def test_asistente_local_no_da_dosis():
    ctx = (DATA / "conocimiento.md").read_text(encoding="utf-8")
    ans, _ = LocalAssistant().answer("¿cuántas gotas de hierro le doy?", ctx)
    assert "no da dosis" in ans
    ans2, _ = LocalAssistant().answer("¿el té quita el hierro?", ctx)
    assert "té" in ans2.lower()
    ans3, _ = LocalAssistant().answer("mi niño no quiere el suplemento, lo escupe", ctx)
    assert "escupe" in ans3 or "rechaza" in ans3


# ---------- clientes HTTP reales con la red simulada ----------
from app.infrastructure.ai import llm as llm_mod
from app.infrastructure.ai.llm import ClaudeClient, OpenAICompatibleClient, UsageMeter, price_for


def test_claude_client_registra_tokens_y_costo(monkeypatch):
    sent = {}

    def fake_post(url, payload, headers, timeout):
        sent.update(url=url, payload=payload, headers=headers)
        return {"content": [{"type": "text", "text": '{"foods":[{"id":"bazo","grams":30}],"confidence":0.9}'}],
                "usage": {"input_tokens": 2000, "output_tokens": 150}}

    monkeypatch.setattr(llm_mod, "post_json", fake_post)
    meter = UsageMeter()
    a = LLMPlateAnalyzer(ClaudeClient("k", "claude-haiku-5-5", meter=meter))
    r = a.analyze("", b"img", "image/jpeg", FOODS)
    assert ids(r) == {"bazo"}
    assert sent["headers"]["x-api-key"] == "k" and sent["payload"]["messages"][0]["content"][0]["type"] == "image"
    snap = meter.snapshot()["claude:claude-haiku-5-5"]
    assert snap["tokens_entrada"] == 2000 and snap["costo_usd"] == round(2000 * 0.10 / 1e6 + 150 * 0.50 / 1e6, 5)


def test_gemini_compatible_usa_max_tokens_y_reasoning(monkeypatch):
    sent = {}

    def fake_post(url, payload, headers, timeout):
        sent.update(url=url, payload=payload)
        return {"choices": [{"message": {"content": '{"foods":[],"confidence":0.4,"is_food_photo":false}'}}],
                "usage": {"prompt_tokens": 1800, "completion_tokens": 300}}

    monkeypatch.setattr(llm_mod, "post_json", fake_post)
    c = OpenAICompatibleClient("k", "gemini-3.1-flash-lite", "https://generativelanguage.googleapis.com/v1beta/openai/",
                               reasoning_effort="low")
    r = LLMPlateAnalyzer(c).analyze("x", b"img", "image/jpeg", FOODS)
    assert c.name == "gemini:gemini-3.1-flash-lite" and not r.is_food_photo
    assert sent["url"].endswith("/openai/chat/completions") and "max_tokens" in sent["payload"]
    assert sent["payload"]["reasoning_effort"] == "low"
    assert sent["payload"]["messages"][1]["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_openai_oficial_usa_max_completion_tokens(monkeypatch):
    sent = {}
    monkeypatch.setattr(llm_mod, "post_json", lambda u, p, h, t: sent.update(p=p) or
                        {"choices": [{"message": {"content": "hola"}}], "usage": {}})
    OpenAICompatibleClient("k", "gpt-4o-mini", "https://api.openai.com/v1").complete("s", "t")
    assert "max_completion_tokens" in sent["p"] and "max_tokens" not in sent["p"]


def test_error_cuenta_en_el_medidor(monkeypatch):
    def boom(*a):
        raise LLMError("HTTP 429")
    monkeypatch.setattr(llm_mod, "post_json", boom)
    meter = UsageMeter()
    with pytest.raises(LLMError):
        ClaudeClient("k", "claude-haiku-5-5", meter=meter).complete("s", "t")
    assert meter.snapshot()["claude:claude-haiku-5-5"]["errores"] == 1


def test_tabla_de_precios():
    assert price_for("claude-haiku-5-5") == (0.10, 0.50)
    assert price_for("gemini-3.1-flash-lite") == (0.25, 1.50)
    assert price_for("modelo-raro") is None and price_for("x", (1, 2)) == (1, 2)

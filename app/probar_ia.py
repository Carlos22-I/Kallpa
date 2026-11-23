"""Prueba rápida de las APIs de IA configuradas en .env.

Uso:
    python -m app.probar_ia                      # prueba con texto
    python -m app.probar_ia --foto plato.jpg     # prueba con una foto real
    python -m app.probar_ia --pregunta "¿El té quita el hierro?"

Muestra por cada proveedor: si responde, qué alimentos detectó, tiempo,
tokens usados y costo estimado de esa llamada.
"""
from __future__ import annotations

import argparse
import mimetypes
import sys
import time
from pathlib import Path

from .config import Config
from .container import build_clients
from .infrastructure.adapters import JsonFoodCatalog
from .infrastructure.ai.llm import LLMAssistant, LLMPlateAnalyzer, UsageMeter
from .infrastructure.ai.local import LocalPlateAnalyzer

TEXTO = "segundo de quinua con 2 cucharadas de bazo, una mandarina y una taza de té"


def main() -> int:
    ap = argparse.ArgumentParser(description="Prueba los proveedores de IA de Kallpa")
    ap.add_argument("--foto", help="ruta a una foto de un plato (JPG/PNG/WEBP)")
    ap.add_argument("--texto", default=TEXTO, help="descripción del plato")
    ap.add_argument("--pregunta", default="¿Qué alimentos de Abancay tienen más hierro?")
    a = ap.parse_args()

    cfg = Config.from_env()
    catalog = JsonFoodCatalog(cfg.data_dir / "alimentos.json", cfg.data_dir / "recetas.json").all()
    image, mime = None, None
    if a.foto:
        image = Path(a.foto).read_bytes()
        mime = mimetypes.guess_type(a.foto)[0] or "image/jpeg"
        if image and len(image) > 1_500_000:
            print("Aviso: la foto pesa más de 1.5 MB; la app la comprime a 1024 px antes de enviarla.")

    meter = UsageMeter()
    clients = build_clients(cfg, meter)
    if not clients:
        print("No hay API key configurada (ANTHROPIC_API_KEY u OPENAI_API_KEY en .env).")
        print("Kallpa funcionará solo con el modelo local (texto). Resultado local:")
        r = LocalPlateAnalyzer().analyze(a.texto, None, None, catalog)
        print("  ", [(f.food_id, f.grams) for f in r.foods], "confianza", r.confidence)
        return 1

    ok_all = True
    for client in clients:
        print(f"\n=== {client.name} ===")
        try:
            t0 = time.monotonic()
            r = LLMPlateAnalyzer(client).analyze("" if image else a.texto, image, mime, catalog)
            dt = time.monotonic() - t0
            tin, tout = client.last_usage
            cost = (tin * client.price[0] + tout * client.price[1]) / 1e6 if client.price else None
            print(f"  Plato: {'foto' if image else 'texto'} · {dt:.1f} s · {tin} tokens entrada + {tout} salida"
                  + (f" · US$ {cost:.5f}" if cost is not None else " · precio no configurado"))
            print(f"  Alimentos: {[(f.food_id, round(f.grams)) for f in r.foods]}")
            print(f"  Consistencia: {r.consistency} · confianza {r.confidence} · privacidad {list(r.privacy_flags)}")
            t0 = time.monotonic()
            ans, _ = LLMAssistant(client).answer(a.pregunta, (cfg.data_dir / "conocimiento.md").read_text(encoding="utf-8"))
            tin, tout = client.last_usage
            cost = (tin * client.price[0] + tout * client.price[1]) / 1e6 if client.price else None
            print(f"  Asistente: {time.monotonic() - t0:.1f} s · {tin}+{tout} tokens"
                  + (f" · US$ {cost:.5f}" if cost is not None else ""))
            print(f"  → {ans[:300]}")
        except Exception as e:  # noqa: BLE001
            ok_all = False
            print(f"  ✗ ERROR: {e}")
            print("    Revisa la API key, el nombre del modelo, el saldo/cuota y la conexión.")
    print("\nResumen de uso:", meter.snapshot())
    return 0 if ok_all else 2


if __name__ == "__main__":
    sys.exit(main())

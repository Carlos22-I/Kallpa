"""Datos SIMULADOS de demostración: niños, comidas y registros de suplemento de 3 semanas.

Uso:  python -m app.seed --reset
Todo pasa por los MISMOS casos de uso que usaría una familia real.
"""
from __future__ import annotations

import argparse
import os
import random
from datetime import datetime, time, timedelta
from pathlib import Path

from .config import Config
from .container import build_container
from .domain.models import LOCAL_TZ, SupplementLog

ALIASES = ["Mia", "Thiago", "Luana", "Mateo", "Killa", "Liam", "Sumaq", "Dylan", "Ayelén", "Inti", "Kiara", "Gael",
           "Wayra", "Ian", "Nayeli", "Fabián", "Illari", "Joaquín", "Yuliana", "Ángel", "Amaru", "Valeria", "Kusi",
           "Santiago", "Ximena", "Ronald", "Micaela", "Rodrigo", "Tika", "Josué", "Alisson", "Brayan", "Nina", "Ítalo"]

GOOD = ["puré de papa con 2 cucharadas de hígado de pollo y jugo de naranja",
        "tortilla de sangrecita con espinaca y mandarina",
        "segundo de quinua con 2 cucharadas de bazo y papaya",
        "arroz con sangrecita y habas, de postre tuna",
        "chanfainita de bofe con papa aplastada y limonada",
        "huk tortilla runtu yawarwan, kinwa, naranja",
        "lentejas espesas con charqui y limón"]
MID = ["arroz con huevo y plátano", "segundo de pollo con arroz y zanahoria", "trucha con olluco y arroz",
       "quinua con leche", "papilla de zapallo con huevo", "frejol con arroz y pan", "fideos con carne picada"]
BAD = ["sopa de fideos con té", "caldo de gallina con pan y mate", "solo pan con té", "sopa de papa con arroz",
       "galletas con gaseosa", "lawa de chuño con café"]
SCHEME = "Hierro en gotas/jarabe según indicación del establecimiento"

# perfil -> (prob. plato bueno, medio, malo), patrón de suplemento
PROFILES = {
    "comprometida": ((0.6, 0.3, 0.1), "constante"),
    "irregular": ((0.25, 0.45, 0.3), "irregular"),
    "abandono": ((0.15, 0.35, 0.5), "abandono"),
    "sin_registro": ((0.1, 0.4, 0.5), "ninguno"),
}


def run(reset: bool = False, n: int = 34, seed: int = 11) -> None:
    random.seed(seed)
    cfg = Config.from_env()
    # Los datos de demo se analizan SIEMPRE con el modelo local: 200+ comidas simuladas no deben
    # gastar cuota ni dinero de la API, ni demorar el arranque cuando el proveedor está saturado.
    cfg.ai_provider = "local"
    if reset:
        for suf in ("", "-wal", "-shm"):
            Path(cfg.database_path + suf).unlink(missing_ok=True)
    c = build_container(cfg)
    if c.children.list():
        print("La base ya tiene datos; usa --reset para regenerarla.")
        return
    today = c.clock.today()
    sectors = [s["nombre"] for s in c.territory.sectors()]
    weights = [3, 5, 3, 3, 4, 4, 2, 2, 4]  # más niños en sectores periurbanos
    with c.children.db.transaction():  # un solo commit: segundos en vez de minutos
        for i in range(n):
            sector = random.choices(sectors, weights)[0]
            base = c.territory.sector_point(sector)
            months = random.choice([6, 7, 8, 9, 10, 11, 13, 15, 18, 21, 24, 28, 32])
            bd = today - timedelta(days=int(months * 30.4) + random.randint(0, 20))
            child = c.register.execute(ALIASES[i % len(ALIASES)], bd.isoformat(), sector, f"mamá {i + 1}",
                                       random.choice("FM"), True,
                                       base.lat + random.uniform(-0.0025, 0.0025), base.lng + random.uniform(-0.0025, 0.0025))
            status = random.choices(["leve", "moderada", "severa", "sin_anemia", "sin_dato"], [38, 18, 2, 30, 12])[0]
            control = today + timedelta(days=random.randint(-20, 40))
            c.update_clinical.execute(child.id, status, {"leve": 9.8, "moderada": 8.6, "severa": 6.8}.get(status),
                                      (today - timedelta(days=random.randint(10, 60))).isoformat() if status != "sin_dato" else None,
                                      SCHEME if status in ("leve", "moderada", "severa") or random.random() < 0.4 else "",
                                      control.isoformat())
            profile = random.choices(list(PROFILES), [40, 30, 18, 12])[0]
            probs, pattern = PROFILES[profile]

            # comidas de los últimos 14 días
            for d in range(14, -1, -1):
                if profile == "sin_registro" and d < 9:
                    continue
                for _ in range(random.choice([0, 1, 1, 2])):
                    text = random.choice(random.choices([GOOD, MID, BAD], probs)[0])
                    meal = c.log_meal.execute(child.family_code, text)
                    when = datetime.combine(today - timedelta(days=d), time(random.choice([8, 12, 13, 18])), LOCAL_TZ)
                    c.meals.set_created_at(meal.id, when)

            # suplemento (solo si tiene esquema)
            if c.children.get(child.id).supplement_scheme and pattern != "ninguno":
                for d in range(20, -1, -1):
                    day = today - timedelta(days=d)
                    if pattern == "constante":
                        given = random.random() < 0.92
                    elif pattern == "irregular":
                        given = random.random() < 0.55
                    else:  # abandono: bien al inicio, deja en la última semana
                        given = random.random() < (0.85 if d > 7 else 0.1)
                    if d > 7:
                        # registros antiguos se insertan directo (el caso de uso solo acepta 7 días atrás)
                            c.supplements.upsert(SupplementLog(child.id, day, given))
                    else:
                        note = random.choice(["", "", "", "estreñimiento", "no quiere, lo escupe", "vomitó un poco"]) if not given else ""
                        c.log_supplement.execute(child.family_code, given, note, day.isoformat())
    # Código fijo para el jurado (no cambia entre despliegues)
    first = c.children.list()[0]
    demo_code = os.environ.get("DEMO_CODE", "K-DEMO1")
    c.children.db.execute("UPDATE children SET family_code=? WHERE id=?", (demo_code, first.id))
    d = c.dashboard.execute()
    demo = c.children.get(first.id)
    print(f"Semilla lista: {d['ninos']} niños, {d['en_tratamiento']} en tratamiento, adherencia {d['adherencia_promedio']} %, "
          f"{d['comidas_semana']} comidas esta semana. Código familiar de prueba: {demo.family_code}")
    Path(cfg.database_path).with_name("codigo_demo.txt").write_text(demo.family_code)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("-n", type=int, default=34)
    a = ap.parse_args()
    run(a.reset, a.n)

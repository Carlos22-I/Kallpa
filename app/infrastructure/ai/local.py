"""IA LOCAL de respaldo (sin internet ni costo).

- Reconocimiento de alimentos en texto (español y quechua) por coincidencia
  de sinónimos normalizados, con extracción de cantidades ("2 cucharadas",
  "medio plato", "una presa").
- Asistente por recuperación de pasajes (BM25 simplificado) sobre la base
  de conocimiento validada.
No ve imágenes: si solo llega una foto, devuelve confianza baja para que
la familia complete la descripción (ADR-002, ADR-006).
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter

from ...application.ports import FamilyAssistant, PlateAnalyzer
from ...domain.models import DetectedFood, Food, PlateAnalysis

NUM_WORDS = {"un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "medio": 0.5, "media": 0.5,
             "huk": 1, "iskay": 2, "kimsa": 3, "tawa": 4}
UNITS_G = {"cucharada": 15, "cucharadas": 15, "cucharadita": 5, "cucharaditas": 5, "cuchara": 15,
           "taza": 150, "tazas": 150, "vaso": 200, "plato": 200, "presa": 50, "presas": 50, "trozo": 30,
           "trozos": 30, "rodaja": 20, "unidad": 50, "puñado": 30, "punado": 30}
SOUP_WORDS = ("sopa", "caldo", "chupe", "lawa", "yaku", "aguadito", "sustancia")
THICK_WORDS = ("segundo", "pure", "papilla", "aplastado", "espeso", "picado", "tortilla", "guiso", "saltado")
QUECHUA = ("yawar", "wallpa", "aycha", "kinwa", "hawas", "runtu", "challwa", "quwi", "mikhun", "mikhurqan", "huk", "iskay")
STOP = set("de la el los las y en a un una que se por con del al es hay mi su lo le para no muy".split())


def norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    return "".join(c for c in t if not unicodedata.combining(c)).replace("'", "").replace("’", "")


class LocalPlateAnalyzer(PlateAnalyzer):
    name = "local-texto"

    def analyze(self, description, image, mime, catalog: list[Food]) -> PlateAnalysis:
        text = norm(description or "")
        if not text.strip():
            return PlateAnalysis((), 0.2, True, note="Recibimos la foto. Escribe también qué comió para calcular el hierro.",
                                 provider=self.name)
        # sinónimos más largos primero ("higado de pollo" antes que "higado")
        syn = sorted(((norm(s), f) for f in catalog for s in (f.synonyms + (f.name,))), key=lambda x: -len(x[0]))
        found: dict[str, DetectedFood] = {}
        taken = [False] * len(text)
        for s, f in syn:
            for m in re.finditer(r"(?<![a-z])" + re.escape(s) + r"(?:wan|ta|pi|cha|kuna|manta|lla)?(?![a-z])", text):
                if any(taken[m.start():m.end()]) or f.id in found:
                    continue
                for i in range(m.start(), m.end()):
                    taken[i] = True
                found[f.id] = DetectedFood(f.id, self._grams(text[:m.start()], f), 0.75)
        consistency = ("sopa" if any(w in text for w in SOUP_WORDS)
                       else "espesa" if any(w in text for w in THICK_WORDS) else "desconocida")
        words = [w for w in re.findall(r"[a-z]+", text) if w not in STOP]
        coverage = min(1.0, len(found) * 2.5 / max(1, len(words)))
        conf = round(min(0.85, 0.45 + 0.4 * coverage), 2) if found else 0.25
        q_hits = sum(1 for q in QUECHUA if q in text)
        return PlateAnalysis(tuple(found.values()), conf, True, consistency=consistency, provider=self.name,
                             language="qu" if q_hits >= 2 else ("mixto" if q_hits else "es"),
                             note="" if found else "No reconocimos alimentos; prueba escribiendo, por ejemplo: 'puré con 2 cucharadas de hígado'.")

    @staticmethod
    def _grams(before: str, f: Food) -> float:
        """Busca una cantidad justo antes del alimento: '2 cucharadas de', 'media presa de'."""
        window = before[-30:]
        m = re.search(r"(\d+(?:[.,]\d+)?|" + "|".join(NUM_WORDS) + r")\s*(" + "|".join(UNITS_G) + r")?\s*(de\s*)?$", window)
        if m:
            raw, unit = m.group(1), m.group(2)
            n = float(raw.replace(",", ".")) if raw[0].isdigit() else NUM_WORDS[raw]
            if unit:
                return n * UNITS_G[unit]
            if raw[0].isdigit() and n > 10:   # "40 g de"/"40 gramos"
                return n
        g = re.search(r"(\d+)\s*(g|gr|gramos)\s*(de\s*)?$", window)
        return float(g.group(1)) if g else f.portion_g


class LocalAssistant(FamilyAssistant):
    """Recuperación de pasajes con BM25 simplificado; responde con el pasaje más relevante."""

    def answer(self, question, context):
        passages = [p.strip() for p in context.split("\n\n") if p.strip()]
        tok = lambda s: [w[:6] for w in re.findall(r"[a-z]+", norm(s)) if w not in STOP and len(w) > 2]
        docs = [tok(p) for p in passages]
        q = tok(question)
        N, avg = len(docs), sum(len(d) for d in docs) / max(1, len(docs))
        df = Counter(w for d in docs for w in set(d))
        best, best_s = None, 0.0
        for p, d in zip(passages, docs):
            tf = Counter(d)
            s = sum(math.log(1 + (N - df[w] + 0.5) / (df[w] + 0.5)) * tf[w] * 2.2 / (tf[w] + 1.2 * (0.25 + 0.75 * len(d) / avg))
                    for w in q if w in tf)
            if s > best_s:
                best, best_s = p, s
        if not best or best_s < 0.5:
            return ("No tengo esa información. Consulta al personal de tu establecimiento de salud; "
                    "ellos te orientarán."), "local"
        return best, "local"

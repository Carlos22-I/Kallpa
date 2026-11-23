"""Ruta de visitas domiciliarias: vecino más cercano + mejora 2-opt.

El personal de salud (y los actores sociales) visita a pie o en mototaxi por
las calles en pendiente de Abancay; un buen orden ahorra horas por semana.
"""
from __future__ import annotations

from ..models import GeoPoint, VisitRoute, VisitStop

ROAD_FACTOR = 1.35          # sinuosidad de calles en pendiente
SPEED_KMH = 4.5             # a pie
VISIT_MIN = 25.0            # duración de cada visita


def _km(a: GeoPoint, b: GeoPoint) -> float:
    return a.distance_m(b) / 1000 * ROAD_FACTOR


def _length(origin: GeoPoint, pts: list[GeoPoint]) -> float:
    if not pts:
        return 0.0
    return _km(origin, pts[0]) + sum(_km(pts[i], pts[i + 1]) for i in range(len(pts) - 1)) + _km(pts[-1], origin)


def plan_visits(origin: GeoPoint, ranked: list[tuple[str, GeoPoint]], max_visits: int = 8) -> VisitRoute:
    """ranked: (child_id, ubicación) ya ordenados por prioridad."""
    chosen = ranked[:max_visits]
    baseline = _length(origin, [p for _, p in chosen])
    remaining, tour, cur = chosen[:], [], origin
    while remaining:
        nxt = min(remaining, key=lambda c: _km(cur, c[1]))
        tour.append(nxt)
        remaining.remove(nxt)
        cur = nxt[1]
    best, best_len, improved = tour, _length(origin, [p for _, p in tour]), True
    while improved:
        improved = False
        for i in range(len(best) - 1):
            for j in range(i + 1, len(best)):
                cand = best[:i] + best[i:j + 1][::-1] + best[j + 1:]
                L = _length(origin, [p for _, p in cand])
                if L + 1e-9 < best_len:
                    best, best_len, improved = cand, L, True
    stops, km, mins, cur = [], 0.0, 0.0, origin
    for i, (cid, p) in enumerate(best, 1):
        leg = _km(cur, p)
        km += leg
        mins += leg / SPEED_KMH * 60
        stops.append(VisitStop(cid, p, i, round(mins), round(km, 2)))
        mins += VISIT_MIN
        cur = p
    total_min = mins + (_km(cur, origin) / SPEED_KMH * 60 if best else 0)
    return VisitRoute(origin, tuple(stops), round(best_len, 2), round(total_min), round(baseline, 2),
                      "prioridad → vecino más cercano → 2-opt")

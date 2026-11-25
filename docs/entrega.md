# Plan de entrega y verificación

**Fecha límite:** lunes 7 de diciembre de 2026, 17:00 (GMT-5). Recomendado: enviar el **domingo 6** (se puede editar hasta la hora límite).

## 1. Elegibilidad
- [ ] Todos son estudiantes y mayores de edad, y están registrados en el hackatón y agregados al proyecto.
- [ ] Si para todos es su primera hackatón, postulen al premio de principiantes (US$ 500).
- [ ] Lean las reglas completas: el proyecto debe crearse durante el periodo del evento.

## 2. Requisitos de Devpost → entregable
| # | Requisito | Dónde | Estado |
|---|---|---|---|
| 1 | Nombre y descripción | `docs/devpost.md` | ✅ |
| 2 | Problema y solución (para quién) | `docs/devpost.md` | ✅ |
| 3 | Implementación de IA | `docs/devpost.md`, `README.md` | ✅ |
| 4 | Demo funcional + acceso | `render.yaml`, `docs/despliegue.md` | ⬜ desplegar |
| 5 | Capturas | `docs/capturas/` | ⬜ recapturar con una foto real y el mapa real |
| 6 | Repositorio con instrucciones | `README.md` | ⬜ subir a GitHub público |
| 7 | Video de 2 a 4 min | `docs/guion-video.md` | ⬜ grabar |

## 3. Criterios → evidencia
La página muestra dos versiones de los criterios (30/30/20/20 y 25/25/20/15/15); cubrimos ambas.

| Criterio | Evidencia |
|---|---|
| Innovación y creatividad (30 / 25) | Problema crítico de Apurímac; foto del plato con alimentos andinos y quechua; une familia y establecimiento en un solo flujo |
| Ejecución técnica (30 / 25) | Hexagonal, Bridge + Strategy, circuit breaker, RAG + BM25, priorización, recomendador, 2-opt, 42 pruebas, CI, Docker |
| Diseño y UX (20 / 15) | Resultado con puntaje, iconos y consejos concretos; registro en 3 pasos; panel accionable |
| Presentación e impacto (20 / 20) | 55.8 % de anemia; impacto en la adherencia; listo para un piloto; video con un caso real |
| IA y uso responsable (15) | "La IA percibe, el dominio calcula"; no diagnostica ni dosifica; privacidad; `docs/ia-responsable.md` |

## 4. Para el curso
- [ ] `docs/arquitectura.md` (drivers, atributos de calidad, C4, vistas, patrones, SOLID, seguridad, pruebas, riesgos).
- [ ] `docs/adr/` (7 ADRs) y `docs/diagramas/*.png`.
- [ ] Defensa: ¿por qué el LLM no calcula el hierro? (ADR-004) ¿Qué pasa si cae la IA? (ADR-002) ¿Cómo evitan diagnosticar? (ADR-006)

## 5. Cronograma (15 días)
| Fechas | Tarea |
|---|---|
| 22–23 nov | Ejecutar en local, repartir roles, crear el repo |
| 24–27 nov | API key (Claude o Gemini gratis); probar **10+ fotos reales de platos de Abancay** y ajustar el prompt y el catálogo |
| 24–28 nov | **Validar los valores de hierro** con la TPCA (CENAN-INS) y, si pueden, con un nutricionista o enfermera; ampliar sinónimos en quechua |
| 27–30 nov | Personalizar la UI, probar en celulares reales, poner los nombres del equipo |
| 29 nov | Desplegar en Render |
| 30 nov–2 dic | (Muy recomendado) Mostrarlo a personal de un establecimiento de Abancay y citar su opinión |
| 1–3 dic | Grabar y editar el video con subtítulos en inglés |
| 4–5 dic | Capturas finales y completar Devpost |
| **6 dic** | **Enviar** |
| 7–14 dic | Mantener la demo despierta para el jurado |

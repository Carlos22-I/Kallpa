# ADR-005: Priorización con fórmula explicable

- **Estado:** Aceptada · **Fecha:** 2026-11-22

## Contexto
El personal de salud tiene poco tiempo para visitas. Decidir a quién visitar afecta a niños vulnerables; la decisión debe poder explicarse y auditarse. No existen datos históricos etiquetados para entrenar un modelo.

## Decisión
Puntaje 0–100 con pesos públicos: hemoglobina 30, adherencia 25, dieta 20, edad 10, control vencido 10, molestias 5. Cada niño muestra sus razones con el puntaje que aporta cada una. Complemento: tendencia de adherencia con suavizado exponencial.

## Consecuencias
- ➕ Transparente para el personal, la DIRESA y las familias.
- ➕ Pesos configurables y calibrables con el equipo de salud durante el piloto.
- ➖ No aprende sola; evolución: usar los datos del piloto para validar los pesos (por ejemplo, con regresión logística sobre el abandono) manteniendo la explicabilidad.

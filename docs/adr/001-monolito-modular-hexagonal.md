# ADR-001: Monolito modular con arquitectura hexagonal

- **Estado:** Aceptada · **Fecha:** 2026-11-22

## Contexto
Equipo estudiantil, un mes de plazo y presupuesto cero. Necesitamos un prototipo funcional que pueda evolucionar (WhatsApp, integración con el MINSA, otro proveedor de IA) sin reescribir la lógica de salud.

## Opciones
1. MVC en Flask con SQL y llamadas a la IA dentro de las rutas.
2. Microservicios (familias, IA, panel).
3. Monolito modular hexagonal.

## Decisión
Opción 3.

## Consecuencias
- ➕ Reglas de nutrición y riesgo en Python puro: 37 pruebas en menos de 1 s.
- ➕ Cambiar de IA o de base de datos solo toca adaptadores y `container.py`.
- ➕ Fronteras listas para extraer un worker de IA.
- ➖ Más archivos y abstracciones que un MVC simple.

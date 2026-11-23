# ADR-004: El LLM percibe, el dominio calcula (catálogo cerrado)

- **Estado:** Aceptada · **Fecha:** 2026-11-22

## Contexto
Los LLM pueden "alucinar" cifras. En salud infantil, un número inventado de hierro es un riesgo real: una familia podría creer que una sopa es suficiente.

## Opciones
1. Pedir al LLM el hierro total del plato.
2. Pedir al LLM solo qué alimentos hay (ids de un catálogo cerrado) y cuántos gramos; calcular en el dominio con una tabla versionada.

## Decisión
Opción 2. La salida del LLM se valida (`to_plate_analysis`): ids desconocidos se descartan y gramos y confianza se acotan. El cálculo y el puntaje son deterministas y explicables (`domain/services/nutrition.py`).

## Consecuencias
- ➕ Cifras trazables y auditables por nutricionistas; la tabla se corrige sin tocar el código.
- ➕ Cambiar de modelo no cambia los números para una misma percepción.
- ➖ Alimentos fuera del catálogo se ignoran; se mitiga ampliando el catálogo (incluye sinónimos quechuas).

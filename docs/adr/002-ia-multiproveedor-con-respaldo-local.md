# ADR-002: IA multiproveedor con respaldo local y circuit breaker

- **Estado:** Aceptada · **Fecha:** 2026-11-22

## Contexto
El reconocimiento de alimentos en fotos requiere un LLM multimodal externo, que puede fallar, demorar o quedarse sin saldo. Una familia no debe quedarse sin registrar lo que comió su niño.

## Decisión
- Separar `LLMClient` (habla HTTP con Claude o con cualquier API compatible con OpenAI) de `PlateAnalyzer` (lógica del puerto): patrón Bridge.
- `ResilientAnalyzer`: cadena de proveedores con `CircuitBreaker` (3 fallos → abierto 60 s → semiabierto).
- El último eslabón es `LocalPlateAnalyzer` (texto en español o quechua), que nunca se corta.
- `urllib` de la biblioteca estándar: sin SDKs.

## Consecuencias
- ➕ Disponibilidad sin API key ni internet (para el registro por texto).
- ➕ Probamos el adaptador LLM con un cliente falso, sin red.
- ➖ El respaldo local no ve imágenes: pide a la familia describir el plato.

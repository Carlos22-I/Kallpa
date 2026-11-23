# ADR-003: SQLite en el prototipo, PostgreSQL en producción

- **Estado:** Aceptada · **Fecha:** 2026-11-22

## Contexto
La demo debe funcionar con `git clone` y en un plan gratuito; un piloto tendrá miles de registros diarios y datos sensibles.

## Decisión
SQLite (WAL, claves foráneas) detrás de los puertos de repositorio. En producción, PostgreSQL gestionado con cifrado en reposo y respaldos. La prioridad y las alertas se calculan al consultar.

## Consecuencias
- ➕ Cero configuración; las pruebas usan una base temporal.
- ➕ La migración no toca los casos de uso.
- ➖ El disco efímero de Render regenera la demo en cada despliegue.
- ➖ La priorización recorre todos los niños (O(n)); suficiente para un establecimiento (cientos de niños).

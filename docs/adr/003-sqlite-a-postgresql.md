# ADR-003: SQLite en desarrollo, PostgreSQL (Neon) en producción

- **Estado:** Aceptada · **Fecha:** 2026-11-22 · **Actualizada:** 2026-11-25 (PostgreSQL implementado)

## Contexto
La demo debe funcionar con `git clone` sin configurar nada, pero en Render el disco del plan gratuito es **efímero**: con SQLite, cada reinicio o despliegue borraba los niños, comidas y fotos registrados. Para la evaluación del hackatón y un piloto necesitamos datos persistentes, sin costo.

## Opciones evaluadas (planes gratuitos, noviembre 2026)
| Opción | Ventaja | Problema |
|---|---|---|
| SQLite en Render | Cero configuración | Se borra al reiniciar o redeplegar |
| Render Postgres Free | Mismo proveedor | Expira a los 30 días y luego se elimina |
| Supabase Free | Postgres + panel | Se pausa tras 1 semana sin actividad (hay que reactivarlo a mano) |
| **Neon Free** | Sin fecha de expiración, 1 GB, se "duerme" y despierta sola en la siguiente consulta | Primera consulta tras inactividad algo más lenta |

## Decisión
- **Local y pruebas:** SQLite (sin `DATABASE_URL`).
- **Producción (Render):** **PostgreSQL en Neon** vía `DATABASE_URL`.
- Los mismos repositorios SQL sirven para ambos: `PostgresDatabase` traduce los marcadores `?` → `%s`, reconecta una vez si Neon cerró la conexión y hace rollback ante errores.
- Las **fotos** se guardan en la tabla `photos` cuando hay PostgreSQL (`DbPhotoStorage`), porque el disco de Render no persiste.
- La semilla de demo solo se ejecuta si la base está vacía.

## Consecuencias
- ➕ Los datos sobreviven a reinicios, despliegues y al "sueño" del plan gratuito.
- ➕ Cambiar de proveedor (Render Postgres, Supabase, RDS) = cambiar `DATABASE_URL`.
- ➕ CI corre la suite completa en SQLite y en PostgreSQL 16.
- ➖ Fechas guardadas como texto ISO (compatibles con ambos motores); en un piloto conviene migrar a `timestamptz`/`date` e índices adicionales.
- ➖ Fotos en la base: bien para cientos o miles; a gran escala, mover a almacenamiento de objetos.

# ADR-006: Privacidad por diseño y "no diagnosticar ni dosificar"

- **Estado:** Aceptada · **Fecha:** 2026-11-22

## Contexto
Se manejan datos de salud de menores (datos sensibles según la Ley N.° 29733). Diagnosticar anemia o indicar dosis de hierro es responsabilidad del personal de salud según la norma técnica del MINSA.

## Decisión
- Código familiar aleatorio, alias en lugar del nombre, sin DNI; consentimiento obligatorio.
- El estado de hemoglobina y el esquema de suplemento **solo los registra el personal de salud** (`UpdateChildClinical`); la app no los calcula.
- El asistente tiene prohibido dar dosis y diagnósticos; deriva ante signos de alarma (también en el respaldo local, porque la base de conocimiento lo dice explícitamente).
- Las fotos con `persona_visible` no se guardan; el resto se re-codifica sin EXIF.
- La vista familiar no expone coordenadas.

## Consecuencias
- ➕ Menor riesgo legal y ético; confianza de las familias y del establecimiento.
- ➖ La app depende de que el establecimiento registre los resultados; se mitiga con el estado "sin dosaje" y el control vencido como factores de prioridad.

# ADR-007: Frontend sin paso de compilación y mapa resiliente

- **Estado:** Aceptada
- **Fecha:** 2026-11-22

## Contexto
Usuarios con celulares de gama baja y señal irregular; un equipo pequeño; despliegue gratuito.

## Decisión
- HTML, CSS y JavaScript sin framework ni bundler, servidos por Flask.
- Leaflet + OpenStreetMap para el mapa, detrás de un adaptador (`createMap`). Si Leaflet o los mosaicos no cargan, se usa `SvgMap`, un mapa esquemático que sigue mostrando a los niños y la ruta de visitas.
- La foto se comprime en el navegador (1024 px, JPEG 80 %) antes de subirse.

## Consecuencias
- ➕ Carga rápida, sin `npm install` ni compilación; cualquier integrante puede modificarlo.
- ➕ Funciona con mala conectividad.
- ➖ Sin componentes reutilizables al estilo React; si la UI crece, migrar a un framework (por ejemplo, Svelte o React) consumiendo la misma API.

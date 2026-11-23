# Despliegue

## Opción A — Render (gratis, recomendado para Devpost)
1. Suban el repositorio a GitHub (público).
2. En <https://render.com> → **New → Blueprint** → elijan el repositorio. Render lee `render.yaml`.
3. En *Environment*, agreguen `ANTHROPIC_API_KEY` **o** `OPENAI_API_KEY` + `OPENAI_BASE_URL` + `OPENAI_MODEL` (por ejemplo, Gemini con su capa gratuita).
4. `PANEL_TOKEN` se genera solo: cópienlo de *Environment* para entrar al panel y pónganlo en las instrucciones de acceso de Devpost para el jurado.
5. Abran `https://<app>.onrender.com/api/health`: debe responder `"status": "ok"` y listar los proveedores de IA.

> El plan gratuito "duerme" tras 15 minutos sin uso (el primer acceso tarda unos 50 s) y el disco es efímero: los datos de demo se regeneran en cada arranque (con el modelo local, sin gastar cuota de IA): **todo lo que se registre en la demo se pierde al reiniciar**. Antes de que el jurado evalúe (8 al 14 de diciembre), entren a la URL para "despertarla" o usen un monitor gratuito tipo UptimeRobot.

## Opción B — Docker
```bash
cp .env.example .env   # completen las claves
docker compose up --build
# http://localhost:8000
```

## Opción C — Railway / Fly.io / VPS
- Comando de arranque: `python -m app.seed && gunicorn -w 1 --threads 8 -b 0.0.0.0:$PORT wsgi:app`
- Variables: las mismas de `.env.example`. Si hay un proxy inverso delante, `TRUSTED_PROXIES=1`.

## Instrucciones de acceso para el jurado (pegar en Devpost)
```
Demo familiar: https://<app>.onrender.com/?codigo=K-DEMO1
Panel de salud: https://<app>.onrender.com/panel   (token: <PANEL_TOKEN>)
Si la página tarda ~50 s en cargar, es el arranque en frío del plan gratuito.
Los datos son simulados. Para probar la IA de visión, usen el código K-DEMO1 y suban la foto de un plato de comida.
```

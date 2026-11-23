# APIs de IA para Kallpa: opciones, costos e implementación

*Precios verificados el 23 de noviembre de 2026 en las páginas oficiales. Revísenlos antes de pagar, porque cambian.*

## 1. Qué necesita Kallpa de la IA

| Tarea | Qué hace el modelo | Requisito |
|---|---|---|
| Reconocer el plato | Ve la foto y devuelve qué alimentos del catálogo hay y cuántos gramos | **Visión** (imagen → texto), salida JSON |
| Asistente | Responde dudas en español o quechua usando la base de conocimiento | Texto, buen español |

Por cada foto se envían unos **1,700 tokens de entrada** (≈ 600 del prompt con el catálogo + ≈ 1,036 de la imagen comprimida a 1024 × 768) y se reciben unos **150–200 de salida**. Cada pregunta al asistente usa ≈ 1,400 de entrada y ≈ 150 de salida.

## 2. Opciones comparadas

| Opción | Precio (USD por 1M tokens, entrada / salida) | Costo aprox. por foto | Capa gratis | Comentario |
|---|---|---|---|---|
| **Claude Haiku 5.5** (`claude-haiku-5-5`) | 0.10 / 0.50 (prompts < 100k) | **≈ US$ 0.0003** | Créditos de prueba para cuentas nuevas | Más barato por foto; buena visión y español; ya es el valor por defecto de Kallpa |
| **Gemini 3.1 Flash-Lite** (`gemini-3.1-flash-lite`) | 0.25 / 1.50 | ≈ US$ 0.001 (pagado) | **Sí, gratis** con límites por minuto y día | Ideal de respaldo a costo cero. En la capa gratis Google puede usar los datos para mejorar sus productos |
| Gemini 2.5 Flash-Lite | 0.10 / 0.40 | ≈ US$ 0.0003 | Sí | Barato, pero es de generación anterior; Google suele retirar los modelos viejos |
| Claude Sonnet 5.5 | 2.00 / 10.00 | ≈ US$ 0.005 | — | Más preciso, ~20× más caro; no hace falta |
| GPT-4o-mini (OpenAI) | 0.15 / 0.60 | ≈ US$ 0.004 | No | OpenAI cobra muchos tokens por imagen en este modelo: en la práctica sale más caro para fotos |

## 3. Recomendación

**Usar las dos, en cadena** (Kallpa ya lo soporta sin cambiar código):

1. **Principal: Claude Haiku 5.5.** Es el más barato por foto. Los datos enviados por la API no se usan para entrenar por defecto, lo que importa porque son datos de salud infantil.
2. **Respaldo: Gemini 3.1 Flash-Lite, capa gratuita.** Si Claude falla o se queda sin saldo, el *circuit breaker* pasa a Gemini sin que la familia lo note.
3. **Último respaldo: el modelo local** (texto), que no cuesta nada y funciona sin internet.

Esto además **demuestra la arquitectura** ante el jurado y en el curso: tres proveedores intercambiables detrás del mismo puerto (ADR-002).

> Si no pueden poner una tarjeta, empiecen **solo con Gemini gratis** (dejen vacío `ANTHROPIC_API_KEY`). La app funciona igual.

## 4. Cuánto les va a costar

| Escenario | Uso estimado | Claude Haiku 5.5 | Gemini 3.1 Flash-Lite |
|---|---|---|---|
| **Hackatón** (pruebas + jurado) | 1,500 fotos + 1,000 preguntas | **≈ US$ 0.65** | US$ 0 (capa gratis) |
| **Piloto de un mes** (300 familias, 2 fotos/día) | 18,000 fotos + 4,500 preguntas | **≈ US$ 6 / mes** | ≈ US$ 25 / mes pagado |
| Hosting (Render plan gratis) | — | US$ 0 | US$ 0 |

**Presupuesto sugerido para el hackatón: recargar US$ 5 en Anthropic.** Les sobra. Además, el panel de salud muestra el **costo real acumulado** (sección "🤖 IA: proveedores y costo").

## 5. Qué necesitan (checklist)

- [ ] **Cuenta en Anthropic Console** (<https://console.anthropic.com>) → *Billing*: recargar crédito → *API Keys*: crear una clave (`sk-ant-...`).
- [ ] En la consola, poner un **límite de gasto mensual** (por ejemplo, US$ 10) para evitar sorpresas.
- [ ] **Cuenta de Google** → <https://aistudio.google.com/apikey> → *Create API key* (gratis, sin tarjeta).
- [ ] Las claves van **solo** en `.env` (local) o en *Environment* de Render. **Nunca** en GitHub ni en el JavaScript del navegador (`.env` ya está en `.gitignore`).

## 6. Cómo implementarlo (paso a paso)

### En su computadora
```bash
cp .env.example .env
# Abre .env y pega:
#   ANTHROPIC_API_KEY=sk-ant-...
#   OPENAI_API_KEY=<clave de Google AI Studio>
python -m app.probar_ia                         # prueba con texto
python -m app.probar_ia --foto plato.jpg        # prueba con una foto real de un plato
python wsgi.py                                  # levanta la app
```
`probar_ia` muestra, para cada proveedor, los alimentos detectados, el tiempo, los tokens y el **costo de esa llamada**. Si algo falla, indica si es la clave, el modelo, la cuota o la conexión.

### En Render (producción)
1. *Dashboard → kallpa → Environment → Add Environment Variable*:
   - `ANTHROPIC_API_KEY` = `sk-ant-...`
   - `OPENAI_API_KEY` = clave de Google
   - `OPENAI_BASE_URL` = `https://generativelanguage.googleapis.com/v1beta/openai/`
   - `OPENAI_MODEL` = `gemini-3.1-flash-lite`
   - `OPENAI_REASONING_EFFORT` = `low`
2. *Save* → Render redepliega solo.
3. Verificar: `https://<app>.onrender.com/api/health` debe listar `claude:claude-haiku-5-5 → gemini:gemini-3.1-flash-lite → local-texto`.
4. Subir una foto desde la app con el código `K-DEMO1` y revisar el panel: aparecen las llamadas y el costo.

### Qué cambió en el código para esto
- `app/infrastructure/ai/llm.py`: medidor de tokens y costo (`UsageMeter`) con la tabla de precios; soporte de `reasoning_effort` para Gemini 3; `max_completion_tokens` para los modelos nuevos de OpenAI.
- `app/probar_ia.py`: herramienta de diagnóstico.
- `GET /api/panel/ia`: estado de la cadena (circuito abierto o cerrado) y costo acumulado, visible en el panel.
- 5 pruebas nuevas que simulan las respuestas de Claude y Gemini (sin gastar saldo).

## 7. Problemas comunes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `HTTP 401` | Clave mal copiada | Volver a copiarla sin espacios |
| `HTTP 400 ... credit balance` (Claude) | Sin saldo | Recargar en *Billing* |
| `HTTP 429` (Gemini) | Límite de la capa gratis | Esperar; Claude o el modelo local responden mientras tanto |
| `HTTP 404 model not found` | El modelo cambió de nombre o fue retirado | Copiar el id exacto de la consola y actualizar `*_MODEL` |
| La foto devuelve "no se reconocieron alimentos" | Foto oscura o el plato no ocupa la imagen | Foto desde arriba, con luz; o describir el plato |

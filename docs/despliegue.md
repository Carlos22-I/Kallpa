# Despliegue de Kallpa en Render + PostgreSQL (Neon)

Arquitectura de producción (todo en planes gratuitos):

```
Celular / PC ──HTTPS──► Render (web service Flask + gunicorn, región Virginia)
                              │
                              ├──► Neon PostgreSQL (AWS us-east-1)  ← niños, comidas, suplemento, fotos
                              └──► Gemini API (capa gratuita)        ← reconocer alimentos, asistente
```

| Componente | Servicio | Costo | Por qué |
|---|---|---|---|
| App web (PaaS) | Render Free | US$ 0 | Despliegue desde GitHub con `render.yaml` |
| Base de datos (DBaaS) | **Neon Free** | US$ 0 | PostgreSQL sin fecha de expiración; se suspende sola tras 5 min sin uso y despierta en la siguiente consulta |
| IA (AIaaS) | Gemini Free | US$ 0 | Ver `docs/ia-apis.md` |

> **¿Por qué no SQLite en Render?** El disco del plan gratuito de Render es efímero: cada reinicio, despliegue o "despertar" borraba los datos. **¿Por qué no Render Postgres?** El gratuito expira a los 30 días. **¿Por qué no Supabase?** Se pausa tras una semana sin actividad y hay que reactivarlo a mano (riesgoso durante la evaluación). Detalle en ADR-003.

---

## Paso 1 · Subir los cambios a GitHub
```bash
git add .
git commit -m "PostgreSQL (Neon) para producción y fotos persistentes"
git push
```

## Paso 2 · Crear la base de datos en Neon (5 min, sin tarjeta)
1. Entren a **https://neon.com** → **Sign up** (pueden usar su cuenta de GitHub o Google).
2. **Create project**:
   - *Project name:* `kallpa`
   - *Postgres version:* 16 o 17 (cualquiera sirve)
   - *Region:* **AWS US East 1 (N. Virginia)** (la misma zona que Render en Virginia)
3. En el panel del proyecto pulsen **Connect** (o *Connection string*):
   - Elijan la conexión **Pooled** (con `-pooler` en el host) si está disponible.
   - Copien la cadena completa, del tipo:
     ```
     postgresql://neondb_owner:XXXXXXXX@ep-xxxx-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require
     ```
4. Guárdenla en un lugar seguro: **es una contraseña**. No la suban a GitHub.

> Las tablas se crean solas la primera vez que arranca Kallpa; no hay que ejecutar SQL a mano.

## Paso 3A · Si TODAVÍA NO crearon el servicio en Render
1. **https://render.com** → **New → Blueprint** → elijan el repositorio `Kallpa` → **Apply**.
2. Render pedirá las variables marcadas como secretas:
   - `DATABASE_URL` → peguen la cadena de Neon.
   - `OPENAI_API_KEY` → su clave de Gemini.
   - `ANTHROPIC_API_KEY` → déjenla **vacía**.
3. Esperen a que diga **Live** (3 a 5 min). Al primer arranque, la semilla crea los datos de demo en Neon (34 niños, código `K-DEMO1`).

## Paso 3B · Si YA tienen el servicio creado en Render
1. Render → su servicio `kallpa` → **Environment** → **Add Environment Variable**:
   - Key: `DATABASE_URL` · Value: la cadena de Neon → **Save changes**.
2. Revisen que el **Start Command** (en *Settings*) sea **sin `--reset`**:
   ```
   python -m app.seed && gunicorn -w 1 --threads 8 -b 0.0.0.0:$PORT wsgi:app
   ```
   (Si se creó con Blueprint, el `git push` del Paso 1 lo actualiza solo.)
3. **Manual Deploy → Deploy latest commit**.
4. **Región:** un servicio existente no cambia de región. Miren en *Settings* en qué región está: si es **Oregon**, creen el proyecto de Neon en **AWS US West 2 (Oregon)**; si es **Ohio**, en **AWS US East 2 (Ohio)**. Base y app en la misma zona = respuestas más rápidas.

## Paso 4 · Verificar
1. `https://<su-app>.onrender.com/api/health` debe mostrar:
   ```json
   {"status": "ok", "base_de_datos": "postgres", "ia": [{"proveedor": "gemini:...", ...}, ...]}
   ```
   Si dice `"sqlite"`, la variable `DATABASE_URL` no se cargó: revisen el nombre exacto y redepliegen.
2. Abran `https://<su-app>.onrender.com/?codigo=K-DEMO1`, registren una comida con foto y marquen el suplemento.
3. En Render: **Manual Deploy → Restart service**. Vuelvan a entrar: **la comida y la foto deben seguir ahí**. ✅
4. En Neon → **Tables**: verán `children`, `meals`, `supplements` y `photos` con datos.

## Paso 5 · Mantenerla lista para el jurado
- El web service gratuito de Render "duerme" tras 15 minutos sin visitas (la primera carga tarda unos 50 s). Neon también se suspende, pero despierta sola: Kallpa reconecta automáticamente.
- Del 8 al 14 de diciembre, abran la app cada día o configuren un monitor gratuito (por ejemplo, UptimeRobot) que visite `/api/health`.

---

## Comandos útiles

| Necesidad | Cómo |
|---|---|
| Regenerar los datos de demo en Neon (borra TODO) | En su PC: `DATABASE_URL="<cadena de Neon>" python -m app.seed --reset`. En Windows PowerShell: `$env:DATABASE_URL="<cadena>"; python -m app.seed --reset` |
| Ver datos con SQL | Neon → **SQL Editor**: `SELECT alias, sector, hb_status FROM children;` |
| Probar todo contra PostgreSQL | `TEST_DATABASE_URL="<cadena de una base SOLO de pruebas>" pytest -q` (vacía esa base) |
| Volver a SQLite en local | No definan `DATABASE_URL` (o déjenla vacía en `.env`) |

## Problemas comunes

| Síntoma | Causa | Solución |
|---|---|---|
| `/api/health` dice `"base_de_datos": "sqlite"` | Falta `DATABASE_URL` en Render | Agregarla en *Environment* y redesplegar |
| Error `Falta el driver de PostgreSQL` | No se instaló `psycopg` | Confirmen que `requirements.txt` incluye `psycopg[binary]` y que el build usa ese archivo |
| `password authentication failed` | Cadena mal copiada | Copiarla de nuevo desde Neon → *Connect* |
| `SSL connection is required` | Falta `?sslmode=require` al final | Agregarlo |
| Primera carga muy lenta | Render y Neon despertando | Normal en planes gratuitos (≈ 1 min); luego es rápida |
| Los datos se "reinician" en cada despliegue | El Start Command tiene `--reset` | Quitar `--reset` |

## Opción alternativa — Docker en su PC
```bash
cp .env.example .env        # pongan OPENAI_API_KEY y, si quieren, DATABASE_URL
docker compose up --build   # http://localhost:8000
```

## Instrucciones de acceso para el jurado (pegar en Devpost)
```
Demo familiar: https://<app>.onrender.com/?codigo=K-DEMO1
Panel de salud: https://<app>.onrender.com/panel   (token: <PANEL_TOKEN>)
Si la página tarda ~50 s en cargar, es el arranque en frío del plan gratuito.
Los datos son simulados y se guardan en PostgreSQL. Para probar la IA de visión, usen el código K-DEMO1 y suban la foto de un plato.
```

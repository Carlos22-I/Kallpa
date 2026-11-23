FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd -m kallpa && mkdir -p instance uploads && chown -R kallpa /app
USER kallpa
EXPOSE 8000
# Carga datos de demo si la BD no existe y levanta gunicorn.
# 1 worker con hilos: el límite de solicitudes, el medidor de IA y los circuit breakers viven en memoria.
CMD ["sh", "-c", "[ -f instance/kallpa.db ] || python -m app.seed; gunicorn -w 1 --threads 8 -b 0.0.0.0:${PORT:-8000} wsgi:app"]

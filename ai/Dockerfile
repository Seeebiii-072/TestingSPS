FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SERVICE_PORT=8001

WORKDIR /app

COPY ai/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ai/ ./ai/

EXPOSE 8001

CMD ["sh", "-c", "uvicorn ai.main:app --host 0.0.0.0 --port ${SERVICE_PORT:-8001}"]

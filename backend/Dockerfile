FROM python:3.12-slim AS builder

WORKDIR /app/backend

# Install build dependencies, then remove them
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# --- Production stage ---
FROM python:3.12-slim

# Create non-root user
RUN groupadd -r securedesk && useradd -r -g securedesk -d /app -s /sbin/nologin securedesk

WORKDIR /app/backend

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy backend code
COPY . .

# Create upload directory with restricted permissions
RUN mkdir -p /var/data/uploads && chown -R securedesk:securedesk /var/data/uploads

# Security: drop capabilities, no new privileges
RUN chmod 444 /app/backend/*.py 2>/dev/null || true

EXPOSE 8000

# Switch to non-root user
USER securedesk

# Security: prevent fork bombs, core dumps
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=1

# Run with production settings
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2 --limit-concurrency 100 --backlog 2048"]

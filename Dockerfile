# =============================================================================
# SPS SecureDesk AI — Email Worker
# Stage: Production image
# =============================================================================
FROM python:3.11-slim AS production

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Create non-root user
RUN groupadd --system --gid 1001 appuser \
    && useradd --system --uid 1001 --gid appuser --create-home appuser

# Set working directory
WORKDIR /app

# Install system dependencies needed for aioimaplib / SSL
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        libffi-dev \
        libssl-dev \
        ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first for dependency caching
COPY email_worker/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the email_worker module
COPY email_worker/ /app/email_worker/

# Create data directory for message store
RUN mkdir -p /app/data && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import socket; socket.create_connection(('localhost', 8000), timeout=5)" || exit 1

# Run the email worker
CMD ["python", "-m", "email_worker.main"]
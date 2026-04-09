# Multi-stage build for Shizuku Nya Bot
# Stage 1: Base Python environment
FROM python:3.12-slim as base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r shizuku && useradd -r -g shizuku shizuku

# Stage 2: Dependencies installation
FROM base as deps

COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Stage 3: Application
FROM base as app

# Copy from deps stage
COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=shizuku:shizuku . .

# Create necessary directories with proper permissions
RUN mkdir -p /app/data /app/logs /app/agent_datas && \
    chown -R shizuku:shizuku /app/data /app/logs /app/agent_datas && \
    chmod 755 /app/data /app/logs /app/agent_datas

# Switch to non-root user
USER shizuku

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Expose ports
EXPOSE 5000 8000

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SHIZUKU_ENV=production \
    PYTHONNOUSERSITE=1

# Run application
CMD ["python", "main.py"]

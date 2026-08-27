# ============================================================
# AI Infrastructure Troubleshooting Agent — Production Dockerfile
#
# Rules:
#  - Production Python slim image (no :latest)
#  - Minimal surface area (no dev tools, no build caches)
#  - Non-root user (uid 1000)
#  - No credentials, secrets, or .env baked in
#  - All configuration via environment variables at runtime
#  - Health check via /health endpoint
#  - Correct signal handling via tini (PID 1) + uvicorn
#  - Read-only filesystem where possible
# ============================================================

# ---- Stage 1: dependency builder ----
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies only in this stage
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first for layer caching
COPY requirements.txt .

# Install into an isolated prefix so we can copy cleanly
RUN pip install --no-cache-dir --prefix=/install \
    fastapi>=0.115.0 \
    uvicorn[standard]>=0.30.0 \
    pydantic>=2.9.0 \
    pydantic-settings>=2.5.0 \
    langgraph>=0.2.0 \
    langchain-core>=0.3.0 \
    langchain-openai>=0.2.0 \
    openai>=1.50.0 \
    httpx>=0.27.0 \
    python-dotenv>=1.0.0


# ---- Stage 2: production runtime ----
FROM python:3.12-slim AS runtime

# Install tini for correct PID 1 / signal handling
RUN apt-get update && apt-get install -y --no-install-recommends \
        tini \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user and group
RUN groupadd --gid 1000 aiagent \
    && useradd --uid 1000 --gid 1000 --no-create-home --shell /bin/false aiagent

# Copy installed packages from builder stage
COPY --from=builder /install /usr/local

# Application directory
WORKDIR /app

# Copy application source
COPY app/ ./app/

# Fix ownership — application runs as non-root
RUN chown -R aiagent:aiagent /app

# Switch to non-root user
USER aiagent

# Environment defaults (all sensitive values MUST be provided at runtime)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONFAULTHANDLER=1 \
    ENVIRONMENT=production \
    DEBUG=false \
    LOG_LEVEL=INFO \
    LOG_FORMAT=json \
    HOST=0.0.0.0 \
    PORT=8080 \
    REQUIRE_HUMAN_APPROVAL=true \
    TOOL_TIMEOUT_SECONDS=30 \
    LLM_TIMEOUT_SECONDS=60 \
    MAX_INVESTIGATION_STEPS=20

# Expose port
EXPOSE 8080

# Health check — liveness probe
# Uses /health (always returns 200 while process is alive)
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# tini handles PID 1 and proper signal forwarding to uvicorn
ENTRYPOINT ["/usr/bin/tini", "--"]

# Production uvicorn startup:
#  - workers=1 (single-process; scale via Kubernetes replicas)
#  - no reload (production mode)
#  - access-log disabled (structured logging handles this)
#  - timeout-keep-alive matches GKE load balancer timeouts
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8080", \
     "--workers", "1", \
     "--no-access-log", \
     "--timeout-keep-alive", "65"]

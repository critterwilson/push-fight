# ============================================================
# Stage 1 — Build React frontend
# ============================================================
FROM node:22-slim AS frontend-builder

WORKDIR /frontend

# Install deps first so this layer caches when source is unchanged
COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ============================================================
# Stage 2 — Python application
# ============================================================
FROM python:3.13-slim

# Non-root user (UID 1001) for security
RUN groupadd -r appuser && useradd -r -g appuser -u 1001 appuser

WORKDIR /app

# Install Python dependencies.
# pygame installs via binary wheel and is needed only for local dev;
# the server entry-point (uvicorn) never imports it.
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Application source — copy selectively to keep the image lean
COPY app/    ./app/
COPY assets/ ./assets/
COPY models/ ./models/

# Built React app — FastAPI StaticFiles mounts this at /
COPY --from=frontend-builder /frontend/dist ./frontend/dist

# Runtime write directory for game saves
RUN mkdir -p saves && chown -R appuser:appuser /app

USER 1001

EXPOSE 8000

# Docker-native health check (supplements the K8s probes in deployment.yaml)
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "app.server.main:app", "--host", "0.0.0.0", "--port", "8000"]

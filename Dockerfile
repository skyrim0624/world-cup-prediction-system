FROM node:22-slim AS web-build

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

COPY index.html tsconfig.json tsconfig.node.json vite.config.ts ./
COPY public ./public
COPY src ./src
RUN npm run build

FROM python:3.12-slim AS runtime

WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV WORLD_CUP_SERVE_STATIC=1
ENV PORT=8000

RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs npm \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /usr/sbin/nologin appuser
RUN python3 -m pip install --no-cache-dir "fastapi>=0.128.0" "uvicorn>=0.40.0"

COPY backend ./backend
COPY scripts ./scripts
COPY package.json ./package.json
COPY --from=web-build /app/dist ./dist

RUN mkdir -p backend/snapshots backend/data_files reports && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).read()"

CMD ["sh", "-c", "python3 -m uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WORLD_CUP_API_WORKERS:-2}"]

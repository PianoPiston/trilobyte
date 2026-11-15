FROM node:22-alpine AS web-build
WORKDIR /build/web
COPY web/package.json web/package-lock.json* ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /opt/driftci
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY server/ ./server/
COPY examples/ ./examples/
COPY --from=web-build /build/web/dist ./web/dist
RUN mkdir -p /data && useradd --system --uid 10001 driftci && chown -R driftci:driftci /data
USER driftci
ENV DRIFTCI_DB_PATH=/data/driftci.db DRIFTCI_EXAMPLE_DIR=/opt/driftci/examples/orders-ai
EXPOSE 8100
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8100/api/health')"
CMD ["python", "-m", "uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8100"]

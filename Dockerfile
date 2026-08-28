FROM node:22-bookworm-slim AS web-build

WORKDIR /build/web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates nmap \
    && rm -rf /var/lib/apt/lists/*

COPY src/ ./src/
COPY pyproject.toml README.md LICENSE ./
COPY --from=web-build /build/web/dist ./web/dist/

EXPOSE 8080
CMD ["python", "-m", "tonmen.web_server"]

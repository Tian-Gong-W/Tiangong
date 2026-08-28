# Railway production image
FROM node:22-bookworm-slim AS web-build

WORKDIR /build/web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM golang:1.26-bookworm AS security-tools

ENV CGO_ENABLED=0
RUN mkdir -p /out \
    && GOBIN=/out go install github.com/projectdiscovery/httpx/cmd/httpx@v1.10.0 \
    && GOBIN=/out go install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@v3.11.1 \
    && GOBIN=/out go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@v2.16.0 \
    && GOBIN=/out go install github.com/projectdiscovery/katana/cmd/katana@v1.7.0

FROM python:3.12-slim AS python-tests

WORKDIR /test
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
COPY tests/ ./tests/
RUN pip install --no-cache-dir '.[dev]' \
    && pytest -q

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV TONMEN_NUCLEI_TEMPLATES=/root/nuclei-templates

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates nmap \
    && rm -rf /var/lib/apt/lists/*

COPY --from=security-tools /out/httpx /usr/local/bin/httpx
COPY --from=security-tools /out/nuclei /usr/local/bin/nuclei
COPY --from=security-tools /out/subfinder /usr/local/bin/subfinder
COPY --from=security-tools /out/katana /usr/local/bin/katana
RUN httpx -version \
    && subfinder -version \
    && katana -version \
    && nuclei -version \
    && nuclei -ut -silent \
    && find "$TONMEN_NUCLEI_TEMPLATES" -type f -name '*.yaml' -print -quit | grep -q .

COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
RUN pip install --no-cache-dir .
COPY --from=web-build /build/web/dist ./web/dist/

EXPOSE 8080
CMD ["python", "-u", "-m", "tonmen.web_server"]

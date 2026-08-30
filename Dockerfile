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

# Official account-login CLIs used only as bounded AI providers. Versions are pinned
# to current stable releases verified when this image was authored.
FROM node:22-bookworm-slim AS ai-clis
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl tar gzip \
    && rm -rf /var/lib/apt/lists/*
RUN npm install -g --omit=dev @openai/codex@0.151.0 @xai-official/grok@1.0.5
ARG AGY_VERSION=1.1.22
ARG AGY_LINUX_X64_SHA256=1e1a219a86e75d7c6351f96d182ca2105302d5c34d8fa9c31265dc0adf24145f
RUN curl -fL "https://github.com/google-antigravity/antigravity-cli/releases/download/${AGY_VERSION}/agy_cli_linux_x64.tar.gz" -o /tmp/agy.tgz \
    && echo "${AGY_LINUX_X64_SHA256}  /tmp/agy.tgz" | sha256sum -c - \
    && mkdir -p /tmp/agy \
    && tar -xzf /tmp/agy.tgz -C /tmp/agy \
    && AGY_BIN="$(find /tmp/agy -type f \( -name 'antigravity' -o -name 'agy' -o -name 'agy_cli' \) | head -n 1)" \
    && test -n "$AGY_BIN" \
    && install -m 0755 "$AGY_BIN" /usr/local/bin/agy \
    && codex --version \
    && grok --version \
    && agy --version

FROM python:3.12-slim AS python-tests

ENV TONMEN_EXTENDED_DISCOVERY=0
WORKDIR /test
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
COPY tests/ ./tests/
RUN pip install --no-cache-dir '.[dev]' \
    && pytest -q \
    && touch /test/.pytest-passed

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV TONMEN_NUCLEI_TEMPLATES=/root/nuclei-templates
ENV TONMEN_EXTENDED_DISCOVERY=1
ENV HOME=/data/provider-home
ENV TONMEN_AI_SETTINGS_FILE=/data/tonmen/ai-settings.json
ENV TONMEN_AI_SECRETS_FILE=/data/tonmen/ai-secrets.json

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates nmap \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /data/provider-home /data/tonmen \
    && chmod 700 /data/provider-home /data/tonmen

COPY --from=security-tools /out/httpx /usr/local/bin/httpx
COPY --from=security-tools /out/nuclei /usr/local/bin/nuclei
COPY --from=security-tools /out/subfinder /usr/local/bin/subfinder
COPY --from=security-tools /out/katana /usr/local/bin/katana

# Codex and Grok npm packages ship native launchers behind Node package wrappers.
# Keep the exact global package tree and Node runtime from the pinned ai-clis stage.
COPY --from=ai-clis /usr/local/bin/node /usr/local/bin/node
COPY --from=ai-clis /usr/local/lib/node_modules /usr/local/lib/node_modules
COPY --from=ai-clis /usr/local/bin/codex /usr/local/bin/codex
COPY --from=ai-clis /usr/local/bin/grok /usr/local/bin/grok
COPY --from=ai-clis /usr/local/bin/agy /usr/local/bin/agy

RUN httpx -version \
    && subfinder -version \
    && katana -version \
    && nuclei -version \
    && nuclei -ut -silent \
    && find "$TONMEN_NUCLEI_TEMPLATES" -type f -name '*.yaml' -print -quit | grep -q . \
    && codex --version \
    && grok --version \
    && agy --version

COPY --from=python-tests /test/.pytest-passed /tmp/pytest-passed
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
RUN pip install --no-cache-dir .
COPY --from=web-build /build/web/dist ./web/dist/

EXPOSE 8080
CMD ["python", "-u", "-m", "tonmen.web_server"]

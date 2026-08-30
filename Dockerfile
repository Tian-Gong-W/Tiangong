FROM python:3.12-slim

ARG NUCLEI_VERSION=3.11.1
ARG HTTPX_VERSION=1.10.0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TONMEN_NUCLEI_TEMPLATES=/opt/nuclei-templates

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        nmap \
        unzip \
    && arch="$(dpkg --print-architecture)" \
    && case "$arch" in \
         amd64) asset_arch=amd64 ;; \
         arm64) asset_arch=arm64 ;; \
         *) echo "Unsupported Debian architecture: $arch" >&2; exit 1 ;; \
       esac \
    && curl --fail --location --retry 3 \
         "https://github.com/projectdiscovery/httpx/releases/download/v${HTTPX_VERSION}/httpx_${HTTPX_VERSION}_linux_${asset_arch}.zip" \
         -o /tmp/httpx.zip \
    && unzip -q /tmp/httpx.zip -d /usr/local/bin \
    && chmod 0755 /usr/local/bin/httpx \
    && curl --fail --location --retry 3 \
         "https://github.com/projectdiscovery/nuclei/releases/download/v${NUCLEI_VERSION}/nuclei_${NUCLEI_VERSION}_linux_${asset_arch}.zip" \
         -o /tmp/nuclei.zip \
    && unzip -q /tmp/nuclei.zip -d /usr/local/bin \
    && chmod 0755 /usr/local/bin/nuclei \
    && mkdir -p /opt/nuclei-templates \
    && nuclei -update-templates -update-template-dir /opt/nuclei-templates -silent \
    && rm -rf /tmp/*.zip /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir . \
    && tonmen --config /app/tonmen.toml.example doctor || true

EXPOSE 8888

CMD ["tonmen", "console", "--no-open"]

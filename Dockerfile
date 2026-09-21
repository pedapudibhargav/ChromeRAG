ARG DOCKER_PYTHON_IMAGE=python:3.12-slim
FROM ${DOCKER_PYTHON_IMAGE}

WORKDIR /app

# Defaults to public PyPI. Override via --build-arg when using a private mirror (.env).
ARG PYPI_INDEX_URL=https://pypi.org/simple/
ARG PIP_TRUSTED_HOST=

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    curl \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
ENV CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
ENV PIP_CERT=/etc/ssl/certs/ca-certificates.crt

COPY requirements.txt requirements-poc.txt pyproject.toml README.md ./
COPY src ./src
COPY poc ./poc
COPY scripts ./scripts

RUN set -eux; \
    PIP_ARGS="--no-cache-dir --index-url ${PYPI_INDEX_URL} \
      --trusted-host pypi.org \
      --trusted-host files.pythonhosted.org \
      --trusted-host pypi.python.org"; \
    if [ -n "${PIP_TRUSTED_HOST}" ]; then \
      for h in ${PIP_TRUSTED_HOST}; do PIP_ARGS="${PIP_ARGS} --trusted-host ${h}"; done; \
    fi; \
    pip install ${PIP_ARGS} -r requirements-poc.txt; \
    pip install ${PIP_ARGS} --no-build-isolation -e .

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app/src

CMD ["python", "-m", "poc.run_benchmark"]

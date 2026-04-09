ARG FRONTEND_BASE_IMAGE=node:22-bookworm-slim
ARG BACKEND_BASE_IMAGE=python:3.12-bookworm
ARG PYPI_INDEX_URL=https://pypi.org/simple
ARG PYPI_TRUSTED_HOST=

FROM ${FRONTEND_BASE_IMAGE} AS frontend-build

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

FROM ${BACKEND_BASE_IMAGE}

ARG PYPI_INDEX_URL=https://pypi.org/simple
ARG PYPI_TRUSTED_HOST=

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_INDEX_URL=${PYPI_INDEX_URL}

WORKDIR /app

COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip \
    && if [ -n "${PYPI_TRUSTED_HOST}" ]; then pip config set global.trusted-host "${PYPI_TRUSTED_HOST}"; fi \
    && pip install -r /tmp/requirements.txt

COPY backend/ /app/backend/
COPY deploy/docker-entrypoint.sh /app/deploy/docker-entrypoint.sh
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist

RUN chmod +x /app/deploy/docker-entrypoint.sh \
    && mkdir -p /app/storage /app/backend/media /app/backend/staticfiles

WORKDIR /app/backend

EXPOSE 8001

CMD ["/app/deploy/docker-entrypoint.sh"]

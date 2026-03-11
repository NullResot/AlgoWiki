FROM node:22-bookworm-slim AS frontend-build

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

FROM python:3.12-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip && pip install -r /tmp/requirements.txt

COPY backend/ /app/backend/
COPY deploy/docker-entrypoint.sh /app/deploy/docker-entrypoint.sh
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist

RUN chmod +x /app/deploy/docker-entrypoint.sh \
    && mkdir -p /app/storage /app/backend/media /app/backend/staticfiles

WORKDIR /app/backend

EXPOSE 8001

CMD ["/app/deploy/docker-entrypoint.sh"]

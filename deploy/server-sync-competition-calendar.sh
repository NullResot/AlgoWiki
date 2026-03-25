#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="deploy/.env.production"
CMD_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file)
      ENV_FILE="$2"
      shift 2
      ;;
    *)
      CMD_ARGS+=("$1")
      shift
      ;;
  esac
done

cd "$ROOT_DIR"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Env file not found: $ENV_FILE" >&2
  exit 1
fi

export APP_ENV_FILE="$ENV_FILE"

docker-compose -f docker-compose.server.yml --env-file "$ENV_FILE" exec -T web \
  python manage.py sync_competition_calendar "${CMD_ARGS[@]}"

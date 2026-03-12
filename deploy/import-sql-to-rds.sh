#!/usr/bin/env bash
set -euo pipefail

env_file="deploy/.env.production"
sql_file=""

export_env_file() {
  local env_source="$1"
  while IFS= read -r raw_line || [[ -n "${raw_line}" ]]; do
    raw_line="${raw_line%$'\r'}"
    [[ -z "${raw_line}" || "${raw_line}" =~ ^[[:space:]]*# ]] && continue
    [[ "${raw_line}" != *=* ]] && continue
    export "${raw_line}"
  done <"${env_source}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file)
      env_file="$2"
      shift 2
      ;;
    --sql-file)
      sql_file="$2"
      shift 2
      ;;
    *)
      echo "Usage: $0 --sql-file path [--env-file path]" >&2
      exit 1
      ;;
  esac
done

if [[ -z "${sql_file}" ]]; then
  echo "SQL file is required. Use --sql-file path." >&2
  exit 1
fi

if [[ ! -f "${env_file}" ]]; then
  echo "Environment file not found: ${env_file}" >&2
  exit 1
fi

if [[ ! -f "${sql_file}" ]]; then
  echo "SQL file not found: ${sql_file}" >&2
  exit 1
fi

if ! command -v mysql >/dev/null 2>&1; then
  echo "mysql client not found. Install 'default-mysql-client' first." >&2
  exit 1
fi

export_env_file "${env_file}"

required_vars=(DB_HOST DB_PORT DB_NAME DB_USER DB_PASSWORD)
for name in "${required_vars[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required variable in ${env_file}: ${name}" >&2
    exit 1
  fi
done

mysql_args=(
  -h "${DB_HOST}"
  -P "${DB_PORT}"
  -u "${DB_USER}"
  "-p${DB_PASSWORD}"
  --default-character-set="${DB_CHARSET:-utf8mb4}"
  "${DB_NAME}"
)

if [[ -n "${DB_SSL_CA:-}" ]]; then
  mysql_args+=(--ssl-ca "${DB_SSL_CA}")
fi

mysql "${mysql_args[@]}" <"${sql_file}"

echo "Imported SQL into RDS target: ${DB_HOST}/${DB_NAME}"

#!/usr/bin/env bash
set -euo pipefail

env_file="deploy/.env.private-validation"
compose_file="docker-compose.server.yml"
profile="local-db"
output_file=""

resolve_compose_cmd() {
  if docker compose version >/dev/null 2>&1; then
    echo "docker compose"
    return 0
  fi

  if command -v docker-compose >/dev/null 2>&1; then
    echo "docker-compose"
    return 0
  fi

  echo "Docker Compose is not available. Install 'docker compose' or 'docker-compose' first." >&2
  exit 1
}

export_compose_env() {
  local env_source="$1"
  while IFS= read -r raw_line || [[ -n "${raw_line}" ]]; do
    raw_line="${raw_line%$'\r'}"
    [[ -z "${raw_line}" || "${raw_line}" =~ ^[[:space:]]*# ]] && continue
    [[ "${raw_line}" != *=* ]] && continue
    export "${raw_line}"
  done <"${env_source}"
}

prepare_legacy_env() {
  local env_source="$1"
  local compose_target="$2"

  legacy_compose_dir="$(cd "$(dirname "${compose_target}")" && pwd)"
  legacy_env_path="${legacy_compose_dir}/.env"
  legacy_env_backup=""

  if [[ -e "${legacy_env_path}" && ! -L "${legacy_env_path}" ]]; then
    legacy_env_backup="${legacy_env_path}.bak.$(date +%s)"
    mv "${legacy_env_path}" "${legacy_env_backup}"
  elif [[ -L "${legacy_env_path}" ]]; then
    rm -f "${legacy_env_path}"
  fi

  ln -s "$(realpath "${env_source}")" "${legacy_env_path}"
}

cleanup_legacy_env() {
  if [[ -n "${legacy_env_path:-}" ]]; then
    rm -f "${legacy_env_path}"
  fi

  if [[ -n "${legacy_env_backup:-}" && -f "${legacy_env_backup}" ]]; then
    mv "${legacy_env_backup}" "${legacy_env_path}"
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file)
      env_file="$2"
      shift 2
      ;;
    --output)
      output_file="$2"
      shift 2
      ;;
    *)
      echo "Usage: $0 [--env-file path] [--output path]" >&2
      exit 1
      ;;
  esac
done

if [[ ! -f "${env_file}" ]]; then
  echo "Environment file not found: ${env_file}" >&2
  exit 1
fi

if [[ -z "${output_file}" ]]; then
  backup_dir="storage/backups"
  mkdir -p "${backup_dir}"
  output_file="${backup_dir}/algowiki_$(date +%F_%H%M%S).sql"
else
  mkdir -p "$(dirname "${output_file}")"
fi

compose_runner="$(resolve_compose_cmd)"
export_compose_env "${env_file}"

if [[ "${compose_runner}" == "docker compose" ]]; then
  compose_cmd=(docker compose --env-file "${env_file}" -f "${compose_file}" --profile "${profile}")
else
  prepare_legacy_env "${env_file}" "${compose_file}"
  trap cleanup_legacy_env EXIT
  compose_cmd=(docker-compose -f "${compose_file}" --profile "${profile}")
fi

db_container_id="$("${compose_cmd[@]}" ps -q db)"
if [[ -z "${db_container_id}" ]]; then
  echo "MySQL container is not running. Start the local-db profile first." >&2
  exit 1
fi

docker exec "${db_container_id}" sh -lc \
  'exec mysqldump -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" --single-transaction --default-character-set=utf8mb4 "$MYSQL_DATABASE"' \
  >"${output_file}"

echo "Exported local-db SQL dump: ${output_file}"

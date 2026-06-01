#!/usr/bin/env bash
set -euo pipefail

env_file="deploy/.env.production"
compose_file="docker-compose.server.yml"
project=""
command_line=""

get_env_value() {
  local key="$1"
  local file="$2"
  local line

  line="$(grep -E "^${key}=" "${file}" | tail -n 1 || true)"
  if [[ -z "${line}" ]]; then
    return 1
  fi

  printf '%s\n' "${line#*=}"
}

usage() {
  cat <<'EOF'
Usage:
  ./deploy/server-manage.sh [--env-file path] -- <command...>

Example:
  ./deploy/server-manage.sh --env-file deploy/.env.test -- python manage.py purge_expired_media --limit 1000
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file)
      env_file="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    --)
      shift
      command_line="$*"
      break
      ;;
    *)
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "${command_line}" ]]; then
  usage >&2
  exit 1
fi

if [[ ! -f "${env_file}" ]]; then
  echo "Environment file not found: ${env_file}" >&2
  exit 1
fi

project="$(get_env_value "COMPOSE_PROJECT_NAME" "${env_file}" || true)"
project="${project:-algowiki}"

echo "Compose project: ${project}"
echo "Command: ${command_line}"

docker-compose -p "${project}" -f "${compose_file}" exec -T web sh -lc "${command_line}"

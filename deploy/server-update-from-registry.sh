#!/usr/bin/env bash
set -euo pipefail

env_file="deploy/.env.production"
image=""
release=""
skip_pull="0"

usage() {
  cat <<'EOF'
Usage:
  ./deploy/server-update-from-registry.sh [--env-file path] [--image ref] [--release value] [--skip-pull]

Examples:
  ./deploy/server-update-from-registry.sh --image ghcr.io/nullresot/algowiki-web:latest --release ghcr-latest
  ./deploy/server-update-from-registry.sh

Notes:
  - If --image is omitted, the script uses APP_IMAGE from the env file.
  - The script removes the old web container before compose up to avoid the docker-compose v1 ContainerConfig recreate bug.
EOF
}

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

set_env_value() {
  local key="$1"
  local value="$2"
  local file="$3"

  if grep -q -E "^${key}=" "${file}"; then
    sed -i "s#^${key}=.*#${key}=${value}#" "${file}"
  else
    printf '\n%s=%s\n' "${key}" "${value}" >> "${file}"
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file)
      env_file="$2"
      shift 2
      ;;
    --image)
      image="$2"
      shift 2
      ;;
    --release)
      release="$2"
      shift 2
      ;;
    --skip-pull)
      skip_pull="1"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      exit 1
      ;;
  esac
done

if [[ ! -f "${env_file}" ]]; then
  echo "Environment file not found: ${env_file}" >&2
  exit 1
fi

if [[ -z "${image}" ]]; then
  image="$(get_env_value "APP_IMAGE" "${env_file}" || true)"
fi

if [[ -z "${image}" ]]; then
  echo "APP_IMAGE is empty. Provide --image or set APP_IMAGE in ${env_file}." >&2
  exit 1
fi

backup_path="${env_file}.bak.$(date +%Y%m%d-%H%M%S)"
cp "${env_file}" "${backup_path}"

set_env_value "APP_IMAGE" "${image}" "${env_file}"
if [[ -n "${release}" ]]; then
  set_env_value "ALGOWIKI_RELEASE" "${release}" "${env_file}"
fi

echo "Using env file: ${env_file}"
echo "Backup saved to: ${backup_path}"
echo "Target image: ${image}"

if [[ "${skip_pull}" != "1" ]]; then
  docker pull "${image}"
fi

docker ps -a --format '{{.Names}}' | grep 'algowiki_web_1' | xargs -r docker rm -f

"$(dirname "$0")/server-compose-up.sh" --env-file "${env_file}"

app_port="$(get_env_value "APP_PORT" "${env_file}" || true)"
app_port="${app_port:-8001}"

echo "Health check:"
curl -fsS -H 'X-Forwarded-Proto: https' "http://127.0.0.1:${app_port}/api/health/"
printf '\n'

#!/usr/bin/env bash
set -euo pipefail

env_file="deploy/.env.production"
archive=""
image=""
release=""
cleanup_archive="0"

usage() {
  cat <<'EOF'
Usage:
  ./deploy/server-update-from-archive.sh --archive path [--env-file path] [--image ref] [--release value] [--cleanup-archive]

Examples:
  ./deploy/server-update-from-archive.sh --archive /root/algowiki-web-quick-52ac8d2.tar --image algowiki-web:quick-52ac8d2 --release archive-52ac8d2
  ./deploy/server-update-from-archive.sh --archive /root/algowiki-web-quick-52ac8d2.tar --image algowiki-web:quick-52ac8d2 --cleanup-archive

Notes:
  - The script loads a prebuilt image archive on the server, updates APP_IMAGE, then recreates the web container.
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

remove_old_web_container() {
  local containers

  containers="$(docker ps -a --format '{{.Names}}' | grep -E '^algowiki[-_]web[-_]1$' || true)"
  if [[ -n "${containers}" ]]; then
    printf '%s\n' "${containers}" | xargs -r docker rm -f
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file)
      env_file="$2"
      shift 2
      ;;
    --archive)
      archive="$2"
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
    --cleanup-archive)
      cleanup_archive="1"
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

if [[ -z "${archive}" ]]; then
  echo "Archive path is required. Provide --archive <path>." >&2
  exit 1
fi

if [[ ! -f "${archive}" ]]; then
  echo "Archive file not found: ${archive}" >&2
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
echo "Loading archive: ${archive}"
echo "Target image: ${image}"

docker load -i "${archive}"
docker image inspect "${image}" >/dev/null

remove_old_web_container

"$(dirname "$0")/server-compose-up.sh" --env-file "${env_file}"

if [[ "${cleanup_archive}" == "1" ]]; then
  rm -f "${archive}"
fi

app_port="$(get_env_value "APP_PORT" "${env_file}" || true)"
app_port="${app_port:-8001}"

echo "Health check:"
curl -fsS -H 'X-Forwarded-Proto: https' "http://127.0.0.1:${app_port}/api/health/"
printf '\n'

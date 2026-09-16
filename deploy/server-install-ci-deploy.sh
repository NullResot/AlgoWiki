#!/usr/bin/env bash

set -Eeuo pipefail
umask 077

PROJECT_DIR="/srv/algowiki"
DEPLOY_GROUP="algowiki-deploy"
TEST_USER="algowiki-deploy-test"
PRODUCTION_USER="algowiki-deploy-production"
LEGACY_USER="algowiki-deploy"
TEST_PUBLIC_KEY_FILE=""
PRODUCTION_PUBLIC_KEY_FILE=""
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat >&2 <<'EOF'
Usage: server-install-ci-deploy.sh \
  --test-public-key-file /path/to/test-key.pub \
  --production-public-key-file /path/to/production-key.pub
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --test-public-key-file)
      TEST_PUBLIC_KEY_FILE="${2:-}"
      shift 2
      ;;
    --production-public-key-file)
      PRODUCTION_PUBLIC_KEY_FILE="${2:-}"
      shift 2
      ;;
    *)
      usage
      exit 2
      ;;
  esac
done

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this installer as root." >&2
  exit 1
fi
if [[ -z "$TEST_PUBLIC_KEY_FILE" || ! -f "$TEST_PUBLIC_KEY_FILE" ]]; then
  usage
  exit 2
fi
if [[ -z "$PRODUCTION_PUBLIC_KEY_FILE" || ! -f "$PRODUCTION_PUBLIC_KEY_FILE" ]]; then
  usage
  exit 2
fi
if [[ ! -f "${SCRIPT_DIR}/server-ci-deploy.sh" || ! -f "${SCRIPT_DIR}/server-ci-ssh-dispatch.sh" || ! -f "${SCRIPT_DIR}/server-db-backup.sh" ]]; then
  echo "Run the installer from the repository deploy directory." >&2
  exit 1
fi

read_public_key() {
  local file="$1"
  local -a key_lines
  local key_type
  local key_blob
  mapfile -t key_lines <"$file"
  if [[ ${#key_lines[@]} -ne 1 || ! "${key_lines[0]}" =~ ^ssh-ed25519[[:space:]]+[A-Za-z0-9+/=]+([[:space:]].*)?$ ]]; then
    echo "Public key files must contain exactly one Ed25519 public key: $file" >&2
    return 1
  fi
  read -r key_type key_blob _ <<<"${key_lines[0]}"
  printf '%s %s' "$key_type" "$key_blob"
}

test_public_key="$(read_public_key "$TEST_PUBLIC_KEY_FILE")"
production_public_key="$(read_public_key "$PRODUCTION_PUBLIC_KEY_FILE")"
if [[ "$test_public_key" == "$production_public_key" ]]; then
  echo "Test and production must use different SSH keys." >&2
  exit 1
fi

if ! getent group "$DEPLOY_GROUP" >/dev/null; then
  groupadd --system "$DEPLOY_GROUP"
fi

for existing_user in "$TEST_USER" "$PRODUCTION_USER"; do
  if id "$existing_user" >/dev/null 2>&1 && id -nG "$existing_user" | tr ' ' '\n' | grep -Fxq docker; then
    echo "Refusing unsafe existing account: $existing_user belongs to the docker group." >&2
    exit 1
  fi
done

configure_deploy_user() {
  local user="$1"
  local public_key="$2"
  local environment="$3"
  local home="/home/${user}"
  local key_temp

  if ! id "$user" >/dev/null 2>&1; then
    useradd \
      --system \
      --gid "$DEPLOY_GROUP" \
      --home-dir "$home" \
      --create-home \
      --shell /bin/bash \
      "$user"
  fi
  usermod --lock --shell /bin/bash "$user"
  install -d -o root -g "$DEPLOY_GROUP" -m 0750 "$home" "${home}/.ssh"
  key_temp="$(mktemp)"
  printf 'command="/usr/local/sbin/algowiki-ci-ssh-dispatch %s",restrict %s\n' "$environment" "$public_key" >"$key_temp"
  install -o root -g "$DEPLOY_GROUP" -m 0640 "$key_temp" "${home}/.ssh/authorized_keys"
  rm -f -- "$key_temp"
}

install -o root -g "$DEPLOY_GROUP" -m 0750 \
  "${SCRIPT_DIR}/server-ci-deploy.sh" \
  /usr/local/sbin/algowiki-ci-deploy
install -o root -g root -m 0750 \
  "${SCRIPT_DIR}/server-db-backup.sh" \
  /usr/local/sbin/algowiki-db-backup
install -o root -g root -m 0755 \
  "${SCRIPT_DIR}/server-ci-ssh-dispatch.sh" \
  /usr/local/sbin/algowiki-ci-ssh-dispatch

install_fixed_wrapper() {
  local environment="$1"
  local destination="/usr/local/sbin/algowiki-ci-deploy-${environment}"
  local wrapper_temp
  wrapper_temp="$(mktemp)"
  {
    printf '%s\n' '#!/usr/bin/env bash'
    printf '%s\n' 'set -Eeuo pipefail'
    printf 'exec /usr/local/sbin/algowiki-ci-deploy "$@" --environment %q\n' "$environment"
  } >"$wrapper_temp"
  install -o root -g root -m 0755 "$wrapper_temp" "$destination"
  rm -f -- "$wrapper_temp"
}

install_fixed_wrapper test
install_fixed_wrapper production

configure_deploy_user "$TEST_USER" "$test_public_key" test
configure_deploy_user "$PRODUCTION_USER" "$production_public_key" production

install_sudo_rule() {
  local user="$1"
  local environment="$2"
  local sudoers_temp
  local destination="/etc/sudoers.d/algowiki-ci-deploy-${environment}"
  sudoers_temp="$(mktemp)"
  printf '%s ALL=(root) NOPASSWD: /usr/local/sbin/algowiki-ci-deploy-%s\n' "$user" "$environment" >"$sudoers_temp"
  visudo -cf "$sudoers_temp" >/dev/null
  install -o root -g root -m 0440 "$sudoers_temp" "$destination"
  rm -f -- "$sudoers_temp"
}

install_sudo_rule "$TEST_USER" test
install_sudo_rule "$PRODUCTION_USER" production

# Remove the superseded shared CI identity so test credentials can never select production.
if id "$LEGACY_USER" >/dev/null 2>&1; then
  usermod --lock --shell /usr/sbin/nologin "$LEGACY_USER"
  rm -f -- "/home/${LEGACY_USER}/.ssh/authorized_keys"
fi
rm -f -- /etc/sudoers.d/algowiki-ci-deploy

install -d -o root -g "$DEPLOY_GROUP" -m 0750 "$PROJECT_DIR" "${PROJECT_DIR}/deploy"
chown root:"$DEPLOY_GROUP" "${PROJECT_DIR}/docker-compose.server.yml"
chmod 0640 "${PROJECT_DIR}/docker-compose.server.yml"

ensure_env_value() {
  local file="$1"
  local key="$2"
  local value="$3"
  if [[ -f "$file" ]] && ! grep -Eq "^[[:space:]]*${key}[[:space:]]*=" "$file"; then
    printf '\n%s=%s\n' "$key" "$value" >>"$file"
  fi
}

production_env="${PROJECT_DIR}/deploy/.env.production"
ensure_env_value "$production_env" APP_LOG_DIR /srv/algowiki/storage/logs
ensure_env_value "$production_env" DJANGO_LOG_DIR /app/storage/logs
ensure_env_value "$production_env" REDIS_IMAGE ghcr.io/nullresot/algowiki-redis@sha256:ff02b58f971e7d7d156a1267e283fcbbeee91773b6aa36c49dac28ecfe28eadf
ensure_env_value "$production_env" REDIS_MAXMEMORY 96mb
ensure_env_value "$production_env" REDIS_MEMORY_LIMIT 128m
ensure_env_value "$production_env" REDIS_CPU_LIMIT 0.15
ensure_env_value "$production_env" REDIS_PIDS_LIMIT 64
ensure_env_value "$production_env" WEB_MEMORY_LIMIT 768m
ensure_env_value "$production_env" WEB_CPU_LIMIT 1.25
ensure_env_value "$production_env" WEB_PIDS_LIMIT 256
ensure_env_value "$production_env" WORKER_MEMORY_LIMIT 256m
ensure_env_value "$production_env" WORKER_CPU_LIMIT 0.35
ensure_env_value "$production_env" WORKER_PIDS_LIMIT 128

test_env="${PROJECT_DIR}/deploy/.env.test"
ensure_env_value "$test_env" APP_LOG_DIR /srv/algowiki/storage/logs/test
ensure_env_value "$test_env" DJANGO_LOG_DIR /app/storage/logs
ensure_env_value "$test_env" REDIS_IMAGE ghcr.io/nullresot/algowiki-redis@sha256:ff02b58f971e7d7d156a1267e283fcbbeee91773b6aa36c49dac28ecfe28eadf
ensure_env_value "$test_env" REDIS_MAXMEMORY 64mb
ensure_env_value "$test_env" REDIS_MEMORY_LIMIT 96m
ensure_env_value "$test_env" REDIS_CPU_LIMIT 0.10
ensure_env_value "$test_env" REDIS_PIDS_LIMIT 64
ensure_env_value "$test_env" WEB_MEMORY_LIMIT 512m
ensure_env_value "$test_env" WEB_CPU_LIMIT 0.50
ensure_env_value "$test_env" WEB_PIDS_LIMIT 192
ensure_env_value "$test_env" WORKER_MEMORY_LIMIT 192m
ensure_env_value "$test_env" WORKER_CPU_LIMIT 0.20
ensure_env_value "$test_env" WORKER_PIDS_LIMIT 96

find "${PROJECT_DIR}/deploy" -maxdepth 1 -type f -exec chown root:"$DEPLOY_GROUP" {} +
find "${PROJECT_DIR}/deploy" -maxdepth 1 -type f -name '*.sh' -exec chmod 0750 {} +
find "${PROJECT_DIR}/deploy" -maxdepth 1 -type f ! -name '*.sh' -exec chmod 0640 {} +
find "${PROJECT_DIR}/deploy" -maxdepth 1 -type f -name '.env*' -exec chown root:root {} +
find "${PROJECT_DIR}/deploy" -maxdepth 1 -type f -name '.env*' -exec chmod 0600 {} +
install -d -o root -g root -m 0700 /var/lib/algowiki/deployments /var/backups/algowiki/db
install -d -o root -g adm -m 0750 "${PROJECT_DIR}/storage" "${PROJECT_DIR}/storage/logs" "${PROJECT_DIR}/storage/logs/test"

for deploy_user in "$TEST_USER" "$PRODUCTION_USER"; do
  if id -nG "$deploy_user" | tr ' ' '\n' | grep -Fxq docker; then
    echo "Refusing unsafe configuration: $deploy_user must not belong to the docker group." >&2
    exit 1
  fi
done

echo "Installed environment-separated CI deployment identities for test and production."

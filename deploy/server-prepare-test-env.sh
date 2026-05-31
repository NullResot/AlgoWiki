#!/usr/bin/env bash
set -euo pipefail

prod_env="deploy/.env.production"
test_env="deploy/.env.test"
test_domain="test.algowiki.cn"
test_port="8002"
test_db_name="algowiki_test"
test_image_repository="crpi-31i8820z65uunzmj.cn-shanghai.personal.cr.aliyuncs.com/algowiki/algowiki-web"
network_subnet="192.168.255.0/24"
create_db="0"
prepare_network="1"

usage() {
  cat <<'EOF'
Usage:
  ./deploy/server-prepare-test-env.sh [--prod-env path] [--test-env path] [--domain test.algowiki.cn] [--port 8002] [--db-name algowiki_test] [--image-repo ref] [--network-subnet 192.168.255.0/24] [--skip-network] [--create-db]

Notes:
  - Copies the production env file to a test env file, then rewrites only environment identity values.
  - Secrets stay on the server and are not printed.
  - The test environment uses an independent Compose project, port, Django hosts, release branch and database name.
  - The test environment defaults to the Aliyun ACR image repository for faster domestic pulls.
  - By default it pre-creates the algowiki_test_default Docker network with a non-conflicting subnet.
  - --create-db runs CREATE DATABASE IF NOT EXISTS with the copied DB credentials. It requires mysql client and DB_CREATE permission.
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

prepare_test_network() {
  local network_name="algowiki_test_default"
  local existing_subnet

  if ! command -v docker >/dev/null 2>&1; then
    echo "docker is not available. Skipped Docker network preparation."
    return 0
  fi

  existing_subnet="$(docker network inspect "${network_name}" --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}' 2>/dev/null || true)"
  if [[ -n "${existing_subnet}" ]]; then
    if [[ "${existing_subnet}" == "${network_subnet}" ]]; then
      echo "Docker network already exists: ${network_name} (${existing_subnet})"
    else
      echo "Docker network already exists: ${network_name} (${existing_subnet})" >&2
      echo "If the test container cannot reach RDS, remove the test container and recreate this network with ${network_subnet}." >&2
    fi
    return 0
  fi

  docker network create \
    --driver bridge \
    --subnet "${network_subnet}" \
    --label com.docker.compose.project=algowiki_test \
    --label com.docker.compose.network=default \
    "${network_name}" >/dev/null

  echo "Docker network created: ${network_name} (${network_subnet})"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prod-env)
      prod_env="$2"
      shift 2
      ;;
    --test-env)
      test_env="$2"
      shift 2
      ;;
    --domain)
      test_domain="$2"
      shift 2
      ;;
    --port)
      test_port="$2"
      shift 2
      ;;
    --db-name)
      test_db_name="$2"
      shift 2
      ;;
    --image-repo)
      test_image_repository="$2"
      shift 2
      ;;
    --network-subnet)
      network_subnet="$2"
      shift 2
      ;;
    --skip-network)
      prepare_network="0"
      shift
      ;;
    --create-db)
      create_db="1"
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

if [[ ! -f "${prod_env}" ]]; then
  echo "Production env file not found: ${prod_env}" >&2
  exit 1
fi

if [[ -f "${test_env}" ]]; then
  backup_path="${test_env}.bak.$(date +%Y%m%d-%H%M%S)"
  cp "${test_env}" "${backup_path}"
  echo "Existing test env backup saved to: ${backup_path}"
else
  cp "${prod_env}" "${test_env}"
  chmod 600 "${test_env}" || true
fi

set_env_value "APP_ENV_FILE" "${test_env}" "${test_env}"
set_env_value "COMPOSE_PROJECT_NAME" "algowiki_test" "${test_env}"
set_env_value "APP_IMAGE" "${test_image_repository}:test" "${test_env}"
set_env_value "APP_IMAGE_REPOSITORY" "${test_image_repository}" "${test_env}"
set_env_value "GITHUB_REPOSITORY" "NullResot/AlgoWiki" "${test_env}"
set_env_value "GITHUB_BRANCH" "test" "${test_env}"
set_env_value "DEPLOY_SYNC_GITHUB_BRANCH" "1" "${test_env}"
set_env_value "DJANGO_ALLOWED_HOSTS" "${test_domain},127.0.0.1,localhost" "${test_env}"
set_env_value "DJANGO_CSRF_TRUSTED_ORIGINS" "https://${test_domain}" "${test_env}"
set_env_value "ALGOWIKI_RELEASE" "gh-test" "${test_env}"
set_env_value "APP_BIND" "127.0.0.1" "${test_env}"
set_env_value "APP_PORT" "${test_port}" "${test_env}"
set_env_value "DB_NAME" "${test_db_name}" "${test_env}"
set_env_value "SITE_NAME" "AlgoWiki Test" "${test_env}"
set_env_value "PUBLIC_SITE_URL" "https://${test_domain}" "${test_env}"
set_env_value "MEDIA_ROOT" "/srv/algowiki-test/media" "${test_env}"
set_env_value "FRONTEND_DIST_DIR" "/srv/algowiki-test/frontend/dist" "${test_env}"

echo "Prepared ${test_env}"
echo "Domain: ${test_domain}"
echo "App port: ${test_port}"
echo "Database: ${test_db_name}"
echo "Image repository: ${test_image_repository}"

if [[ "${prepare_network}" == "1" ]]; then
  prepare_test_network
fi

if [[ "${create_db}" != "1" ]]; then
  exit 0
fi

if ! command -v mysql >/dev/null 2>&1; then
  echo "mysql client is not available. Install it or create database ${test_db_name} manually." >&2
  exit 1
fi

db_host="$(get_env_value "DB_HOST" "${test_env}")"
db_port="$(get_env_value "DB_PORT" "${test_env}" || true)"
db_port="${db_port:-3306}"
db_user="$(get_env_value "DB_USER" "${test_env}")"
db_password="$(get_env_value "DB_PASSWORD" "${test_env}")"
db_charset="$(get_env_value "DB_CHARSET" "${test_env}" || true)"
db_charset="${db_charset:-utf8mb4}"

MYSQL_PWD="${db_password}" mysql \
  -h "${db_host}" \
  -P "${db_port}" \
  -u "${db_user}" \
  -e "CREATE DATABASE IF NOT EXISTS \`${test_db_name}\` CHARACTER SET ${db_charset} COLLATE ${db_charset}_unicode_ci;"

echo "Database is ready: ${test_db_name}"

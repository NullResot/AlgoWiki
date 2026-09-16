#!/usr/bin/env bash

set -Eeuo pipefail
umask 077

PROJECT_DIR="/srv/algowiki"
COMPOSE_FILE="${PROJECT_DIR}/docker-compose.server.yml"
BACKUP_COMMAND="/usr/local/sbin/algowiki-db-backup"
STATE_ROOT="/var/lib/algowiki/deployments"
LOCK_FILE="/run/lock/algowiki-ci-deploy.lock"
PINNED_REDIS_IMAGE="ghcr.io/nullresot/algowiki-redis@sha256:ff02b58f971e7d7d156a1267e283fcbbeee91773b6aa36c49dac28ecfe28eadf"

environment=""
image=""
source_revision=""
deployment_revision=""

usage() {
  cat >&2 <<'EOF'
Usage: algowiki-ci-deploy \
  --environment test|production \
  --source-revision <40-hex commit> \
  --deployment-revision <40-hex commit> \
  [--image ghcr.io/nullresot/algowiki-web@sha256:<digest>]

Test requires --image. Production rejects it and promotes the exact digest
recorded by a successful test deployment of --source-revision.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --environment)
      if [[ -n "$environment" ]]; then
        echo "Environment may be specified only once." >&2
        exit 2
      fi
      environment="${2:-}"
      shift 2
      ;;
    --image)
      image="${2:-}"
      shift 2
      ;;
    --source-revision)
      source_revision="${2:-}"
      shift 2
      ;;
    --deployment-revision)
      deployment_revision="${2:-}"
      shift 2
      ;;
    *)
      usage
      exit 2
      ;;
  esac
done

if [[ "${EUID}" -ne 0 ]]; then
  echo "This command must run as root through the approved sudo rule." >&2
  exit 1
fi

if [[ ! "$source_revision" =~ ^[0-9a-f]{40}$ ]]; then
  echo "Invalid source revision." >&2
  exit 2
fi
if [[ ! "$deployment_revision" =~ ^[0-9a-f]{40}$ ]]; then
  echo "Invalid deployment revision." >&2
  exit 2
fi

case "$environment" in
  test)
    env_file="${PROJECT_DIR}/deploy/.env.test"
    project_name="algowiki_test"
    local_health_url="http://127.0.0.1:8002/api/health/"
    public_health_url="https://test.algowiki.cn/api/health/"
    ;;
  production)
    env_file="${PROJECT_DIR}/deploy/.env.production"
    project_name="algowiki"
    local_health_url="http://127.0.0.1:8001/api/health/"
    public_health_url="https://www.algowiki.cn/api/health/"
    ;;
  *)
    echo "Environment must be test or production." >&2
    exit 2
    ;;
esac

for required_file in "$COMPOSE_FILE" "$env_file"; do
  if [[ ! -f "$required_file" ]]; then
    echo "Required deployment file is missing: $required_file" >&2
    exit 1
  fi
done

for required_command in docker curl flock; do
  if ! command -v "$required_command" >/dev/null 2>&1; then
    echo "Required command is unavailable: $required_command" >&2
    exit 1
  fi
done

exec 9>"$LOCK_FILE"
if ! flock -w 900 9; then
  echo "Timed out waiting for another AlgoWiki deployment to finish." >&2
  exit 1
fi

read_key_value_file() {
  local file="$1"
  local key="$2"
  local value
  value="$(sed -n -E "s/^[[:space:]]*${key}[[:space:]]*=[[:space:]]*(.*)[[:space:]]*$/\\1/p" "$file" | tail -n 1)"
  value="${value%$'\r'}"
  if [[ ${#value} -ge 2 && "${value:0:1}" == '"' && "${value: -1}" == '"' ]]; then
    value="${value:1:${#value}-2}"
  elif [[ ${#value} -ge 2 && "${value:0:1}" == "'" && "${value: -1}" == "'" ]]; then
    value="${value:1:${#value}-2}"
  fi
  printf '%s' "$value"
}

read_env_value() {
  local key="$1"
  read_key_value_file "$env_file" "$key"
}

promotion_record="${STATE_ROOT}/test/by-source/${source_revision}"
if [[ "$environment" == "test" ]]; then
  if [[ ! "$image" =~ ^ghcr\.io/nullresot/algowiki-web@sha256:[0-9a-f]{64}$ ]]; then
    echo "Test deployments require an immutable AlgoWiki image digest." >&2
    exit 2
  fi
  if [[ -f "$promotion_record" ]]; then
    recorded_image="$(read_key_value_file "$promotion_record" image)"
    if [[ "$recorded_image" != "$image" ]]; then
      echo "This source revision was already tested with a different immutable digest." >&2
      exit 1
    fi
  fi
else
  if [[ -n "$image" ]]; then
    echo "Production selects its image from the successful test deployment record; --image is forbidden." >&2
    exit 2
  fi
  if [[ ! -f "$promotion_record" ]]; then
    echo "No successful test deployment record exists for source revision $source_revision." >&2
    exit 1
  fi
  recorded_source_revision="$(read_key_value_file "$promotion_record" source_revision)"
  image="$(read_key_value_file "$promotion_record" image)"
  if [[ "$recorded_source_revision" != "$source_revision" ]]; then
    echo "The successful test deployment record does not match the requested source revision." >&2
    exit 1
  fi
fi

if [[ ! "$image" =~ ^ghcr\.io/nullresot/algowiki-web@sha256:[0-9a-f]{64}$ ]]; then
  echo "Refusing invalid promoted application image: $image" >&2
  exit 1
fi

redis_image="$(read_env_value REDIS_IMAGE)"
redis_image="${redis_image:-$PINNED_REDIS_IMAGE}"
if [[ "$redis_image" != "$PINNED_REDIS_IMAGE" ]]; then
  echo "REDIS_IMAGE must match the reviewed immutable digest: $PINNED_REDIS_IMAGE" >&2
  exit 1
fi
export REDIS_IMAGE="$redis_image"

previous_image="$(read_env_value APP_IMAGE)"
previous_release="$(read_env_value ALGOWIKI_RELEASE)"
release="${environment}-${deployment_revision:0:12}"

export APP_ENV_FILE="$env_file"
export APP_IMAGE="$image"
export ALGOWIKI_RELEASE="$release"
export COMPOSE_PROJECT_NAME="$project_name"

compose=(
  docker compose
  --project-directory "$PROJECT_DIR"
  --env-file "$env_file"
  -f "$COMPOSE_FILE"
  -p "$project_name"
)

switched=0
runtime_env_backup=""
runtime_env_updated=0
last_success_backup=""
last_success_path=""
last_success_updated=0
promotion_record_created=0
staged_env=""
staged_state=""
staged_promotion=""
rollback_on_error() {
  local exit_code=$?
  trap - ERR
  set +e
  if [[ "$promotion_record_created" == "1" ]]; then
    rm -f -- "$promotion_record"
  fi
  if [[ "$last_success_updated" == "1" && -n "$last_success_path" ]]; then
    if [[ -n "$last_success_backup" && -f "$last_success_backup" ]]; then
      mv -f -- "$last_success_backup" "$last_success_path"
      last_success_backup=""
    else
      rm -f -- "$last_success_path"
    fi
  fi
  if [[ "$runtime_env_updated" == "1" && -n "$runtime_env_backup" && -f "$runtime_env_backup" ]]; then
    mv -f -- "$runtime_env_backup" "$env_file"
    runtime_env_backup=""
  fi
  rm -f -- "$staged_env" "$staged_state" "$staged_promotion" "$last_success_backup" "$runtime_env_backup"
  if [[ "$switched" == "1" && -n "$previous_image" ]]; then
    echo "Deployment failed after service switch; rolling back containers to $previous_image" >&2
    export APP_IMAGE="$previous_image"
    export ALGOWIKI_RELEASE="${previous_release:-rollback}"
    "${compose[@]}" up -d --no-build --wait --wait-timeout 120 redis web moderation-worker
    echo "Container image rollback attempted. Database migrations were not reversed." >&2
  fi
  exit "$exit_code"
}
trap rollback_on_error ERR

retry_health_check() {
  local url="$1"
  local forwarded_proto="${2:-0}"
  local attempt
  for ((attempt = 1; attempt <= 12; attempt++)); do
    if [[ "$forwarded_proto" == "1" ]]; then
      if curl --fail --silent --show-error --max-time 10 -H "X-Forwarded-Proto: https" "$url" >/dev/null; then
        return 0
      fi
    elif curl --fail --silent --show-error --max-time 10 "$url" >/dev/null; then
      return 0
    fi
    sleep 5
  done
  echo "Health check failed after 12 attempts: $url" >&2
  return 1
}

persist_runtime_state() {
  local state_dir="${STATE_ROOT}/${environment}"
  local promotion_dir="${STATE_ROOT}/test/by-source"

  install -d -o root -g root -m 0700 "$state_dir"
  last_success_path="${state_dir}/last-success"
  staged_env="$(mktemp "${env_file}.tmp.XXXXXX")"
  awk -v image="$image" -v release="$release" '
    BEGIN { image_seen = 0; release_seen = 0 }
    /^[[:space:]]*APP_IMAGE[[:space:]]*=/ {
      if (!image_seen) { print "APP_IMAGE=" image; image_seen = 1 }
      next
    }
    /^[[:space:]]*ALGOWIKI_RELEASE[[:space:]]*=/ {
      if (!release_seen) { print "ALGOWIKI_RELEASE=" release; release_seen = 1 }
      next
    }
    { print }
    END {
      if (!image_seen) print "APP_IMAGE=" image
      if (!release_seen) print "ALGOWIKI_RELEASE=" release
    }
  ' "$env_file" >"$staged_env"
  chown --reference="$env_file" "$staged_env"
  chmod --reference="$env_file" "$staged_env"

  staged_state="$(mktemp "${state_dir}/last-success.tmp.XXXXXX")"
  {
    printf 'environment=%s\n' "$environment"
    printf 'image=%s\n' "$image"
    printf 'source_revision=%s\n' "$source_revision"
    printf 'deployment_revision=%s\n' "$deployment_revision"
    printf 'release=%s\n' "$release"
    printf 'deployed_at=%s\n' "$(date --utc +%Y-%m-%dT%H:%M:%SZ)"
  } >"$staged_state"
  chmod 0600 "$staged_state"

  runtime_env_backup="$(mktemp "${env_file}.rollback.XXXXXX")"
  cp -p -- "$env_file" "$runtime_env_backup"
  if [[ -f "$last_success_path" ]]; then
    last_success_backup="$(mktemp "${state_dir}/last-success.rollback.XXXXXX")"
    cp -p -- "$last_success_path" "$last_success_backup"
  fi

  if [[ "$environment" == "test" && ! -f "$promotion_record" ]]; then
    install -d -o root -g root -m 0700 "$promotion_dir"
    staged_promotion="$(mktemp "${promotion_dir}/.${source_revision}.tmp.XXXXXX")"
    cp -p -- "$staged_state" "$staged_promotion"
  fi

  mv -f -- "$staged_env" "$env_file"
  staged_env=""
  runtime_env_updated=1
  mv -f -- "$staged_state" "$last_success_path"
  staged_state=""
  last_success_updated=1

  if [[ -n "$staged_promotion" ]]; then
    mv -f -- "$staged_promotion" "$promotion_record"
    staged_promotion=""
    promotion_record_created=1
  fi

  rm -f -- "$runtime_env_backup" "$last_success_backup" || true
  runtime_env_backup=""
  last_success_backup=""
  runtime_env_updated=0
  last_success_updated=0
  promotion_record_created=0
}

echo "Pulling immutable application image: $image"
docker pull "$image"
actual_revision="$(docker image inspect --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}' "$image")"
if [[ "$actual_revision" != "$source_revision" ]]; then
  echo "Image revision label mismatch: expected $source_revision, got ${actual_revision:-<empty>}" >&2
  exit 1
fi

"${compose[@]}" pull redis
"${compose[@]}" config --quiet
"${compose[@]}" up -d --no-build --wait --wait-timeout 60 redis

if [[ "$environment" == "production" ]]; then
  if [[ ! -x "$BACKUP_COMMAND" ]]; then
    echo "Production backup command is missing: $BACKUP_COMMAND" >&2
    exit 1
  fi
  "$BACKUP_COMMAND" \
    --env-file "$env_file" \
    --backup-dir "/var/backups/algowiki/db" \
    --retention-days 7
fi

"${compose[@]}" run --rm --no-deps web python manage.py check --deploy
switched=1
"${compose[@]}" stop --timeout 45 web moderation-worker
"${compose[@]}" run --rm --no-deps web python manage.py migrate --noinput

"${compose[@]}" up -d --no-build --wait --wait-timeout 120 redis web moderation-worker
retry_health_check "$local_health_url" 1
retry_health_check "$public_health_url"

persist_runtime_state
switched=0
trap - ERR

echo "Deployment completed: environment=$environment release=$release image=$image"

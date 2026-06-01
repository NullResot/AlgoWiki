#!/usr/bin/env bash
set -euo pipefail

env_file="deploy/.env.production"
image=""
explicit_image="0"
release=""
skip_pull="0"
sync_github_branch="0"
github_repo=""
github_branch=""
image_repo=""
dry_run="0"

usage() {
  cat <<'EOF'
Usage:
  ./deploy/server-update-from-registry.sh [--env-file path] [--image ref] [--release value] [--skip-pull]
  ./deploy/server-update-from-registry.sh [--sync-github-branch] [--github-repo owner/repo] [--github-branch branch] [--image-repo ref] [--release value] [--dry-run]

Examples:
  ./deploy/server-update-from-registry.sh --image ghcr.io/nullresot/algowiki-web:latest --release ghcr-latest
  ./deploy/server-update-from-registry.sh --sync-github-branch
  ./deploy/server-update-from-registry.sh --sync-github-branch --dry-run
  ./deploy/server-update-from-registry.sh

Notes:
  - If --image is omitted, the script uses APP_IMAGE from the env file.
  - --sync-github-branch resolves the current GitHub branch tip and deploys the matching sha-* image from the image repository.
  - The script removes the old web container for the configured Compose project before compose up to avoid the docker-compose v1 ContainerConfig recreate bug.
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

parse_image_repository() {
  local ref="$1"
  local tail

  if [[ -z "${ref}" ]]; then
    return 1
  fi

  if [[ "${ref}" == *@* ]]; then
    printf '%s\n' "${ref%@*}"
    return 0
  fi

  tail="${ref##*/}"
  if [[ "${tail}" == *:* ]]; then
    printf '%s\n' "${ref%:*}"
    return 0
  fi

  printf '%s\n' "${ref}"
}

is_truthy() {
  local value="${1:-}"

  case "${value}" in
    1|true|TRUE|yes|YES|on|ON)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

resolve_github_branch_sha() {
  local repo="$1"
  local branch="$2"
  local api_url
  local response
  local sha

  api_url="https://api.github.com/repos/${repo}/commits/${branch}"
  response="$(curl -fsSL -H 'Accept: application/vnd.github+json' "${api_url}")"
  sha="$(printf '%s\n' "${response}" | sed -n 's/^[[:space:]]*"sha":[[:space:]]*"\([0-9a-f]\{40\}\)",$/\1/p' | head -n 1)"

  if [[ -z "${sha}" ]]; then
    return 1
  fi

  printf '%s\n' "${sha}"
}

remove_old_web_container() {
  local project="$1"
  local containers

  containers="$(docker ps -a \
    --filter "label=com.docker.compose.project=${project}" \
    --filter "label=com.docker.compose.service=web" \
    --format '{{.Names}}' || true)"

  if [[ -z "${containers}" ]]; then
    containers="$(
      docker ps -a --format '{{.Names}}' | while read -r container_name; do
        if [[ "${container_name}" == "${project}_web_1" || "${container_name}" == "${project}-web-1" ]]; then
          printf '%s\n' "${container_name}"
        fi
      done
    )"
  fi

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
    --image)
      image="$2"
      explicit_image="1"
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
    --sync-github-branch)
      sync_github_branch="1"
      shift
      ;;
    --github-repo)
      github_repo="$2"
      shift 2
      ;;
    --github-branch)
      github_branch="$2"
      shift 2
      ;;
    --image-repo)
      image_repo="$2"
      shift 2
      ;;
    --dry-run)
      dry_run="1"
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

configured_image="$(get_env_value "APP_IMAGE" "${env_file}" || true)"
configured_image_repo="$(get_env_value "APP_IMAGE_REPOSITORY" "${env_file}" || true)"
configured_github_repo="$(get_env_value "GITHUB_REPOSITORY" "${env_file}" || true)"
configured_github_branch="$(get_env_value "GITHUB_BRANCH" "${env_file}" || true)"
configured_sync_github_branch="$(get_env_value "DEPLOY_SYNC_GITHUB_BRANCH" "${env_file}" || true)"
configured_compose_project="$(get_env_value "COMPOSE_PROJECT_NAME" "${env_file}" || true)"
configured_compose_project="${configured_compose_project:-algowiki}"

if [[ "${sync_github_branch}" != "1" ]] && [[ "${explicit_image}" != "1" ]] && is_truthy "${configured_sync_github_branch}"; then
  sync_github_branch="1"
fi

if [[ -z "${image}" ]]; then
  image="${configured_image}"
fi

if [[ "${sync_github_branch}" == "1" ]]; then
  github_repo="${github_repo:-${configured_github_repo:-NullResot/AlgoWiki}}"
  github_branch="${github_branch:-${configured_github_branch:-main}}"
  image_repo="${image_repo:-${configured_image_repo:-}}"

  if [[ -z "${image_repo}" ]]; then
    image_repo="$(parse_image_repository "${image}" || true)"
  fi

  image_repo="${image_repo:-ghcr.io/nullresot/algowiki-web}"

  full_sha="$(resolve_github_branch_sha "${github_repo}" "${github_branch}")" || {
    echo "Unable to resolve ${github_repo}@${github_branch} from GitHub." >&2
    exit 1
  }
  short_sha="${full_sha:0:7}"
  image="${image_repo}:sha-${short_sha}"

  if [[ -z "${release}" ]]; then
    release="gh-${github_branch}-${short_sha}"
  fi

  echo "Resolved GitHub ${github_repo}@${github_branch} -> ${full_sha}"
  echo "Resolved image repository -> ${image_repo}"
fi

if [[ -z "${image}" ]]; then
  echo "APP_IMAGE is empty. Provide --image or set APP_IMAGE in ${env_file}." >&2
  exit 1
fi

if [[ "${dry_run}" == "1" ]]; then
  echo "Dry run only. No files or containers were changed."
  echo "Using env file: ${env_file}"
  echo "Target image: ${image}"
  if [[ -n "${release}" ]]; then
    echo "Release label: ${release}"
  fi
  exit 0
fi

backup_path="${env_file}.bak.$(date +%Y%m%d-%H%M%S)"
cp "${env_file}" "${backup_path}"

set_env_value "APP_IMAGE" "${image}" "${env_file}"
if [[ -n "${release}" ]]; then
  set_env_value "ALGOWIKI_RELEASE" "${release}" "${env_file}"
fi

echo "Using env file: ${env_file}"
echo "Backup saved to: ${backup_path}"
echo "Compose project: ${configured_compose_project}"
echo "Target image: ${image}"

if [[ "${skip_pull}" != "1" ]]; then
  if ! docker pull "${image}"; then
    if [[ "${sync_github_branch}" == "1" ]]; then
      echo "Pull failed for ${image}." >&2
      echo "Wait for the 'Publish Container Images' workflow to finish for ${github_repo}@${github_branch}, then retry." >&2
    fi
    exit 1
  fi
fi

remove_old_web_container "${configured_compose_project}"

"$(dirname "$0")/server-compose-up.sh" --env-file "${env_file}"

app_port="$(get_env_value "APP_PORT" "${env_file}" || true)"
app_port="${app_port:-8001}"

echo "Health check:"
curl -fsS -H 'X-Forwarded-Proto: https' "http://127.0.0.1:${app_port}/api/health/"
printf '\n'

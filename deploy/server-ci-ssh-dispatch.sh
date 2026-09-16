#!/usr/bin/env bash

set -Eeuo pipefail

environment="${1:-}"
original_command="${SSH_ORIGINAL_COMMAND:-}"
declare -a args
read -r -a args <<<"$original_command"

case "$environment" in
  test)
    if [[ ${#args[@]} -ne 7 || "${args[0]}" != "deploy" || "${args[1]}" != "--image" || "${args[3]}" != "--source-revision" || "${args[5]}" != "--deployment-revision" ]]; then
      echo "Only the test deployment protocol is allowed." >&2
      exit 2
    fi
    image="${args[2]}"
    source_revision="${args[4]}"
    deployment_revision="${args[6]}"
    if [[ ! "$image" =~ ^ghcr\.io/nullresot/algowiki-web@sha256:[0-9a-f]{64}$ || ! "$source_revision" =~ ^[0-9a-f]{40}$ || ! "$deployment_revision" =~ ^[0-9a-f]{40}$ ]]; then
      echo "Invalid test deployment protocol values." >&2
      exit 2
    fi
    exec /usr/bin/sudo -n /usr/local/sbin/algowiki-ci-deploy-test \
      --image "$image" \
      --source-revision "$source_revision" \
      --deployment-revision "$deployment_revision"
    ;;
  production)
    if [[ ${#args[@]} -ne 5 || "${args[0]}" != "deploy" || "${args[1]}" != "--source-revision" || "${args[3]}" != "--deployment-revision" ]]; then
      echo "Only the production deployment protocol is allowed." >&2
      exit 2
    fi
    source_revision="${args[2]}"
    deployment_revision="${args[4]}"
    if [[ ! "$source_revision" =~ ^[0-9a-f]{40}$ || ! "$deployment_revision" =~ ^[0-9a-f]{40}$ ]]; then
      echo "Invalid production deployment protocol values." >&2
      exit 2
    fi
    exec /usr/bin/sudo -n /usr/local/sbin/algowiki-ci-deploy-production \
      --source-revision "$source_revision" \
      --deployment-revision "$deployment_revision"
    ;;
  *)
    echo "Invalid forced-command environment." >&2
    exit 2
    ;;
esac

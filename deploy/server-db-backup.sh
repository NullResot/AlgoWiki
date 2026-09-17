#!/usr/bin/env bash

set -euo pipefail
umask 077

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_DIR="${ALGOWIKI_PROJECT_DIR:-$ROOT_DIR}"
ENV_FILE="deploy/.env.production"
BACKUP_DIR="/var/backups/algowiki/db"
RETENTION_DAYS=7
LOCK_FILE="/run/lock/algowiki-db-backup.lock"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file)
      ENV_FILE="$2"
      shift 2
      ;;
    --backup-dir)
      BACKUP_DIR="$2"
      shift 2
      ;;
    --retention-days)
      RETENTION_DAYS="$2"
      shift 2
      ;;
    *)
      echo "Usage: $0 [--env-file path] [--backup-dir path] [--retention-days days]" >&2
      exit 1
      ;;
  esac
done

cd "$PROJECT_DIR"

if ! command -v flock >/dev/null 2>&1; then
  echo "flock not found." >&2
  exit 1
fi
exec 8>"$LOCK_FILE"
if ! flock -w 300 8; then
  echo "Timed out waiting for another database backup to finish." >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Env file not found: $ENV_FILE" >&2
  exit 1
fi

while IFS= read -r raw_line || [[ -n "$raw_line" ]]; do
  raw_line="${raw_line%$'\r'}"
  [[ -z "$raw_line" || "$raw_line" =~ ^[[:space:]]*# ]] && continue
  [[ "$raw_line" != *=* ]] && continue
  key="${raw_line%%=*}"
  value="${raw_line#*=}"
  key="${key#"${key%%[![:space:]]*}"}"
  key="${key%"${key##*[![:space:]]}"}"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  if [[ ${#value} -ge 2 && "${value:0:1}" == "'" && "${value: -1}" == "'" ]]; then
    value="${value:1:${#value}-2}"
  elif [[ ${#value} -ge 2 && "${value:0:1}" == "\"" && "${value: -1}" == "\"" ]]; then
    value="${value:1:${#value}-2}"
  fi
  export "${key}=${value}"
done <"$ENV_FILE"

install -d -m 700 "$BACKUP_DIR"

timestamp="$(date +%Y%m%d-%H%M%S-%N)"
backup_base="algowiki-db-${timestamp}"
temporary_file=""
temporary_checksum=""

cleanup_temporary_files() {
  if [[ -n "$temporary_file" ]]; then
    rm -f -- "$temporary_file"
  fi
  if [[ -n "$temporary_checksum" ]]; then
    rm -f -- "$temporary_checksum"
  fi
}
trap cleanup_temporary_files EXIT

case "${DB_ENGINE:-mysql}" in
  mysql)
    if ! command -v mysqldump >/dev/null 2>&1; then
      echo "mysqldump not found. Install default-mysql-client first." >&2
      exit 1
    fi

    output_file="${BACKUP_DIR}/${backup_base}.sql.gz"
    temporary_file="$(mktemp "${BACKUP_DIR}/.${backup_base}.XXXXXX.sql.gz")"
    dump_cmd=(
      mysqldump
      --single-transaction
      --quick
      --default-character-set="${DB_CHARSET:-utf8mb4}"
      --host="${DB_HOST:-127.0.0.1}"
      --port="${DB_PORT:-3306}"
      --user="${DB_USER:-root}"
    )

    if [[ -n "${DB_SSL_CA:-}" ]]; then
      dump_cmd+=("--ssl-ca=${DB_SSL_CA}")
    fi
    if [[ -n "${DB_SSL_CERT:-}" ]]; then
      dump_cmd+=("--ssl-cert=${DB_SSL_CERT}")
    fi
    if [[ -n "${DB_SSL_KEY:-}" ]]; then
      dump_cmd+=("--ssl-key=${DB_SSL_KEY}")
    fi

    export MYSQL_PWD="${DB_PASSWORD:-}"
    "${dump_cmd[@]}" "${DB_NAME:-algowiki}" | gzip -9 >"$temporary_file"
    unset MYSQL_PWD
    gzip -t "$temporary_file"
    ;;
  sqlite)
    sqlite_path="${SQLITE_NAME:-storage/db_live.sqlite3}"
    if [[ ! -f "$sqlite_path" ]]; then
      echo "SQLite database not found: $sqlite_path" >&2
      exit 1
    fi
    output_file="${BACKUP_DIR}/${backup_base}.sqlite3.gz"
    temporary_file="$(mktemp "${BACKUP_DIR}/.${backup_base}.XXXXXX.sqlite3.gz")"
    gzip -9 -c "$sqlite_path" >"$temporary_file"
    gzip -t "$temporary_file"
    ;;
  *)
    echo "Unsupported DB_ENGINE: ${DB_ENGINE}" >&2
    exit 1
    ;;
esac

temporary_checksum="$(mktemp "${BACKUP_DIR}/.${backup_base}.XXXXXX.sha256")"
checksum="$(sha256sum "$temporary_file" | awk '{ print $1 }')"
printf '%s  %s\n' "$checksum" "$(basename "$output_file")" >"$temporary_checksum"
chmod 600 "$temporary_file" "$temporary_checksum"
mv -f -- "$temporary_file" "$output_file"
temporary_file=""
mv -f -- "$temporary_checksum" "${output_file}.sha256"
temporary_checksum=""

find "$BACKUP_DIR" -type f \( -name "algowiki-db-*.sql.gz" -o -name "algowiki-db-*.sqlite3.gz" -o -name "algowiki-db-*.sha256" \) -mtime +"$RETENTION_DAYS" -delete

echo "Backup written to: $output_file"
echo "Checksum written to: ${output_file}.sha256"

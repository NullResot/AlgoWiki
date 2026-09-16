#!/usr/bin/env bash

set -Eeuo pipefail
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
POLLER_SOURCE="${SCRIPT_DIR}/server-poll-github-releases.py"

if [[ ${EUID} -ne 0 ]]; then
  echo "Run this installer as root." >&2
  exit 1
fi
if [[ ! -f "$POLLER_SOURCE" ]]; then
  echo "Missing poller source: $POLLER_SOURCE" >&2
  exit 1
fi
for command in python3 docker curl flock; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "Required command is unavailable: $command" >&2
    exit 1
  fi
done

install -o root -g root -m 0750 "$POLLER_SOURCE" /usr/local/sbin/algowiki-release-poller

if [[ ! -f /etc/algowiki-release-poller.env ]]; then
  config_temp="$(mktemp)"
  printf 'ALGOWIKI_RELEASE_NOT_BEFORE=%s\n' "$(date --utc +%Y-%m-%dT%H:%M:%SZ)" >"$config_temp"
  install -o root -g root -m 0600 "$config_temp" /etc/algowiki-release-poller.env
  rm -f -- "$config_temp"
fi

service_temp="$(mktemp)"
cat >"$service_temp" <<'EOF'
[Unit]
Description=Poll approved AlgoWiki GitHub releases
After=network-online.target docker.service
Wants=network-online.target
Requires=docker.service

[Service]
Type=oneshot
User=root
Group=root
EnvironmentFile=/etc/algowiki-release-poller.env
ExecStart=/usr/local/sbin/algowiki-release-poller
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=read-only
ProtectSystem=full
EOF
install -o root -g root -m 0644 "$service_temp" /etc/systemd/system/algowiki-release-poller.service
rm -f -- "$service_temp"

timer_temp="$(mktemp)"
cat >"$timer_temp" <<'EOF'
[Unit]
Description=Check for approved AlgoWiki releases every three minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=3min
RandomizedDelaySec=15s
Persistent=true
Unit=algowiki-release-poller.service

[Install]
WantedBy=timers.target
EOF
install -o root -g root -m 0644 "$timer_temp" /etc/systemd/system/algowiki-release-poller.timer
rm -f -- "$timer_temp"

systemctl daemon-reload
systemctl enable --now algowiki-release-poller.timer

echo "Installed outbound-only AlgoWiki release poller."

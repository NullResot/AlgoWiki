#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script as root." >&2
  exit 1
fi

SWAP_MB="${SWAP_MB:-2048}"
CONFIGURE_UFW="${CONFIGURE_UFW:-1}"
INSTALL_NGINX="${INSTALL_NGINX:-0}"

apt-get update
apt-get install -y ca-certificates curl gnupg lsb-release ufw default-mysql-client

install -m 0755 -d /etc/apt/keyrings

if [[ ! -f /etc/apt/keyrings/docker.gpg ]]; then
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
fi

arch="$(dpkg --print-architecture)"
codename="$(. /etc/os-release && echo "${VERSION_CODENAME}")"
cat >/etc/apt/sources.list.d/docker.list <<EOF
deb [arch=${arch} signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${codename} stable
EOF

if ! apt-get update || ! apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin; then
  rm -f /etc/apt/sources.list.d/docker.list
  apt-get update
  if ! apt-get install -y docker.io docker-compose; then
    apt-get install -y docker.io
  fi

  if ! docker compose version >/dev/null 2>&1 && command -v docker-compose >/dev/null 2>&1; then
    cat >/usr/local/bin/docker <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "compose" ]]; then
  shift
  exec docker-compose "$@"
fi

exec /usr/bin/docker "$@"
EOF
    chmod 0755 /usr/local/bin/docker
  fi
fi

systemctl enable --now docker

if [[ "${INSTALL_NGINX}" == "1" ]]; then
  apt-get install -y nginx
  systemctl enable --now nginx
fi

if [[ "${SWAP_MB}" -gt 0 ]] && ! swapon --show --noheadings | grep -q "/swapfile"; then
  if ! fallocate -l "${SWAP_MB}M" /swapfile 2>/dev/null; then
    dd if=/dev/zero of=/swapfile bs=1M count="${SWAP_MB}" status=progress
  fi
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  if ! grep -q "^/swapfile " /etc/fstab; then
    echo "/swapfile none swap sw 0 0" >>/etc/fstab
  fi
fi

if [[ "${CONFIGURE_UFW}" == "1" ]]; then
  ufw allow 22/tcp
  ufw allow 80/tcp
  ufw allow 443/tcp
  ufw --force enable
fi

docker --version
if docker compose version >/dev/null 2>&1; then
  docker compose version
elif command -v docker-compose >/dev/null 2>&1; then
  docker-compose version
else
  echo "docker compose not available"
fi
free -h
swapon --show

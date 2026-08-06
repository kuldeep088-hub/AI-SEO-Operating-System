#!/usr/bin/env bash
# Provision a fresh Ubuntu 24.04 server. Run once, as root. Idempotent.
#
#   ./bootstrap.sh seo.yourdomain.com you@yourdomain.com
#
# System-level only: packages, the service user, Caddy, systemd units, firewall.
# Everything that needs .env — starting Postgres, migrations, the build — lives
# in update.sh, because .env does not exist yet when this runs.
set -euo pipefail

DOMAIN="${1:-}"
EMAIL="${2:-}"
if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
    echo "usage: $0 <domain> <email-for-tls>" >&2
    exit 1
fi
[ "$(id -u)" -eq 0 ] || { echo "run as root" >&2; exit 1; }

APP_DIR=/opt/seoos/app
[ -d "$APP_DIR" ] || { echo "clone the repo to $APP_DIR first" >&2; exit 1; }

step() { printf '\n\033[1m▸ %s\033[0m\n' "$1"; }

step "System packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq ca-certificates curl gnupg git jq zstd ufw

# UTC, deliberately. apps/worker/scheduler.py converts to Asia/Kolkata itself —
# that conversion is the thing it exists to get right. Setting the system clock
# to IST invites a double conversion and a sync that fires at the wrong hour.
timedatectl set-timezone UTC

step "Docker"
if ! command -v docker >/dev/null; then
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
        | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
fi
systemctl enable --now docker

step "Node 22"
# Ubuntu 24.04 ships Node 18, which Next.js 15 does not support.
if ! command -v node >/dev/null || [ "$(node -v | cut -d. -f1 | tr -d v)" -lt 20 ]; then
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
    apt-get install -y -qq nodejs
fi

step "Caddy"
if ! command -v caddy >/dev/null; then
    curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/gpg.key \
        | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt \
        > /etc/apt/sources.list.d/caddy-stable.list
    apt-get update -qq
    apt-get install -y -qq caddy
fi

step "Service user"
if ! id seoos >/dev/null 2>&1; then
    useradd --system --create-home --home-dir /opt/seoos --shell /bin/bash seoos
fi
# backup.sh shells out to `docker compose exec postgres pg_dump`.
usermod -aG docker seoos

# backup.sh hardcodes ./backups relative to the repo. Symlinking it out of the
# repo means archives survive a re-clone, and stay out of any git operation.
mkdir -p /opt/seoos/backups
if [ ! -e "$APP_DIR/backups" ]; then
    ln -s /opt/seoos/backups "$APP_DIR/backups"
fi
chown -R seoos:seoos /opt/seoos

step "uv"
if [ ! -x /opt/seoos/.local/bin/uv ]; then
    sudo -u seoos sh -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'
fi
ln -sf /opt/seoos/.local/bin/uv /usr/local/bin/uv

step "Caddy config"
install -d -m 0755 /var/log/caddy
chown caddy:caddy /var/log/caddy
sed "s/DOMAIN_PLACEHOLDER/${DOMAIN}/g" "$APP_DIR/deploy/Caddyfile" > /etc/caddy/Caddyfile
# Caddy needs a contact address for the ACME account that issues the certificate.
if ! grep -q "^{" /etc/caddy/Caddyfile; then
    printf '{\n\temail %s\n}\n\n%s' "$EMAIL" "$(cat /etc/caddy/Caddyfile)" \
        > /etc/caddy/Caddyfile.tmp
    mv /etc/caddy/Caddyfile.tmp /etc/caddy/Caddyfile
fi
caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
systemctl enable caddy

step "systemd units"
cp "$APP_DIR"/deploy/systemd/*.service "$APP_DIR"/deploy/systemd/*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable seoos-api seoos-worker seoos-web seoos-backup.timer

step "Firewall"
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
# 5432 is deliberately absent. Postgres binds 127.0.0.1 in docker-compose.yml;
# ufw would not protect it anyway, since Docker writes iptables rules ahead of
# ufw's chain. The bind address is the control, not the firewall.
ufw --force enable

cat <<EOF

  ┌──────────────────────────────────────────────────────────────┐
  │  Provisioned. Nothing is running yet — .env does not exist.  │
  └──────────────────────────────────────────────────────────────┘

  1. cp $APP_DIR/deploy/env.server.example $APP_DIR/.env
     \$EDITOR $APP_DIR/.env
     chown seoos:seoos $APP_DIR/.env && chmod 600 $APP_DIR/.env

     Copy TOKEN_ENCRYPTION_KEY from your Mac's .env, or every stored
     Google connection is orphaned and every client must reconnect.

  2. Point $DOMAIN at this server's IP before step 3 —
     Caddy provisions TLS on first start and needs the DNS to resolve.

  3. $APP_DIR/deploy/update.sh

  4. Register BOTH redirect URIs in Google Cloud Console:
       https://$DOMAIN/v1/auth/google/callback
       https://$DOMAIN/v1/google/callback

EOF

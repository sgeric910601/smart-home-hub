#!/usr/bin/env bash
# 安裝或移除 systemd 服務（需 root）：pkexec bash deploy/native/install.sh [--uninstall]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
UNITS=(smart-home-hub smart-home-hub-caddy)
[ "$(id -u)" = 0 ] || { echo "✗ 請以 root 執行：pkexec bash $0" >&2; exit 1; }

if [ "${1:-}" = "--uninstall" ]; then
  systemctl disable --now "${UNITS[@]/%/.service}" 2>/dev/null || true
  for unit in "${UNITS[@]}"; do rm -f "/etc/systemd/system/$unit.service"; done
  rm -f /usr/local/bin/caddy-homehub
  systemctl daemon-reload
  echo "✓ 已移除服務；專案資料夾、.env 與 /var/lib/smart-home-hub-caddy 憑證保留"
  exit 0
fi

# 服務以專案擁有者身分執行，不用 root。
OWNER="${SUDO_USER:-}"
if [ -z "$OWNER" ] && [ -n "${PKEXEC_UID:-}" ]; then OWNER="$(id -nu "$PKEXEC_UID")"; fi
if [ -z "$OWNER" ]; then OWNER="$(stat -c %U "$ROOT")"; fi
[ "$OWNER" != root ] || { echo "✗ 無法判斷專案擁有者，請用一般使用者帳號透過 pkexec 執行" >&2; exit 1; }

for need in "$ROOT/.venv/bin/python" "$ROOT/frontend/dist/index.html" "$ROOT/deploy/native/build/caddy" "$ROOT/deploy/caddy.env" "$ROOT/.env"; do
  [ -e "$need" ] || { echo "✗ 缺少 $need，請先依 docs/PRIVATE_DEPLOYMENT.md 完成前面步驟" >&2; exit 1; }
done

install -d -o "$OWNER" -m 700 "$ROOT/backend/data"
install -o root -g root -m 755 "$ROOT/deploy/native/build/caddy" /usr/local/bin/caddy-homehub
for unit in "${UNITS[@]}"; do
  sed -e "s|@ROOT@|$ROOT|g" -e "s|@USER@|$OWNER|g" "$ROOT/deploy/native/$unit.service.in" > "/etc/systemd/system/$unit.service"
done
systemctl daemon-reload
systemctl enable "${UNITS[@]/%/.service}"
systemctl restart "${UNITS[@]/%/.service}"
systemctl --no-pager --lines=3 status "${UNITS[@]/%/.service}" || true
echo "✓ 已安裝並啟動。查看憑證進度：journalctl -u smart-home-hub-caddy -f"

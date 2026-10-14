#!/usr/bin/env bash
# 以官方 Go 工具鏈編譯含 Cloudflare DNS 模組的 Caddy，不需 root。
# Go 壓縮檔依 go.dev 公布的 SHA-256 驗證；Go 模組由 sum.golang.org 透明日誌驗證。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$ROOT/deploy/native/build"
CADDY_VERSION="${CADDY_VERSION:-v2.11.7}"
XCADDY_VERSION="${XCADDY_VERSION:-v0.4.7}"
CLOUDFLARE_VERSION="${CLOUDFLARE_VERSION:-v0.2.4}"
GO_DIR="${GO_DIR:-$HOME/.local/go}"

case "$(uname -m)" in
  x86_64) GOARCH=amd64 ;;
  aarch64 | arm64) GOARCH=arm64 ;;
  *) echo "✗ 不支援的架構：$(uname -m)" >&2; exit 1 ;;
esac

if ! "$GO_DIR/bin/go" version >/dev/null 2>&1; then
  read -r GO_FILE GO_SHA < <(curl -fsSL "https://go.dev/dl/?mode=json" | python3 -c '
import json, sys
release = json.load(sys.stdin)[0]
item = next(f for f in release["files"] if f["os"] == "linux" and f["arch"] == sys.argv[1] and f["kind"] == "archive")
print(item["filename"], item["sha256"])' "$GOARCH")
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  echo "下載 $GO_FILE"
  curl -fsSLo "$TMP/$GO_FILE" "https://go.dev/dl/$GO_FILE"
  echo "$GO_SHA  $TMP/$GO_FILE" | sha256sum -c -
  tar -C "$TMP" -xzf "$TMP/$GO_FILE"
  mkdir -p "$(dirname "$GO_DIR")"
  rm -rf "$GO_DIR"
  mv "$TMP/go" "$GO_DIR"
fi

export PATH="$GO_DIR/bin:$PATH" GOPROXY=https://proxy.golang.org GOSUMDB=sum.golang.org GOFLAGS=
mkdir -p "$OUT"
go version
GOBIN="$OUT" go install "github.com/caddyserver/xcaddy/cmd/xcaddy@$XCADDY_VERSION"
"$OUT/xcaddy" build "$CADDY_VERSION" --with "github.com/caddy-dns/cloudflare@$CLOUDFLARE_VERSION" --output "$OUT/caddy"
"$OUT/caddy" list-modules | grep -qx "dns.providers.cloudflare" || { echo "✗ 缺少 Cloudflare DNS 模組" >&2; exit 1; }
"$OUT/caddy" version
echo "✓ 已建置 $OUT/caddy"

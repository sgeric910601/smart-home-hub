"""在樹莓派設定私人部署：Tailscale 位址、Cloudflare DNS、平台 .env，並可直接啟動容器。

用法：
    python3 deploy/setup_pi.py homehub.example.com      # 第一次設定或重新設定
    python3 deploy/setup_pi.py --dns-only               # Tailscale 位址改變後只更新 DNS
"""

import argparse
import getpass
import ipaddress
import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CADDY_ENV = ROOT / "deploy" / "caddy.env"
HUB_ENV = ROOT / ".env"
COMPOSE = ROOT / "deploy" / "docker-compose.yml"
API = "https://api.cloudflare.com/client/v4"
TAILNET = (ipaddress.ip_network("100.64.0.0/10"), ipaddress.ip_network("fd7a:115c:a1e0::/48"))


def fail(message: str):
    raise SystemExit(f"✗ {message}")


def read_env(path: Path):
    values = {}
    if path.exists():
        for line in path.read_text(encoding="utf8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    return values


def write_env(path: Path, updates: dict[str, str]):
    """只改指定欄位，保留其他設定與註解；檔案權限固定為 600。"""
    lines = path.read_text(encoding="utf8").splitlines() if path.exists() else []
    pending = dict(updates)
    for index, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if not line.lstrip().startswith("#") and "=" in line and key in pending:
            lines[index] = f"{key}={pending.pop(key)}"
    lines += [f"{key}={value}" for key, value in pending.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf8")
    path.chmod(0o600)


def run(*command: str):
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout.strip()


def tailscale_addresses():
    try:
        found = [run("tailscale", "ip", "-4"), run("tailscale", "ip", "-6")]
    except (subprocess.CalledProcessError, FileNotFoundError):
        fail("Tailscale 尚未連線，請先執行 sudo tailscale up")
    addresses = [line.strip() for text in found for line in text.splitlines() if line.strip()]
    for address in addresses:
        if not any(ipaddress.ip_address(address) in network for network in TAILNET):
            fail(f"{address} 不是 Tailscale 位址，停止設定以免公開錯誤的 IP")
    return addresses


def tailscale_owner():
    try:
        status = json.loads(run("tailscale", "status", "--json"))
        login = status["User"][str(status["Self"]["UserID"])]["LoginName"]
    except (subprocess.CalledProcessError, KeyError, ValueError):
        return ""
    # 加上標籤的主機屬於 tagged-devices，不是實際使用者。
    return login if "@" in login else ""


def cloudflare(token: str, method: str, path: str, body: dict | None = None):
    request = urllib.request.Request(
        API + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.load(response)
    except urllib.error.HTTPError as error:
        try:
            data = json.load(error)
        except ValueError:
            fail(f"Cloudflare API 回應 HTTP {error.code}")
    except urllib.error.URLError as error:
        fail(f"無法連到 Cloudflare API：{error.reason}")
    if not data.get("success"):
        messages = "；".join(item.get("message", "") for item in data.get("errors", []))
        fail(f"Cloudflare API 錯誤：{messages or '未知原因'}")
    return data["result"]


def update_dns(domain: str, token: str, addresses: list[str]):
    labels = domain.split(".")
    zone = None
    for index in range(len(labels) - 1):
        candidate = ".".join(labels[index:])
        result = cloudflare(token, "GET", f"/zones?name={urllib.parse.quote(candidate)}")
        if result:
            zone = result[0]["id"]
            break
    if not zone:
        fail("找不到網域所屬的 Cloudflare Zone，請確認 Token 權限包含 Zone:Read")
    for address in addresses:
        kind = "A" if ipaddress.ip_address(address).version == 4 else "AAAA"
        query = f"type={kind}&name={urllib.parse.quote(domain)}"
        existing = cloudflare(token, "GET", f"/zones/{zone}/dns_records?{query}")
        # 僅 DNS（灰雲）：Cloudflare 代理連不到私有位址，也不應經手家中流量。
        body = {
            "type": kind,
            "name": domain,
            "content": address,
            "ttl": 300,
            "proxied": False,
            "comment": "Smart Home Hub: Tailscale only",
        }
        if existing and existing[0]["content"] == address and not existing[0].get("proxied"):
            print(f"✓ {kind} {domain} → {address}（未變更）")
            continue
        if existing:
            cloudflare(token, "PUT", f"/zones/{zone}/dns_records/{existing[0]['id']}", body)
        else:
            cloudflare(token, "POST", f"/zones/{zone}/dns_records", body)
        print(f"✓ {kind} {domain} → {address}")


def ask(prompt: str, default: str = ""):
    answer = input(f"{prompt}{f'［{default}］' if default else ''}：").strip()
    return answer or default


def configure(domain: str):
    for command in ("docker", "tailscale"):
        if not shutil.which(command):
            fail(f"缺少 {command}，請先依 docs/PRIVATE_DEPLOYMENT.md 安裝")
    addresses = tailscale_addresses()
    current = read_env(CADDY_ENV)
    email = ask("Let's Encrypt 憑證通知 Email", current.get("ACME_EMAIL", ""))
    token = current.get("CLOUDFLARE_API_TOKEN", "")
    if not token or ask("要更換 Cloudflare API Token 嗎？(y/N)", "N").lower() == "y":
        token = getpass.getpass("Cloudflare API Token（輸入時不顯示）：").strip()
    if not (email and token):
        fail("Email 與 Cloudflare API Token 都必須填寫")
    write_env(
        CADDY_ENV,
        {
            "HUB_DOMAIN": domain,
            "HUB_BIND": " ".join(addresses),
            "ACME_EMAIL": email,
            "CLOUDFLARE_API_TOKEN": token,
        },
    )
    print(f"✓ 已寫入 {CADDY_ENV.relative_to(ROOT)}（權限 600）")

    if not HUB_ENV.exists():
        subprocess.run([sys.executable, str(ROOT / "scripts" / "init_env.py")], check=True)
    owner = ask("自動登入為管理員的 Tailscale 帳號（多個以逗號分隔）", tailscale_owner())
    admins = [item.strip().lower() for item in owner.split(",") if item.strip()]
    if not admins:
        fail("至少需要一個管理員 Tailscale 帳號")
    write_env(
        HUB_ENV,
        {
            "HUB_PUBLIC_ORIGIN": f"https://{domain}",
            "HUB_SECURE_COOKIE": "true",
            "HUB_SERVE_FRONTEND": "false",
            "HUB_TAILSCALE_AUTH": "true",
            "HUB_TAILSCALE_ADMINS": json.dumps(admins),
            "HUB_SESSION_HOURS": read_env(HUB_ENV).get("HUB_SESSION_HOURS", "168"),
        },
    )
    print("✓ 已更新平台 .env：私人網址、Tailscale 自動登入與安全 Cookie")
    update_dns(domain, token, addresses)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("domain", nargs="?", help="私人網址，例如 homehub.example.com")
    parser.add_argument("--dns-only", action="store_true", help="只依目前 Tailscale 位址更新 DNS 與綁定位址")
    args = parser.parse_args()
    if args.dns_only:
        current = read_env(CADDY_ENV)
        if not current.get("HUB_DOMAIN") or not current.get("CLOUDFLARE_API_TOKEN"):
            fail("尚未完成設定，請先執行 python3 deploy/setup_pi.py <網域>")
        addresses = tailscale_addresses()
        write_env(CADDY_ENV, {"HUB_BIND": " ".join(addresses)})
        update_dns(current["HUB_DOMAIN"], current["CLOUDFLARE_API_TOKEN"], addresses)
    else:
        if not args.domain:
            parser.error("請提供網域，例如 python3 deploy/setup_pi.py homehub.example.com")
        configure(args.domain.strip().lower().rstrip("."))
    if ask("要現在建置並啟動平台嗎？(Y/n)", "Y").lower() != "n":
        subprocess.run(["docker", "compose", "-f", str(COMPOSE), "up", "-d", "--build"], check=True)
        print(f"✓ 已啟動。開啟 https://{read_env(CADDY_ENV)['HUB_DOMAIN']}（裝置需已登入 Tailscale）")
    else:
        print(f"稍後執行：docker compose -f {COMPOSE.relative_to(ROOT)} up -d --build")


if __name__ == "__main__":
    main()

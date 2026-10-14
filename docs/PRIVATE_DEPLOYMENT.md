# 私人部署（樹莓派／Ubuntu + Tailscale + Cloudflare 網域）

目標：手機、平板、電腦用同一個網址（例如 `https://homehub.example.com`）開啟平台，可安裝成 App；只有登入自己 Tailscale 的裝置連得到，網際網路上的其他人即使知道網址也連不進來。

```text
手機／平板／電腦（已登入 Tailscale）
  → DNS：homehub.example.com → 樹莓派的 Tailscale IP（Cloudflare 僅 DNS，灰雲）
  → 樹莓派 Caddy（只監聽 Tailscale 位址，正式 HTTPS 憑證）
      ├─ 前端靜態檔（PWA）
      └─ 127.0.0.1:8000 FastAPI → Home Assistant／BLE
```

## 安全設計

| 層級 | 做法 |
| --- | --- |
| DNS | 紀錄指向 `100.x.y.z` Tailscale 私有位址，關閉 Cloudflare 代理；外網解析得到，但路由不到 |
| 路由器 | 不開任何連接埠轉發；憑證以 DNS-01 驗證取得，不需要對外的 80／443 |
| Caddy | 只綁定樹莓派的 Tailscale IP，並拒絕 `100.64.0.0/10`、`fd7a:115c:a1e0::/48` 以外的來源 |
| 後端 | 只監聽 `127.0.0.1:8000`，經 Caddy 才能存取 |
| 登入 | Tailscale 白名單帳號免密碼；其他帳號、標籤裝置一律拒絕；密碼登入保留作備用 |
| Tailscale ACL | 可選：只允許自己的帳號連到樹莓派 443 埠（見下文） |

憑證會記錄在公開的 Certificate Transparency 日誌，代表網域名稱會被看見，但仍只解析到私有 IP。

## 1. 準備主機

可用 Ubuntu 22.04／24.04，或 Raspberry Pi 4／5 的 64 位元 Raspberry Pi OS（Bookworm 以上）。主機需 24 小時開機；放在學校、公司等共用網路時，務必完成第 7 節的加固。

1. 選擇部署方式：
   - **Docker**（樹莓派等專用主機）：依 [Docker 官方安裝指南](https://docs.docker.com/engine/install/) 使用官方 apt 套件庫（含 GPG 簽章驗證），完成後執行 `sudo usermod -aG docker $USER` 並重新登入。
   - **原生 systemd**（已有其他服務的工作站）：不安裝 Docker。Docker 會把 iptables 的轉送預設改為丟棄，常使 Waydroid、LXC、libvirt 等既有虛擬網路斷線。需要 Python 3.12+ 與 Node.js 24。
2. 安裝 Tailscale：依 [Tailscale 官方 Linux 指南](https://tailscale.com/kb/1031/install-linux) 加入官方 apt 套件庫，再執行：

    ```sh
    sudo tailscale up
    ```

3. 到 [Tailscale 管理後台](https://login.tailscale.com/admin/machines)：
   - 對樹莓派選「Disable key expiry」，避免 180 天後掉線。
   - 確認樹莓派的 Tailscale IPv4（`tailscale ip -4`）。
4. 下載專案：

    ```sh
    git clone https://github.com/sgeric910601/smart-home-hub.git
    cd smart-home-hub
    ```

## 2. 建立 Cloudflare API Token

在 Cloudflare 後台「My Profile → API Tokens → Create Token」，選「Create Custom Token」：

- 權限：`Zone → Zone → Read`、`Zone → DNS → Edit`
- Zone Resources：`Include → Specific zone →` 你的網域
- 建議設定到期日；Token 只在建立時顯示一次，不要貼到聊天、截圖或 Git。

## 3. 執行設定腳本

Docker 部署：

```sh
python3 deploy/setup_host.py homehub.example.com
```

原生 systemd 部署：先建立後端環境、建置前端與 Caddy（皆不需 root），再執行設定腳本：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
npm ci --prefix frontend
npm run build --prefix frontend
bash deploy/native/build_caddy.sh
python3 deploy/setup_host.py --native homehub.example.com
```

`build_caddy.sh` 會把官方 Go 工具鏈下載到 `~/.local/go`（依 go.dev 公布的 SHA-256 驗證），再以 xcaddy 編譯含 Cloudflare DNS 模組的 Caddy；Go 模組經 sum.golang.org 驗證。設定腳本最後以 `pkexec` 跳出系統密碼視窗，安裝兩個 systemd 服務：

| 服務 | 執行身分 | 監聽 |
| --- | --- | --- |
| `smart-home-hub` | 專案擁有者 | `127.0.0.1:8000` |
| `smart-home-hub-caddy` | 專案擁有者，僅授予綁定低埠號的權限 | Tailscale 位址的 443／80 |

移除服務：`pkexec bash deploy/native/install.sh --uninstall`（保留專案、`.env` 與憑證）。

腳本會依序：

1. 讀取樹莓派的 Tailscale IPv4／IPv6，拒絕非 Tailscale 位址。
2. 詢問 Let's Encrypt 通知 Email 與 Cloudflare Token（輸入不顯示），寫入 `deploy/caddy.env`（權限 600，已列入 `.gitignore`）。
3. 建立或更新 `.env`：`HUB_PUBLIC_ORIGIN`、安全 Cookie、Tailscale 自動登入與管理員帳號（預設帶入樹莓派登入的 Tailscale 帳號）。
4. 在 Cloudflare 建立或更新 `A`／`AAAA` 紀錄，固定為「僅 DNS」。
5. 詢問是否立即 `docker compose -f deploy/docker-compose.yml up -d --build`。

Docker 第一次建置會編譯前端與含 Cloudflare 模組的 Caddy，樹莓派約需 10–20 分鐘。查看狀態：

```sh
docker compose -f deploy/docker-compose.yml logs -f caddy      # Docker
journalctl -u smart-home-hub-caddy -f                          # 原生 systemd
```

Caddy 日誌出現 `certificate obtained successfully` 即完成。

## 4. 新增裝置

1. 在手機、平板或電腦安裝 Tailscale App，登入**同一個** Tailscale 帳號。
2. 開啟 `https://homehub.example.com`，平台會自動以 Tailscale 身分登入。
3. 安裝成 App：
   - iPhone／iPad：Safari 分享按鈕 →「加入主畫面」。
   - Android：Chrome 選單 →「安裝應用程式」。
   - 電腦：Chrome／Edge 網址列右側的安裝圖示。

家人使用自己的 Tailscale 帳號時，先在 Tailscale 後台把對方加入 tailnet，再將帳號加進 `.env`：

```sh
HUB_TAILSCALE_ADMINS=["you@example.com"]
HUB_TAILSCALE_VIEWERS=["family@example.com"]
```

`VIEWERS` 只能查看，不能控制設備。修改後執行 `docker compose -f deploy/docker-compose.yml up -d` 重新套用。

## 5. 登出與清除快取

右上角（手機在頂部）登出按鈕會：

- 撤銷這台裝置的登入。
- 清除 Service Worker、離線快取與本機設定（例如深淺色主題）。
- 停止自動以 Tailscale 身分登入；下次要按「以 Tailscale 身分登入」才會進入。

要讓某台裝置完全失去存取權，請在 Tailscale 後台將它移除；平台登入在 `HUB_SESSION_HOURS`（預設 168 小時）內仍有效，可重新啟動後端或等待到期。

## 6. 可選：Tailscale ACL 只開放平台

預設 tailnet 內所有裝置互通。若要只允許自己的帳號連到樹莓派的平台，可在 [Access Controls](https://login.tailscale.com/admin/acls) 將樹莓派加上 `tag:homehub`，並加入：

```json
{
  "tagOwners": { "tag:homehub": ["autogroup:admin"] },
  "grants": [
    { "src": ["autogroup:member"], "dst": ["tag:homehub"], "ip": ["tcp:443", "tcp:80"] }
  ]
}
```

修改 ACL 前先保留原本允許其他裝置互通的規則，避免把自己鎖在外面；SSH 管理樹莓派也需另外允許 `tcp:22` 或使用 Tailscale SSH。

## 7. 共用網路（學校、公司）加固

主機和陌生人在同一個網段時，除了 Caddy 只綁定 Tailscale，再加上主機防火牆，讓主機上的任何服務都不會對該網段開放。

> 主機已有其他服務（遠端桌面、學校監控代理等）時，先以 `sudo ufw status verbose` 查看現有規則，不要直接改預設政策；改為只針對本平台補上 `sudo ufw allow in on tailscale0 to any port 443,80 proto tcp`，並以下方的驗證步驟確認。

1. 先確認能透過 Tailscale 連進主機（`ssh <使用者>@<主機的 Tailscale IP>` 或 Tailscale SSH），避免啟用防火牆後把自己鎖在外面。
2. 啟用 ufw：只允許 Tailscale 網卡進入，並開放 Tailscale 直連用的 UDP 41641。

    ```sh
    sudo ufw default deny incoming
    sudo ufw default allow outgoing
    sudo ufw allow in on tailscale0
    sudo ufw allow 41641/udp
    sudo ufw enable
    sudo ufw status verbose
    ```

    仍需從學校網段 SSH 時，可暫時加上 `sudo ufw allow 22/tcp`，確認 Tailscale SSH 可用後再移除。
3. Docker 發布的連接埠（`ports:`）會繞過 ufw。本部署使用主機網路、不發布連接埠；其他容器若要發布，一律寫成 `127.0.0.1:主機埠:容器埠`。
4. Home Assistant 與本平台裝在同一台時，預設會對所有網卡開放 8123。用 Docker 主機網路時，在 HA 的 `configuration.yaml` 加入以下設定只監聽本機；平台的 `HA_URL` 使用 `http://127.0.0.1:8123`：

    ```yaml
    http:
      server_host: 127.0.0.1
    ```

### 驗證只有 Tailscale 連得到

在主機上確認沒有服務對外監聽：

```sh
sudo ss -ltnup | grep -vE '127\.0\.0\.1|\[::1\]|100\.|fd7a:'
```

除了 SSH（若暫時保留）與 Tailscale 自身，不應出現其他服務。接著用一台**在同一網段、沒開 Tailscale** 的裝置測試，下列都應逾時或被拒絕：

```sh
curl -m 5 https://homehub.example.com
nc -vz -w 3 <主機的學校 IP> 443
nc -vz -w 3 <主機的學校 IP> 8000
nc -vz -w 3 <主機的學校 IP> 8123
```

再用開啟 Tailscale 的手機開啟網址，應直接進入平台。

學校網路若阻擋 Tailscale 的 UDP 直連，Tailscale 會自動改走加密中繼（DERP），仍可使用，只是延遲較高；`tailscale netcheck` 可查看狀態。

## 8. 設備在其他網路：Tailscale 子網路路由

米家、Electrolux 等可在 Home Assistant 以帳號走雲端的設備，主機放在哪裡都能控制。Tapo 插座、攝影機、紅外線等需要區網連線的設備，可在設備所在的網路放一台常開的小主機（例如樹莓派接該地 Wi-Fi），把那個網段分享進 tailnet：

```sh
echo 'net.ipv4.ip_forward = 1' | sudo tee /etc/sysctl.d/99-tailscale.conf
sudo sysctl -p /etc/sysctl.d/99-tailscale.conf
sudo tailscale up --advertise-routes=192.168.1.0/24
```

在 Tailscale 後台核准該路由，主機端執行 `sudo tailscale up --accept-routes` 後，Home Assistant 即可用設備的區網 IP 連線。該網路的路由器同樣不需開任何連接埠；路由只在你的 tailnet 內可見，ACL 可再限制只有主機能使用。

## 9. 更新與維護

```sh
git pull
docker compose -f deploy/docker-compose.yml up -d --build      # Docker
npm run build --prefix frontend && pkexec systemctl restart smart-home-hub smart-home-hub-caddy   # 原生
```

- Tailscale IP 改變（例如重新加入 tailnet）：`python3 deploy/setup_host.py --dns-only`。
- 備份：`hub-data` volume 含 SQLite 操作紀錄；`caddy-data` 含憑證，可重新申請。
- 更換 Cloudflare Token：重新執行設定腳本並選擇更換 Token。

## 疑難排解

| 狀況 | 檢查 |
| --- | --- |
| 開啟網址顯示「連不到家庭平台」 | 裝置的 Tailscale 是否開啟；`tailscale ping <樹莓派>` |
| 瀏覽器找不到網址 | 部分路由器或 DNS 會擋「公開網域解析到私有 IP」（DNS rebinding 保護）；在 Tailscale 後台 DNS 啟用 MagicDNS 並設定全域 DNS（例如 1.1.1.1），或在路由器將此網域加入例外 |
| Caddy 一直重啟 | 開機時 Tailscale 尚未取得 IP 會暫時綁定失敗，會自動重試；持續失敗時檢查 `deploy/caddy.env` 的 `HUB_BIND` |
| 憑證申請失敗 | Token 權限、網域是否在該 Cloudflare 帳號、`docker compose logs caddy` |
| 沒有自動登入 | 登入頁會顯示原因：帳號不在白名單、標籤裝置或主機無法查詢 Tailscale；也可能是先前主動登出過，按「以 Tailscale 身分登入」 |
| 後端無法查詢 Tailscale | 確認 `/var/run/tailscale/tailscaled.sock` 存在，且已掛載到 backend 容器 |

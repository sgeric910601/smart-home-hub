# 樹莓派私人部署（Tailscale + Cloudflare 網域）

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

## 1. 準備樹莓派

建議 Raspberry Pi 4／5、64 位元 Raspberry Pi OS（Bookworm 以上），網路線接家中路由器，並在路由器替它保留固定區網 IP。

1. 安裝 Docker Engine 與 Compose 外掛：依 [Docker 官方 Debian 安裝指南](https://docs.docker.com/engine/install/debian/) 使用官方 apt 套件庫（含 GPG 簽章驗證），完成後執行 `sudo usermod -aG docker $USER` 並重新登入。
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

```sh
python3 deploy/setup_pi.py homehub.example.com
```

腳本會依序：

1. 讀取樹莓派的 Tailscale IPv4／IPv6，拒絕非 Tailscale 位址。
2. 詢問 Let's Encrypt 通知 Email 與 Cloudflare Token（輸入不顯示），寫入 `deploy/caddy.env`（權限 600，已列入 `.gitignore`）。
3. 建立或更新 `.env`：`HUB_PUBLIC_ORIGIN`、安全 Cookie、Tailscale 自動登入與管理員帳號（預設帶入樹莓派登入的 Tailscale 帳號）。
4. 在 Cloudflare 建立或更新 `A`／`AAAA` 紀錄，固定為「僅 DNS」。
5. 詢問是否立即 `docker compose -f deploy/docker-compose.yml up -d --build`。

第一次建置會編譯前端與含 Cloudflare 模組的 Caddy，樹莓派約需 10–20 分鐘。之後查看狀態：

```sh
docker compose -f deploy/docker-compose.yml ps
docker compose -f deploy/docker-compose.yml logs -f caddy
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

## 7. 更新與維護

```sh
git pull
docker compose -f deploy/docker-compose.yml up -d --build
```

- Tailscale IP 改變（例如重新加入 tailnet）：`python3 deploy/setup_pi.py --dns-only`。
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

# 更新紀錄

## 尚未標記版本

- 可安裝成手機、平板與電腦 App（PWA）：manifest、圖示、Service Worker 與離線說明頁；API 與攝影機串流不經快取。
- 攝影機播放器改為按下播放才載入並改用精簡版，首頁主程式由 899 KB 降至 328 KB。
- 新增樹莓派／Linux 私人部署：Caddy 只監聽 Tailscale 位址並拒絕其他來源，以 Cloudflare DNS 驗證取得正式 HTTPS 憑證；`deploy/setup_pi.py` 一次設定 DNS、憑證 Token 與 `.env`。
- 新增 Tailscale 身分登入：白名單帳號免密碼，標籤裝置與未授權帳號拒絕；密碼登入保留。
- 登出時一併清除該裝置的離線快取、Service Worker 與本機設定，並停止自動登入。
- 新增 `HUB_PUBLIC_ORIGIN`、`HUB_SESSION_HOURS`；建置檔長期快取、頁面每次確認；觸控裝置輸入框避免 iOS 自動放大。

- 新增探索／配對入口：讀取當前 HA 動態整合目錄、搜尋品牌別名與協定，顯示待設定探索結果。
- 提供硬體條件、HA 官方設定連結及配對後重新讀取；新增 HA_BROWSER_URL 支援手機使用不同的 HA 位址。
- 加入 Zigbee2MQTT、CSA、ESPHome 相容性資料庫查詢連結；不宣稱全型號可控制。

- 新增跨品牌 Home Assistant 實體匯入精靈，支援命名、房間及唯讀保護。
- 基本開關需使用者逐次雙向測試與新狀態確認後才可開放；設定／診斷開關固定唯讀。
- SQLite 保存匯入映射，新增 Mock 示範流程、權限與異常測試。

## 0.1.0 — 2026-10-13

第一個公開預覽版。

- React／TypeScript 網頁、FastAPI、SQLite 與統一設備模型。
- Mock 與 Real Mode，Home Assistant REST／WebSocket 連線、狀態確認及重連。
- 同高裝置捷徑、手機全螢幕詳情、平板／電腦側邊面板與深淺色。
- 登入、唯讀角色、CSRF、能力白名單、離線／逾時處理與操作紀錄。
- 依 HA Entity 提供插座、燈具、部分除濕機、攝影機影像／PTZ／隱私與紅外線控制。
- 可選米家香氛機 BLE Provider：開關、時長、間隔、亮度與 RGB，已完成單台實機驗證。
- 從零建立 Home Assistant、設備映射、私人存取與樹莓派部署界線的教學。

尚未完成：定時排程、一般化自動化編輯、真實情境編輯、未有資料來源的電力統計、溫濕度計實測，以及容器／arm64 的完整部署驗證。公開程式碼不包含 HA 設定備份、私人憑證或裝置配對資訊。

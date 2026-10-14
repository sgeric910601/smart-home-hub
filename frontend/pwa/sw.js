// 建置時由 vite.config.ts 填入版本與預先快取清單；開發模式不註冊。
const VERSION = __HUB_VERSION__;
const PRECACHE = __HUB_PRECACHE__;
const CACHE = `hub-shell-${VERSION}`;
const OFFLINE = "/offline.html";
const NAVIGATION_TIMEOUT = 10000;
// API、即時事件與攝影機串流一律直連後端，不經快取，避免保存設備狀態或登入資訊。
const BYPASS = ["/api/", "/ws/", "/docs", "/openapi.json"];

// 不呼叫 skipWaiting：舊頁面仍可能延後載入舊版播放器檔案，等所有頁面關閉後才切換新版。
self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(PRECACHE)));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys.filter((key) => key.startsWith("hub-shell-") && key !== CACHE).map((key) => caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin || BYPASS.some((prefix) => url.pathname.startsWith(prefix))) return;
  if (request.mode === "navigate") {
    event.respondWith(navigate(request));
    return;
  }
  event.respondWith(cached(request));
});

// 頁面一律取最新版本；VPN 未開啟或主機離線時，限時改顯示離線說明頁。
async function navigate(request) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), NAVIGATION_TIMEOUT);
  try {
    return await fetch(request, { signal: controller.signal });
  } catch {
    return (await caches.match(OFFLINE)) ?? Response.error();
  } finally {
    clearTimeout(timer);
  }
}

// 建置檔名含內容雜湊，可長期沿用；未預先快取的同源靜態檔於第一次成功載入後保存。
async function cached(request) {
  const hit = await caches.match(request);
  if (hit) return hit;
  const response = await fetch(request);
  if (response.ok && new URL(request.url).pathname.startsWith("/assets/")) {
    const cache = await caches.open(CACHE);
    await cache.put(request, response.clone());
  }
  return response;
}

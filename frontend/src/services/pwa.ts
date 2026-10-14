// Service Worker 只在 HTTPS 或 localhost 可用；註冊失敗不影響平台操作。
export function registerServiceWorker() {
  if (!("serviceWorker" in navigator) || !window.isSecureContext) return;
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => undefined);
  });
}

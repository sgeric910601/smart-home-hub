// 主動登出後不再自動以 Tailscale 身分登入，直到使用者在登入頁再次選擇。
const AUTO_LOGIN = "hub-tailscale-auto";

export function autoLoginAllowed() {
  try {
    return localStorage.getItem(AUTO_LOGIN) !== "off";
  } catch {
    return false;
  }
}

export function setAutoLogin(allowed: boolean) {
  try {
    localStorage.setItem(AUTO_LOGIN, allowed ? "on" : "off");
  } catch {
    // 私密瀏覽等情況無法保存設定，只影響下次是否自動登入。
  }
}

// 清除這台裝置上的離線快取、Service Worker 與本機設定；登入 Cookie 由後端登出時撤銷。
export async function clearDeviceData() {
  const tasks: Promise<unknown>[] = [];
  if ("caches" in window)
    tasks.push(
      caches.keys().then((keys) => Promise.all(keys.map((key) => caches.delete(key)))),
    );
  if ("serviceWorker" in navigator)
    tasks.push(
      navigator.serviceWorker
        .getRegistrations()
        .then((items) => Promise.all(items.map((item) => item.unregister()))),
    );
  await Promise.allSettled(tasks);
  try {
    localStorage.clear();
    sessionStorage.clear();
  } catch {
    // 儲存空間不可用時沒有資料需要清除。
  }
}

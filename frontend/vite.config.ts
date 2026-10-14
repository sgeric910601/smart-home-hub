import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// public/ 的檔案不在 bundle 內，需手動列入離線頁、圖示與 manifest。
const PUBLIC_PRECACHE = [
  "/offline.html",
  "/manifest.webmanifest",
  "/icons/icon.svg",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/icons/apple-touch-icon.png",
];

// 依建置結果產生 sw.js：預先快取含雜湊的 JS／CSS，內容改變時版本號跟著改變。
function serviceWorker(): Plugin {
  return {
    name: "hub-service-worker",
    apply: "build",
    async generateBundle(_options, bundle) {
      const template = await readFile(new URL("./pwa/sw.js", import.meta.url), "utf8");
      const assets = Object.keys(bundle)
        .filter((name) => name !== "index.html" && /\.(js|css|woff2?|png|svg)$/.test(name))
        .sort()
        .map((name) => `/${name}`);
      const index = bundle["index.html"];
      const hash = createHash("sha256").update(template).update(assets.join("\n"));
      if (index?.type === "asset") hash.update(index.source);
      for (const file of PUBLIC_PRECACHE) {
        hash.update(await readFile(new URL(`./public${file}`, import.meta.url)));
      }
      this.emitFile({
        type: "asset",
        fileName: "sw.js",
        source: template
          .replace("__HUB_VERSION__", JSON.stringify(hash.digest("hex").slice(0, 12)))
          .replace("__HUB_PRECACHE__", JSON.stringify([...PUBLIC_PRECACHE, ...assets])),
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), tailwindcss(), serviceWorker()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/ws": { target: "ws://127.0.0.1:8000", ws: true },
      "/docs": "http://127.0.0.1:8000",
      "/openapi.json": "http://127.0.0.1:8000",
    },
  },
  test: { include: ["src/**/*.test.{ts,tsx}"] },
});

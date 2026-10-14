# 建置前端靜態檔，並編譯含 Cloudflare DNS 模組的 Caddy；皆使用官方映像，支援樹莓派 arm64。
FROM node:24-slim AS frontend
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM caddy:2-builder AS caddy
RUN xcaddy build --with github.com/caddy-dns/cloudflare

FROM caddy:2
COPY --from=caddy /usr/bin/caddy /usr/bin/caddy
COPY deploy/caddy/Caddyfile /etc/caddy/Caddyfile
COPY --from=frontend /app/dist /srv

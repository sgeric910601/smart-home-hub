import ipaddress

import httpx

from app.core.errors import HubError

# Tailscale 只會從這兩段私有位址連入；其他來源（區網、本機）一律不得以 Tailscale 身分登入。
TAILNET = (ipaddress.ip_network("100.64.0.0/10"), ipaddress.ip_network("fd7a:115c:a1e0::/48"))


class TailscaleIdentity:
    """向本機 tailscaled 查詢連線來源的帳號與裝置，再依白名單決定角色。"""

    def __init__(self, settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self.transport = transport

    async def resolve(self, address: str):
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            raise HubError(403, "TAILSCALE_REQUIRED", "請透過 Tailscale 連線後再使用自動登入。") from None
        if getattr(ip, "ipv4_mapped", None):
            ip = ip.ipv4_mapped
        if not any(ip in network for network in TAILNET):
            raise HubError(403, "TAILSCALE_REQUIRED", "請透過 Tailscale 連線後再使用自動登入。")
        transport = self.transport or httpx.AsyncHTTPTransport(uds=self.settings.hub_tailscale_socket)
        try:
            async with httpx.AsyncClient(
                transport=transport, base_url="http://local-tailscaled.sock", timeout=3
            ) as client:
                response = await client.get("/localapi/v0/whois", params={"addr": str(ip)})
        except httpx.HTTPError:
            raise HubError(503, "TAILSCALE_UNAVAILABLE", "主機目前無法查詢 Tailscale 身分。") from None
        if response.status_code != 200:
            raise HubError(403, "TAILSCALE_UNKNOWN", "無法確認這台裝置的 Tailscale 身分。")
        data = response.json()
        node, profile = data.get("Node") or {}, data.get("UserProfile") or {}
        # 標籤裝置（伺服器、共用裝置）不代表特定使用者，不自動授權。
        if node.get("Tags"):
            raise HubError(403, "TAILSCALE_TAGGED", "Tailscale 標籤裝置不能自動登入，請改用密碼。")
        login = str(profile.get("LoginName") or "").lower()
        if login in self.settings.hub_tailscale_admins:
            role = "admin"
        elif login in self.settings.hub_tailscale_viewers:
            role = "viewer"
        else:
            raise HubError(403, "TAILSCALE_NOT_ALLOWED", "這個 Tailscale 帳號尚未獲准使用平台。")
        device = str(node.get("ComputedName") or str(node.get("Name") or "").split(".")[0])
        return {"login": login, "device": device, "role": role}

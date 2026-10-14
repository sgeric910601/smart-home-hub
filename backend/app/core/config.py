from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


def logins(items: list[str]):
    # Tailscale 登入名稱不分大小寫，統一小寫後比對。
    return [item.strip().lower() for item in items if item.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    hub_mode: Literal["mock", "real"] = "mock"
    hub_admin_password: SecretStr
    hub_session_secret: SecretStr
    hub_viewer_password: SecretStr = SecretStr("")
    hub_database_url: str = "sqlite:///./data/hub.db"
    hub_secure_cookie: bool = False
    # 私人網域的完整 HTTPS Origin，例如 https://hub.example.com；設定後自動允許此來源並只發安全 Cookie。
    hub_public_origin: str = ""
    hub_session_hours: int = Field(8, ge=1, le=720)
    # Tailscale 身分登入：白名單內的 Tailscale 帳號免密碼登入；未啟用時只接受密碼。
    hub_tailscale_auth: bool = False
    hub_tailscale_socket: str = "/var/run/tailscale/tailscaled.sock"
    hub_tailscale_admins: list[str] = []
    hub_tailscale_viewers: list[str] = []
    hub_serve_frontend: bool = False
    hub_mapping_file: str = ""
    hub_ble_diffuser_config: str = ""
    hub_allowed_origins: list[str] = [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://127.0.0.1:8080",
        "http://localhost:8080",
    ]
    ha_url: str = ""
    ha_browser_url: str = ""
    ha_token: SecretStr = SecretStr("")

    @model_validator(mode="after")
    def validate_secrets(self):
        if self.ha_browser_url:
            from app.services.onboarding import browser_url

            browser_url(self.ha_browser_url)
        if len(self.hub_admin_password.get_secret_value()) < 12:
            raise ValueError("平台密碼至少需要 12 個字元")
        if len(self.hub_session_secret.get_secret_value()) < 32:
            raise ValueError("Session 密鑰至少需要 32 個字元")
        if not self.hub_database_url.startswith("sqlite:///"):
            raise ValueError("本版僅支援 SQLite")
        if self.hub_public_origin:
            parsed = urlparse(self.hub_public_origin)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.path not in {"", "/"}
                or parsed.params
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("HUB_PUBLIC_ORIGIN 需為不含路徑的 HTTPS 網址，例如 https://hub.example.com")
            # 瀏覽器送出的 Origin 不含預設 443 埠，統一成相同格式再比對。
            port = f":{parsed.port}" if parsed.port not in {None, 443} else ""
            origin = f"https://{parsed.hostname}{port}"
            self.hub_public_origin = origin
            if origin not in self.hub_allowed_origins:
                self.hub_allowed_origins = [*self.hub_allowed_origins, origin]
            self.hub_secure_cookie = True
        self.hub_tailscale_admins = logins(self.hub_tailscale_admins)
        self.hub_tailscale_viewers = logins(self.hub_tailscale_viewers)
        if self.hub_tailscale_auth and not (self.hub_tailscale_admins or self.hub_tailscale_viewers):
            raise ValueError("啟用 Tailscale 登入時，需列出 HUB_TAILSCALE_ADMINS 或 HUB_TAILSCALE_VIEWERS")
        if self.hub_mode == "real":
            parsed = urlparse(self.ha_url)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
                or not self.ha_token.get_secret_value()
            ):
                raise ValueError("Real Mode 需要合法 HA URL 與 Token")
        return self

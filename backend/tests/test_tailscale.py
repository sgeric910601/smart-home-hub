import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def peer(name, login, tags=None):
    return {"Node": {"ComputedName": name, "Tags": tags}, "UserProfile": {"LoginName": login}}


PEERS = {
    "100.101.1.1": peer("kuan-iphone", "Owner@Example.com"),
    "100.101.1.2": peer("family-ipad", "family@example.com"),
    "100.101.1.3": peer("guest-phone", "guest@example.com"),
    "100.101.1.4": peer("server", "tagged-devices", ["tag:server"]),
}


def fake_tailscaled(request: httpx.Request):
    assert request.url.path == "/localapi/v0/whois"
    match = PEERS.get(request.url.params["addr"])
    return httpx.Response(200, json=match) if match else httpx.Response(404, text="no match for IP")


def make_client(tmp_path, address, **overrides):
    settings = Settings(
        _env_file=None,
        hub_admin_password="test-password-long",
        hub_session_secret="s" * 40,
        hub_database_url=f"sqlite:///{tmp_path / 'tailscale.db'}",
        hub_tailscale_auth=True,
        hub_tailscale_admins=[" owner@example.com "],
        hub_tailscale_viewers=["family@example.com"],
        **overrides,
    )
    app = create_app(settings, tailscale_transport=httpx.MockTransport(fake_tailscaled))
    return TestClient(app, client=(address, 51000))


def test_owner_device_logs_in_without_password(tmp_path):
    with make_client(tmp_path, "100.101.1.1") as client:
        status = client.get("/api/auth/tailscale").json()
        assert status == {
            "enabled": True,
            "available": True,
            "login": "owner@example.com",
            "device": "kuan-iphone",
            "role": "admin",
        }
        result = client.post("/api/auth/tailscale", headers={"Origin": "http://127.0.0.1:8000"})
        assert result.status_code == 200
        assert result.json()["role"] == "admin"
        assert "httponly" in result.headers["set-cookie"].lower()
        assert client.get("/api/auth/me").json()["role"] == "admin"
        headers = {"X-CSRF-Token": result.json()["csrf_token"]}
        assert client.post("/api/auth/logout", headers=headers, json={}).status_code == 200
        assert client.get("/api/auth/me").status_code == 401


def test_viewer_list_grants_read_only_role(tmp_path):
    with make_client(tmp_path, "100.101.1.2") as client:
        result = client.post("/api/auth/tailscale")
        assert result.json()["role"] == "viewer"


@pytest.mark.parametrize(
    ("address", "code"),
    [
        ("100.101.1.3", "TAILSCALE_NOT_ALLOWED"),
        ("100.101.1.4", "TAILSCALE_TAGGED"),
        ("100.101.9.9", "TAILSCALE_UNKNOWN"),
        ("192.168.1.20", "TAILSCALE_REQUIRED"),
        ("127.0.0.1", "TAILSCALE_REQUIRED"),
    ],
)
def test_other_sources_cannot_log_in(tmp_path, address, code):
    with make_client(tmp_path, address) as client:
        result = client.post("/api/auth/tailscale")
        assert result.status_code == 403
        assert result.json()["error"]["code"] == code
        assert "set-cookie" not in result.headers
        assert client.get("/api/auth/tailscale").json()["available"] is False


def test_rejects_foreign_origin(tmp_path):
    with make_client(tmp_path, "100.101.1.1") as client:
        result = client.post("/api/auth/tailscale", headers={"Origin": "https://evil.example.com"})
        assert result.status_code == 403


def test_unreachable_tailscaled_is_reported(tmp_path):
    def broken(request):
        raise httpx.ConnectError("socket missing")

    settings = Settings(
        _env_file=None,
        hub_admin_password="test-password-long",
        hub_session_secret="s" * 40,
        hub_database_url=f"sqlite:///{tmp_path / 'broken.db'}",
        hub_tailscale_auth=True,
        hub_tailscale_admins=["owner@example.com"],
    )
    app = create_app(settings, tailscale_transport=httpx.MockTransport(broken))
    with TestClient(app, client=("100.101.1.1", 51000)) as client:
        assert client.post("/api/auth/tailscale").json()["error"]["code"] == "TAILSCALE_UNAVAILABLE"


def test_disabled_by_default_and_requires_allow_list(tmp_path):
    settings = Settings(
        _env_file=None,
        hub_admin_password="test-password-long",
        hub_session_secret="s" * 40,
        hub_database_url=f"sqlite:///{tmp_path / 'off.db'}",
    )
    with TestClient(create_app(settings), client=("100.101.1.1", 51000)) as client:
        assert client.get("/api/auth/tailscale").json() == {"enabled": False}
        assert client.post("/api/auth/tailscale").status_code == 404
    with pytest.raises(ValueError):
        Settings(
            _env_file=None,
            hub_admin_password="x" * 20,
            hub_session_secret="s" * 40,
            hub_tailscale_auth=True,
        )

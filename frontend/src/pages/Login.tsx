import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { House, ArrowRight, ShieldCheck, Network } from "lucide-react";
import { api } from "../services/api";
import { autoLoginAllowed, setAutoLogin } from "../services/deviceSession";
import type { Session, TailscaleStatus } from "../types/device";
export function Login({ onLogin }: { onLogin: (s: Session) => void }) {
  const [username, setUsername] = useState("admin"),
    [password, setPassword] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [tailscale, setTailscale] = useState<TailscaleStatus | null>(null),
    [checking, setChecking] = useState(autoLoginAllowed),
    started = useRef(false);
  const tailscaleLogin = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      setAutoLogin(true);
      onLogin(await api.tailscaleLogin());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Tailscale 登入失敗");
    } finally {
      setBusy(false);
    }
  }, [onLogin]);
  // 已加入 Tailscale 且獲准的裝置直接登入；主動登出過的裝置改為顯示按鈕，由使用者決定。
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    api
      .tailscaleStatus()
      .then(async (status) => {
        setTailscale(status);
        if (status.available && autoLoginAllowed()) await tailscaleLogin();
      })
      .catch(() => setTailscale(null))
      .finally(() => setChecking(false));
  }, [tailscaleLogin]);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      onLogin(await api.login(username, password));
      setPassword("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "登入失敗");
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="login-page">
      <div className="login-art">
        <div className="brand">
          <span>
            <House size={25} />
          </span>
          Smart Home Hub
        </div>
        <p className="eyebrow">A LITTLE CLOSER TO HOME</p>
        <h1>
          讓生活的節奏，
          <br />
          回到你的手中。
        </h1>
        <p>
          所有設備，一個熟悉的地方。
          <br />
          從這台電腦開始，打造屬於你的智慧家庭。
        </p>
        <div className="house-orbit">
          <House size={110} strokeWidth={0.8} />
          <span className="orbit o1" />
          <span className="orbit o2" />
          <span className="orbit o3" />
        </div>
        <div className="art-footer">
          <ShieldCheck size={17} /> 本機優先 · 安全存取 · 跨品牌整合
        </div>
      </div>
      <section className="login-form">
        <div>
          <p className="eyebrow">WELCOME HOME</p>
          <h2>歡迎回家</h2>
          <p>登入你的智慧家庭管理平台。</p>
          {checking ? (
            <p role="status" className="tailscale-note">
              正在確認這台裝置的 Tailscale 身分…
            </p>
          ) : (
            tailscale?.enabled &&
            (tailscale.available ? (
              <>
                <button
                  type="button"
                  className="primary tailscale-login"
                  disabled={busy}
                  onClick={() => void tailscaleLogin()}
                >
                  <Network size={18} />
                  <span>
                    以 Tailscale 身分登入
                    <small>
                      {tailscale.login} · {tailscale.device}
                    </small>
                  </span>
                </button>
                <p className="login-divider">或使用密碼</p>
              </>
            ) : (
              <p className="tailscale-note">{tailscale.message}</p>
            ))
          )}
          <form onSubmit={submit}>
            <label>
              帳號
              <input
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
              />
            </label>
            <label>
              密碼
              <input
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </label>
            {error && (
              <p role="alert" className="error">
                {error}
              </p>
            )}
            <button className="primary" disabled={busy}>
              {busy ? "登入中…" : "登入平台"}
              <ArrowRight size={18} />
            </button>
          </form>
          <p className="login-hint">
            首次測試請使用 <code>admin</code>。隨機產生的本機密碼位於專案根目錄{" "}
            <code>.env</code> 的 <code>HUB_ADMIN_PASSWORD</code>。
          </p>
          <div className="local-label">
            <span className="green-dot" /> 本機測試環境 · 不預設開放網際網路
          </div>
        </div>
      </section>
    </main>
  );
}

"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { requestCode, verifyCode } from "./server/auth-actions";

export function LoginForm({ next }: { next: string }) {
  const router = useRouter();
  const [step, setStep] = useState<"email" | "code">("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [consent, setConsent] = useState(false);

  async function onEmail(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const result = await requestCode({ email }).catch(() => ({ ok: false as const, error: "Error de conexión." }));
    setBusy(false);
    if (result.ok) setStep("code");
    else setError(result.error);
  }

  async function onCode(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const result = await verifyCode({ email, code }).catch(() => ({ ok: false as const, error: "Error de conexión." }));
    if (result.ok) {
      router.replace(next);
      router.refresh();
      return;
    }
    setBusy(false);
    setError(result.error);
  }

  if (step === "code") {
    return (
      <form className="esc-panel" onSubmit={onCode}>
        <h2 className="esc-panel-title">Revisa tu correo</h2>
        <p className="esc-note" style={{ margin: 0 }}>
          Te hemos enviado un código de 6 números a <strong>{email}</strong>.
        </p>
        <label className="esc-label">
          Código
          <input
            className="esc-input"
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            value={code}
            onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))}
            autoFocus
            style={{ fontSize: 24, letterSpacing: 6, fontWeight: 700 }}
          />
        </label>
        {error ? (
          <p className="esc-msg-error" role="alert">
            {error}
          </p>
        ) : null}
        <div className="esc-hero-ctas">
          <button className="esc-btn esc-btn-primary" type="submit" disabled={busy || code.length !== 6}>
            {busy ? "Comprobando…" : "Entrar"}
          </button>
          <button
            className="esc-btn esc-btn-ghost"
            type="button"
            onClick={() => {
              setStep("email");
              setCode("");
              setError(null);
            }}
          >
            Cambiar correo
          </button>
        </div>
      </form>
    );
  }

  return (
    <form className="esc-panel" onSubmit={onEmail}>
      <h2 className="esc-panel-title">Entra o crea tu cuenta</h2>
      <p className="esc-note" style={{ margin: 0 }}>
        Sin contraseñas: te mandamos un código al correo. Si es tu primera vez, te regalamos créditos para
        probar.
      </p>
      <label className="esc-label">
        Correo electrónico
        <input
          className="esc-input"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          autoFocus
          required
        />
      </label>
      <label className="esc-check">
        <input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} />
        <span>
          Acepto las <a href="/escaparate/legal">condiciones de uso y la política de privacidad</a>.
        </span>
      </label>
      {error ? (
        <p className="esc-msg-error" role="alert">
          {error}
        </p>
      ) : null}
      <div>
        <button className="esc-btn esc-btn-primary" type="submit" disabled={busy || !email || !consent}>
          {busy ? "Enviando…" : "Enviarme el código"}
        </button>
      </div>
    </form>
  );
}

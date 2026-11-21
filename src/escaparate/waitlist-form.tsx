"use client";

import { useState, type FormEvent } from "react";

import { joinWaitlist } from "./actions";
import { SECTORS } from "./content";

export function WaitlistForm() {
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError(null);
    const result = await joinWaitlist({
      email: form.get("email"),
      business: form.get("business"),
      sector: form.get("sector"),
      city: form.get("city"),
      consent: form.get("consent") === "on",
    }).catch(() => ({ ok: false as const, error: "No hemos podido enviar tu solicitud." }));
    setBusy(false);
    if (result.ok) setDone(true);
    else setError(result.error);
  }

  if (done) {
    return (
      <p className="esc-msg-ok" role="status">
        ¡Apuntado! Te escribiremos con las novedades.
      </p>
    );
  }

  return (
    <form className="esc-form" onSubmit={onSubmit} noValidate>
      <div className="esc-form-row">
        <label className="esc-label">
          Correo electrónico
          <input className="esc-input" name="email" type="email" required autoComplete="email" />
        </label>
        <label className="esc-label">
          Nombre de tu negocio
          <input className="esc-input" name="business" autoComplete="organization" />
        </label>
      </div>
      <div className="esc-form-row">
        <label className="esc-label">
          Sector
          <select className="esc-input" name="sector" defaultValue="">
            <option value="" disabled>
              Elige uno
            </option>
            {SECTORS.map((sector) => (
              <option key={sector.id} value={sector.id}>
                {sector.label}
              </option>
            ))}
          </select>
        </label>
        <label className="esc-label">
          Ciudad
          <input className="esc-input" name="city" autoComplete="address-level2" />
        </label>
      </div>
      <label className="esc-check">
        <input type="checkbox" name="consent" required />
        <span>
          Acepto que Escaparate me escriba sobre el lanzamiento. Puedo darme de baja cuando quiera.
        </span>
      </label>
      {error ? (
        <p className="esc-msg-error" role="alert">
          {error}
        </p>
      ) : null}
      <div>
        <button className="esc-btn esc-btn-primary" type="submit" disabled={busy}>
          {busy ? "Enviando…" : "Apuntarme"}
        </button>
      </div>
    </form>
  );
}

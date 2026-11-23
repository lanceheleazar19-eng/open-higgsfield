import { useState, type FormEvent } from "react";
import { api } from "../api/client";
import { useAsync } from "../api/useAsync";
import { Panel } from "./Panel";

function Connector({ name, title, connected, account, lastSync, userLabel, steps, onChange }: {
  name: "gmail" | "icloud"; title: string; connected: boolean; account: string | null; lastSync: string | null;
  userLabel: string; steps: React.ReactNode; onChange: () => void;
}) {
  const [user, setUser] = useState("");
  const [pwd, setPwd] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ tone: "pos" | "neg"; text: string } | null>(null);

  async function connect(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setMsg(null);
    try {
      await api.connectIntegration(name, user, pwd);
      setPwd(""); setMsg({ tone: "pos", text: "Conectado." }); onChange();
    } catch (err) { setMsg({ tone: "neg", text: (err as Error).message }); }
    finally { setBusy(false); }
  }

  return (
    <section className="connector">
      <h3>{title} {connected && <span className="badge live">Conectado</span>}</h3>
      {connected ? (
        <>
          <p className="small">Cuenta: <strong>{account}</strong>{lastSync ? ` · última sincronización ${new Date(lastSync).toLocaleString("es-ES")}` : ""}</p>
          <button className="mini-btn danger" onClick={async () => {
            if (!window.confirm(`¿Desconectar ${title}? Se borrarán las credenciales guardadas.`)) return;
            await api.disconnectIntegration(name); onChange();
          }}>Desconectar</button>
        </>
      ) : (
        <form className="form" onSubmit={connect}>
          <details className="help"><summary>Cómo obtener la contraseña de aplicación</summary>{steps}</details>
          <label><span>{userLabel}</span><input value={user} onChange={(e) => setUser(e.target.value)} autoComplete="username" /></label>
          <label><span>Contraseña de aplicación (no tu contraseña normal)</span>
            <input type="password" value={pwd} onChange={(e) => setPwd(e.target.value)} autoComplete="off" /></label>
          <div className="form-actions">
            <button className="btn" type="submit" disabled={busy || user.length < 3 || pwd.replace(/\s/g, "").length < 8}>{busy ? "Comprobando…" : "Conectar"}</button>
            {msg && <span role="status" className={`small ${msg.tone}`}>{msg.text}</span>}
          </div>
        </form>
      )}
    </section>
  );
}

/** Configuración › Integraciones. Las credenciales van al Llavero de macOS; solo lectura salvo crear eventos con confirmación. */
export function IntegrationsSettings() {
  const st = useAsync(api.integrations);
  const [syncing, setSyncing] = useState(false);
  const d = st.data;
  return (
    <Panel title="Integraciones" aside={d && (d.gmail.connected || d.icloud.connected) ? (
      <button className="mini-btn" disabled={syncing} onClick={async () => { setSyncing(true); try { await api.syncIntegrations(); await st.reload(); } finally { setSyncing(false); } }}>
        {syncing ? "Sincronizando…" : "Sincronizar ahora"}</button>) : undefined}>
      {!d ? <p className="muted">Cargando…</p> : (
        <div className="grid grid-2">
          <Connector name="gmail" title="Gmail" connected={d.gmail.connected} account={d.gmail.address} lastSync={d.gmail.last_sync}
            userLabel="Tu dirección de Gmail" onChange={() => void st.reload()} steps={
              <ol className="steps">
                <li>Activa la <strong>verificación en dos pasos</strong> en myaccount.google.com → Seguridad.</li>
                <li>Abre <strong>myaccount.google.com/apppasswords</strong>, escribe «ATLAS» y pulsa Crear.</li>
                <li>Copia la contraseña de 16 letras y pégala aquí.</li>
              </ol>} />
          <Connector name="icloud" title="Calendario de iCloud" connected={d.icloud.connected} account={d.icloud.user} lastSync={d.icloud.last_sync}
            userLabel="Tu Apple ID (correo)" onChange={() => void st.reload()} steps={
              <ol className="steps">
                <li>Entra en <strong>account.apple.com</strong> → Inicio de sesión y seguridad.</li>
                <li>Pulsa <strong>Contraseñas específicas de app</strong> → «+», escribe «ATLAS».</li>
                <li>Copia la contraseña (xxxx-xxxx-xxxx-xxxx) y pégala aquí.</li>
              </ol>} />
        </div>
      )}
      <p className="muted small">ATLAS solo lee tu correo (asunto, remitente y un extracto) para avisarte de lo importante; nunca envía ni borra. Las contraseñas se guardan en el Llavero de tu Mac. Se sincroniza cada 30 minutos mientras ATLAS está abierto.</p>
    </Panel>
  );
}

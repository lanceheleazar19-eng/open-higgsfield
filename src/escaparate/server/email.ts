import "server-only";

/** Sends the sign-in code. Uses Resend when RESEND_API_KEY is set; otherwise,
    in development (or with ESCAPARATE_LOG_LOGIN_CODES=1, for local testing of a
    production build) prints the code to the server log. Never set that flag in
    a real deployment. */
export async function sendLoginCode(email: string, code: string): Promise<void> {
  const apiKey = process.env.RESEND_API_KEY;
  if (!apiKey) {
    const logCodes = process.env.NODE_ENV !== "production" || process.env.ESCAPARATE_LOG_LOGIN_CODES === "1";
    if (!logCodes) throw new Error("Missing RESEND_API_KEY");
    console.info(`[escaparate] login code for ${email}: ${code}`);
    return;
  }

  const from = process.env.ESCAPARATE_EMAIL_FROM ?? "Escaparate <hola@escaparate.app>";
  const response = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      from,
      to: [email],
      subject: `Tu código de acceso: ${code}`,
      text: `Tu código para entrar en Escaparate es ${code}.\n\nCaduca en 10 minutos. Si no lo has pedido tú, ignora este correo.`,
      html: `<div style="font-family:system-ui,sans-serif;font-size:16px;color:#1f1a16">
  <p>Tu código para entrar en <strong>Escaparate</strong> es:</p>
  <p style="font-size:32px;font-weight:800;letter-spacing:6px">${code}</p>
  <p style="color:#5d544c">Caduca en 10 minutos. Si no lo has pedido tú, ignora este correo.</p>
</div>`,
    }),
  });
  if (!response.ok) throw new Error(`Email provider refused the message (${response.status})`);
}

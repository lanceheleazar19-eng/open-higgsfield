/** VISTAN LIFE OS — cliente. Las rutas privadas devuelven 423 si hay PIN y este navegador no lo ha introducido. */
import { ApiError } from "./client";

export class LockedError extends Error {
  constructor() { super("LIFE OS bloqueado"); }
}

type Json = Record<string, unknown>;
export type Row = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any

async function call<T = Row>(path: string, method = "GET", body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api/life${path}`, { method, headers: { "Content-Type": "application/json" }, credentials: "same-origin",
      body: body === undefined ? undefined : JSON.stringify(body) });
  } catch {
    throw new ApiError(0, "No se puede conectar con el núcleo de VISTAN");
  }
  const data = await res.json().catch(() => ({}));
  if (res.status === 423) {
    window.dispatchEvent(new Event("vistan-life-locked"));
    throw new LockedError();
  }
  if (!res.ok) {
    const d = (data as Json).detail;
    const msg = typeof d === "string" ? d : Array.isArray(d) ? d.map((x: Json) => `${(x.loc as string[])?.slice(-1)[0] ?? ""}: ${x.msg}`).join("; ") : `Error ${res.status}`;
    throw new ApiError(res.status, msg);
  }
  return data as T;
}

export const life = {
  get: <T = Row>(p: string) => call<T>(p),
  post: <T = Row>(p: string, b?: unknown) => call<T>(p, "POST", b ?? {}),
  put: <T = Row>(p: string, b: unknown) => call<T>(p, "PUT", b),
  patch: <T = Row>(p: string, b: unknown) => call<T>(p, "PATCH", b),
  del: <T = Row>(p: string, b?: unknown) => call<T>(p, "DELETE", b),
};

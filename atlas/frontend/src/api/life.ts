/** VISTAN LIFE OS — cliente. Las rutas privadas devuelven 423 si hay PIN y este navegador no lo ha introducido. */
import { ApiError } from "./client";

export class LockedError extends Error {
  constructor() { super("LIFE OS bloqueado"); }
}

type Json = Record<string, unknown>;
export type Row = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any

async function call<T = Row>(path: string, method = "GET", body?: unknown, prefix = "/api/life"): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${prefix}${path}`, { method, headers: { "Content-Type": "application/json" }, credentials: "same-origin",
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

export interface Client {
  get: <T = Row>(p: string) => Promise<T>;
  post: <T = Row>(p: string, b?: unknown) => Promise<T>;
  put: <T = Row>(p: string, b: unknown) => Promise<T>;
  patch: <T = Row>(p: string, b: unknown) => Promise<T>;
  del: <T = Row>(p: string, b?: unknown) => Promise<T>;
}

export function makeClient(prefix: string): Client {
  return {
    get: <T = Row>(p: string) => call<T>(p, "GET", undefined, prefix),
    post: <T = Row>(p: string, b?: unknown) => call<T>(p, "POST", b ?? {}, prefix),
    put: <T = Row>(p: string, b: unknown) => call<T>(p, "PUT", b, prefix),
    patch: <T = Row>(p: string, b: unknown) => call<T>(p, "PATCH", b, prefix),
    del: <T = Row>(p: string, b?: unknown) => call<T>(p, "DELETE", b, prefix),
  };
}

export const life = makeClient("/api/life");
export const lab = makeClient("/api/lab");

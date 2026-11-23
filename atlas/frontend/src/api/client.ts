import type { Dashboard, Health, ModuleInfo, Prefs } from "./types";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(0, "No se puede conectar con el núcleo de ATLAS");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* respuesta sin JSON */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<Health>("/api/system/health"),
  modules: () => request<ModuleInfo[]>("/api/system/modules"),
  dashboard: () => request<Dashboard>("/api/dashboard"),
  prefs: () => request<Prefs>("/api/settings"),
  updatePrefs: (p: Partial<Prefs>) => request<Prefs>("/api/settings", { method: "PUT", body: JSON.stringify(p) }),
  timezones: () => request<string[]>("/api/settings/timezones"),
};

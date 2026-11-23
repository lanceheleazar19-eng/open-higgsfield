import { createContext, useContext, type ReactNode } from "react";
import { api } from "../api/client";
import type { Health, ModuleInfo, Prefs } from "../api/types";
import { useAsync } from "../api/useAsync";

interface AtlasCtx {
  health: Health | null;
  healthError: Error | null;
  modules: ModuleInfo[];
  prefs: Prefs | null;
  reloadPrefs: () => Promise<void>;
}

const Ctx = createContext<AtlasCtx | null>(null);

export function AtlasProvider({ children }: { children: ReactNode }) {
  const health = useAsync(api.health, 30_000);
  const modules = useAsync(api.modules);
  const prefs = useAsync(api.prefs);
  return (
    <Ctx.Provider
      value={{
        health: health.data,
        healthError: health.error,
        modules: modules.data ?? [],
        prefs: prefs.data,
        reloadPrefs: prefs.reload,
      }}
    >
      {children}
    </Ctx.Provider>
  );
}

export function useAtlas(): AtlasCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAtlas fuera de AtlasProvider");
  return c;
}

import { api } from "../api/client";
import type { Profile } from "../api/types";

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "A";
  return (parts[0][0] + (parts[1]?.[0] ?? "")).toUpperCase();
}

/** Foto de perfil (local) o iniciales. */
export function Avatar({ profile, size = 44, src }: { profile: Profile | null; size?: number; src?: string | null }) {
  const url = src ?? (profile?.has_avatar ? api.avatarUrl(profile.avatar_version) : null);
  return (
    <span className="avatar" style={{ width: size, height: size, fontSize: size * 0.38 }}>
      {url ? <img src={url} alt="" width={size} height={size} /> : <span aria-hidden="true">{initials(profile?.display_name ?? "")}</span>}
    </span>
  );
}

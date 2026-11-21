import "server-only";

import { put } from "@vercel/blob";

const MAX_BYTES = 80 * 1024 * 1024;

/** Copies a finished result off the generation platform's CDN, whose links
    expire, into our own Blob store so the shop's gallery keeps working.
    Returns the permanent URL, or null to keep using the platform's link. */
export async function persistResult(sourceUrl: string, userId: string, requestId: string, kind: "image" | "video") {
  const token = process.env.OPEN_HIGGSFIELD_READ_WRITE_TOKEN;
  if (!token) return null;
  try {
    const response = await fetch(sourceUrl, { signal: AbortSignal.timeout(30_000) });
    if (!response.ok) return null;
    const contentType = response.headers.get("content-type") ?? (kind === "video" ? "video/mp4" : "image/png");
    const length = Number(response.headers.get("content-length") ?? 0);
    if (length > MAX_BYTES) return null;
    const ext = extensionFor(contentType, kind);
    const blob = await put(`escaparate/resultados/${userId}/${requestId}.${ext}`, await response.arrayBuffer(), {
      access: "public",
      contentType,
      token,
      addRandomSuffix: true,
    });
    return blob.url;
  } catch (caught) {
    console.error("[escaparate] could not persist result", caught instanceof Error ? caught.message : caught);
    return null;
  }
}

function extensionFor(contentType: string, kind: "image" | "video"): string {
  if (contentType.includes("jpeg")) return "jpg";
  if (contentType.includes("webp")) return "webp";
  if (contentType.includes("png")) return "png";
  if (contentType.includes("mp4")) return "mp4";
  return kind === "video" ? "mp4" : "png";
}

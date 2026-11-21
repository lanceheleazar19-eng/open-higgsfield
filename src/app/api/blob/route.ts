import { handleUpload, type HandleUploadBody } from "@vercel/blob/client";
import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { safeCurrentUser } from "@/escaparate/server/viewer";
import { PLATFORM_KEY_COOKIE, decodeCredentials } from "@/generation/credentials";
import {
  DEVICE_COOKIE,
  DEVICE_COOKIE_OPTIONS,
  blobPathname,
  resolveDeviceId,
} from "@/generation/device";

/* Uploads cost storage, so a token is issued only to someone who can use the
   result: a studio visitor holding a platform key, or a signed-in Escaparate
   shop (images only, 15 MB). The upload-completed callback comes from Vercel
   itself and is verified by handleUpload. */
const SHOP_MAX_BYTES = 15 * 1024 * 1024;
const SHOP_TYPES = ["image/jpeg", "image/png", "image/webp"];

export async function POST(request: Request): Promise<NextResponse> {
  const incoming = (await request.json()) as HandleUploadBody;
  let uploader: "studio" | "shop" | null = null;
  if (incoming.type === "blob.generate-client-token") {
    uploader = await resolveUploader();
    if (!uploader) return NextResponse.json({ error: "Inicia sesión para subir archivos." }, { status: 401 });
  }
  const device =
    incoming.type === "blob.generate-client-token" ? await readDeviceId() : null;
  const body = device ? withDevicePath(incoming, device.deviceId) : incoming;
  console.info("[blob] upload", summarizeBlobEvent(body));

  try {
    const token = process.env.OPEN_HIGGSFIELD_READ_WRITE_TOKEN;
    if (!token) throw new Error("Missing OPEN_HIGGSFIELD_READ_WRITE_TOKEN");
    const json = await handleUpload({
      body,
      request,
      token,
      onBeforeGenerateToken: async (pathname) => {
        console.info("[blob] token", { pathname, uploader });
        if (uploader === "shop") {
          return { allowedContentTypes: SHOP_TYPES, maximumSizeInBytes: SHOP_MAX_BYTES, addRandomSuffix: true };
        }
        return {
          allowedContentTypes: [
            "image/jpeg",
            "image/png",
            "image/webp",
            "image/gif",
            "video/mp4",
            "audio/wav",
            "audio/x-wav",
          ],
          addRandomSuffix: true,
        };
      },
    });
    return withDeviceCookie(
      json.type === "blob.generate-client-token" && body.type === "blob.generate-client-token"
        ? NextResponse.json({ ...json, pathname: body.payload.pathname })
        : NextResponse.json(json),
      device,
    );
  } catch (error) {
    console.error("[blob] upload failed", error instanceof Error ? error.message : error);
    if (device?.minted) return withDeviceCookie(new NextResponse(null, { status: 500 }), device);
    throw error;
  }
}

async function resolveUploader(): Promise<"studio" | "shop" | null> {
  const jar = await cookies();
  if (decodeCredentials(jar.get(PLATFORM_KEY_COOKIE)?.value)) return "studio";
  return (await safeCurrentUser()) ? "shop" : null;
}

async function readDeviceId() {
  const jar = await cookies();
  return resolveDeviceId(jar.get(DEVICE_COOKIE)?.value);
}

function withDeviceCookie(
  response: NextResponse,
  device: { deviceId: string; minted: boolean } | null,
) {
  if (device?.minted) response.cookies.set(DEVICE_COOKIE, device.deviceId, DEVICE_COOKIE_OPTIONS);
  return response;
}

function withDevicePath(body: HandleUploadBody, deviceId: string): HandleUploadBody {
  if (body.type !== "blob.generate-client-token") return body;
  return {
    ...body,
    payload: { ...body.payload, pathname: blobPathname(deviceId, body.payload.pathname) },
  };
}

function summarizeBlobEvent(body: HandleUploadBody) {
  if (body.type === "blob.generate-client-token") {
    return { type: body.type, pathname: body.payload.pathname };
  }
  return { type: body.type, url: body.payload.blob.url };
}

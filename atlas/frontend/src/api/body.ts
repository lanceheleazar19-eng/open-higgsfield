/** VISTAN · fotos de físico, comidas con foto, asesor nutricional y Progress. */
import { ApiError, request, requestEmpty } from "./client";
import type { MealEntryItem } from "./types";

export interface VisionRoute { provider: string; label: string; model: string | null; local: boolean; available: boolean; note: string | null }
export interface BodyPhotoItem { id: number; taken_on: string; pose: string; pose_es: string; note: string | null; width: number; height: number; url: string; thumb: string }
export interface PhysiqueResult {
  fiabilidad: "alta" | "media" | "baja"; motivos_fiabilidad: string[]; observaciones: string[]; mas_desarrollados: string[];
  a_trabajar: string[]; simetria: string; cambios: string[]; recomendaciones_entrenamiento: string[]; habitos: string[];
  relacion_con_datos: string; omitidos: number; aviso: string;
}
export interface AnalysisItem<R = Record<string, unknown>> { id: number; kind: string; refs: number[]; result: R; model: string | null; provider: string | null; created_at: string }
export interface MealItemEst {
  name: string; detected: string; food_id: number | null; grams: number; preparation: string | null; confidence: string;
  source: string; kcal: number; protein: number; carbs: number; fat: number;
}
export interface MealAnalysis {
  is_food: boolean; items: MealItemEst[]; totals: { kcal: number; protein: number; carbs: number; fat: number };
  quality: string | null; quality_note: string | null; questions: string[]; description: string | null; disclaimer: string;
}
export interface MealPhotoItem {
  id: number; eaten_at: string; meal: string; description: string | null; status: string; analysis: MealAnalysis | null;
  model: string | null; error: string | null; entries: MealEntryItem[]; url: string; thumb: string;
  needs_consent?: { provider: string; model: string; message: string };
}
export interface Trend { status: "subiendo" | "bajando" | "estable" | "insuficiente"; points: number; reason?: string; days?: number; per_week?: number; change?: number; noise?: number; first?: number; last?: number; unit?: string }
export interface ProgressData {
  weights: { date: string; kg: number }[]; weight_trend: Trend;
  training_weeks: { week: string; sessions: number; tonnage: number }[]; sessions_trend: Trend; tonnage_trend: Trend;
  nutrition_days: { date: string; kcal: number; protein: number }[]; targets: { kcal: number; protein: number } | null; kcal_trend: Trend;
  protein_days_met: number; goals: { id: number; title: string; pace?: string; progress_pct?: number | null }[];
  photos: { id: number; date: string; pose: string; note: string | null }[]; weeks_trained: number; facts: string[];
}

export class ConsentError extends Error {
  constructor(public provider: string, public model: string, message: string) { super(message); }
}

async function upload<T>(path: string, file: File, fields: Record<string, string | undefined>): Promise<T> {
  const fd = new FormData();
  fd.append("file", file);
  Object.entries(fields).forEach(([k, v]) => { if (v !== undefined && v !== "") fd.append(k, v); });
  let res: Response;
  try { res = await fetch(path, { method: "POST", body: fd }); } catch { throw new ApiError(0, "No se puede conectar con el núcleo de VISTAN"); }
  if (!res.ok) { let d = res.statusText; try { d = (await res.json()).detail; } catch { /* */ } throw new ApiError(res.status, String(d)); }
  return res.json();
}

/** Como request, pero convierte el 409 de consentimiento en ConsentError para preguntar al usuario. */
async function withConsent<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
    .catch(() => { throw new ApiError(0, "No se puede conectar con el núcleo de VISTAN"); });
  if (res.status === 409) {
    const d = (await res.json()).detail;
    if (d?.needs_consent) throw new ConsentError(d.provider, d.model, d.message);
  }
  if (!res.ok) { let d = res.statusText; try { d = (await res.json()).detail; } catch { /* */ } throw new ApiError(res.status, typeof d === "string" ? d : JSON.stringify(d)); }
  return res.json();
}

/** Ejecuta un análisis; si la imagen saldría a un proveedor externo, pide permiso explícito y repite. */
export async function askingConsent<T>(run: (allowCloud: boolean) => Promise<T>): Promise<T | null> {
  try { return await run(false); } catch (e) {
    if (!(e instanceof ConsentError)) throw e;
    const ok = window.confirm(`Para este análisis la foto se enviaría a ${e.provider} (${e.model}), fuera de tu ordenador.\n\n¿Lo autorizas solo para esta vez?`);
    return ok ? run(true) : null;
  }
}

export const body = {
  visionRoute: () => request<VisionRoute>("/api/vision/route"),
  photos: () => request<BodyPhotoItem[]>("/api/progress/photos"),
  uploadPhoto: (f: File, taken_on?: string, pose?: string, note?: string) => upload<BodyPhotoItem>("/api/progress/photos", f, { taken_on, pose, note }),
  patchPhoto: (id: number, p: Partial<Pick<BodyPhotoItem, "taken_on" | "pose" | "note">>) => request<BodyPhotoItem>(`/api/progress/photos/${id}`, { method: "PATCH", body: JSON.stringify(p) }),
  deletePhoto: (id: number) => requestEmpty(`/api/progress/photos/${id}`, { method: "DELETE" }),
  analyzePhotos: (photo_ids: number[], allow_cloud = false) => withConsent<AnalysisItem<PhysiqueResult>>("/api/progress/photos/analyze", { photo_ids, allow_cloud }),
  analyses: <R = Record<string, unknown>>(kind: string) => request<AnalysisItem<R>[]>(`/api/progress/analyses?kind=${kind}`),
  deleteAnalysis: (id: number) => requestEmpty(`/api/progress/analyses/${id}`, { method: "DELETE" }),

  meals: (meal?: string, days = 60) => request<MealPhotoItem[]>(`/api/meals/photos?days=${days}${meal ? `&meal=${meal}` : ""}`),
  uploadMeal: (f: File, fields: { meal?: string; eaten_at?: string; description?: string; allow_cloud?: boolean }) =>
    upload<MealPhotoItem>("/api/meals/photos", f, { meal: fields.meal, eaten_at: fields.eaten_at, description: fields.description, allow_cloud: fields.allow_cloud ? "true" : undefined }),
  analyzeMeal: (id: number, description: string | null, allow_cloud = false) => withConsent<MealPhotoItem>(`/api/meals/photos/${id}/analyze`, { description, allow_cloud }),
  logMeal: (id: number, items: { name: string; grams: number; food_id: number | null; kcal: number; protein: number; carbs: number; fat: number }[]) =>
    request<MealPhotoItem>(`/api/meals/photos/${id}/log`, { method: "POST", body: JSON.stringify({ items }) }),
  patchMeal: (id: number, p: { meal?: string; eaten_at?: string; description?: string | null }) => request<MealPhotoItem>(`/api/meals/photos/${id}`, { method: "PATCH", body: JSON.stringify(p) }),
  deleteMeal: (id: number, withEntries = true) => requestEmpty(`/api/meals/photos/${id}?with_entries=${withEntries}`, { method: "DELETE" }),
  nutritionAdvice: () => request<AnalysisItem<{ advice: Record<string, unknown>; data: Record<string, unknown>; mode: string }>>("/api/nutrition/advice", { method: "POST" }),

  progress: () => request<ProgressData>("/api/progress"),
  progressSummary: () => request<AnalysisItem<{ resumen: string; tendencias: string[]; variaciones_puntuales: string[]; conexiones: string[]; recomendaciones: string[]; faltan_datos: string[]; mode: string; facts: string[] }>>("/api/progress/summary", { method: "POST" }),
};

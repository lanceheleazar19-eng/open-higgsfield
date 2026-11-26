import type { MemoryAccess, MemoryKind } from "../api/types";

export const KIND_LABEL: Record<MemoryKind, string> = {
  preference: "Preferencia",
  goal: "Objetivo",
  decision: "Decisión",
  fact: "Dato",
  note: "Nota",
  procedure: "Procedimiento",
  episode: "Episodio",
};

export const ACCESS_LABEL: Record<MemoryAccess, string> = {
  all: "Cualquier modelo",
  local: "Solo modelos locales",
  private: "Privado (nunca a la IA)",
};

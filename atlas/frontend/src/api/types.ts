export type Priority = "low" | "medium" | "high" | "critical";

export interface Health {
  status: "online" | "degraded";
  version: string;
  database: { ok: boolean; engine: string };
  ai: { configured: boolean; provider: string | null; note: string };
  python: string;
  storage: { db_bytes: number; disk_free_bytes: number; disk_total_bytes: number; records: number } | null;
}

export interface Alert {
  level: "critical" | "warning" | "info";
  module: string;
  text: string;
}

export interface AssistantReply {
  intent: string;
  reply: string;
  mode: "local" | "ai";
}

export interface ModuleInfo {
  id: string;
  name: string;
  phase: number;
  status: "active" | "planned";
  summary: string;
  planned: string[];
}

export interface Prefs {
  user_name: string;
  timezone: string;
  currency: string;
}

export interface Dashboard {
  generated_at: string;
  greeting: { name: string; part_of_day: "morning" | "afternoon" | "night"; timezone: string };
  summary: {
    pending_tasks: number;
    overdue_tasks: number;
    upcoming_events: number;
    active_projects: number;
    sessions_7d: number;
  };
  tasks: {
    pending: number;
    overdue: number;
    due_today: number;
    items: { id: number; title: string; priority: Priority; status: string; due_at: string | null; overdue: boolean }[];
  };
  events: {
    items: { id: number; title: string; location: string | null; start_at: string; end_at: string | null; in_progress: boolean }[];
  };
  finance: {
    has_data: boolean;
    currency: string;
    month: string;
    income_cents: number;
    expense_cents: number;
    net_cents: number;
    balance_cents: number;
    top_expense_categories: { category: string; amount_cents: number }[];
  };
  fitness: {
    sessions_7d: number;
    minutes_7d: number;
    days: { date: string; sessions: number }[];
    last_session: { date: string; routine: string | null; duration_min: number | null } | null;
  };
  projects: {
    active: number;
    items: { id: number; name: string; description: string | null; open_tasks: number }[];
  };
  activity: {
    items: { id: number; module: string; action: string; summary: string; created_at: string }[];
  };
  alerts: Alert[];
}

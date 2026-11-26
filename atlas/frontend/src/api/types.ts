export type Priority = "low" | "medium" | "high" | "critical";

export interface Health {
  status: "online" | "degraded";
  version: string;
  database: { ok: boolean; engine: string };
  ai: { configured: boolean; provider: string | null; model: string | null; models_installed: number; note: string };
  python: string;
  storage: {
    db_bytes: number; disk_free_bytes: number; disk_total_bytes: number; records: number;
    memories: number; conversations: number;
  } | null;
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
  ai_model: string;
}

export interface AiStatus {
  provider: string;
  url: string | null;
  reachable: boolean;
  models: { name: string; size_bytes: number; parameter_size: string | null; family: string | null }[];
  model: string | null;
  preferred: string | null;
  configured: boolean;
  error: string | null;
  note: string | null;
}

export type MemoryKind = "preference" | "goal" | "decision" | "fact" | "note" | "procedure" | "episode";
export type MemoryAccess = "all" | "local" | "private";

export interface MemoryItem {
  id: number;
  content: string;
  kind: MemoryKind;
  permanent: boolean;
  expires_at: string | null;
  expired: boolean;
  project_id: number | null;
  source: "manual" | "chat" | "suggested";
  access?: MemoryAccess;
  superseded_by?: number | null;
  created_at: string;
  updated_at: string;
}

export interface MemorySuggestion {
  content: string;
  kind: MemoryKind;
  temporary: boolean;
}

export interface ConversationSummary {
  id: number;
  title: string;
  messages: number;
  created_at: string;
  updated_at: string;
}

export interface StoredMessage {
  id: number;
  conversation_id: number;
  role: "user" | "assistant";
  content: string;
  mode: "ai" | "local" | null;
  model: string | null;
  created_at: string;
}

export type ChatEvent =
  | { type: "meta"; conversation_id: number }
  | { type: "memory"; action: "saved" | "duplicate" | "forget_candidate"; memory: MemoryItem }
  | { type: "task"; action: "created" | "complete_candidate" | "not_found"; task: TaskItem | null }
  | { type: "gym"; action: "logged"; session: GymSession }
  | { type: "meal"; action: "logged" | "not_found"; entries: MealEntryItem[]; missing: string[] }
  | { type: "finance"; action: "logged"; transaction: TxItem }
  | { type: "agents"; run: import("./v4").AgentRunItem }
  | { type: "sources"; items: { n: number; document_id: number; title: string; chunk: number; url: string | null; kind: string }[] }
  | { type: "research"; research: import("./v4").ResearchItem }
  | { type: "status"; state: "thinking"; model: string }
  | { type: "delta"; text: string }
  | { type: "done"; mode: "ai" | "local" | "memory" | "tasks" | "gym" | "nutrition" | "finance" | "research"; model: string | null; reason?: string | null; provider?: string }
  | { type: "error"; message: string };

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface Dashboard {
  trading?: { open: number; closed: number; pnl: number };
  generated_at: string;
  greeting: { name: string; custom?: string; part_of_day: "morning" | "afternoon" | "night"; timezone: string };
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
    items: { id: number; title: string; priority: Priority; status: string; due_at: string | null; all_day?: boolean; overdue: boolean }[];
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
    series?: { date: string; net_cents: number }[];
    budgets?: BudgetItem[];
  };
  fitness: {
    today_routine?: string | null;
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
  goals?: { items: DashGoal[] };
}

export type Pace = "ahead" | "on_track" | "behind" | "overdue" | "achieved" | "no_deadline" | "not_started";

export interface DashGoal {
  id: number; title: string; unit: string | null; kind: "numeric" | "milestones"; progress: number | null;
  pace: Pace; deadline: string | null; current: number; target: number | null; required_per_week?: number | null;
}

export interface TaskItem {
  id: number;
  title: string;
  description: string | null;
  priority: Priority;
  status: "pending" | "in_progress" | "done" | "cancelled";
  category: string | null;
  due_at: string | null;
  due_date: string | null;
  all_day: boolean;
  overdue: boolean;
  reminder_at: string | null;
  goal_id: number | null;
  goal_title: string | null;
  project_id: number | null;
  project_name: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface GoalMetrics {
  progress: number | null; current: number; target: number | null; start: number; elapsed_days: number;
  pace?: Pace; remaining?: number | null; rate_per_week?: number; projected_date?: string; days_left?: number;
  expected_progress?: number; required_per_week?: number;
}

export interface GoalItem {
  id: number; title: string; description: string | null; area: string | null; kind: "numeric" | "milestones";
  unit: string | null; start_value: number; target_value: number | null; current_value: number;
  start_date: string; deadline: string | null; status: "active" | "achieved" | "paused" | "abandoned";
  tasks_total: number; tasks_done: number; achieved_at: string | null; metrics: GoalMetrics;
  auto_metric?: "exercise_weight" | "exercise_e1rm" | "exercise_reps" | "workout_count" | null; auto_exercise_id?: number | null;
  history?: { id: number; value: number; note: string | null; recorded_at: string }[];
}

export interface PlanTask { id: number; title: string; priority: Priority; pinned: boolean; overdue: boolean; all_day: boolean; time: string | null }
export interface WeekPlan {
  days: { date: string; tasks: PlanTask[]; load: number; over_capacity: boolean }[];
  if_time: PlanTask[]; later: PlanTask[]; per_day: number;
}
export interface TaskSummary {
  period: "day" | "week"; from: string; to: string; completed: number; completed_titles: string[];
  created: number; due: number; due_open: number; overdue: number; completion_rate: number | null;
}

export interface GymExercise {
  id: number; name: string; muscle: string; muscle_label: string; secondary: string[]; equipment: string | null;
  per_side: boolean; aliases: string[]; custom: boolean;
}
export interface RoutineItem {
  id: number; exercise_id: number; name: string; muscle: string; per_side: boolean; position: number; warmup_sets: number;
  sets: number; reps_min: number; reps_max: number | null; weight: number | null; notes: string | null;
  done?: boolean; last?: { date: string; sets: { reps: number; weight: number; rir: number | null }[]; top: { reps: number; weight: number } } | null;
}
export interface RoutineData { id: number; name: string; weekday: number | null; weekday_name: string | null; notes: string | null; active: boolean; exercises: RoutineItem[] }
export interface RoutineTemplate { id: string; name: string; description: string | null; days: { name: string; weekday: number | null }[] }
export interface GymSet { id: number; set_number: number; reps: number; weight: number; rir: number | null; warmup: boolean; e1rm: number | null }
export interface GymSession {
  id: number; date: string; routine_name: string | null; routine_id: number | null; duration_min: number | null; notes: string | null;
  exercises: { exercise_id: number; name: string; muscle: string; per_side: boolean; sets: GymSet[] }[];
  working_sets: number; tonnage: number;
}
export interface GymToday {
  date: string; weekday_name: string; rest_day: boolean; routine: RoutineData | null; session_id: number | null;
  session?: GymSession; next: { name: string; date: string; weekday_name: string } | null;
}
export interface ProgressPoint { date: string; e1rm: number; top_weight: number; top_reps: number; sets: number; volume: number }
export interface GymProgress {
  exercise: { id: number; name: string; per_side: boolean }; points: ProgressPoint[]; sessions: number;
  change_e1rm?: number; change_pct?: number | null; change_top_weight?: number; since?: string; best: ProgressPoint | null; stagnant: boolean;
}
export interface MuscleVolume { muscle: string; label: string; sets: number; frequency: number; status: "sin trabajar" | "bajo" | "óptimo" | "alto" }
export interface GymVolume { from: string; to: string; muscles: MuscleVolume[]; reference: { min: number; max: number } }
export interface GymInsights {
  stagnations: { exercise_id: number; name: string; sessions: number; best_e1rm: number | null }[];
  undertrained: MuscleVolume[];
  compare: { current: string; previous: string; tonnage_delta: number; exercises: { name: string; now: GymSet; before: GymSet; delta_e1rm: number }[] } | null;
}
export interface BodyEntry {
  id: number; measured_on: string; weight_kg: number | null; body_fat_pct: number | null; waist_cm: number | null;
  chest_cm: number | null; arm_cm: number | null; thigh_cm: number | null; notes: string | null;
}
export interface ParsedLog { exercise_id: number; name: string; reps: number[]; weight: number | null; rir: number | null; warmup_sets: number; per_side: boolean; notes: string[] }

export interface Profile {
  display_name: string; username: string; preferences: string; greeting?: string; created_at: string;
  has_avatar: boolean; avatar_version: number | null;
}
export interface SystemMetrics { cpu_percent: number; ram_percent: number; ram_used_bytes: number; ram_total_bytes: number }

export interface Macros { kcal: number; protein: number; carbs: number; fat: number }
export interface NutritionProfile {
  sex: "male" | "female"; age: number; height_cm: number; weight_kg: number | null; activity: number;
  goal: "bulk" | "cut" | "maintain"; target_weight_kg: number | null; protein_per_kg: number;
}
export interface NutritionTargets extends Macros { bmr: number; tdee: number; weight_used: number }
export interface FoodItem { id: number; name: string; kcal: number; protein: number; carbs: number; fat: number; unit_name: string; unit_grams: number; custom: boolean }
export interface MealProposal { food: FoodItem | null; grams: number | null; text: string; kcal?: number; protein?: number; carbs?: number; fat?: number }
export interface MealEntryItem extends Macros { id: number; date: string; meal: string; food_id: number | null; name: string; grams: number; source: string }
export interface NutritionDay { date: string; entries: MealEntryItem[]; totals: Macros; targets: NutritionTargets | null; tips: string[]; suggested_meal: string }

export interface Integrations {
  gmail: { connected: boolean; address: string | null; last_sync: string | null };
  icloud: { connected: boolean; user: string | null; last_sync: string | null };
}
export interface ImportantMail { id: number; sender: string; subject: string; snippet: string; reason: string | null; received_at: string }
export interface CalEvent { id: number; title: string; location: string | null; source: string; start_at: string; end_at: string | null }

export interface TxItem {
  id: number; kind: "income" | "expense"; amount_cents: number; currency: string;
  category: string | null; description: string | null; occurred_on: string;
}
export interface BudgetItem { category: string; monthly_cents: number; spent_cents: number; pct: number; status: "ok" | "warning" | "over" }
export interface FinanceSummary {
  month: string; income_cents: number; expense_cents: number; net_cents: number; savings_rate: number | null;
  balance_cents: number; by_category: { category: string; cents: number }[]; budgets: BudgetItem[];
  months: { month: string; income_cents: number; expense_cents: number; net_cents: number }[]; count: number;
}
export interface PaperTradeItem {
  id: number; symbol: string; side: "long" | "short"; quantity: number; entry_price: number;
  stop_loss: number | null; take_profit: number | null; exit_price: number | null; opened_at: string; closed_at: string | null;
  strategy: string | null; mistakes: string[]; notes: string | null; status: "open" | "closed";
  pnl: number | null; risk: number | null; planned_rr: number | null; r: number | null;
}
export interface TradeAgg {
  trades: number; wins: number; losses: number; win_rate: number | null; pnl: number; avg_win: number | null;
  avg_loss: number | null; profit_factor: number | null; expectancy: number | null; avg_r: number | null;
}
export interface TradingStats {
  simulation: true; initial_capital: number | null; equity: number | null; return_pct: number | null;
  max_drawdown: number; max_drawdown_pct: number | null; overall: TradeAgg; curve: { date: string; equity: number }[];
  by_strategy: (TradeAgg & { strategy: string })[]; mistakes: { mistake: string; count: number; pnl: number }[];
  without_stop: number; open: PaperTradeItem[]; open_risk: number;
}
export interface HealthDayItem {
  day: string; steps: number | null; sleep_hours: number | null; weight_kg: number | null;
  active_kcal: number | null; distance_km: number | null; resting_hr: number | null;
}
export interface HealthSetup { token: string; path: string; header: string; fields: string[] }

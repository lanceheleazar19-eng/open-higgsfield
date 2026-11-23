import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { App } from "../App";
import { emptyDashboard, health, mockFetch, modules, prefs } from "./fixtures";

function renderAt(path: string) {
  return render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
}

const base = {
  "/api/system/health": health,
  "/api/system/modules": modules,
  "/api/settings": prefs,
  "/api/settings/timezones": ["Europe/Madrid", "America/Mexico_City"],
};

afterEach(() => vi.unstubAllGlobals());

test("dashboard vacío muestra estados vacíos honestos y no cifras inventadas", async () => {
  mockFetch({ ...base, "/api/dashboard": emptyDashboard });
  renderAt("/");
  expect(await screen.findByText(/Buenos días/)).toBeInTheDocument();
  expect(screen.getByText(/No hay tareas registradas/)).toBeInTheDocument();
  expect(screen.getByText(/Aún no hay movimientos de dinero real/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Dime cómo te llamas/ })).toHaveAttribute("href", "/settings");
});

test("dashboard con datos muestra nombre, tareas atrasadas y finanzas", async () => {
  mockFetch({
    ...base,
    "/api/dashboard": {
      ...emptyDashboard,
      greeting: { ...emptyDashboard.greeting, name: "Lance" },
      summary: { ...emptyDashboard.summary, pending_tasks: 1, overdue_tasks: 1 },
      tasks: { pending: 1, overdue: 1, due_today: 0, items: [
        { id: 1, title: "Pagar seguro", priority: "high", status: "pending", due_at: "2026-11-22T09:00:00+01:00", overdue: true },
      ] },
      finance: { ...emptyDashboard.finance, has_data: true, income_cents: 200000, expense_cents: 50000, net_cents: 150000, balance_cents: 150000,
        top_expense_categories: [{ category: "Vivienda", amount_cents: 50000 }] },
    },
  });
  renderAt("/");
  expect(await screen.findByText("Lance")).toBeInTheDocument();
  expect(screen.getByText("Pagar seguro")).toBeInTheDocument();
  expect(screen.getByText(/Atrasada ·/)).toBeInTheDocument();
  expect(screen.getByText("Vivienda")).toBeInTheDocument();
});

test("backend caído muestra estado sin conexión con reintento", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("network"); }));
  renderAt("/");
  expect(await screen.findByText(/Núcleo de ATLAS sin conexión/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
});

test("sidebar marca módulos planificados con su fase y abre su página", async () => {
  mockFetch({ ...base, "/api/dashboard": emptyDashboard });
  renderAt("/tasks");
  expect(await screen.findByText("F4")).toBeInTheDocument();
  expect(await screen.findByText("Fase 4 · en desarrollo")).toBeInTheDocument();
  expect(screen.getByText("Prioridades")).toBeInTheDocument();
});

test("configuración guarda el nombre vía PUT", async () => {
  const calls = mockFetch({ ...base, "PUT /api/settings": { ...prefs, user_name: "Tony" } });
  renderAt("/settings");
  const input = await screen.findByPlaceholderText("Tu nombre");
  await waitFor(() => expect(input).toHaveValue("Lance"));
  fireEvent.change(input, { target: { value: "Tony" } });
  fireEvent.click(screen.getByRole("button", { name: "Guardar" }));
  await screen.findByText("Preferencias guardadas.");
  const put = calls.find((c) => c.init?.method === "PUT");
  expect(JSON.parse(put!.init!.body as string)).toMatchObject({ user_name: "Tony" });
});

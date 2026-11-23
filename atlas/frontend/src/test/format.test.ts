import { formatMoney, greetingFor, weekdayInitial } from "../lib/format";

test("formatMoney usa céntimos y formato español", () => {
  expect(formatMoney(123456, "EUR").replace(/\s/g, " ")).toBe("1234,56 €");
  expect(formatMoney(-500, "EUR")).toContain("-5,00");
});

test("saludo según momento del día", () => {
  expect(greetingFor("morning")).toBe("Buenos días");
  expect(greetingFor("night")).toBe("Buenas noches");
});

test("inicial de día de la semana desde fecha local", () => {
  expect(weekdayInitial("2026-11-23")).toBe("L"); // lunes
});

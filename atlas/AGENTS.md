# Instrucciones para agentes de código (Codex, Claude Code, etc.)

Proyecto: ATLAS, asistente personal local. Lee `docs/ARCHITECTURE.md` y `docs/ROADMAP.md` primero.

## Comandos
- Backend: `cd backend && .venv/bin/pytest -q` (Windows: `.venv\Scripts\pytest -q`)
- Frontend: `cd frontend && npx tsc -b && npx vitest run`
- Todo: `./scripts/test.sh`

## Reglas
- Interfaz y textos de usuario en **español**.
- **Nunca inventar datos**: toda cifra sale de una consulta; sin datos → estado vacío.
- **Nada de botones sin función.** Un módulo no construido muestra su fase, no controles falsos.
- Cambiar un modelo en `backend/atlas/models/` ⇒ crear migración Alembic
  (`tests/test_migrations.py` falla si falta). Nunca borrar `data/`.
- Fechas en BD: UTC naive. Dinero: enteros en céntimos. Dinero real y trading en tablas separadas.
- Lógica en `services/`, HTTP en `api/`, registrar el router en `main.py` y el módulo en `modules.py`
  (`status="active"` solo cuando funcione de verdad).
- Secretos solo en `backend/.env`. El servidor escucha en 127.0.0.1.
- Acciones sensibles (dinero, trading real, comandos del sistema, borrar datos) requieren confirmación explícita del usuario.
- Cada fase termina con pruebas en verde.

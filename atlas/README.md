# ATLAS — Personal Intelligence System

> Your life. Your data. Your intelligence.

Asistente personal de IA local: centro de control de tareas, entrenamiento,
finanzas, trading (simulado), proyectos, calendario y memoria. Todos los datos
se guardan **solo en tu ordenador** (`atlas/data/`).

**Estado actual: Fase 1 completada** (arquitectura + dashboard). Ver
[docs/ROADMAP.md](docs/ROADMAP.md).

## Requisitos

| Herramienta | Versión | Para qué |
|---|---|---|
| Python | 3.11 o superior | Backend (FastAPI) |
| Node.js | 20 o superior | Compilar la interfaz |
| [uv](https://docs.astral.sh/uv/) | opcional | Instalación de Python más rápida |
| [Ollama](https://ollama.com) | opcional, Fase 2 | Modelos de IA locales |

## Arrancar ATLAS

**Windows (PowerShell):**

```powershell
.\scripts\start.ps1
```

Si PowerShell bloquea el script: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

**Linux / macOS:**

```bash
./scripts/start.sh
```

La primera vez instala las dependencias y compila la interfaz. Después abre
**http://127.0.0.1:8000**. Tras cambiar código del frontend, usa `-Rebuild` /
`--rebuild`.

### Modo desarrollo (recarga en caliente)

```bash
cd backend && .venv/bin/uvicorn atlas.main:app --reload --port 8000
```

```bash
cd frontend && npm run dev
```

Interfaz en http://127.0.0.1:5173 (redirige `/api` al backend).

## Pruebas

```bash
./scripts/test.sh
```

Backend: pytest (API, agregaciones del dashboard, límites de mes, restricciones
de BD, migraciones sincronizadas con los modelos). Frontend: typecheck + Vitest
(estados vacíos, datos, sin conexión, navegación, guardar configuración).

## Configuración

Copia `backend/.env.example` a `backend/.env` (el script de arranque lo hace
por ti). Las claves de API **solo** van en ese archivo, que git ignora.
Por defecto ATLAS escucha únicamente en `127.0.0.1` (no accesible desde la red).

## Estructura

```
atlas/
├── backend/            FastAPI + SQLAlchemy + Alembic
│   ├── atlas/
│   │   ├── api/        Endpoints HTTP (uno por módulo)
│   │   ├── models/     Tablas de la base de datos
│   │   ├── services/   Lógica de negocio (sin HTTP)
│   │   ├── modules.py  Registro de módulos y su fase
│   │   ├── config.py   Configuración por variables de entorno
│   │   └── db.py       Motor, sesiones y migraciones
│   ├── migrations/     Migraciones de esquema (Alembic)
│   └── tests/
├── frontend/           React 19 + TypeScript + Vite
│   └── src/{api,components,pages,lib,styles,test}
├── scripts/            start.sh, start.ps1, test.sh
├── docs/               Arquitectura y hoja de ruta
└── data/               Tu base de datos (ignorada por git)
```

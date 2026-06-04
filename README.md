# CiXiS

CiXiS is an offline-first Persian/RTL cafe POS. The local app is an Electron + React frontend connected to a local Django + DRF backend on `127.0.0.1:8000` with SQLite; an optional remote Django server hosts the public QR menu and receives day-closing sync.

## Prerequisites

- Node 20+
- Python 3.11+; Python 3.13 recommended, avoid 3.14
- npm

## Quick start (development)

```bash
# Backend (terminal 1)
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py init_settings
python manage.py seed_menu
python manage.py runserver 8000

# Frontend (terminal 2)
cd frontend
npm install
npm run electron:dev   # launches Electron; it also auto-spawns the backend
```

`npm run dev` is available for browser-only frontend development without Electron. The Electron main process spawns the local Django backend on launch.

## Remote server setup (optional)

```bash
cd remote
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
export CIXIS_API_KEY=dev-cixis-key
python manage.py runserver 9000
```

The public menu is available at `/menu/<cafe_slug>/`.

Configure the local app settings for `remote_server_url`, `api_key`, and `cafe_slug` through `AppSetting`. Defaults are created by `python manage.py init_settings`.

## Build for Windows

```bash
cd frontend
npm run electron:build
```

The NSIS installer is written to `frontend/dist/` or `dist/`.

## Running tests

```bash
cd backend
python manage.py test pos
```

```bash
cd frontend
npm test
```

## Tech stack

| Area | Stack |
| --- | --- |
| Frontend | React, TypeScript, Tailwind, Electron |
| Backend | Django, DRF |
| Local DB | SQLite |
| Packaging | electron-builder NSIS |

## Project structure

```text
.
├── backend/     # Local Django POS API app (`pos`), SQLite DB, seed/settings commands, backend tests
├── frontend/    # Vite + React + TypeScript + Tailwind + Electron app and Windows packaging
├── remote/      # Optional Django QR-menu server and private sync endpoints
├── .documents/  # PRD, tasks, and BDD feature planning files; not shipped
└── menu.json    # Seed menu with 12 categories and about 90 products
```

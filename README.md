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

## Updates and data persistence

Cafe data is **never** stored inside the install directory. The packaged app
keeps the live SQLite DB and all backups under the OS user-data dir
(`%APPDATA%/CiXiS/data` on Windows), passed to Django via the `CIXIS_DB_PATH`
and `CIXIS_BACKUP_DIR` env vars set by the Electron main process. Reinstalling
or updating the app replaces only code; the data dir is untouched.

On every launch the app, before running migrations:

1. Snapshots the current DB to `data/pre-update-backups/` (newest 5 kept).
2. Runs `migrate --noinput`, applying any new schema from the build to the
   existing data.

So shipping a new feature/fix = build a new installer, user runs it, data
carries forward. Day-closing backups in `data/backups/` are separate and
unaffected.

### Auto-update

`electron-updater` checks the release feed on launch and downloads new versions
in the background (feed configured under `publish:` in
[electron-builder.yml](frontend/electron-builder.yml), pointing at the GitHub
Releases of `Navidoo/cixis`).

### Shipping a release (GitHub Actions)

Releases are cut by CI — [`.github/workflows/windows-build.yml`](.github/workflows/windows-build.yml)
builds the Windows installer and publishes it to GitHub Releases on any `v*`
tag. To ship a feature or fix:

```bash
# 1. bump version in frontend/package.json (e.g. 1.0.0 -> 1.0.1)
# 2. commit, then tag and push:
git tag v1.0.1
git push origin v1.0.1
```

The workflow then:

1. Creates a Windows backend venv and builds the installer.
2. Runs `electron-builder --publish always`, which uploads the `.exe` **and** the
   `latest.yml` feed to a GitHub Release for tag `v1.0.1`.
3. Installed apps pick it up on next launch, download in the background, and
   apply the new build on restart — DB and backups in the user-data dir carry
   forward untouched.

Notes:

- The tag version **must** match `package.json`'s `version`; electron-updater
  compares them.
- CI uses the built-in `GITHUB_TOKEN` (workflow has `contents: write`); no manual
  secret needed for the default GitHub feed.
- Non-tag / manual (`workflow_dispatch`) runs build with `--publish never` and
  only upload the installer as a CI artifact — no release, no auto-update push.
- Without a reachable feed the updater no-ops; manual installer download still
  works.

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

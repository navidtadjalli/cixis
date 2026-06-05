// Electron main process.
// Responsibilities:
//   1. Spawn the local Django backend on 127.0.0.1:8000.
//   2. On first launch, run migrations + seed_menu (checked via AppSetting).
//   3. Open a frameless dark window loading the React app.
//   4. Kill the Django subprocess on quit.
const { app, BrowserWindow, ipcMain } = require("electron");
const { spawn, spawnSync } = require("child_process");
const path = require("path");
const fs = require("fs");
const http = require("http");

const isDev = process.env.ELECTRON_DEV === "1";
const BACKEND_PORT = 8000;
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`;

let djangoProc = null;
let mainWindow = null;

// Resolve backend dir + python executable for both dev and packaged builds.
function backendPaths() {
  if (isDev) {
    const backendDir = path.join(__dirname, "..", "..", "backend");
    const py =
      process.platform === "win32"
        ? path.join(backendDir, ".venv", "Scripts", "python.exe")
        : path.join(backendDir, ".venv", "bin", "python");
    return { backendDir, py };
  }
  // Packaged: backend shipped via extraResources (see electron-builder.yml).
  const backendDir = path.join(process.resourcesPath, "backend");
  const py =
    process.platform === "win32"
      ? path.join(backendDir, ".venv", "Scripts", "python.exe")
      : path.join(backendDir, ".venv", "bin", "python");
  return { backendDir, py };
}

// Persistent data dir in userData. Survives app updates/reinstalls, unlike the
// install dir (resourcesPath) which NSIS replaces on every update.
function dataDir() {
  const dir = path.join(app.getPath("userData"), "data");
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

function dbPath() {
  return path.join(dataDir(), "cixis.sqlite3");
}

// Env handed to every Django process so DB + backups live in userData.
function backendEnv() {
  return {
    ...process.env,
    CIXIS_DB_PATH: dbPath(),
    CIXIS_BACKUP_DIR: path.join(dataDir(), "backups"),
  };
}

function logFilePath() {
  const dir = app.getPath("userData");
  return path.join(dir, "backend.log");
}

// Pre-update safety: snapshot the DB before migrations run. If a new release
// ships a destructive/buggy migration, the user keeps a restorable copy.
function preUpdateBackup() {
  const db = dbPath();
  if (!fs.existsSync(db)) return; // first launch: no DB yet
  const dir = path.join(dataDir(), "pre-update-backups");
  fs.mkdirSync(dir, { recursive: true });
  const ts = new Date().toISOString().replace(/[:.]/g, "-");
  try {
    fs.copyFileSync(db, path.join(dir, `cixis-${ts}.sqlite3`));
  } catch (e) {
    console.error("pre-update backup failed:", e);
  }
  // Keep only the newest 5 pre-update snapshots.
  const snaps = fs
    .readdirSync(dir)
    .filter((f) => f.endsWith(".sqlite3"))
    .sort()
    .reverse();
  for (const stale of snaps.slice(5)) {
    try {
      fs.unlinkSync(path.join(dir, stale));
    } catch (e) {
      // best-effort
    }
  }
}

function runManage(py, backendDir, args) {
  return spawnSync(py, ["manage.py", ...args], {
    cwd: backendDir,
    encoding: "utf-8",
    env: backendEnv(),
  });
}

function startDjango() {
  const { backendDir, py } = backendPaths();
  if (!fs.existsSync(py)) {
    console.error("Python executable not found:", py);
    return;
  }

  // Snapshot existing DB before applying any new migrations from this build.
  preUpdateBackup();

  // First-launch setup: migrate, ensure default settings, then seed menu once.
  runManage(py, backendDir, ["migrate", "--noinput"]);
  runManage(py, backendDir, ["init_settings"]);
  const seeded = runManage(py, backendDir, [
    "shell",
    "-c",
    "from pos.models import AppSetting; print(AppSetting.objects.filter(key='menu_seeded', value='true').exists())",
  ]);
  if (!String(seeded.stdout).includes("True")) {
    runManage(py, backendDir, ["seed_menu"]);
  }
  const tablesSeeded = runManage(py, backendDir, [
    "shell",
    "-c",
    "from pos.models import AppSetting; print(AppSetting.objects.filter(key='tables_seeded', value='true').exists())",
  ]);
  if (!String(tablesSeeded.stdout).includes("True")) {
    runManage(py, backendDir, ["seed_tables"]);
  }

  const logStream = fs.createWriteStream(logFilePath(), { flags: "a" });
  djangoProc = spawn(
    py,
    ["manage.py", "runserver", `127.0.0.1:${BACKEND_PORT}`, "--noreload"],
    { cwd: backendDir, env: backendEnv() },
  );
  djangoProc.stdout.pipe(logStream);
  djangoProc.stderr.pipe(logStream);
}

function waitForBackend(retries = 40) {
  return new Promise((resolve) => {
    const attempt = (n) => {
      http
        .get(`${BACKEND_URL}/api/`, (res) => {
          res.resume();
          resolve(true);
        })
        .on("error", () => {
          if (n <= 0) return resolve(false);
          setTimeout(() => attempt(n - 1), 300);
        });
    };
    attempt(retries);
  });
}

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1320,
    height: 860,
    minWidth: 1024,
    minHeight: 700,
    backgroundColor: "#0f1115",
    frame: false,
    titleBarStyle: "hidden",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  await waitForBackend();

  if (isDev) {
    mainWindow.loadURL("http://localhost:5173");
  } else {
    mainWindow.loadFile(path.join(__dirname, "..", "dist", "index.html"));
  }
}

ipcMain.on("win:minimize", () => mainWindow && mainWindow.minimize());
ipcMain.on("win:toggle-maximize", () => {
  if (!mainWindow) return;
  mainWindow.isMaximized() ? mainWindow.unmaximize() : mainWindow.maximize();
});
ipcMain.on("win:close", () => mainWindow && mainWindow.close());

// Check for a newer release and download+notify in the background.
// No-op in dev and when no publish feed is configured.
function initAutoUpdate() {
  if (isDev) return;
  let autoUpdater;
  try {
    ({ autoUpdater } = require("electron-updater"));
  } catch (e) {
    return; // electron-updater not installed
  }
  autoUpdater.autoDownload = true;
  autoUpdater.on("error", (err) =>
    console.error("auto-update error:", err && err.message),
  );
  autoUpdater.checkForUpdatesAndNotify().catch(() => {});
}

app.whenReady().then(() => {
  startDjango();
  createWindow();
  initAutoUpdate();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

function killDjango() {
  if (djangoProc && !djangoProc.killed) {
    try {
      if (process.platform === "win32") {
        spawnSync("taskkill", ["/pid", String(djangoProc.pid), "/f", "/t"]);
      } else {
        djangoProc.kill("SIGTERM");
      }
    } catch (e) {
      // best-effort
    }
  }
}

app.on("window-all-closed", () => {
  killDjango();
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", killDjango);
process.on("exit", killDjango);

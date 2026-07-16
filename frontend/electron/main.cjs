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
  // Windows ships a standalone embeddable Python (no install needed). Its
  // python313._pth adds ../backend and ../backend/pylibs to sys.path, so Django
  // + deps resolve without a venv. macOS/Linux still use a local .venv.
  const py =
    process.platform === "win32"
      ? path.join(process.resourcesPath, "python", "python.exe")
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
    // Packaged builds must never run Django with DEBUG on: its error page leaks
    // SECRET_KEY and the environment, and it retains every SQL query it runs.
    CIXIS_DEBUG: isDev ? "1" : "0",
  };
}

function logFilePath() {
  const dir = app.getPath("userData");
  return path.join(dir, "backend.log");
}

// backend.log is append-only and Django logs a line per request, including the
// front-end's 30s table poll. A POS that runs for weeks without a restart would
// otherwise grow it without bound, so keep the current log plus one previous.
const LOG_MAX_BYTES = 5 * 1024 * 1024;
const LOG_CHECK_MS = 60 * 60 * 1000;

function logIsOversized() {
  try {
    return fs.statSync(logFilePath()).size > LOG_MAX_BYTES;
  } catch (e) {
    return false; // no log yet
  }
}

function rotateLog() {
  const p = logFilePath();
  try {
    fs.rmSync(`${p}.1`, { force: true });
    fs.renameSync(p, `${p}.1`);
  } catch (e) {
    // best-effort: a failed rotation must never stop the backend from starting
  }
}

// Pipe the backend's output to the log, rolling it over when it gets too big.
function attachLog(proc) {
  if (logIsOversized()) rotateLog();

  let stream = fs.createWriteStream(logFilePath(), { flags: "a" });
  proc.stdout.pipe(stream);
  proc.stderr.pipe(stream);

  const timer = setInterval(() => {
    if (!logIsOversized()) return;
    proc.stdout.unpipe(stream);
    proc.stderr.unpipe(stream);
    // Rotate only once the current stream has flushed, or the rename races the
    // in-flight writes and we lose the tail of the log.
    stream.end(() => {
      rotateLog();
      stream = fs.createWriteStream(logFilePath(), { flags: "a" });
      proc.stdout.pipe(stream);
      proc.stderr.pipe(stream);
    });
  }, LOG_CHECK_MS);
  timer.unref();

  proc.on("exit", () => clearInterval(timer));
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

  djangoProc = spawn(
    py,
    [
      "manage.py",
      "runserver",
      `127.0.0.1:${BACKEND_PORT}`,
      "--noreload",
      // With DEBUG off, runserver stops serving static files, which would break
      // the bundled /admin/ pages. We're bound to 127.0.0.1, so serving them is
      // as safe here as it was when DEBUG was doing it implicitly.
      "--insecure",
    ],
    { cwd: backendDir, env: backendEnv() },
  );
  attachLog(djangoProc);
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

// A second launch (staff double-clicking the icon) would otherwise bring up a
// whole second Electron *and* a second Django fighting over port 8000, doubling
// the machine's memory for a window nobody asked for. Hand focus to the running
// instance instead. Bail before whenReady so the duplicate never spawns Django.
if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (!mainWindow) return;
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.show();
    mainWindow.focus();
  });

  app.whenReady().then(() => {
    startDjango();
    createWindow();

    app.on("activate", () => {
      if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
  });
}

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

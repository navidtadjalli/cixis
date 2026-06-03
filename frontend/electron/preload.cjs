// Minimal preload. The renderer talks to Django over HTTP (same as the browser),
// so we only expose lightweight window controls for the frameless titlebar.
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("cixis", {
  platform: process.platform,
  minimize: () => ipcRenderer.send("win:minimize"),
  toggleMaximize: () => ipcRenderer.send("win:toggle-maximize"),
  close: () => ipcRenderer.send("win:close"),
});

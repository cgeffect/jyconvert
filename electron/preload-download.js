const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("jyDownload", {
  getDefaultOutputDir: () => ipcRenderer.invoke("download-default-dir"),
  pickOutputDir: () => ipcRenderer.invoke("pick-download-dir"),
  pickCookiesFile: () => ipcRenderer.invoke("pick-cookies-file"),
  checkChromeCookies: () => ipcRenderer.invoke("check-chrome-cookies"),
  checkDouyinSessionCookies: () => ipcRenderer.invoke("check-douyin-session-cookies"),
  openDouyinLogin: () => ipcRenderer.invoke("open-douyin-login"),
  exportDouyinSessionCookies: () => ipcRenderer.invoke("export-douyin-session-cookies"),
  startDownload: (opts) => ipcRenderer.invoke("download-video", opts),
  writeDownloadIndex: (opts) => ipcRenderer.invoke("write-download-index", opts),
  openInFinder: (targetPath) => ipcRenderer.invoke("open-in-finder", targetPath),
  openExternal: (url) => ipcRenderer.invoke("open-external", url),
  onProgress: (callback) => {
    const handler = (_event, payload) => callback(payload);
    ipcRenderer.on("download-progress", handler);
    return () => ipcRenderer.removeListener("download-progress", handler);
  },
  onDouyinLoginClosed: (callback) => {
    const handler = () => callback();
    ipcRenderer.on("douyin-login-closed", handler);
    return () => ipcRenderer.removeListener("douyin-login-closed", handler);
  },
});

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("jyconvert", {
  pickZip: () => ipcRenderer.invoke("pick-zip"),
  openPackage: (zipPath) => ipcRenderer.invoke("open-package", zipPath),
  convertDraft: (opts) => ipcRenderer.invoke("convert-draft", opts),
  importDraft: (opts) => ipcRenderer.invoke("import-draft", opts),
  getPythonRoot: () => ipcRenderer.invoke("get-python-root"),
  getPythonBinary: () => ipcRenderer.invoke("get-python-binary"),
  openInFinder: (targetPath) => ipcRenderer.invoke("open-in-finder", targetPath),
  openExternal: (url) => ipcRenderer.invoke("open-external", url),
  openDownloader: () => ipcRenderer.invoke("open-downloader-window"),
  getJianyingDraftPath: (opts) => ipcRenderer.invoke("jianying-draft-path", opts),
  getJianyingDraftsRoot: () => ipcRenderer.invoke("get-jianying-drafts-root"),
  setJianyingDraftsRoot: (draftsRoot) => ipcRenderer.invoke("set-jianying-drafts-root", draftsRoot),
  pickJianyingDraftsDir: () => ipcRenderer.invoke("pick-jianying-drafts-dir"),
});

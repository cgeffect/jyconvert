const { app, BrowserWindow, ipcMain, dialog, shell, session } = require("electron");
const path = require("path");
const fs = require("fs");
const { extractZip } = require("./lib/package");
const { convertDraft, importDraft } = require("./lib/runner");
const { extractUrl, downloadVideo, checkChromeCookies } = require("./lib/downloader");
const { collectDouyinCookies, exportDouyinCookiesToFile, hasDouyinLoginCookies } = require("./lib/cookies");
const { resolveDouyinVideo, destroyDouyinFetchWindow } = require("./lib/douyin-fetch");
const { downloadDouyinVideoToDir } = require("./lib/douyin-download");
const { attachDouyinWebGuards, stopWebContentsMedia } = require("./lib/douyin-browser");
const {
  createDownloadProgressEmitter,
  fileSizeOf,
  parseDownloadOutput,
  isDouyinInput,
} = require("./lib/download-video");
const { pythonRoot } = require("./lib/paths");
const { writeDownloadIndexCsv } = require("./lib/download-index");
const {
  getJianyingDraftsRoot,
  setJianyingDraftsRoot,
  detectDefaultDraftsRoot,
  resolveJianyingDraftDir,
} = require("./lib/jianying-config");

let mainWindow = null;
let downloadWindow = null;
let douyinLoginWindow = null;
let lastPackage = null;

const DOUYIN_PARTITION = "persist:jyconvert-douyin";
const DEFAULT_WINDOW_WIDTH = 1200;
const DEFAULT_WINDOW_HEIGHT = 800;
const DEFAULT_WINDOW_MIN_WIDTH = 560;
const DEFAULT_WINDOW_MIN_HEIGHT = 560;

function defaultDownloadDir() {
  return path.join(app.getPath("home"), "Downloads", "jyconvert");
}

function createDownloadWindow() {
  if (downloadWindow && !downloadWindow.isDestroyed()) {
    downloadWindow.focus();
    return;
  }

  const iconPath = path.join(__dirname, "../assets/icon.png");
  downloadWindow = new BrowserWindow({
    width: DEFAULT_WINDOW_WIDTH,
    height: DEFAULT_WINDOW_HEIGHT,
    minWidth: DEFAULT_WINDOW_MIN_WIDTH,
    minHeight: DEFAULT_WINDOW_MIN_HEIGHT,
    title: "视频下载",
    icon: iconPath,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload-download.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  downloadWindow.loadFile(path.join(__dirname, "../renderer/downloader/index.html"));
  downloadWindow.once("ready-to-show", () => {
    if (downloadWindow && !downloadWindow.isDestroyed()) {
      if (mainWindow && !mainWindow.isDestroyed()) {
        const [mx, my] = mainWindow.getPosition();
        downloadWindow.setPosition(mx + 24, my + 24);
      } else {
        downloadWindow.center();
      }
      downloadWindow.show();
    }
  });
  downloadWindow.on("closed", () => {
    downloadWindow = null;
  });
}

function douyinSession() {
  return session.fromPartition(DOUYIN_PARTITION);
}

function createDouyinLoginWindow() {
  if (douyinLoginWindow && !douyinLoginWindow.isDestroyed()) {
    douyinLoginWindow.show();
    douyinLoginWindow.focus();
    return;
  }

  const iconPath = path.join(__dirname, "../assets/icon.png");
  douyinLoginWindow = new BrowserWindow({
    width: 960,
    height: 720,
    minWidth: 720,
    minHeight: 560,
    title: "抖音登录",
    icon: iconPath,
    show: false,
    webPreferences: {
      partition: DOUYIN_PARTITION,
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  douyinLoginWindow.webContents.setUserAgent(
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
  );
  attachDouyinWebGuards(douyinLoginWindow.webContents);
  douyinLoginWindow.once("ready-to-show", () => {
    if (douyinLoginWindow && !douyinLoginWindow.isDestroyed()) {
      douyinLoginWindow.showInactive();
    }
  });
  douyinLoginWindow.loadURL("https://www.douyin.com/");
  douyinLoginWindow.on("close", () => {
    if (douyinLoginWindow && !douyinLoginWindow.isDestroyed()) {
      stopWebContentsMedia(douyinLoginWindow.webContents);
    }
    destroyDouyinFetchWindow();
  });
  douyinLoginWindow.on("closed", () => {
    douyinLoginWindow = null;
    if (downloadWindow && !downloadWindow.isDestroyed()) {
      downloadWindow.webContents.send("douyin-login-closed");
    }
  });
}

function createWindow() {
  const iconPath = path.join(__dirname, "../assets/icon.png");
  mainWindow = new BrowserWindow({
    width: DEFAULT_WINDOW_WIDTH,
    height: DEFAULT_WINDOW_HEIGHT,
    minWidth: DEFAULT_WINDOW_MIN_WIDTH,
    minHeight: DEFAULT_WINDOW_MIN_HEIGHT,
    title: "jyconvert",
    icon: iconPath,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.loadFile(path.join(__dirname, "../renderer/index.html"));
}

ipcMain.handle("pick-zip", async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: "选择项目预览页下载的素材包",
    properties: ["openFile"],
    filters: [{ name: "压缩包", extensions: ["zip"] }],
  });
  if (result.canceled || !result.filePaths.length) {
    return null;
  }
  return result.filePaths[0];
});

ipcMain.handle("open-package", async (_event, zipPath) => {
  lastPackage = extractZip(zipPath);
  return lastPackage;
});

ipcMain.handle("convert-draft", async (_event, { draftName }) => {
  if (!lastPackage) {
    throw new Error("请先选择素材包");
  }
  if (!draftName || !draftName.trim()) {
    throw new Error("请填写草稿目录名");
  }

  const name = draftName.trim();
  const outputDir = lastPackage.parentDir;
  const { stdout, stderr } = await convertDraft({
    protocolPath: lastPackage.protocolPath,
    resourceRoot: lastPackage.resourceRoot,
    draftName: name,
    outputDir,
  });

  const draftDir = path.join(outputDir, name);
  if (!fs.existsSync(path.join(draftDir, "draft_info.json"))) {
    throw new Error("转换完成但未找到 draft_info.json");
  }

  return {
    draftDir,
    outputDir,
    draftName: name,
    log: [stdout, stderr].filter(Boolean).join("\n"),
  };
});

ipcMain.handle("import-draft", async (_event, { draftDir, jianyingName, jianyingDraftsRoot }) => {
  if (!draftDir || !draftDir.trim()) {
    throw new Error("请指定草稿目录");
  }
  if (!jianyingName || !jianyingName.trim()) {
    throw new Error("请填写剪映草稿名称");
  }

  const dir = draftDir.trim();
  const name = jianyingName.trim();
  if (!fs.existsSync(path.join(dir, "draft_info.json"))) {
    throw new Error(`草稿不完整: ${dir}`);
  }

  const draftsRoot = jianyingDraftsRoot?.trim()
    ? setJianyingDraftsRoot(jianyingDraftsRoot.trim())
    : getJianyingDraftsRoot();

  const { stdout, stderr } = await importDraft({
    draftDir: dir,
    jianyingName: name,
    jianyingDraftsRoot: draftsRoot,
  });

  const importedDraftDir = resolveJianyingDraftDir(name);

  let draftCreatedAt = null;
  let draftDisplayName = name;
  const metaPath = path.join(importedDraftDir, "draft_meta_info.json");
  if (fs.existsSync(metaPath)) {
    try {
      const meta = JSON.parse(fs.readFileSync(metaPath, "utf-8"));
      draftDisplayName = meta.draft_name || name;
      const ts = meta.tm_draft_create;
      if (typeof ts === "number" && ts > 0) {
        draftCreatedAt = new Date(ts / 1000).toISOString();
      }
    } catch {
      // ignore parse errors
    }
  }
  if (!draftCreatedAt && fs.existsSync(importedDraftDir)) {
    draftCreatedAt = fs.statSync(importedDraftDir).birthtime.toISOString();
  }

  return {
    jianyingDraftDir: importedDraftDir,
    draftName: draftDisplayName,
    draftCreatedAt,
    log: [stdout, stderr].filter(Boolean).join("\n"),
  };
});

ipcMain.handle("open-downloader-window", () => {
  createDownloadWindow();
});

ipcMain.handle("download-default-dir", () => defaultDownloadDir());

ipcMain.handle("pick-download-dir", async () => {
  const parent = downloadWindow && !downloadWindow.isDestroyed() ? downloadWindow : mainWindow;
  const result = await dialog.showOpenDialog(parent, {
    title: "选择保存目录",
    properties: ["openDirectory", "createDirectory"],
    defaultPath: defaultDownloadDir(),
  });
  if (result.canceled || !result.filePaths.length) {
    return null;
  }
  return result.filePaths[0];
});

ipcMain.handle("pick-cookies-file", async () => {
  const parent = downloadWindow && !downloadWindow.isDestroyed() ? downloadWindow : mainWindow;
  const result = await dialog.showOpenDialog(parent, {
    title: "选择 cookies.txt",
    properties: ["openFile"],
    filters: [
      { name: "Cookies", extensions: ["txt"] },
      { name: "All Files", extensions: ["*"] },
    ],
    defaultPath: app.getPath("downloads"),
  });
  if (result.canceled || !result.filePaths.length) {
    return null;
  }
  return result.filePaths[0];
});

ipcMain.handle("write-download-index", async (_event, { outputDir, rows }) => {
  if (!outputDir || !String(outputDir).trim()) {
    throw new Error("缺少保存目录");
  }
  if (!Array.isArray(rows) || !rows.length) {
    throw new Error("没有可写入的对照记录");
  }
  const filePath = writeDownloadIndexCsv(String(outputDir).trim(), rows);
  return {
    filePath,
    filename: path.basename(filePath),
  };
});

ipcMain.handle("check-chrome-cookies", async () => {
  return checkChromeCookies();
});

ipcMain.handle("open-douyin-login", () => {
  createDouyinLoginWindow();
});

ipcMain.handle("export-douyin-session-cookies", async () => {
  const cookies = await collectDouyinCookies(douyinSession());
  const loggedIn = hasDouyinLoginCookies(cookies);
  const { filePath, count } = await exportDouyinCookiesToFile(douyinSession());
  return {
    filePath,
    count,
    ok: loggedIn,
    message: loggedIn
      ? `已从应用内登录读取 ${count} 条 douyin Cookie（含 sessionid）`
      : count > 0
        ? `读取到 ${count} 条 Cookie，但未发现 sessionid，请在登录窗口重新登录抖音`
        : "应用内尚未检测到 douyin Cookie，请先在登录窗口完成登录",
  };
});

ipcMain.handle("check-douyin-session-cookies", async () => {
  const cookies = await collectDouyinCookies(douyinSession());
  const loggedIn = hasDouyinLoginCookies(cookies);
  return {
    count: cookies.length,
    ok: loggedIn,
    message: loggedIn
      ? `应用内已登录（${cookies.length} 条 douyin Cookie，含 sessionid）`
      : cookies.length > 0
        ? `检测到 ${cookies.length} 条 Cookie，但缺少 sessionid，请重新应用内登录`
        : "应用内尚未登录抖音",
  };
});

async function resolveDownloadInput(input) {
  const text = String(input || "").trim();
  if (!text) {
    return "";
  }
  if (/^https?:\/\/(?:www\.)?douyin\.com\/(?:video|note)\/\d+/i.test(text)) {
    return text;
  }
  try {
    return await extractUrl(text);
  } catch {
    return text;
  }
}

ipcMain.handle(
  "download-video",
  async (event, { input, outputDir, cookiesBrowser = "chrome", cookiesFile, progressId = 1 }) => {
  if (!input || !String(input).trim()) {
    throw new Error("请输入链接或分享文案");
  }
  if (!outputDir || !String(outputDir).trim()) {
    throw new Error("请选择保存目录");
  }

  const dir = path.resolve(String(outputDir).trim());
  fs.mkdirSync(dir, { recursive: true });

  const sender = event.sender;
  const emit = createDownloadProgressEmitter(sender, progressId);

  const resolvedInput = await resolveDownloadInput(String(input).trim());
  let douyinLoggedIn = false;

  if (isDouyinInput(resolvedInput)) {
    const sessionCookies = await collectDouyinCookies(douyinSession());
    douyinLoggedIn = hasDouyinLoginCookies(sessionCookies);

    if (douyinLoggedIn || sessionCookies.length > 0) {
      if (!douyinLoggedIn) {
        emit("提示: 应用内 Cookie 缺少 sessionid，可能未真正登录，建议重新应用内登录");
      }
      try {
        emit({ phase: "stage", message: "使用应用内浏览器解析抖音视频…" });
        const meta = await resolveDouyinVideo(resolvedInput, {
          session: douyinSession(),
        });
        emit({ phase: "stage", message: `解析成功：${meta.title}` });
        const sessionCookies = await collectDouyinCookies(douyinSession());
        const cookieHeader = sessionCookies.map((item) => `${item.name}=${item.value}`).join("; ");
        const filepath = await downloadDouyinVideoToDir(meta, dir, emit, { cookieHeader });
        const fileSize = fileSizeOf(filepath);
        emit({
          phase: "done",
          percent: 100,
          message: "下载完成",
          fileSize,
          received: fileSize,
          total: fileSize,
        });
        return {
          outputDir: dir,
          filepath,
          fileSize,
          url: meta.playUrl,
          log: `应用内下载完成\n文件: ${filepath}\n链接: ${resolvedInput}`,
        };
      } catch (browserErr) {
        if (douyinLoggedIn) {
          throw browserErr;
        }
        emit(`应用内解析失败，尝试 yt-dlp: ${browserErr.message || browserErr}`);
      }
    } else {
      emit("提示: 应用内尚未登录抖音，将尝试 yt-dlp（通常仍会失败，请先应用内登录）");
    }
  }

  try {
    const { stdout, stderr } = await downloadVideo(resolvedInput, {
      outputDir: dir,
      cookiesBrowser: cookiesFile ? "none" : cookiesBrowser || "chrome",
      cookiesFile: cookiesFile ? String(cookiesFile).trim() : undefined,
      onProgress: emit,
    });

    const parsed = parseDownloadOutput(stdout);
    const fileSize = fileSizeOf(parsed.filepath);
    emit({ phase: "done", percent: 100, message: "下载完成", fileSize, received: fileSize, total: fileSize });
    return {
      outputDir: dir,
      log: [stdout, stderr].filter(Boolean).join("\n"),
      fileSize,
      ...parsed,
    };
  } catch (err) {
    const msg = String(err.message || err);
    const friendly = msg.replace(/^下载失败:\s*/m, "").trim();
    if (isDouyinInput(resolvedInput)) {
      if (douyinLoggedIn) {
        throw new Error(friendly || msg);
      }
      throw new Error("下载失败，请先登录抖音后再试。如果已登录，请确认视频链接可以正常打开。");
    }
    throw new Error(friendly || msg);
  }
  },
);

ipcMain.handle("open-external", async (_event, url) => {
  if (!url || typeof url !== "string") {
    throw new Error("无效链接");
  }
  const trimmed = url.trim();
  if (!/^https?:\/\//i.test(trimmed)) {
    throw new Error("仅支持 http / https 链接");
  }
  await shell.openExternal(trimmed);
});

ipcMain.handle("open-in-finder", async (_event, targetPath) => {
  if (!targetPath || typeof targetPath !== "string") {
    throw new Error("无效路径");
  }
  const resolved = path.resolve(targetPath.trim());
  if (!fs.existsSync(resolved)) {
    throw new Error(`路径不存在: ${resolved}`);
  }
  const stat = fs.statSync(resolved);
  if (stat.isDirectory()) {
    const err = await shell.openPath(resolved);
    if (err) {
      throw new Error(err);
    }
    return;
  }
  shell.showItemInFolder(resolved);
});

ipcMain.handle("get-jianying-drafts-root", () => {
  return {
    draftsRoot: getJianyingDraftsRoot(),
    defaultDraftsRoot: detectDefaultDraftsRoot(),
  };
});

ipcMain.handle("set-jianying-drafts-root", (_event, draftsRoot) => {
  return setJianyingDraftsRoot(draftsRoot);
});

ipcMain.handle("pick-jianying-drafts-dir", async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: "选择剪映草稿目录",
    properties: ["openDirectory", "createDirectory"],
    defaultPath: getJianyingDraftsRoot(),
    message: "请选择 com.lveditor.draft 文件夹，或剪映安装目录下的 JianyingPro 文件夹",
  });
  if (result.canceled || !result.filePaths.length) {
    return null;
  }
  return setJianyingDraftsRoot(result.filePaths[0]);
});

ipcMain.handle("jianying-draft-path", (_event, { name, draftsRoot } = {}) => {
  return resolveJianyingDraftDir(name, draftsRoot);
});

ipcMain.handle("get-python-root", () => pythonRoot());
ipcMain.handle("get-python-binary", () => {
  const { bundledPythonBinary } = require("./lib/paths");
  return bundledPythonBinary();
});

app.whenReady().then(() => {
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

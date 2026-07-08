const fs = require("fs");
const os = require("os");
const path = require("path");
const { app } = require("electron");

const CONFIG_NAME = "jianying-config.json";
const DRAFTS_SUFFIX = path.join("User Data", "Projects", "com.lveditor.draft");

function configPath() {
  return path.join(app.getPath("userData"), CONFIG_NAME);
}

function defaultDraftsRoots() {
  const home = os.homedir();
  if (process.platform === "win32") {
    const roots = [];
    const local = process.env.LOCALAPPDATA;
    if (local) {
      roots.push(path.join(local, "JianyingPro", DRAFTS_SUFFIX));
    }
    roots.push(path.join(home, "AppData", "Local", "JianyingPro", DRAFTS_SUFFIX));
    return roots;
  }

  return [
    path.join(home, "Movies", "JianyingPro", DRAFTS_SUFFIX),
    path.join(
      home,
      "Library",
      "Containers",
      "com.lemon.lvpro",
      "Data",
      "Movies",
      "JianyingPro",
      DRAFTS_SUFFIX,
    ),
  ];
}

function detectDefaultDraftsRoot() {
  for (const candidate of defaultDraftsRoots()) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  return defaultDraftsRoots()[0];
}

function readConfig() {
  try {
    return JSON.parse(fs.readFileSync(configPath(), "utf-8"));
  } catch {
    return {};
  }
}

function normalizeDraftsRoot(raw) {
  const trimmed = String(raw || "").trim();
  if (!trimmed) {
    throw new Error("请填写剪映草稿目录");
  }

  const resolved = path.resolve(trimmed);
  if (!fs.existsSync(resolved)) {
    throw new Error(`目录不存在: ${resolved}`);
  }

  if (path.basename(resolved) === "com.lveditor.draft") {
    return resolved;
  }

  const nested = path.join(resolved, "User Data", "Projects", "com.lveditor.draft");
  if (fs.existsSync(nested) && fs.statSync(nested).isDirectory()) {
    return nested;
  }

  if (path.basename(resolved) === "JianyingPro") {
    const candidate = path.join(resolved, DRAFTS_SUFFIX);
    if (fs.existsSync(candidate) && fs.statSync(candidate).isDirectory()) {
      return candidate;
    }
  }

  return resolved;
}

function getJianyingDraftsRoot() {
  const saved = readConfig().draftsRoot;
  if (saved && fs.existsSync(saved)) {
    return saved;
  }
  return detectDefaultDraftsRoot();
}

function setJianyingDraftsRoot(draftsRoot) {
  const resolved = normalizeDraftsRoot(draftsRoot);
  if (!fs.statSync(resolved).isDirectory()) {
    throw new Error(`不是有效目录: ${resolved}`);
  }

  const config = readConfig();
  config.draftsRoot = resolved;
  fs.mkdirSync(path.dirname(configPath()), { recursive: true });
  fs.writeFileSync(configPath(), `${JSON.stringify(config, null, 2)}\n`, "utf-8");
  return resolved;
}

function resolveJianyingDraftDir(name, draftsRoot) {
  const root = draftsRoot?.trim() ? normalizeDraftsRoot(draftsRoot) : getJianyingDraftsRoot();
  return path.join(root, String(name || "").trim());
}

module.exports = {
  defaultDraftsRoots,
  detectDefaultDraftsRoot,
  getJianyingDraftsRoot,
  setJianyingDraftsRoot,
  normalizeDraftsRoot,
  resolveJianyingDraftDir,
};

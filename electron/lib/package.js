const fs = require("fs");
const path = require("path");
const AdmZip = require("adm-zip");

function isProtocolJson(filePath) {
  try {
    const data = JSON.parse(fs.readFileSync(filePath, "utf-8"));
    return Boolean(data.materials && data.tracks);
  } catch {
    return false;
  }
}

function findProtocolJson(rootDir) {
  const entries = fs.readdirSync(rootDir, { withFileTypes: true });
  const jsonFiles = entries
    .filter((e) => e.isFile() && e.name.endsWith(".json"))
    .map((e) => path.join(rootDir, e.name));

  for (const filePath of jsonFiles) {
    if (isProtocolJson(filePath)) {
      return filePath;
    }
  }

  for (const entry of entries) {
    if (!entry.isDirectory() || entry.name.startsWith(".") || entry.name === "__MACOSX") {
      continue;
    }
    const nested = findProtocolJson(path.join(rootDir, entry.name));
    if (nested) {
      return nested;
    }
  }

  return null;
}

/** 协议内媒体路径相对协议 JSON 所在目录解析 */
function resolveProtocolPath(raw, protocolDir) {
  if (!raw || typeof raw !== "string") {
    return null;
  }
  if (path.isAbsolute(raw)) {
    return fs.existsSync(raw) ? raw : null;
  }
  const rel = raw.replace(/^\.\//, "");
  const candidates = [
    path.join(protocolDir, raw),
    path.join(protocolDir, rel),
  ];
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  return null;
}

function collectProtocolMediaPaths(protocol) {
  const paths = [];
  const materials = protocol.materials || {};
  for (const category of ["videos", "audios", "images"]) {
    for (const item of materials[category] || []) {
      if (item.path) {
        paths.push(item.path);
      }
    }
  }
  for (const item of materials.texts || []) {
    try {
      const content = JSON.parse(item.content || "{}");
      for (const style of content.styles || []) {
        const fontPath = style.font && style.font.path;
        if (fontPath) {
          paths.push(fontPath);
        }
      }
    } catch {
      // ignore malformed rich text
    }
  }
  return paths;
}

/** 资源根目录 = 协议 JSON 所在目录（./assets/、./abc/ 等相对它解析） */
function resolveResourceRoot(protocolPath) {
  return path.resolve(path.dirname(protocolPath));
}

function validateProtocolPackage(protocolPath, protocol) {
  const protocolDir = resolveResourceRoot(protocolPath);
  const mediaPaths = collectProtocolMediaPaths(protocol);
  if (!mediaPaths.length) {
    return;
  }
  const missing = mediaPaths.filter((rel) => !resolveProtocolPath(rel, protocolDir));
  if (missing.length) {
    throw new Error(
      "素材包不完整：协议引用的媒体文件未找到。\n"
      + `  协议: ${protocolPath}\n`
      + `  协议目录: ${protocolDir}\n`
      + `  缺失示例: ${missing.slice(0, 3).join(", ")}`
      + (missing.length > 3 ? ` …共 ${missing.length} 个` : ""),
    );
  }
}

function extractZip(zipPath) {
  const absZip = path.resolve(zipPath);
  if (!fs.existsSync(absZip)) {
    throw new Error(`压缩包不存在: ${absZip}`);
  }

  const parentDir = path.dirname(absZip);
  const baseName = path.basename(absZip, path.extname(absZip));
  // 素材包解压目录（勿与草稿输出目录同名）
  const packageDir = path.join(parentDir, baseName);

  fs.rmSync(packageDir, { recursive: true, force: true });
  fs.mkdirSync(packageDir, { recursive: true });

  const zip = new AdmZip(absZip);
  zip.extractAllTo(packageDir, true);

  const protocolPath = findProtocolJson(packageDir);
  if (!protocolPath) {
    throw new Error(`在压缩包中未找到协议 JSON（需含 materials、tracks 字段）: ${packageDir}`);
  }

  const protocol = JSON.parse(fs.readFileSync(protocolPath, "utf-8"));
  validateProtocolPackage(protocolPath, protocol);
  const resourceRoot = resolveResourceRoot(protocolPath);

  return {
    zipPath: absZip,
    parentDir,
    extractDir: packageDir,
    protocolPath,
    resourceRoot,
    defaultDraftName: `${baseName}_draft`,
  };
}

module.exports = {
  extractZip,
  findProtocolJson,
  isProtocolJson,
  resolveResourceRoot,
  resolveProtocolPath,
  collectProtocolMediaPaths,
  validateProtocolPackage,
};

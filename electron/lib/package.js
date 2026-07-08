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

/** 找到含 assets/ 或 fonts/ 的资源根目录（协议 JSON 可能在子目录） */
function resolveResourceRoot(protocolPath, packageDir) {
  let dir = path.resolve(path.dirname(protocolPath));
  const root = path.resolve(packageDir);

  while (dir === root || dir.startsWith(`${root}${path.sep}`)) {
    if (
      fs.existsSync(path.join(dir, "assets"))
      || fs.existsSync(path.join(dir, "fonts"))
    ) {
      return dir;
    }
    const parent = path.dirname(dir);
    if (parent === dir) {
      break;
    }
    dir = parent;
  }

  return path.dirname(protocolPath);
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

  const resourceRoot = resolveResourceRoot(protocolPath, packageDir);
  const assetsDir = path.join(resourceRoot, "assets");
  if (!fs.existsSync(assetsDir)) {
    throw new Error(
      `素材包不完整：未找到 assets/ 目录。\n`
      + `  解压目录: ${packageDir}\n`
      + `  协议: ${protocolPath}\n`
      + `  请确认 zip 内包含 assets/、fonts/ 与协议 JSON。`,
    );
  }

  return {
    zipPath: absZip,
    parentDir,
    extractDir: packageDir,
    protocolPath,
    resourceRoot,
    defaultDraftName: `${baseName}_draft`,
  };
}

module.exports = { extractZip, findProtocolJson, isProtocolJson, resolveResourceRoot };

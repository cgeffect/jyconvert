const path = require("path");
const fs = require("fs");
const { app } = require("electron");

function pythonRoot() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, "python");
  }
  return path.resolve(__dirname, "../../python");
}

/** PyInstaller 打包后的内嵌二进制（优先使用） */
function bundledPythonBinary() {
  const name = process.platform === "win32" ? "jyconvert-py.exe" : "jyconvert-py";
  const candidates = [];

  if (app.isPackaged) {
    candidates.push(path.join(process.resourcesPath, name));
  } else {
    candidates.push(path.resolve(__dirname, "../../bin", name));
  }

  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  return null;
}

function pythonCommand() {
  return process.env.JYCONVERT_PYTHON || "python3";
}

function assertPythonReady() {
  if (bundledPythonBinary()) {
    return;
  }
  const root = pythonRoot();
  const cli = path.join(root, "cli.py");
  if (!fs.existsSync(cli)) {
    throw new Error(
      "找不到 Python 后端。请运行 npm run build:python 打包，或确保 python/cli.py 存在。",
    );
  }
}

function bundledYtdlpBinary() {
  const name = process.platform === "win32" ? "yt-dlp.exe" : "yt-dlp";
  const candidates = [];

  if (app.isPackaged) {
    candidates.push(path.join(process.resourcesPath, "yt-dlp.app", name));
    candidates.push(path.join(process.resourcesPath, name));
  } else {
    candidates.push(path.resolve(__dirname, "../../bin/yt-dlp.app", name));
    candidates.push(path.resolve(__dirname, "../../bin", name));
  }

  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  return null;
}

function assertYtdlpReady() {
  if (bundledYtdlpBinary()) {
    return;
  }
  throw new Error(
    "找不到内嵌 yt-dlp。请运行: bash scripts/fetch-ytdlp.sh",
  );
}

function bundledFfmpegBinary() {
  const name = process.platform === "win32" ? "ffmpeg.exe" : "ffmpeg";
  const candidates = [];

  if (app.isPackaged) {
    candidates.push(path.join(process.resourcesPath, name));
  } else {
    candidates.push(path.resolve(__dirname, "../../bin", name));
  }

  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  return null;
}

module.exports = {
  pythonRoot,
  bundledPythonBinary,
  bundledYtdlpBinary,
  bundledFfmpegBinary,
  pythonCommand,
  assertPythonReady,
  assertYtdlpReady,
};

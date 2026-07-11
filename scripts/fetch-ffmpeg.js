#!/usr/bin/env node
/** 将 @ffmpeg-installer 提供的 ffmpeg 复制到 bin/，随 Electron 打包分发。 */
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");

const root = path.join(__dirname, "..");
const destName = process.platform === "win32" ? "ffmpeg.exe" : "ffmpeg";
const dest = path.join(root, "bin", destName);

function ffmpegWorks(binPath) {
  try {
    execFileSync(binPath, ["-version"], { stdio: "pipe", timeout: 8000 });
    return true;
  } catch {
    return false;
  }
}

function shouldRefresh(src, current) {
  if (!fs.existsSync(current)) {
    return true;
  }
  try {
    const srcStat = fs.statSync(src);
    const dstStat = fs.statSync(current);
    if (srcStat.size !== dstStat.size) {
      return true;
    }
  } catch {
    return true;
  }
  return !ffmpegWorks(current);
}

const { path: src } = require("@ffmpeg-installer/ffmpeg");

if (!shouldRefresh(src, dest)) {
  console.log(`==> ffmpeg 已存在且可用: ${dest}`);
  process.exit(0);
}

if (fs.existsSync(dest)) {
  console.log(`==> 刷新 ffmpeg: ${dest}`);
}

fs.mkdirSync(path.dirname(dest), { recursive: true });
fs.copyFileSync(src, dest);
if (process.platform !== "win32") {
  fs.chmodSync(dest, 0o755);
}

if (!ffmpegWorks(dest)) {
  console.error(`==> ffmpeg 复制后仍不可用: ${dest}`);
  process.exit(1);
}

console.log(`==> ffmpeg → ${dest}`);

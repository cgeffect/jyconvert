#!/usr/bin/env node
/** 将 @ffmpeg-installer 提供的 ffmpeg 复制到 bin/，随 Electron 打包分发。 */
const fs = require("fs");
const path = require("path");

const root = path.join(__dirname, "..");
const destName = process.platform === "win32" ? "ffmpeg.exe" : "ffmpeg";
const dest = path.join(root, "bin", destName);

if (fs.existsSync(dest)) {
  console.log(`==> ffmpeg 已存在: ${dest}`);
  process.exit(0);
}

const { path: src } = require("@ffmpeg-installer/ffmpeg");
fs.mkdirSync(path.dirname(dest), { recursive: true });
fs.copyFileSync(src, dest);
if (process.platform !== "win32") {
  fs.chmodSync(dest, 0o755);
}
console.log(`==> ffmpeg → ${dest}`);

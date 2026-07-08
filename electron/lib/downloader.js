const path = require("path");
const { spawn } = require("child_process");
const fs = require("fs");
const { app } = require("electron");
const { bundledYtdlpBinary, assertYtdlpReady, pythonCommand } = require("./paths");

function downloaderRoot() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, "downloader");
  }
  return path.resolve(__dirname, "../../downloader");
}

function spawnEnv(extra = {}) {
  const ytdlp = bundledYtdlpBinary();
  assertYtdlpReady();
  const base = { ...process.env, ...extra };
  if (ytdlp) {
    base.YTDLP_PATH = ytdlp;
  }
  const pathExtra = ["/opt/homebrew/bin", "/usr/local/bin"].filter((dir) => fs.existsSync(dir));
  if (pathExtra.length) {
    base.PATH = `${pathExtra.join(":")}:${base.PATH || ""}`;
  }
  return base;
}

function runDownloaderCli(args, { onLine, allowNonZero = false } = {}) {
  assertYtdlpReady();
  const cliPath = path.join(downloaderRoot(), "cli.py");
  if (!fs.existsSync(cliPath)) {
    return Promise.reject(new Error(`找不到 downloader/cli.py: ${cliPath}`));
  }

  return new Promise((resolve, reject) => {
    const child = spawn(pythonCommand(), [cliPath, ...args], {
      cwd: downloaderRoot(),
      env: spawnEnv(),
    });

    let stdout = "";
    let stderr = "";

    const handleChunk = (stream, chunk, isErr) => {
      const text = chunk.toString();
      if (isErr) {
        stderr += text;
      } else {
        stdout += text;
      }
      if (onLine) {
        for (const line of text.split("\n")) {
          if (line.trim()) {
            onLine(line);
          }
        }
      }
    };

    child.stdout.on("data", (chunk) => handleChunk("stdout", chunk, false));
    child.stderr.on("data", (chunk) => handleChunk("stderr", chunk, true));

    child.on("error", (err) => {
      reject(new Error(`无法启动 downloader: ${err.message}`));
    });

    child.on("close", (code) => {
      if (code === 0 || allowNonZero) {
        resolve({ stdout, stderr, code });
        return;
      }
      const combined = [stderr, stdout].filter(Boolean).join("\n").trim();
      const failMatch = combined.match(/下载失败:\s*([\s\S]+)/);
      if (failMatch) {
        reject(new Error(failMatch[1].trim()));
        return;
      }
      reject(new Error(combined || `downloader 退出码 ${code}`));
    });
  });
}

function extractUrl(text) {
  return runDownloaderCli(["extract", text]).then(({ stdout }) => {
    const urls = stdout
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
    if (!urls.length) {
      throw new Error("未在文案中找到链接");
    }
    return urls[0];
  });
}

function probeVideo(input, { cookiesBrowser = "chrome" } = {}) {
  const args = ["probe", input, "--cookies-browser", cookiesBrowser];
  return runDownloaderCli(args).then(({ stdout }) => stdout);
}

function downloadVideo(input, { outputDir, cookiesBrowser = "chrome", cookiesFile, onProgress } = {}) {
  const args = [
    "download",
    input,
    "-o",
    outputDir,
    "--cookies-browser",
    cookiesBrowser,
    "-v",
  ];
  if (cookiesFile) {
    args.push("--cookies-file", cookiesFile);
  }
  return runDownloaderCli(args, { onLine: onProgress });
}

function checkChromeCookies() {
  return runDownloaderCli(["check-cookies"], { allowNonZero: true }).then(({ stdout }) => {
    const line = stdout.trim().split("\n").find((row) => row.trim().startsWith("{"));
    if (!line) {
      throw new Error("Cookie 检测返回格式异常");
    }
    const data = JSON.parse(line);
    return {
      total: Number(data.total) || 0,
      douyin: Number(data.douyin) || 0,
      ok: Boolean(data.ok),
      message: data.message || "",
      dbPath: data.db_path || null,
    };
  });
}

module.exports = {
  extractUrl,
  probeVideo,
  downloadVideo,
  checkChromeCookies,
  runDownloaderCli,
};

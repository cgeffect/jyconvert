const fs = require("fs");
const https = require("https");
const http = require("http");
const path = require("path");
const { URL } = require("url");

const IDLE_TIMEOUT_MS = 12000;
const REDIRECT_LIMIT = 8;
const PROGRESS_INTERVAL_MS = 450;

function sanitizeFilename(name) {
  return String(name || "douyin_video")
    .replace(/[\\/:*?"<>|]/g, "_")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 80);
}

function normalizeDownloadUrl(url) {
  const text = String(url || "").trim();
  if (text.startsWith("//")) {
    return `https:${text}`;
  }
  return text;
}

function formatBytes(bytes) {
  if (bytes >= 1024 * 1024) {
    return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
  }
  if (bytes >= 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${bytes} B`;
}

function createThrottledProgress(onProgress) {
  let lastEmitAt = 0;
  let lastPercent = -1;

  return (update, { force = false } = {}) => {
    if (!onProgress) {
      return;
    }
    if (update.phase === "downloading" && !force) {
      const now = Date.now();
      const percent = Number(update.percent || 0);
      if (now - lastEmitAt < PROGRESS_INTERVAL_MS && Math.abs(percent - lastPercent) < 1) {
        return;
      }
      lastEmitAt = now;
      lastPercent = percent;
    }
    onProgress(update);
  };
}

function downloadFile(url, destPath, onProgress, options = {}) {
  const { redirectCount = 0, cookieHeader = "" } = options;

  return new Promise((resolve, reject) => {
    const normalized = normalizeDownloadUrl(url);
    const parsed = new URL(normalized);
    const client = parsed.protocol === "https:" ? https : http;
    const emitProgress = createThrottledProgress(onProgress);

    const request = client.get(
      normalized,
      {
        headers: {
          Referer: "https://www.douyin.com/",
          "User-Agent":
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
          ...(cookieHeader ? { Cookie: cookieHeader } : {}),
        },
      },
      (response) => {
        if (response.statusCode >= 300 && response.statusCode < 400 && response.headers.location) {
          response.resume();
          if (redirectCount >= REDIRECT_LIMIT) {
            reject(new Error("下载重定向次数过多"));
            return;
          }
          downloadFile(response.headers.location, destPath, onProgress, {
            redirectCount: redirectCount + 1,
            cookieHeader,
          })
            .then(resolve)
            .catch(reject);
          return;
        }

        if (response.statusCode !== 200) {
          reject(new Error(`下载失败，HTTP ${response.statusCode}`));
          response.resume();
          return;
        }

        const declaredTotal = Number(response.headers["content-length"] || 0);
        let received = 0;
        let lastDataAt = Date.now();
        let settled = false;
        const file = fs.createWriteStream(destPath);

        function progressUpdate(done = false) {
          if (done) {
            emitProgress(
              {
                phase: "done",
                percent: 100,
                received,
                total: declaredTotal || received,
                message: `下载完成 ${formatBytes(received)}`,
              },
              { force: true },
            );
            return;
          }

          if (declaredTotal > 0) {
            const percent = Math.min(100, (received / declaredTotal) * 100);
            emitProgress({
              phase: "downloading",
              percent,
              received,
              total: declaredTotal,
              message: `下载中 ${percent.toFixed(1)}% (${formatBytes(received)} / ${formatBytes(declaredTotal)})`,
            });
            return;
          }

          emitProgress({
            phase: "downloading",
            percent: null,
            received,
            total: 0,
            message: `已下载 ${formatBytes(received)}`,
          });
        }

        function finishOk(extraMessage) {
          if (settled) {
            return;
          }
          settled = true;
          clearInterval(idleTimer);
          if (extraMessage) {
            emitProgress(
              {
                phase: "done",
                percent: 100,
                received,
                total: declaredTotal || received,
                message: extraMessage,
              },
              { force: true },
            );
          } else {
            progressUpdate(true);
          }
          resolve(destPath);
        }

        function finishError(err) {
          if (settled) {
            return;
          }
          settled = true;
          clearInterval(idleTimer);
          request.destroy();
          response.destroy();
          file.destroy();
          fs.unlink(destPath, () => reject(err));
        }

        const idleTimer = setInterval(() => {
          if (settled || received === 0) {
            return;
          }
          if (Date.now() - lastDataAt < IDLE_TIMEOUT_MS) {
            return;
          }
          request.destroy();
          response.destroy();
          file.end(() => {
            finishOk(`下载完成（连接空闲 ${Math.round(IDLE_TIMEOUT_MS / 1000)}s，共 ${formatBytes(received)}）`);
          });
        }, 2000);

        response.on("data", (chunk) => {
          received += chunk.length;
          lastDataAt = Date.now();
          progressUpdate(false);
        });

        response.pipe(file);

        file.on("finish", () => finishOk());
        file.on("error", finishError);
        response.on("error", finishError);
        request.on("error", finishError);
      },
    );

    request.on("error", reject);
  });
}

async function downloadDouyinVideoToDir(meta, outputDir, onProgress, { cookieHeader = "" } = {}) {
  const filename = `${sanitizeFilename(meta.title)} [${meta.awemeId}].mp4`;
  const destPath = path.join(outputDir, filename);
  fs.mkdirSync(outputDir, { recursive: true });
  onProgress?.({
    phase: "downloading",
    percent: 0,
    message: `开始下载：${meta.title}`,
  });
  await downloadFile(meta.playUrl, destPath, onProgress, { cookieHeader });
  return destPath;
}

module.exports = {
  downloadDouyinVideoToDir,
  sanitizeFilename,
};

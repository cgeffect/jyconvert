const fs = require("fs");

function normalizeProgressUpdate(update, progressId) {
  if (typeof update === "string") {
    const text = update.trim();
    const percentMatch = text.match(/([\d.]+)\s*%/);
    const isByteProgress = text.startsWith("下载中") || text.startsWith("已下载");
    return {
      progressId,
      type: isByteProgress ? "progress" : "stage",
      phase: isByteProgress ? "downloading" : "stage",
      percent: percentMatch ? parseFloat(percentMatch[1]) : undefined,
      message: text,
    };
  }

  return {
    progressId,
    type: update.phase === "stage" ? "stage" : "progress",
    phase: update.phase || "downloading",
    percent: update.percent,
    received: update.received,
    total: update.total,
    fileSize: update.fileSize,
    message: update.message || "",
  };
}

function createDownloadProgressEmitter(sender, progressId) {
  return (update) => {
    if (sender.isDestroyed()) {
      return;
    }
    sender.send("download-progress", normalizeProgressUpdate(update, progressId));
  };
}

function fileSizeOf(filepath) {
  if (!filepath || !fs.existsSync(filepath)) {
    return 0;
  }
  try {
    return fs.statSync(filepath).size;
  } catch {
    return 0;
  }
}

function parseDownloadOutput(stdout) {
  const fileMatch = stdout.match(/文件:\s*(.+)/);
  const urlMatch = stdout.match(/链接:\s*(.+)/);
  return {
    filepath: fileMatch ? fileMatch[1].trim() : null,
    url: urlMatch ? urlMatch[1].trim() : null,
  };
}

function isDouyinInput(text) {
  return /douyin\.com|v\.douyin\.com/i.test(String(text || ""));
}

module.exports = {
  normalizeProgressUpdate,
  createDownloadProgressEmitter,
  fileSizeOf,
  parseDownloadOutput,
  isDouyinInput,
};

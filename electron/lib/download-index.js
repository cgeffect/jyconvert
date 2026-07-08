const fs = require("fs");
const path = require("path");

function csvCell(value) {
  const text = String(value ?? "");
  if (/[",\r\n]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

function formatTimestampForFilename(date = new Date()) {
  const pad = (value) => String(value).padStart(2, "0");
  return [
    date.getFullYear(),
    pad(date.getMonth() + 1),
    pad(date.getDate()),
  ].join("-") + `_${pad(date.getHours())}-${pad(date.getMinutes())}-${pad(date.getSeconds())}`;
}

function writeDownloadIndexCsv(outputDir, rows) {
  const dir = path.resolve(String(outputDir || "").trim());
  if (!dir) {
    throw new Error("缺少保存目录");
  }
  fs.mkdirSync(dir, { recursive: true });

  const lines = ["分享内容,视频文件名,视频下载链接"];
  for (const row of rows) {
    lines.push(
      `${csvCell(row.shareText)},${csvCell(row.filename || "")},${csvCell(row.downloadUrl || "")}`,
    );
  }

  const filePath = path.join(dir, `下载记录_${formatTimestampForFilename()}.csv`);
  fs.writeFileSync(filePath, `\uFEFF${lines.join("\n")}\n`, "utf-8");
  return filePath;
}

module.exports = {
  writeDownloadIndexCsv,
};

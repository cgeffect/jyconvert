const $ = (id) => document.getElementById(id);

const els = {
  input: $("input-text"),
  inputFullscreen: $("input-fullscreen"),
  inputFullscreenText: $("input-text-fullscreen"),
  btnInputFullscreen: $("btn-input-fullscreen"),
  btnInputFullscreenClose: $("btn-input-fullscreen-close"),
  outputDir: $("output-dir"),
  btnPickDir: $("btn-pick-dir"),
  useCookies: $("use-cookies"),
  cookiesBrowser: $("cookies-browser"),
  cookiesFile: $("cookies-file"),
  btnPickCookies: $("btn-pick-cookies"),
  btnClearCookies: $("btn-clear-cookies"),
  btnDouyinLogin: $("btn-douyin-login"),
  btnImportSessionCookies: $("btn-import-session-cookies"),
  btnCheckCookies: $("btn-check-cookies"),
  cookieStatus: $("cookie-status"),
  extractPreview: $("extract-preview"),
  progressBox: $("progress-box"),
  progressSummary: $("progress-summary"),
  progressList: $("progress-list"),
  resultBox: $("result-box"),
  status: $("status"),
  btnDownload: $("btn-download"),
};

let unsubscribeProgress = null;
let unsubscribeLoginClosed = null;
let activeProgressId = null;

function openInputFullscreen() {
  els.inputFullscreenText.value = els.input.value;
  els.inputFullscreen.classList.remove("hidden");
  els.inputFullscreen.setAttribute("aria-hidden", "false");
  els.inputFullscreenText.focus();
}

function closeInputFullscreen() {
  els.input.value = els.inputFullscreenText.value;
  els.inputFullscreen.classList.add("hidden");
  els.inputFullscreen.setAttribute("aria-hidden", "true");
  updateInputPreview();
}

function setStatus(message, type = "info") {
  if (!message) {
    els.status.classList.add("hidden");
    els.status.textContent = "";
    return;
  }
  els.status.textContent = message;
  els.status.className = `status-msg ${type}`;
  els.status.classList.remove("hidden");
}

function initProgressList(items) {
  els.progressList.innerHTML = items
    .map(
      (item) => `
        <div class="dl-progress-item is-waiting" data-index="${item.index}">
          <div class="dl-progress-label">${escapeHtml(item.label)}</div>
          <div class="dl-progress-bar"><div class="dl-progress-fill"></div></div>
          <div class="dl-progress-text">等待中</div>
        </div>
      `,
    )
    .join("");
  els.progressSummary.textContent =
    items.length > 1 ? `共 ${items.length} 个视频` : "正在下载";
}

function formatSize(bytes) {
  const value = Number(bytes);
  if (!Number.isFinite(value) || value < 0) {
    return null;
  }
  if (value >= 1024 * 1024 * 1024) {
    return `${(value / 1024 / 1024 / 1024).toFixed(2)} GB`;
  }
  if (value >= 1024 * 1024) {
    return `${(value / 1024 / 1024).toFixed(1)} MB`;
  }
  if (value >= 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  return `${Math.round(value)} B`;
}

function parseSizesFromMessage(message) {
  const text = String(message || "");
  const match = text.match(/\(([\d.]+\s*(?:MB|KB|GB|B))\s*\/\s*([\d.]+\s*(?:MB|KB|GB|B))\)/i);
  if (!match) {
    return null;
  }
  return { received: match[1].trim(), total: match[2].trim() };
}

function getDoneFileSize(payload) {
  const size = formatSize(payload.fileSize || payload.total || payload.received);
  if (size) {
    return size;
  }
  const parsed = parseSizesFromMessage(payload.message || "");
  return parsed?.total || parsed?.received || null;
}

function renderDoneStatusRow(container, label, sizeText) {
  if (!container) {
    return;
  }
  if (sizeText) {
    container.classList.add("dl-status-row");
    container.innerHTML = `<span>${escapeHtml(label)}</span><span class="dl-status-size">${escapeHtml(sizeText)}</span>`;
    return;
  }
  container.classList.remove("dl-status-row");
  container.textContent = label;
}

function setProgressText(textEl, payload) {
  if (!textEl) {
    return;
  }
  const phase = payload.phase || payload.type;
  if (phase === "done") {
    renderDoneStatusRow(textEl, "下载完成", getDoneFileSize(payload));
    return;
  }
  textEl.classList.remove("dl-status-row");
  textEl.textContent = friendlyProgressText(payload);
}

function friendlyProgressText(payload) {
  const raw = String(payload.message || "").trim();
  const phase = payload.phase || payload.type;
  const receivedSize = formatSize(payload.received);
  const totalSize = formatSize(payload.total);
  const parsedSizes = parseSizesFromMessage(raw);
  const percent =
    typeof payload.percent === "number" && Number.isFinite(payload.percent)
      ? Math.round(payload.percent)
      : null;

  if (phase === "stage" || payload.type === "stage") {
    if (/解析|获取|浏览器/.test(raw)) {
      return "正在获取视频信息…";
    }
    if (/解析成功|开始下载/.test(raw)) {
      return "已找到视频，准备下载…";
    }
    if (/失败|yt-dlp/.test(raw)) {
      return "正在尝试其他方式…";
    }
    if (/Cookie|登录/.test(raw)) {
      return "请先完成抖音登录";
    }
    return "处理中…";
  }

  if (receivedSize && totalSize) {
    const suffix = percent != null ? `（${percent}%）` : "";
    return `已下载 ${receivedSize} / 共 ${totalSize}${suffix}`;
  }

  if (parsedSizes) {
    const suffix = percent != null ? `（${percent}%）` : "";
    return `已下载 ${parsedSizes.received} / 共 ${parsedSizes.total}${suffix}`;
  }

  if (receivedSize) {
    return `已下载 ${receivedSize}（视频大小未知）`;
  }

  if (raw.startsWith("已下载")) {
    const single = raw.replace(/^已下载\s*/, "").trim();
    return single ? `已下载 ${single}（视频大小未知）` : "正在下载…";
  }

  if (percent != null) {
    return `正在下载 ${percent}%`;
  }

  return "正在下载…";
}

function friendlyErrorMessage(message) {
  const text = String(message || "").trim();
  if (!text) {
    return "下载失败，请稍后重试";
  }
  if (/Cookie|sessionid|登录/.test(text)) {
    return "请先登录抖音后再试";
  }
  if (/yt-dlp|接口/.test(text)) {
    return "暂时无法下载这个视频，请确认链接有效且已登录";
  }
  if (text.length > 60) {
    return `${text.slice(0, 60)}…`;
  }
  return text;
}

function getProgressRow(index) {
  return els.progressList.querySelector(`.dl-progress-item[data-index="${index}"]`);
}

function setProgressRowState(index, ...states) {
  const row = getProgressRow(index);
  if (!row) {
    return;
  }
  row.classList.remove("is-waiting", "is-active", "is-stage", "is-done", "is-fail");
  for (const state of states) {
    if (state) {
      row.classList.add(state);
    }
  }
}

function updateProgressRow(index, payload) {
  const row = getProgressRow(index);
  if (!row) {
    return;
  }

  const fill = row.querySelector(".dl-progress-fill");
  const text = row.querySelector(".dl-progress-text");
  const phase = payload.phase || payload.type;

  if (phase === "stage" || payload.type === "stage") {
    setProgressRowState(index, "is-stage", "is-active");
    if (fill) {
      fill.style.width = "35%";
    }
    if (text) {
      setProgressText(text, payload);
    }
    return;
  }

  if (phase === "done") {
    setProgressRowState(index, "is-done");
    if (fill) {
      fill.style.width = "100%";
    }
    if (text) {
      setProgressText(text, payload);
    }
    return;
  }

  setProgressRowState(index, "is-active");
  row.classList.remove("is-stage");

  const percent =
    typeof payload.percent === "number" && Number.isFinite(payload.percent)
      ? Math.max(0, Math.min(100, payload.percent))
      : null;

  if (fill) {
    fill.style.width = percent == null ? "12%" : `${percent}%`;
  }
  if (text) {
    setProgressText(text, { ...payload, percent });
  }
}

function markProgressRowFailed(index, message) {
  setProgressRowState(index, "is-fail");
  const row = getProgressRow(index);
  if (!row) {
    return;
  }
  const fill = row.querySelector(".dl-progress-fill");
  const text = row.querySelector(".dl-progress-text");
  if (fill) {
    fill.style.width = "100%";
  }
  if (text) {
    text.textContent = friendlyErrorMessage(message);
  }
}

function handleDownloadProgress(payload) {
  const progressId = payload.progressId || activeProgressId || 1;
  updateProgressRow(progressId, payload);
}

function setCookieStatus(text, kind = "info") {
  els.cookieStatus.textContent = text;
  els.cookieStatus.className = `field-hint cookie-status ${kind}`;
}

async function refreshCookieStatus() {
  const [chromeStatus, sessionStatus] = await Promise.all([
    window.jyDownload.checkChromeCookies(),
    window.jyDownload.checkDouyinSessionCookies(),
  ]);

  if (sessionStatus.ok) {
    setCookieStatus("已登录，可以直接下载", "ok");
    return;
  }

  if (sessionStatus.count > 0) {
    setCookieStatus("登录可能不完整，请重新打开抖音登录", "warn");
    return;
  }

  if (chromeStatus.ok) {
    setCookieStatus("检测到浏览器已登录抖音，也可以直接试试下载", "ok");
    return;
  }

  setCookieStatus("尚未登录，请先点「打开抖音登录」", "warn");
}

async function importSessionCookies({ silent = false } = {}) {
  const result = await window.jyDownload.exportDouyinSessionCookies();
  if (result.ok) {
    els.cookiesFile.value = result.filePath;
    setCookieStatus("已登录，可以直接下载", "ok");
    if (!silent) {
      setStatus("登录信息已更新", "success");
    }
  } else {
    setCookieStatus("还没登录成功，请在弹出窗口里完成登录", "warn");
    if (!silent) {
      setStatus("请先完成抖音登录", "error");
    }
  }
  return result;
}

async function resolveDownloadOptions() {
  let cookiesFile = els.cookiesFile.value.trim() || null;
  if (!cookiesFile) {
    const sessionStatus = await window.jyDownload.checkDouyinSessionCookies();
    if (sessionStatus.ok) {
      const imported = await importSessionCookies({ silent: true });
      if (imported.ok) {
        cookiesFile = imported.filePath;
      }
    }
  }

  let cookiesBrowser = "none";
  if (!cookiesFile && els.useCookies.checked) {
    cookiesBrowser = els.cookiesBrowser.value;
  }

  return { cookiesBrowser, cookiesFile };
}

function updateInputPreview() {
  const text = els.input.value.trim();
  if (!text) {
    els.extractPreview.classList.add("hidden");
    return;
  }

  const items = window.parseBatchInputs(text);
  if (!items.length) {
    els.extractPreview.classList.add("hidden");
    return;
  }

  if (items.length === 1) {
    els.extractPreview.textContent = "已识别 1 个视频";
  } else {
    els.extractPreview.textContent = `已识别 ${items.length} 个视频，将依次下载`;
  }
  els.extractPreview.classList.remove("hidden");
}

function fileNameFromPath(filepath) {
  if (!filepath) {
    return "";
  }
  const parts = String(filepath).split(/[/\\]/);
  return parts[parts.length - 1] || "";
}

async function saveDownloadIndex(outputDir, results) {
  const rows = results.map((item) => ({
    shareText: item.shareText || "",
    filename: item.ok ? fileNameFromPath(item.filepath) : "",
    downloadUrl: item.downloadUrl || "",
  }));
  const hasFile = rows.some((row) => row.filename);
  if (!hasFile) {
    return null;
  }
  return window.jyDownload.writeDownloadIndex({ outputDir, rows });
}

function renderSingleResult(result, indexCsv) {
  const sizeText = formatSize(result.fileSize);
  const titleHtml = sizeText
    ? `<h3 class="dl-status-row result-title-row"><span>下载完成</span><span class="dl-status-size">${escapeHtml(sizeText)}</span></h3>`
    : "<h3>下载完成</h3>";
  const indexHint = indexCsv
    ? `<p class="result-path">已生成对照表「${escapeHtml(indexCsv.filename)}」，方便查找每个分享对应的视频</p>`
    : "";
  els.resultBox.innerHTML = `
    ${titleHtml}
    <p class="result-path">视频已保存到电脑</p>
    ${indexHint}
    <button type="button" class="btn-secondary" id="btn-open-result">打开文件夹查看</button>
  `;
  els.resultBox.classList.remove("hidden");
  $("btn-open-result").addEventListener("click", () => {
    window.jyDownload.openInFinder(result.filepath || result.outputDir);
  });
}

function renderBatchResult(summary, indexCsv) {
  const title =
    summary.failed === 0
      ? `${summary.success} 个视频全部下载完成`
      : `完成 ${summary.success} 个，${summary.failed} 个未成功`;

  const indexHint = indexCsv
    ? `<p class="result-path">已生成对照表「${escapeHtml(indexCsv.filename)}」，可用 Excel 或 Numbers 打开查看</p>`
    : "";

  const failHint =
    summary.failed > 0
      ? `<p class="result-path">未成功的视频请查看上方进度说明</p>`
      : `<p class="result-path">视频已保存到电脑</p>`;

  els.resultBox.innerHTML = `
    <h3>${title}</h3>
    ${failHint}
    ${indexHint}
    <button type="button" class="btn-secondary" id="btn-open-result">打开文件夹查看</button>
  `;
  els.resultBox.classList.remove("hidden");
  $("btn-open-result").addEventListener("click", () => {
    window.jyDownload.openInFinder(summary.outputDir);
  });
}

function previewLabel(_input, index) {
  return `视频 ${index}`;
}

async function downloadOne(input, outputDir, options, index) {
  activeProgressId = index;
  setProgressRowState(index, "is-stage", "is-active");
  updateProgressRow(index, { phase: "stage", message: "正在获取视频信息…" });

  return window.jyDownload.startDownload({
    input,
    outputDir,
    cookiesBrowser: options.cookiesBrowser,
    cookiesFile: options.cookiesFile,
    progressId: index,
  });
}

async function init() {
  const dir = await window.jyDownload.getDefaultOutputDir();
  els.outputDir.value = dir;
  await refreshCookieStatus();

  if (unsubscribeLoginClosed) {
    unsubscribeLoginClosed();
  }
  unsubscribeLoginClosed = window.jyDownload.onDouyinLoginClosed(async () => {
    await importSessionCookies({ silent: true });
    await refreshCookieStatus();
  });

  const extLink = $("link-cookies-ext");
  if (extLink) {
    extLink.addEventListener("click", (event) => {
      event.preventDefault();
      window.jyDownload.openExternal(
        "https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc",
      );
    });
  }
}

els.btnPickDir.addEventListener("click", async () => {
  const dir = await window.jyDownload.pickOutputDir();
  if (dir) {
    els.outputDir.value = dir;
  }
});

els.btnInputFullscreen.addEventListener("click", openInputFullscreen);
els.btnInputFullscreenClose.addEventListener("click", closeInputFullscreen);
els.inputFullscreenText.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeInputFullscreen();
  }
});

els.btnPickCookies.addEventListener("click", async () => {
  const file = await window.jyDownload.pickCookiesFile();
  if (file) {
    els.cookiesFile.value = file;
  }
});

els.btnClearCookies.addEventListener("click", () => {
  els.cookiesFile.value = "";
});

els.btnDouyinLogin.addEventListener("click", () => {
  window.jyDownload.openDouyinLogin();
  setStatus("请在弹出的窗口里登录抖音，完成后关掉窗口即可", "info");
});

els.btnImportSessionCookies.addEventListener("click", async () => {
  els.btnImportSessionCookies.disabled = true;
  try {
    await importSessionCookies();
  } catch (err) {
    setStatus(err.message || String(err), "error");
  } finally {
    els.btnImportSessionCookies.disabled = false;
  }
});

els.btnCheckCookies.addEventListener("click", async () => {
  els.btnCheckCookies.disabled = true;
  setStatus("正在检查登录状态…", "loading");
  try {
    await refreshCookieStatus();
    setStatus("", "info");
  } catch (err) {
    setStatus(err.message || String(err), "error");
  } finally {
    els.btnCheckCookies.disabled = false;
  }
});

els.input.addEventListener("input", updateInputPreview);

els.btnDownload.addEventListener("click", async () => {
  const outputDir = els.outputDir.value.trim();
  if (!outputDir) {
    setStatus("请选择保存目录", "error");
    return;
  }

  const items = window.parseBatchInputs(els.input.value);
  if (!items.length) {
    setStatus("请先粘贴抖音分享内容", "error");
    return;
  }

  els.btnDownload.disabled = true;
  els.resultBox.classList.add("hidden");
  els.progressBox.classList.remove("hidden");

  const progressItems = items.map((input, i) => ({
    index: i + 1,
    label: previewLabel(input, i + 1),
  }));
  initProgressList(progressItems);
  setStatus(items.length > 1 ? `正在下载 ${items.length} 个视频…` : "正在下载…", "loading");

  if (unsubscribeProgress) {
    unsubscribeProgress();
  }
  unsubscribeProgress = window.jyDownload.onProgress(handleDownloadProgress);

  try {
    const options = await resolveDownloadOptions();
    const results = [];

    for (let i = 0; i < items.length; i += 1) {
      const index = i + 1;
      const input = items[i];

      try {
        const result = await downloadOne(input, outputDir, options, index);
        results.push({
          index,
          label: progressItems[i].label,
          shareText: input,
          ok: true,
          filepath: result.filepath || null,
          fileSize: result.fileSize || 0,
          downloadUrl: result.url || "",
          error: null,
        });
      } catch (err) {
        const message = err.message || String(err);
        markProgressRowFailed(index, message);
        results.push({
          index,
          label: progressItems[i].label,
          shareText: input,
          ok: false,
          filepath: null,
          downloadUrl: "",
          error: message,
        });
      }

      if (items.length > 1) {
        const finished = results.length;
        els.progressSummary.textContent = `已完成 ${finished} / ${items.length} 个`;
      }
    }

    const success = results.filter((item) => item.ok).length;
    const failed = results.length - success;
    const summary = {
      total: results.length,
      success,
      failed,
      outputDir,
      results,
    };

    let indexCsv = null;
    try {
      indexCsv = await saveDownloadIndex(outputDir, results);
    } catch {
      indexCsv = null;
    }

    if (items.length === 1) {
      const only = results[0];
      if (only.ok) {
        renderSingleResult(
          { filepath: only.filepath, outputDir, fileSize: only.fileSize },
          indexCsv,
        );
        setStatus("下载完成", "success");
      } else {
        throw new Error(only.error || "下载失败");
      }
      return;
    }

    renderBatchResult(summary, indexCsv);
    if (failed === 0) {
      setStatus(`${success} 个视频全部下载完成`, "success");
    } else if (success === 0) {
      setStatus("下载未成功，请检查是否已登录抖音", "error");
    } else {
      setStatus(`${success} 个成功，${failed} 个未成功`, "warn");
    }
  } catch (err) {
    setStatus(friendlyErrorMessage(err.message || String(err)), "error");
  } finally {
    activeProgressId = null;
    if (unsubscribeProgress) {
      unsubscribeProgress();
      unsubscribeProgress = null;
    }
    els.btnDownload.disabled = false;
  }
});

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

init();

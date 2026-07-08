const $ = (id) => document.getElementById(id);

const DOWNLOAD_HELP_URL = "https://agent.tfwang.top/#/project-preview";

const STAGE = {
  IDLE: "idle",
  READY: "ready",
  CONVERTING: "converting",
  CONVERTED: "converted",
  IMPORTING: "importing",
  DONE: "done",
};

const state = {
  stage: STAGE.IDLE,
  package: null,
  draftDir: null,
  draftName: null,
  importResult: null,
  logExpanded: false,
};

const els = {
  pipelineView: $("pipeline-view"),
  successView: $("success-view"),
  successSubtitle: $("success-subtitle"),
  successMeta: $("success-meta"),
  btnSuccessOpen: $("btn-success-open"),
  btnSuccessNext: $("btn-success-next"),
  cardPackage: $("card-package"),
  cardConvert: $("card-convert"),
  cardImport: $("card-import"),
  dropZone: $("drop-zone"),
  btnPick: $("btn-pick"),
  btnDownloadHelp: $("btn-download-help"),
  btnOpenDownloader: $("btn-open-downloader"),
  btnChangeZip: $("btn-change-zip"),
  packageSummary: $("package-summary"),
  packageBody: $("package-body"),
  packageCollapsed: $("package-collapsed"),
  packageCollapsedName: $("package-collapsed-name"),
  packageDetails: $("package-details"),
  packagePaths: $("package-paths"),
  convertBody: $("convert-body"),
  convertSummary: $("convert-summary"),
  convertOutputDetails: $("convert-output-details"),
  convertOutputPaths: $("convert-output-paths"),
  convertStatus: $("convert-status"),
  importBody: $("import-body"),
  importSummaryLine: $("import-summary-line"),
  importPathDetails: $("import-path-details"),
  importPaths: $("import-paths"),
  importStatus: $("import-status"),
  draftName: $("draft-name"),
  useDifferentImportName: $("use-different-import-name"),
  jianyingNameField: $("jianying-name-field"),
  jianyingName: $("jianying-name"),
  jianyingDraftsRoot: $("jianying-drafts-root"),
  btnPickJianyingDir: $("btn-pick-jianying-dir"),
  btnPrimary: $("btn-primary"),
  actionHint: $("action-hint"),
  log: $("log"),
  logSummary: $("log-summary"),
  btnToggleLog: $("btn-toggle-log"),
  btnCopyLog: $("btn-copy-log"),
  actionBar: document.querySelector(".action-bar"),
};

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function basename(filePath) {
  if (!filePath) {
    return "";
  }
  const parts = filePath.split(/[/\\]/);
  return parts[parts.length - 1] || filePath;
}

function formatTime(iso) {
  if (!iso) {
    return "—";
  }
  try {
    return new Date(iso).toLocaleString("zh-CN", { hour12: false });
  } catch {
    return iso;
  }
}

function appendLog(text, isError = false) {
  const prefix = isError ? "[错误] " : "";
  els.log.textContent = `${els.log.textContent}${prefix}${text}\n`;
  els.log.scrollTop = els.log.scrollHeight;
  els.btnCopyLog.classList.remove("hidden");
  updateLogSummary(isError ? text : text.split("\n")[0]);
  if (isError) {
    expandLog(true);
  }
}

function updateLogSummary(line) {
  if (!line) {
    els.logSummary.textContent = "";
    els.logSummary.classList.add("hidden");
    return;
  }
  els.logSummary.textContent = line;
  els.logSummary.classList.remove("hidden");
}

function expandLog(expanded) {
  state.logExpanded = expanded;
  els.btnToggleLog.setAttribute("aria-expanded", String(expanded));
  els.log.classList.toggle("collapsed", !expanded);
  els.btnToggleLog.querySelector(".chevron").textContent = expanded ? "▾" : "▸";
}

function setStatus(el, message, type = "info") {
  if (!message) {
    el.classList.add("hidden");
    el.textContent = "";
    return;
  }
  el.textContent = message;
  el.className = `status-msg ${type}`;
  el.classList.remove("hidden");
}

function pathRows(items) {
  if (!items.length) {
    return "";
  }
  return items
    .map(
      ({ label, path, openPath }) => `
      <div class="path-row">
        <div class="path-meta">
          <div class="path-label">${escapeHtml(label)}</div>
          <div class="path-value" title="${escapeHtml(path)}">${escapeHtml(path)}</div>
        </div>
        <button type="button" class="btn-secondary btn-open" data-open-path="${escapeHtml(openPath || path)}">
          打开
        </button>
      </div>`,
    )
    .join("");
}

function renderPathList(container, items) {
  if (!items.length) {
    container.innerHTML = "";
    return;
  }
  container.innerHTML = pathRows(items);
  container.querySelectorAll(".btn-open").forEach((btn) => {
    btn.addEventListener("click", () => openPath(btn.dataset.openPath));
  });
}

async function openPath(targetPath) {
  try {
    await window.jyconvert.openInFinder(targetPath);
  } catch (err) {
    appendLog(err.message, true);
  }
}

function getJianyingDraftsRootValue() {
  return els.jianyingDraftsRoot.value.trim();
}

function getImportName() {
  if (els.useDifferentImportName.checked) {
    return els.jianyingName.value.trim();
  }
  return els.draftName.value.trim() || state.draftName || "";
}

function setStage(stage) {
  state.stage = stage;
  updateUI();
}

function updateCard(card, { active, done, locked, collapsed }) {
  card.classList.toggle("active", Boolean(active));
  card.classList.toggle("done", Boolean(done));
  card.classList.toggle("locked", Boolean(locked));
  card.classList.toggle("collapsed-card", Boolean(collapsed));
}

function updatePrimaryAction() {
  const configs = {
    [STAGE.IDLE]: {
      label: "选择压缩包",
      disabled: false,
      hint: "拖入或选择 Chrome 下载的 zip 素材包",
      action: "pick",
    },
    [STAGE.READY]: {
      label: "开始转换",
      disabled: false,
      hint: "确认草稿名称后点击开始转换",
      action: "convert",
    },
    [STAGE.CONVERTING]: {
      label: "转换中…",
      disabled: true,
      hint: "正在生成本地剪映草稿",
      action: null,
    },
    [STAGE.CONVERTED]: {
      label: "导入剪映",
      disabled: false,
      hint: "将草稿写入剪映目录",
      action: "import",
    },
    [STAGE.IMPORTING]: {
      label: "导入中…",
      disabled: true,
      hint: "正在写入剪映草稿目录",
      action: null,
    },
    [STAGE.DONE]: {
      label: "打开剪映草稿文件夹",
      disabled: false,
      hint: "",
      action: "openDraft",
    },
  };

  const cfg = configs[state.stage] || configs[STAGE.IDLE];
  els.btnPrimary.textContent = cfg.label;
  els.btnPrimary.disabled = cfg.disabled;
  els.btnPrimary.dataset.action = cfg.action || "";
  els.actionHint.textContent = cfg.hint;
  els.actionHint.classList.toggle("hidden", !cfg.hint);
}

function updateUI() {
  const { stage, package: pkg } = state;
  const showSuccess = stage === STAGE.DONE;

  els.successView.classList.toggle("hidden", !showSuccess);
  els.pipelineView.classList.toggle("hidden", showSuccess);
  els.actionBar.classList.toggle("hidden", showSuccess);

  updatePrimaryAction();

  // Card 1: package
  const packageDone = stage !== STAGE.IDLE;
  const packageActive = stage === STAGE.IDLE;
  const packageCollapsed = stage !== STAGE.IDLE;

  updateCard(els.cardPackage, {
    active: packageActive,
    done: packageDone && !packageActive,
    locked: false,
    collapsed: packageCollapsed,
  });

  if (pkg) {
    els.packageSummary.textContent = basename(pkg.zipPath);
    els.packageSummary.classList.remove("hidden");
    els.packageCollapsedName.textContent = basename(pkg.zipPath);
    renderPathList(els.packagePaths, [
      { label: "压缩包", path: pkg.zipPath, openPath: pkg.zipPath },
      { label: "解压目录（素材）", path: pkg.extractDir },
    ]);
    els.packageDetails.classList.remove("hidden");
  } else {
    els.packageSummary.classList.add("hidden");
    els.packageDetails.classList.add("hidden");
  }

  els.packageBody.classList.toggle("hidden", packageCollapsed);
  els.packageCollapsed.classList.toggle("hidden", !packageCollapsed);
  els.dropZone.classList.toggle("has-file", Boolean(pkg));

  // Card 2: convert
  const convertUnlocked = stage !== STAGE.IDLE;
  const convertActive = stage === STAGE.READY || stage === STAGE.CONVERTING;
  const convertDone = stage === STAGE.CONVERTED || stage === STAGE.IMPORTING || stage === STAGE.DONE;
  const convertCollapsed = convertDone;

  updateCard(els.cardConvert, {
    active: convertActive,
    done: convertDone,
    locked: !convertUnlocked,
    collapsed: convertCollapsed,
  });

  els.convertBody.classList.toggle("hidden", !convertUnlocked || convertCollapsed);
  if (convertDone && state.draftName) {
    els.convertSummary.textContent = `已生成「${state.draftName}」`;
    els.convertSummary.classList.remove("hidden");
  } else {
    els.convertSummary.classList.add("hidden");
  }

  // Card 3: import
  const importUnlocked = stage === STAGE.CONVERTED || stage === STAGE.IMPORTING || stage === STAGE.DONE;
  const importActive = stage === STAGE.CONVERTED || stage === STAGE.IMPORTING;
  const importDone = stage === STAGE.DONE;

  updateCard(els.cardImport, {
    active: importActive,
    done: importDone,
    locked: !importUnlocked,
    collapsed: importDone,
  });

  els.importBody.classList.toggle("hidden", !importUnlocked || importDone);
  if (importUnlocked && !importDone) {
    els.importSummaryLine.textContent = `将导入为「${getImportName() || "…"}」`;
    els.importSummaryLine.classList.remove("hidden");
  } else {
    els.importSummaryLine.classList.add("hidden");
  }
}

function renderConvertPreview() {
  const pkg = state.package;
  if (!pkg || state.stage === STAGE.CONVERTED || state.stage === STAGE.IMPORTING || state.stage === STAGE.DONE) {
    return;
  }
  const name = els.draftName.value.trim() || pkg.defaultDraftName;
  renderPathList(els.convertOutputPaths, [
    { label: "草稿输出路径", path: `${pkg.parentDir}/${name}` },
  ]);
  els.convertOutputDetails.classList.remove("hidden");
}

async function loadJianyingDraftsRoot() {
  try {
    const { draftsRoot } = await window.jyconvert.getJianyingDraftsRoot();
    els.jianyingDraftsRoot.value = draftsRoot || "";
  } catch (err) {
    appendLog(err.message, true);
  }
}

async function saveJianyingDraftsRoot(raw) {
  const value = String(raw || "").trim();
  if (!value) {
    throw new Error("请选择剪映草稿目录");
  }
  const saved = await window.jyconvert.setJianyingDraftsRoot(value);
  els.jianyingDraftsRoot.value = saved;
  return saved;
}

async function renderImportPreview() {
  if (!state.draftDir) {
    return;
  }
  const name = getImportName();
  const draftsRoot = getJianyingDraftsRootValue();
  const jianyingPath = await window.jyconvert.getJianyingDraftPath({
    name,
    draftsRoot: draftsRoot || undefined,
  });
  renderPathList(els.importPaths, [
    { label: "本地草稿目录", path: state.draftDir },
    { label: "剪映草稿根目录", path: draftsRoot || "（未配置）" },
    { label: "剪映草稿路径", path: jianyingPath },
  ]);
  els.importPathDetails.classList.remove("hidden");
  if (state.stage === STAGE.CONVERTED) {
    els.importSummaryLine.textContent = `将导入为「${name || "…"}」`;
    els.importSummaryLine.classList.remove("hidden");
  }
}

function renderSuccessView(result) {
  els.successSubtitle.textContent = `已导入「${result.draftName}」`;
  els.successMeta.innerHTML = `
    <div class="success-meta-item">
      <dt>创建时间</dt>
      <dd>${escapeHtml(formatTime(result.draftCreatedAt))}</dd>
    </div>
    <div class="success-meta-item">
      <dt>草稿路径</dt>
      <dd class="mono">${escapeHtml(result.jianyingDraftDir)}</dd>
    </div>
  `;
}

function resetWorkflow() {
  state.package = null;
  state.draftDir = null;
  state.draftName = null;
  state.importResult = null;

  els.draftName.value = "";
  els.jianyingName.value = "";
  els.useDifferentImportName.checked = false;
  els.jianyingNameField.classList.add("hidden");

  els.packagePaths.innerHTML = "";
  els.convertOutputPaths.innerHTML = "";
  els.importPaths.innerHTML = "";
  els.packageDetails.classList.add("hidden");
  els.convertOutputDetails.classList.add("hidden");
  els.importPathDetails.classList.add("hidden");

  setStatus(els.convertStatus, "");
  setStatus(els.importStatus, "");

  setStage(STAGE.IDLE);
}

async function loadPackage(zipPath) {
  if (!zipPath || !zipPath.toLowerCase().endsWith(".zip")) {
    throw new Error("请选择 .zip 压缩包");
  }

  appendLog(`选择压缩包: ${zipPath}`);
  resetWorkflow();

  state.package = await window.jyconvert.openPackage(zipPath);
  els.draftName.value = state.package.defaultDraftName;
  els.jianyingName.value = state.package.defaultDraftName;

  renderConvertPreview();
  appendLog("素材包解析完成");
  updateLogSummary(`已加载 ${basename(zipPath)}`);
  setStage(STAGE.READY);
}

async function handlePickZip() {
  els.btnPick.disabled = true;
  els.btnPrimary.disabled = true;
  try {
    const zipPath = await window.jyconvert.pickZip();
    if (!zipPath) {
      return;
    }
    await loadPackage(zipPath);
  } catch (err) {
    appendLog(err.message, true);
    setStatus(els.convertStatus, err.message, "error");
  } finally {
    els.btnPick.disabled = false;
    updatePrimaryAction();
  }
}

async function handleConvert() {
  if (!state.package) {
    setStatus(els.convertStatus, "请先选择压缩包", "error");
    return;
  }

  const draftName = els.draftName.value.trim();
  if (!draftName) {
    setStatus(els.convertStatus, "请填写草稿名称", "error");
    return;
  }

  if (els.useDifferentImportName.checked && !els.jianyingName.value.trim()) {
    setStatus(els.convertStatus, "请填写剪映列表中的名称", "error");
    return;
  }

  setStage(STAGE.CONVERTING);
  setStatus(els.convertStatus, "正在转换…", "loading");
  els.btnPrimary.disabled = true;

  try {
    appendLog(`开始转换: ${draftName}`);
    const result = await window.jyconvert.convertDraft({ draftName });

    state.draftDir = result.draftDir;
    state.draftName = draftName;

    if (!els.useDifferentImportName.checked) {
      els.jianyingName.value = draftName;
    }

    renderPathList(els.convertOutputPaths, [
      { label: "本地草稿目录", path: result.draftDir },
    ]);
    els.convertOutputDetails.classList.remove("hidden");

    setStatus(els.convertStatus, "转换完成", "success");
    if (result.log) {
      appendLog(result.log);
    }
    appendLog("转换完成");
    updateLogSummary(`转换完成: ${draftName}`);

    setStage(STAGE.CONVERTED);
    await renderImportPreview();
  } catch (err) {
    setStage(STAGE.READY);
    setStatus(els.convertStatus, err.message, "error");
    appendLog(err.message, true);
  }
}

async function handleImport() {
  const draftDir = state.draftDir;
  const jianyingName = getImportName();

  if (!draftDir) {
    setStatus(els.importStatus, "请先完成转换", "error");
    return;
  }
  if (!jianyingName) {
    setStatus(els.importStatus, "请填写草稿名称", "error");
    return;
  }
  if (!getJianyingDraftsRootValue()) {
    setStatus(els.importStatus, "请先配置剪映草稿目录", "error");
    return;
  }

  setStage(STAGE.IMPORTING);
  setStatus(els.importStatus, "正在导入剪映…", "loading");
  els.btnPrimary.disabled = true;

  try {
    const jianyingDraftsRoot = await saveJianyingDraftsRoot(getJianyingDraftsRootValue());
    appendLog(`导入剪映: ${jianyingName}`);
    appendLog(`剪映草稿目录: ${jianyingDraftsRoot}`);
    const result = await window.jyconvert.importDraft({
      draftDir,
      jianyingName,
      jianyingDraftsRoot,
    });
    state.importResult = result;

    if (result.log) {
      appendLog(result.log);
    }
    appendLog("已导入剪映");
    updateLogSummary(`已导入: ${result.draftName}`);

    renderSuccessView(result);
    setStage(STAGE.DONE);
  } catch (err) {
    setStage(STAGE.CONVERTED);
    setStatus(els.importStatus, err.message, "error");
    appendLog(err.message, true);
  }
}

function handlePrimaryAction() {
  const action = els.btnPrimary.dataset.action;
  if (els.btnPrimary.disabled || !action) {
    return;
  }
  switch (action) {
    case "pick":
      handlePickZip();
      break;
    case "convert":
      handleConvert();
      break;
    case "import":
      handleImport();
      break;
    case "openDraft":
      if (state.importResult?.jianyingDraftDir) {
        openPath(state.importResult.jianyingDraftDir);
      }
      break;
    default:
      break;
  }
}

function setupDragDrop() {
  const prevent = (e) => {
    e.preventDefault();
    e.stopPropagation();
  };

  ["dragenter", "dragover", "dragleave", "drop"].forEach((eventName) => {
    document.body.addEventListener(eventName, prevent);
  });

  els.dropZone.addEventListener("dragenter", () => {
    els.dropZone.classList.add("drag-over");
  });
  els.dropZone.addEventListener("dragleave", (e) => {
    if (!els.dropZone.contains(e.relatedTarget)) {
      els.dropZone.classList.remove("drag-over");
    }
  });
  els.dropZone.addEventListener("drop", async (e) => {
    els.dropZone.classList.remove("drag-over");
    const files = [...(e.dataTransfer?.files || [])];
    const zipFile = files.find((f) => f.path && f.path.toLowerCase().endsWith(".zip"));
    if (!zipFile) {
      appendLog("请拖入 .zip 文件", true);
      return;
    }
    try {
      await loadPackage(zipFile.path);
    } catch (err) {
      appendLog(err.message, true);
      setStatus(els.convertStatus, err.message, "error");
    }
  });
}

els.btnPrimary.addEventListener("click", handlePrimaryAction);
els.btnPick.addEventListener("click", handlePickZip);
els.btnDownloadHelp.addEventListener("click", async () => {
  try {
    await window.jyconvert.openExternal(DOWNLOAD_HELP_URL);
  } catch (err) {
    appendLog(err.message, true);
  }
});

if (els.btnOpenDownloader) {
  els.btnOpenDownloader.addEventListener("click", async () => {
    try {
      await window.jyconvert.openDownloader();
    } catch (err) {
      appendLog(err.message, true);
    }
  });
}

els.btnChangeZip.addEventListener("click", handlePickZip);

els.draftName.addEventListener("input", () => {
  renderConvertPreview();
  if (state.stage === STAGE.CONVERTED) {
    renderImportPreview();
  }
  if (!els.useDifferentImportName.checked) {
    els.jianyingName.value = els.draftName.value;
  }
});

els.useDifferentImportName.addEventListener("change", () => {
  const show = els.useDifferentImportName.checked;
  els.jianyingNameField.classList.toggle("hidden", !show);
  if (!show) {
    els.jianyingName.value = els.draftName.value;
  }
  renderImportPreview();
});

els.jianyingName.addEventListener("input", () => {
  if (state.stage === STAGE.CONVERTED) {
    renderImportPreview();
  }
});

els.jianyingDraftsRoot.addEventListener("input", () => {
  if (state.stage === STAGE.CONVERTED) {
    renderImportPreview();
  }
});

els.btnPickJianyingDir.addEventListener("click", async () => {
  try {
    const picked = await window.jyconvert.pickJianyingDraftsDir();
    if (!picked) {
      return;
    }
    els.jianyingDraftsRoot.value = picked;
    if (state.stage === STAGE.CONVERTED) {
      await renderImportPreview();
    }
  } catch (err) {
    setStatus(els.importStatus, err.message, "error");
    appendLog(err.message, true);
  }
});

els.btnSuccessOpen.addEventListener("click", () => {
  if (state.importResult?.jianyingDraftDir) {
    openPath(state.importResult.jianyingDraftDir);
  }
});

els.btnSuccessNext.addEventListener("click", () => {
  els.log.textContent = "";
  els.btnCopyLog.classList.add("hidden");
  updateLogSummary("");
  expandLog(false);
  resetWorkflow();
});

els.btnToggleLog.addEventListener("click", () => {
  expandLog(!state.logExpanded);
});

els.btnCopyLog.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(els.log.textContent);
    updateLogSummary("日志已复制");
  } catch {
    appendLog("复制失败", true);
  }
});

setupDragDrop();
loadJianyingDraftsRoot();

Promise.all([
  window.jyconvert.getPythonRoot(),
  window.jyconvert.getPythonBinary(),
]).then(([root, binary]) => {
  appendLog(binary ? `python: ${binary} (内嵌)` : `python: ${root}/cli.py (开发)`);
  els.log.textContent = els.log.textContent.trimEnd() + "\n";
  expandLog(false);
});

updateUI();

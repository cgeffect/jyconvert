const { BrowserWindow } = require("electron");
const http = require("http");
const https = require("https");
const { attachDouyinWebGuards, attachDouyinAutoplayBlock, stopWebContentsMedia } = require("./douyin-browser");
const { collectDouyinCookies } = require("./cookies");

const DOUYIN_UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36";

const AWEME_QUERY =
  "device_platform=webapp&aid=6383&channel=channel_pc_web&pc_client_type=1&version_code=190500&version_name=19.5.0&cookie_enabled=true&browser_language=zh-CN&browser_platform=MacIntel&browser_name=Chrome&browser_online=true&engine_name=Blink&os_name=Mac+OS&os_version=10.15.7&platform=PC&screen_width=1920&screen_height=1080";

function extractDouyinVideoId(input) {
  const text = String(input || "").trim();
  const direct = text.match(/douyin\.com\/video\/(\d+)/i);
  if (direct) {
    return direct[1];
  }
  const note = text.match(/douyin\.com\/note\/(\d+)/i);
  if (note) {
    return note[1];
  }
  const short = text.match(/v\.douyin\.com\/([A-Za-z0-9_-]+)/i);
  if (short) {
    return { shortUrl: `https://v.douyin.com/${short[1]}/` };
  }
  return null;
}

function getVideoFromDetail(detail) {
  return detail?.video || detail?.aweme_detail?.video || {};
}

function extractPlayUri(detail, awemeId) {
  const video = getVideoFromDetail(detail);
  const uri = video?.play_addr?.uri || video?.download_addr?.uri || "";
  if (uri) {
    return String(uri);
  }
  if (awemeId) {
    return String(awemeId);
  }
  return "";
}

function stripWatermarkFromUrl(url) {
  const text = String(url || "").trim();
  if (!text || !/playwm/i.test(text)) {
    return text;
  }
  return text.replace(/playwm/gi, "play");
}

function isWatermarkedUrl(url) {
  return /playwm|watermark/i.test(String(url || ""));
}

function isLikelyVideoCdnUrl(url) {
  const text = String(url || "");
  if (!/^https?:\/\//i.test(text)) {
    return false;
  }
  if (isWatermarkedUrl(text)) {
    return false;
  }
  return /douyinvod|douyinstatic|snssdk|amemv|bytecdn|tos-cn/i.test(text) || /\.mp4(\?|$)/i.test(text);
}

async function cookieHeaderFromSession(ses) {
  const cookies = await collectDouyinCookies(ses);
  if (!cookies.length) {
    return "";
  }
  return cookies.map((item) => `${item.name}=${item.value}`).join("; ");
}

function followHttpRedirects(startUrl, options = {}) {
  const opts = typeof options === "number" ? { maxHops: options } : options;
  const maxHops = opts.maxHops ?? 10;
  const extraHeaders = opts.headers || {};

  return new Promise((resolve, reject) => {
    let current = String(startUrl || "").trim();

    function visit(hopsLeft) {
      if (!current || hopsLeft < 0) {
        reject(new Error("短链重定向次数过多"));
        return;
      }

      let parsed;
      try {
        parsed = new URL(current);
      } catch (err) {
        reject(err);
        return;
      }

      const lib = parsed.protocol === "https:" ? https : http;
      const req = lib.request(
        current,
        {
          method: "GET",
          headers: {
            "User-Agent": DOUYIN_UA,
            Accept: "*/*",
            Referer: "https://www.douyin.com/",
            ...extraHeaders,
          },
        },
        (res) => {
          const status = res.statusCode || 0;
          if ([301, 302, 303, 307, 308].includes(status) && res.headers.location && hopsLeft > 0) {
            current = new URL(res.headers.location, current).href;
            res.resume();
            visit(hopsLeft - 1);
            return;
          }
          res.resume();
          resolve(current);
        },
      );
      req.on("error", reject);
      req.setTimeout(15000, () => {
        req.destroy(new Error("请求超时"));
      });
      req.end();
    }

    visit(maxHops);
  });
}

async function resolveUrlWithSession(startUrl, ses) {
  const cookie = await cookieHeaderFromSession(ses);
  const headers = cookie ? { Cookie: cookie } : {};
  const finalUrl = await followHttpRedirects(startUrl, { headers });
  return stripWatermarkFromUrl(finalUrl);
}

function buildPlayApiCandidates(detail, awemeId) {
  const video = getVideoFromDetail(detail);
  const uri = String(video?.play_addr?.uri || video?.download_addr?.uri || "").trim();
  const urlKey = String(video?.play_addr?.url_key || "").trim();
  const candidates = [];
  const seen = new Set();

  function add(params) {
    const search = new URLSearchParams(AWEME_QUERY);
    for (const [key, value] of Object.entries(params)) {
      if (value != null && value !== "") {
        search.set(key, String(value));
      }
    }
    const url = `https://www.douyin.com/aweme/v1/play/?${search.toString()}`;
    if (!seen.has(url)) {
      seen.add(url);
      candidates.push(url);
    }
  }

  if (uri) {
    add({ video_id: uri, watermark: "0", ratio: "default", improve_bitrate: "1" });
    add({ video_id: uri, watermark: "0", ratio: "1080p", line: "0", improve_bitrate: "1" });
    add({
      video_id: uri,
      watermark: "0",
      ratio: "default",
      improve_bitrate: "1",
      is_play_url: "1",
      source: "PackSourceEnum_PUBLISH",
    });
    if (urlKey) {
      add({
        video_id: uri,
        watermark: "0",
        ratio: "default",
        line: "0",
        sign: urlKey,
        source: "PackSourceEnum_AWEME_DETAIL",
      });
    }
  }

  if (awemeId) {
    add({ video_id: String(awemeId), watermark: "0", ratio: "default", improve_bitrate: "1" });
  }

  return candidates;
}

function collectDirectUrlCandidates(detail) {
  const video = getVideoFromDetail(detail);
  const bitRates = [...(video?.bit_rate || [])].sort(
    (a, b) => (Number(b.bit_rate) || 0) - (Number(a.bit_rate) || 0),
  );

  const urls = [
    ...(video?.download_addr?.url_list || []),
    ...(video?.download_addr_h265?.url_list || []),
    ...bitRates.flatMap((item) => item?.play_addr?.url_list || []),
    ...(video?.play_addr?.url_list || []),
  ]
    .filter(Boolean)
    .map(stripWatermarkFromUrl);

  const unique = [];
  const seen = new Set();
  for (const url of urls) {
    if (!seen.has(url)) {
      seen.add(url);
      unique.push(url);
    }
  }
  return unique;
}

async function resolveNoWatermarkViaPlayApi(session, detail, awemeId) {
  const cookie = await cookieHeaderFromSession(session);
  const headers = cookie ? { Cookie: cookie } : {};
  const candidates = buildPlayApiCandidates(detail, awemeId);

  for (const playApiUrl of candidates) {
    try {
      const finalUrl = await followHttpRedirects(playApiUrl, { headers });
      if (isAcceptableDownloadUrl(finalUrl)) {
        return finalUrl;
      }
    } catch {
      /* try next */
    }
  }
  return null;
}

async function resolveNoWatermarkViaDirectUrls(session, detail) {
  const candidates = collectDirectUrlCandidates(detail).filter((url) => !isWatermarkedUrl(url));

  for (const url of candidates) {
    try {
      if (isLikelyVideoCdnUrl(url)) {
        return url;
      }
      const finalUrl = await resolveUrlWithSession(url, session);
      if (isAcceptableDownloadUrl(finalUrl)) {
        return finalUrl;
      }
    } catch {
      /* try next */
    }
  }
  return null;
}

async function fetchNoWatermarkPlayUrlInBrowser(win, detail, awemeId) {
  const videoUri = extractPlayUri(detail, awemeId);
  if (!videoUri || !win) {
    return null;
  }

  const script = `
    (async () => {
      const videoId = ${JSON.stringify(videoUri)};
      const awemeId = ${JSON.stringify(String(awemeId || ""))};
      const baseQuery = ${JSON.stringify(AWEME_QUERY)};

      async function resolvePlayRedirect(video_id) {
        const params = new URLSearchParams(baseQuery);
        params.set("video_id", video_id);
        params.set("ratio", "default");
        params.set("improve_bitrate", "1");
        params.set("watermark", "0");
        const playUrl = "https://www.douyin.com/aweme/v1/play/?" + params.toString();
        const res = await fetch(playUrl, {
          method: "GET",
          credentials: "include",
          redirect: "follow",
          headers: {
            accept: "*/*",
            referer: "https://www.douyin.com/",
          },
        });
        if (res.ok && res.url && !res.url.includes("/aweme/v1/play")) {
          return res.url;
        }
        return null;
      }

      for (const id of [videoId, awemeId].filter(Boolean)) {
        try {
          const url = await resolvePlayRedirect(id);
          if (url && !/playwm|watermark/i.test(url)) {
            return { ok: true, url };
          }
        } catch (error) {
          /* try next */
        }
      }
      return { ok: false };
    })()
  `;

  const result = await win.webContents.executeJavaScript(script, true);
  if (result?.ok && result.url) {
    return stripWatermarkFromUrl(result.url);
  }
  return null;
}

function isAcceptableDownloadUrl(url) {
  const text = String(url || "");
  if (!/^https?:\/\//i.test(text) || isWatermarkedUrl(text)) {
    return false;
  }
  if (isLikelyVideoCdnUrl(text)) {
    return true;
  }
  return /douyin\.com\/aweme\/v1\/play\//i.test(text) && /watermark=0/i.test(text);
}

function pickPlayUrlFallback(detail) {
  const candidates = collectDirectUrlCandidates(detail);
  const clean = candidates.filter((url) => !isWatermarkedUrl(url));
  if (clean.length) {
    return clean[0];
  }
  return candidates[0] ? stripWatermarkFromUrl(candidates[0]) : null;
}

async function resolvePlayUrl(session, win, detail, awemeId) {
  const directUrl = await resolveNoWatermarkViaDirectUrls(session, detail);
  if (directUrl) {
    return { url: directUrl, source: "download_addr" };
  }

  const playApiUrl = await resolveNoWatermarkViaPlayApi(session, detail, awemeId);
  if (playApiUrl && isAcceptableDownloadUrl(playApiUrl)) {
    return { url: playApiUrl, source: "play_api" };
  }

  const browserPlayUrl = await fetchNoWatermarkPlayUrlInBrowser(win, detail, awemeId);
  if (browserPlayUrl && isAcceptableDownloadUrl(browserPlayUrl)) {
    return { url: browserPlayUrl, source: "play_api_browser" };
  }

  const fallback = pickPlayUrlFallback(detail);
  if (fallback) {
    return { url: fallback, source: "detail_fallback" };
  }

  return null;
}

async function buildVideoResult(session, win, awemeId, detail, sourcePrefix) {
  const play = await resolvePlayUrl(session, win, detail, awemeId);
  if (!play?.url) {
    return null;
  }

  const title = detail.desc || detail.preview_title || `douyin_${awemeId}`;
  return {
    awemeId: String(awemeId),
    title,
    playUrl: play.url,
    detail,
    source: sourcePrefix ? `${sourcePrefix}:${play.source}` : play.source,
  };
}

function destroyDouyinFetchWindow() {
  const win = global.__jyDouyinFetchWindow;
  if (!win || win.isDestroyed()) {
    global.__jyDouyinFetchWindow = null;
    return;
  }
  stopWebContentsMedia(win.webContents).finally(() => {
    if (!win.isDestroyed()) {
      win.destroy();
    }
    if (global.__jyDouyinFetchWindow === win) {
      global.__jyDouyinFetchWindow = null;
    }
  });
}

function normalizeDetail(raw) {
  if (!raw || typeof raw !== "object") {
    return null;
  }
  if (raw.aweme_detail) {
    return raw.aweme_detail;
  }
  if (raw.awemeDetail) {
    return raw.awemeDetail;
  }
  if (raw.video && (raw.desc || raw.aweme_id || raw.awemeId)) {
    return raw;
  }
  return null;
}

async function ensureDouyinFetchWindow(session) {
  if (global.__jyDouyinFetchWindow && !global.__jyDouyinFetchWindow.isDestroyed()) {
    return global.__jyDouyinFetchWindow;
  }

  const win = new BrowserWindow({
    show: false,
    width: 960,
    height: 720,
    webPreferences: {
      session,
      contextIsolation: true,
      nodeIntegration: false,
      backgroundThrottling: false,
    },
  });

  win.webContents.setUserAgent(DOUYIN_UA);
  attachDouyinWebGuards(win.webContents);
  attachDouyinAutoplayBlock(win.webContents);
  global.__jyDouyinFetchWindow = win;
  win.on("closed", () => {
    if (global.__jyDouyinFetchWindow === win) {
      global.__jyDouyinFetchWindow = null;
    }
  });
  return win;
}

function waitForNavigation(win, url, timeoutMs = 20000) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      cleanup();
      reject(new Error("页面加载超时，请确认网络正常"));
    }, timeoutMs);

    function cleanup() {
      clearTimeout(timer);
      win.webContents.removeListener("did-finish-load", onLoad);
      win.webContents.removeListener("did-fail-load", onFail);
    }

    function onLoad() {
      cleanup();
      resolve(win.webContents.getURL());
    }

    function onFail(_event, _code, desc) {
      cleanup();
      reject(new Error(`页面加载失败: ${desc || "unknown"}`));
    }

    win.webContents.once("did-finish-load", onLoad);
    win.webContents.once("did-fail-load", onFail);
    win.loadURL(url, { userAgent: DOUYIN_UA }).catch((err) => {
      cleanup();
      reject(err);
    });
  });
}

function extractAwemeIdFromUrl(url) {
  const text = String(url || "");
  let matched = text.match(/(?:video|note)\/(\d+)/i);
  if (matched) {
    return matched[1];
  }
  matched = text.match(/[?&]modal_id=(\d+)/i);
  if (matched) {
    return matched[1];
  }
  matched = text.match(/[?&]vid=(\d+)/i);
  if (matched) {
    return matched[1];
  }
  return null;
}

async function resolveShortLink(win, shortUrl) {
  let finalUrl = shortUrl;
  try {
    finalUrl = await followHttpRedirects(shortUrl);
  } catch {
    finalUrl = shortUrl;
  }

  let awemeId = extractAwemeIdFromUrl(finalUrl);
  if (awemeId) {
    return { awemeId, finalUrl };
  }

  await waitForNavigation(win, shortUrl, 25000);
  await stopWebContentsMedia(win.webContents);
  finalUrl = win.webContents.getURL();
  awemeId = extractAwemeIdFromUrl(finalUrl);
  if (awemeId) {
    return { awemeId, finalUrl };
  }

  const pageExtract = await extractDetailFromPage(win);
  if (pageExtract?.detail) {
    const detail = normalizeDetail(pageExtract.detail);
    const fromDetail = detail?.aweme_id || detail?.awemeId;
    if (fromDetail) {
      return { awemeId: String(fromDetail), finalUrl, detail };
    }
  }

  throw new Error(`无法从短链解析视频（当前页面: ${finalUrl}）`);
}

async function extractDetailFromPage(win) {
  const script = `
    (() => {
      function deepFind(obj, depth = 0) {
        if (!obj || typeof obj !== "object" || depth > 14) return null;
        if (obj.aweme_detail) return obj.aweme_detail;
        if (obj.awemeDetail) return obj.awemeDetail;
        if (obj.video && (obj.desc || obj.aweme_id || obj.awemeId)) return obj;
        for (const key of Object.keys(obj)) {
          const found = deepFind(obj[key], depth + 1);
          if (found) return found;
        }
        return null;
      }

      const universal = window.__UNIVERSAL_DATA_FOR_REHYDRATION__;
      if (universal) {
        const detail = deepFind(universal);
        if (detail) return { source: "universal", detail };
      }

      const renderEl = document.getElementById("RENDER_DATA");
      if (renderEl && renderEl.textContent) {
        try {
          const parsed = JSON.parse(decodeURIComponent(renderEl.textContent));
          const detail = deepFind(parsed);
          if (detail) return { source: "render_data", detail };
        } catch (error) {
          /* ignore */
        }
      }

      const scripts = Array.from(document.querySelectorAll("script"));
      for (const node of scripts) {
        const text = node.textContent || "";
        if (!text.includes("aweme") && !text.includes("playAddr")) {
          continue;
        }
        const match = text.match(/\\{[\\s\\S]*"aweme_detail"[\\s\\S]*\\}/);
        if (!match) {
          continue;
        }
        try {
          const parsed = JSON.parse(match[0]);
          const detail = deepFind(parsed);
          if (detail) return { source: "inline_script", detail };
        } catch (error) {
          /* ignore */
        }
      }

      return null;
    })()
  `;
  return win.webContents.executeJavaScript(script, true);
}

async function fetchAwemeDetail(win, awemeId) {
  const script = `
    (async () => {
      const awemeId = ${JSON.stringify(awemeId)};
      const query = ${JSON.stringify(AWEME_QUERY)} + '&aweme_id=' + encodeURIComponent(awemeId);
      const url = 'https://www.douyin.com/aweme/v1/web/aweme/detail/?' + query;
      const response = await fetch(url, {
        credentials: 'include',
        headers: { accept: 'application/json, text/plain, */*' },
      });
      const text = await response.text();
      if (!text) {
        return { ok: false, error: 'empty response', status: response.status };
      }
      try {
        const data = JSON.parse(text);
        return { ok: true, data, status: response.status };
      } catch (error) {
        return { ok: false, error: 'invalid json', status: response.status, preview: text.slice(0, 200) };
      }
    })()
  `;
  return win.webContents.executeJavaScript(script, true);
}

async function ensureDouyinOrigin(win) {
  const current = win.webContents.getURL();
  if (/^https:\/\/(www\.)?douyin\.com\//i.test(current)) {
    return;
  }
  await waitForNavigation(win, "https://www.douyin.com/");
}

async function resolveDouyinVideo(input, { session } = {}) {
  if (!session) {
    throw new Error("缺少抖音会话，请先点「应用内登录抖音」");
  }

  let awemeId = extractDouyinVideoId(input);
  const win = await ensureDouyinFetchWindow(session);

  try {
    if (awemeId && typeof awemeId === "object" && awemeId.shortUrl) {
      const resolved = await resolveShortLink(win, awemeId.shortUrl);
      awemeId = resolved.awemeId;
      if (resolved.detail) {
        const meta = await buildVideoResult(session, win, awemeId, resolved.detail, "short_link_page");
        if (meta) {
          return meta;
        }
      }
    }

    if (!awemeId || typeof awemeId !== "string") {
      throw new Error("无法识别抖音视频 ID，请粘贴完整分享文案或链接");
    }

    let detail = null;
    let source = "";
    let apiResult = null;

    await ensureDouyinOrigin(win);
    apiResult = await fetchAwemeDetail(win, awemeId);
    if (apiResult?.ok) {
      detail = normalizeDetail(apiResult.data);
      source = "api";
    }

    if (!detail) {
      const pageUrl = `https://www.douyin.com/video/${awemeId}`;
      await waitForNavigation(win, pageUrl);
      await stopWebContentsMedia(win.webContents);
      const pageExtract = await extractDetailFromPage(win);
      if (pageExtract?.detail) {
        detail = normalizeDetail(pageExtract.detail);
        source = pageExtract.source || "page";
      }
    }

    if (!detail) {
      const hint = apiResult?.preview ? ` 响应片段: ${apiResult.preview}` : "";
      throw new Error(
        `抖音页面与 API 均未解析到视频 (${apiResult?.status || "unknown"}): ${apiResult?.error || "unknown"}${hint}。请确认已在应用内登录且视频可公开访问。`,
      );
    }

    const meta = await buildVideoResult(session, win, awemeId, detail, source);
    if (!meta) {
      throw new Error("未找到视频下载地址，可能是图文或私密视频");
    }

    return meta;
  } finally {
    await stopWebContentsMedia(win.webContents);
    destroyDouyinFetchWindow();
  }
}

module.exports = {
  extractDouyinVideoId,
  resolveDouyinVideo,
  ensureDouyinFetchWindow,
  destroyDouyinFetchWindow,
};

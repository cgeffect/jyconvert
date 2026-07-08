const ALLOWED_PROTOCOLS = new Set(["http:", "https:", "about:"]);

function isAllowedNavigationUrl(url) {
  try {
    return ALLOWED_PROTOCOLS.has(new URL(url).protocol);
  } catch {
    return false;
  }
}

function attachDouyinWebGuards(webContents) {
  if (!webContents || webContents.__jyDouyinGuardsAttached) {
    return;
  }
  webContents.__jyDouyinGuardsAttached = true;

  webContents.setWindowOpenHandler(({ url }) => {
    if (!isAllowedNavigationUrl(url)) {
      return { action: "deny" };
    }
    return { action: "allow" };
  });

  const blockIfNeeded = (event, url) => {
    if (!isAllowedNavigationUrl(url)) {
      event.preventDefault();
    }
  };

  webContents.on("will-navigate", blockIfNeeded);
  webContents.on("will-redirect", blockIfNeeded);
  webContents.on("will-frame-navigate", blockIfNeeded);

  const injectLinkGuards = () => {
    if (webContents.isDestroyed()) {
      return;
    }
    webContents
      .executeJavaScript(
        `
          (() => {
            if (window.__jyDouyinLinkGuards) {
              return true;
            }
            window.__jyDouyinLinkGuards = true;

            function isAllowedHref(href) {
              if (!href) {
                return true;
              }
              try {
                const protocol = new URL(href, location.href).protocol;
                return protocol === "http:" || protocol === "https:" || protocol === "about:";
              } catch (error) {
                return false;
              }
            }

            document.addEventListener(
              "click",
              (event) => {
                const anchor = event.target && event.target.closest ? event.target.closest("a[href]") : null;
                if (!anchor) {
                  return;
                }
                if (!isAllowedHref(anchor.href)) {
                  event.preventDefault();
                  event.stopPropagation();
                }
              },
              true,
            );

            const originalOpen = window.open;
            window.open = function open(url, ...rest) {
              if (url && !isAllowedHref(String(url))) {
                return null;
              }
              return originalOpen.call(window, url, ...rest);
            };

            return true;
          })()
        `,
        true,
      )
      .catch(() => {});
  };

  webContents.on("dom-ready", injectLinkGuards);
  webContents.on("did-navigate", injectLinkGuards);
}

async function stopWebContentsMedia(webContents) {
  if (!webContents || webContents.isDestroyed()) {
    return;
  }
  try {
    await webContents.executeJavaScript(
      `
        (() => {
          document.querySelectorAll("video,audio").forEach((el) => {
            try {
              el.pause();
              el.muted = true;
              el.autoplay = false;
              el.removeAttribute("src");
              el.load();
            } catch (error) {
              /* ignore */
            }
          });
          return true;
        })()
      `,
      true,
    );
  } catch {
    /* ignore */
  }
}

function attachDouyinAutoplayBlock(webContents) {
  if (!webContents || webContents.__jyDouyinAutoplayBlocked) {
    return;
  }
  webContents.__jyDouyinAutoplayBlocked = true;
  webContents.setAudioMuted(true);

  webContents.on("media-started-playing", () => {
    stopWebContentsMedia(webContents);
  });

  const injectAutoplayBlock = () => {
    if (webContents.isDestroyed()) {
      return;
    }
    webContents
      .executeJavaScript(
        `
          (() => {
            if (window.__jyDouyinAutoplayBlocked) {
              return true;
            }
            window.__jyDouyinAutoplayBlocked = true;

            function silenceMedia(root) {
              root.querySelectorAll("video,audio").forEach((el) => {
                try {
                  el.autoplay = false;
                  el.muted = true;
                  el.pause();
                  el.setAttribute("playsinline", "");
                } catch (error) {
                  /* ignore */
                }
              });
            }

            silenceMedia(document);
            const observer = new MutationObserver((records) => {
              for (const record of records) {
                for (const node of record.addedNodes) {
                  if (!(node instanceof Element)) {
                    continue;
                  }
                  if (node.matches("video,audio")) {
                    silenceMedia(node.parentElement || document);
                  } else {
                    silenceMedia(node);
                  }
                }
              }
            });
            observer.observe(document.documentElement, { childList: true, subtree: true });
            return true;
          })()
        `,
        true,
      )
      .catch(() => {});
  };

  webContents.on("dom-ready", injectAutoplayBlock);
  webContents.on("did-navigate", injectAutoplayBlock);
}

module.exports = {
  attachDouyinWebGuards,
  attachDouyinAutoplayBlock,
  stopWebContentsMedia,
  isAllowedNavigationUrl,
};

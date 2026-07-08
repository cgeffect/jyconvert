(function initBatchInput() {
  function isLikelySingleLineEntry(line) {
    const text = String(line || "").trim();
    if (!text) {
      return false;
    }
    return (
      /^https?:\/\//i.test(text) ||
      /v\.douyin\.com/i.test(text) ||
      /douyin\.com\/(video|note)\/\d+/i.test(text)
    );
  }

  function hasDouyinLink(text) {
    return /douyin\.com|v\.douyin\.com/i.test(String(text || ""));
  }

  function parseBatchInputs(text) {
    const raw = String(text || "").trim();
    if (!raw) {
      return [];
    }

    const lines = raw
      .split(/\n/)
      .map((line) => line.trim())
      .filter(Boolean);

    if (lines.length <= 1) {
      return [raw];
    }

    if (lines.every(isLikelySingleLineEntry)) {
      return lines;
    }

    const urlLineCount = lines.filter(hasDouyinLink).length;
    if (urlLineCount > 1) {
      const items = [];
      let current = "";
      for (const line of lines) {
        if (hasDouyinLink(line) && current) {
          items.push(current.trim());
          current = line;
        } else {
          current = current ? `${current}\n${line}` : line;
        }
      }
      if (current.trim()) {
        items.push(current.trim());
      }
      return items.length ? items : [raw];
    }

    return [raw];
  }

  window.parseBatchInputs = parseBatchInputs;
})();

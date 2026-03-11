function escapeHtml(text) {
  return String(text || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function splitLines(text) {
  return String(text || "").replace(/\r\n/g, "\n").split("\n");
}

function buildLcsMatrix(a, b) {
  const rows = a.length + 1;
  const cols = b.length + 1;
  const dp = Array.from({ length: rows }, () => Array(cols).fill(0));
  for (let i = 1; i < rows; i += 1) {
    for (let j = 1; j < cols; j += 1) {
      if (a[i - 1] === b[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
  }
  return dp;
}

function sequenceDiff(beforeList, afterList) {
  const dp = buildLcsMatrix(beforeList, afterList);
  const ops = [];
  let i = beforeList.length;
  let j = afterList.length;

  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && beforeList[i - 1] === afterList[j - 1]) {
      ops.push({ type: "equal", text: beforeList[i - 1] });
      i -= 1;
      j -= 1;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      ops.push({ type: "insert", text: afterList[j - 1] });
      j -= 1;
    } else {
      ops.push({ type: "delete", text: beforeList[i - 1] });
      i -= 1;
    }
  }

  return ops.reverse();
}

function inlineDiff(beforeText, afterText) {
  const before = Array.from(String(beforeText || ""));
  const after = Array.from(String(afterText || ""));

  // Protect against very long single-line diff cost.
  if (before.length * after.length > 40000) {
    return {
      deleteSegments: [{ type: "delete", text: String(beforeText || "") }],
      insertSegments: [{ type: "insert", text: String(afterText || "") }],
    };
  }

  const ops = sequenceDiff(before, after);
  const deleteSegments = [];
  const insertSegments = [];

  for (const part of ops) {
    if (part.type === "equal") {
      deleteSegments.push({ type: "equal", text: part.text });
      insertSegments.push({ type: "equal", text: part.text });
    } else if (part.type === "delete") {
      deleteSegments.push({ type: "delete", text: part.text });
    } else if (part.type === "insert") {
      insertSegments.push({ type: "insert", text: part.text });
    }
  }

  return { deleteSegments, insertSegments };
}

function compactSegments(segments) {
  const packed = [];
  for (const segment of segments) {
    const last = packed[packed.length - 1];
    if (last && last.type === segment.type) {
      last.text += segment.text;
    } else {
      packed.push({ ...segment });
    }
  }
  return packed;
}

function renderSegments(segments, mode) {
  const safeSegments = compactSegments(segments).map((item) => {
    const content = escapeHtml(item.text);
    if (!content) return "";
    if (mode === "delete" && item.type === "delete") {
      return `<mark class="diff-inline-delete">${content}</mark>`;
    }
    if (mode === "insert" && item.type === "insert") {
      return `<mark class="diff-inline-insert">${content}</mark>`;
    }
    return content;
  });
  return safeSegments.join("") || "&nbsp;";
}

function renderLine(type, htmlText) {
  const sign = type === "insert" ? "+" : type === "delete" ? "-" : " ";
  return `<div class="diff-line diff-line--${type}"><span class="diff-sign">${sign}</span><span class="diff-text">${htmlText}</span></div>`;
}

export function countChangedLines(beforeText, afterText) {
  const before = splitLines(beforeText);
  const after = splitLines(afterText);
  const max = Math.max(before.length, after.length);
  let changed = 0;
  for (let idx = 0; idx < max; idx += 1) {
    if ((before[idx] || "") !== (after[idx] || "")) {
      changed += 1;
    }
  }
  return changed;
}

export function renderUnifiedDiffHtml(beforeText, afterText, options = {}) {
  const maxLines = Number.isFinite(options.maxLines) ? options.maxLines : 0;
  const beforeLines = splitLines(beforeText);
  const afterLines = splitLines(afterText);
  const ops = sequenceDiff(beforeLines, afterLines);

  const rows = [];
  let index = 0;
  while (index < ops.length) {
    const current = ops[index];
    if (current.type === "equal") {
      rows.push(renderLine("equal", escapeHtml(current.text) || "&nbsp;"));
      index += 1;
      continue;
    }

    if (current.type === "delete") {
      const deleteBlock = [];
      while (index < ops.length && ops[index].type === "delete") {
        deleteBlock.push(ops[index].text);
        index += 1;
      }
      const insertBlock = [];
      while (index < ops.length && ops[index].type === "insert") {
        insertBlock.push(ops[index].text);
        index += 1;
      }

      const pairCount = Math.max(deleteBlock.length, insertBlock.length);
      for (let blockIndex = 0; blockIndex < pairCount; blockIndex += 1) {
        const deleteLine = deleteBlock[blockIndex];
        const insertLine = insertBlock[blockIndex];
        if (typeof deleteLine === "string" && typeof insertLine === "string") {
          const { deleteSegments, insertSegments } = inlineDiff(deleteLine, insertLine);
          rows.push(renderLine("delete", renderSegments(deleteSegments, "delete")));
          rows.push(renderLine("insert", renderSegments(insertSegments, "insert")));
        } else if (typeof deleteLine === "string") {
          rows.push(renderLine("delete", escapeHtml(deleteLine) || "&nbsp;"));
        } else if (typeof insertLine === "string") {
          rows.push(renderLine("insert", escapeHtml(insertLine) || "&nbsp;"));
        }
      }
      continue;
    }

    rows.push(renderLine("insert", escapeHtml(current.text) || "&nbsp;"));
    index += 1;
  }

  const limitedRows = maxLines > 0 ? rows.slice(0, maxLines) : rows;
  if (maxLines > 0 && rows.length > maxLines) {
    limitedRows.push('<div class="diff-line diff-line--ellipsis"><span class="diff-sign">…</span><span class="diff-text">更多内容请进入详情页查看</span></div>');
  }
  return `<div class="diff-view">${limitedRows.join("")}</div>`;
}

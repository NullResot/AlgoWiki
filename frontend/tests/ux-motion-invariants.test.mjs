import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import api, { isRequestCanceled } from "../src/services/api.js";
import { captchaErrorMessage, isCaptchaCanceled } from "../src/composables/useCaptcha.js";
import { resolveConfirmTone } from "../src/stores/ui.js";
import {
  extractApiError,
  formatDurationZh,
  maskContactPreview,
  resolveSafeRedirect,
} from "../src/utils/format.js";
import { safeScrollBehavior } from "../src/utils/motion.js";

const FRONTEND_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SRC_DIR = path.join(FRONTEND_ROOT, "src");

async function walkFiles(dir, extensions) {
  const entries = await readdir(dir, { withFileTypes: true });
  const results = [];
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...(await walkFiles(fullPath, extensions)));
    } else if (extensions.some((ext) => entry.name.endsWith(ext))) {
      results.push(fullPath);
    }
  }
  return results;
}

function stripCssComments(source) {
  return String(source || "").replace(/\/\*[\s\S]*?\*\//g, "");
}

test("UX invariant: zero native window.confirm/prompt/alert dialogs in frontend/src", async () => {
  const files = await walkFiles(SRC_DIR, [".vue", ".js"]);
  const hits = [];
  for (const filePath of files) {
    const content = await readFile(filePath, "utf8");
    if (/\bwindow\.(confirm|prompt|alert)\s*\(/.test(content)) {
      hits.push(path.relative(FRONTEND_ROOT, filePath));
    }
  }
  assert.deepEqual(hits, [], `Found native browser dialog calls in: ${hits.join(", ")}`);
});

test("Motion invariant: zero nuclear .01ms reduced-motion CSS overrides in frontend/src", async () => {
  const files = await walkFiles(SRC_DIR, [".vue", ".css"]);
  const hits = [];
  for (const filePath of files) {
    const content = stripCssComments(await readFile(filePath, "utf8"));
    if (/\b0?\.01ms\b/i.test(content)) {
      hits.push(path.relative(FRONTEND_ROOT, filePath));
    }
  }
  assert.deepEqual(hits, [], `Found forbidden .01ms reduced-motion rule in: ${hits.join(", ")}`);
});

test("Unified motion system defines tokens, transition primitives, and reduced-motion rules", async () => {
  const motionCss = await readFile(path.join(SRC_DIR, "assets/motion.css"), "utf8");
  for (const requiredToken of [
    "--ease-standard",
    "--ease-out",
    "--ease-in",
    "--dur-press",
    "--dur-fast",
    "--dur-base",
    "--dur-panel",
    "--dur-exit",
    ".aw-route-enter-active",
    ".aw-modal-enter-active",
    ".aw-popover-enter-active",
    ".aw-sheet-enter-active",
    ".aw-collapse-enter-active",
    ".aw-swap-enter-active",
    ".aw-list-enter-active",
    ".aw-icon-enter-active",
    ".aw-num-enter-active",
    "@media (prefers-reduced-motion: reduce)",
  ]) {
    assert.ok(motionCss.includes(requiredToken), `Missing motion.css token/selector: ${requiredToken}`);
  }
});

test("UX utility contracts behave safely and predictably", () => {
  assert.equal(resolveSafeRedirect("//evil.com"), null);
  assert.equal(resolveSafeRedirect("https://evil.com"), null);
  assert.equal(resolveSafeRedirect("javascript:alert(1)"), null);
  assert.equal(resolveSafeRedirect("/auth?next=/wiki"), null);
  assert.equal(resolveSafeRedirect("/wiki?section=1"), "/wiki?section=1");

  assert.equal(extractApiError({ response: { data: { detail: "服务繁忙" } } }), "服务繁忙");
  assert.equal(extractApiError({ message: "网络超时" }, "默认错误"), "网络超时");
  assert.equal(
    formatDurationZh("2026-01-01T00:00:00Z", "2026-01-01T02:30:00Z"),
    "2小时 30分钟",
  );
  assert.equal(maskContactPreview("13800138000"), "138****8000");

  assert.equal(isCaptchaCanceled({ code: "CAPTCHA_CANCELED" }), true);
  assert.equal(isCaptchaCanceled({ isCaptchaCanceled: true }), true);
  assert.equal(captchaErrorMessage({ code: "CAPTCHA_CANCELED" }), "已取消人机验证");

  assert.equal(safeScrollBehavior("smooth"), "smooth");
  assert.equal(typeof api.request, "function");
  assert.equal(isRequestCanceled({ code: "ERR_CANCELED" }), true);

  assert.equal(resolveConfirmTone(undefined, true), "danger");
  assert.equal(resolveConfirmTone("default", true), "danger");
  assert.equal(resolveConfirmTone("default", false), "default");
  assert.equal(resolveConfirmTone("warning", true), "warning");
});

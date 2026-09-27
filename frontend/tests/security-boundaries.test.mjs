import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { JSDOM } from "jsdom";

const dom = new JSDOM("<!doctype html><html><body></body></html>", {
  url: "https://test.algowiki.cn/",
});
globalThis.window = dom.window;
globalThis.sessionStorage = dom.window.sessionStorage;
const parsedMarkup = [];
globalThis.DOMParser = class extends dom.window.DOMParser {
  parseFromString(markup, type) {
    parsedMarkup.push(markup);
    return super.parseFromString(markup, type);
  }
};

sessionStorage.setItem("algowiki_phone_verification_number", "13800138000");
sessionStorage.setItem("algowiki_phone_verification_ticket", "old-ticket");

const { renderMarkdown, renderInlineMarkdown } = await import("../src/services/markdown.js");
const {
  clearPhoneVerificationDraft,
  getPhoneVerificationDraft,
  isSamePhoneVerificationPrincipal,
  savePhoneVerificationDraft,
} = await import("../src/services/phoneVerificationDraft.js");

test("Markdown is sanitized before normalization and remains safe for HTML insertion", () => {
  parsedMarkup.length = 0;
  const output = renderMarkdown(
    '<img src="assets/photo.png" onerror="alert(1)"><a href="javascript:alert(1)" onclick="alert(1)">unsafe</a>',
  );
  assert.match(output, /src="\/wiki-assets\/photo\.png"/);
  assert.match(output, /target="_blank"/);
  assert.doesNotMatch(output, /onerror|onclick|javascript:/i);
  assert.equal(parsedMarkup.length, 1);
  assert.doesNotMatch(parsedMarkup[0], /onerror|onclick|javascript:/i);

  const inline = renderInlineMarkdown('<svg onload="alert(1)"></svg>safe');
  assert.doesNotMatch(inline, /onload|alert\(1\)/i);
  assert.match(inline, /safe/);
  assert.equal(parsedMarkup.length, 2);
  assert.doesNotMatch(parsedMarkup[1], /onload|alert\(1\)/i);
});

test("phone verification state stays in memory across page navigation and expires", () => {
  assert.equal(sessionStorage.getItem("algowiki_phone_verification_number"), null);
  assert.equal(sessionStorage.getItem("algowiki_phone_verification_ticket"), null);

  savePhoneVerificationDraft("13800138000", {
    ticket_token: "new-ticket",
    masked_phone: "138****8000",
    expires_in_seconds: 60,
  });
  assert.deepEqual(getPhoneVerificationDraft().phoneNumber, "13800138000");
  assert.deepEqual(getPhoneVerificationDraft().ticketToken, "new-ticket");
  assert.equal(sessionStorage.length, 0);

  clearPhoneVerificationDraft();
  assert.equal(getPhoneVerificationDraft().phoneNumber, "");
  assert.equal(getPhoneVerificationDraft().ticketToken, "");

  savePhoneVerificationDraft("13800138000", {
    ticket_token: "expired-ticket",
    expires_in_seconds: 0,
  });
  assert.equal(getPhoneVerificationDraft().ticketToken, "");
});

test("auth changes clear a previous account's pending phone verification", async () => {
  const source = await readFile(new URL("../src/stores/auth.js", import.meta.url), "utf8");
  assert.match(source, /applyAuth\(token, user\)\s*\{\s*if \(!isSamePhoneVerificationPrincipal\(this\.user, user\)\)\s*\{\s*clearPhoneVerificationDraft\(\)/);
  assert.match(source, /clearAuth\(\)\s*\{[\s\S]*?clearPhoneVerificationDraft\(\)/);
  assert.equal(isSamePhoneVerificationPrincipal({ id: 1 }, { id: 1 }), true);
  assert.equal(isSamePhoneVerificationPrincipal({ id: 1 }, { id: 2 }), false);
  assert.equal(isSamePhoneVerificationPrincipal(null, { id: 2 }), false);
});

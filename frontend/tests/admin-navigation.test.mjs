import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const adminPage = await readFile(new URL("../src/pages/AdminPage.vue", import.meta.url), "utf8");
const pulseManager = await readFile(
  new URL("../src/components/admin/PulseManager.vue", import.meta.url),
  "utf8",
);

test("daily check-in, captcha, and invitations live under basic management", () => {
  assert.match(adminPage, /key:\s*"pulse",\s*label:\s*"每日签到管理"/s);

  const basicGroup = adminPage.match(/label:\s*"基础管理",\s*items:\s*\[([^\]]+)\]/s)?.[1] || "";
  assert.match(basicGroup, /"pulse"/);
  assert.match(basicGroup, /"captcha"/);
  assert.match(basicGroup, /"invitations"/);

  const auditGroup = adminPage.match(/label:\s*"审计日志",\s*items:\s*\[([^\]]+)\]/s)?.[1] || "";
  assert.doesNotMatch(auditGroup, /"pulse"|"captcha"|"invitations"/);
  assert.match(pulseManager, /<h2>每日签到管理<\/h2>/);
});

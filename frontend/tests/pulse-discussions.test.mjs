import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("../", import.meta.url);

async function source(path) {
  return readFile(new URL(path, root), "utf8");
}

test("daily discussion routes and moments entry are registered", async () => {
  const [router, moments] = await Promise.all([
    source("src/router/index.js"),
    source("src/pages/MomentsPage.vue"),
  ]);

  assert.match(router, /name:\s*"pulse-discussions"/);
  assert.match(router, /path:\s*"\/moments\/discussions"/);
  assert.match(router, /name:\s*"pulse-discussion-detail"/);
  assert.match(router, /path:\s*"\/moments\/discussions\/:date"/);
  assert.match(moments, /:to="\{ name: 'pulse-discussions' \}"/);
  assert.match(moments, />每日讨论</);
});

test("archive exposes search, ordering, pagination, and inline proposal states", async () => {
  const [page, proposal] = await Promise.all([
    source("src/pages/PulseDiscussionsPage.vue"),
    source("src/components/pulse-discussions/TopicProposalForm.vue"),
  ]);
  const experience = `${page}\n${proposal}`;

  assert.match(page, /aria-label="讨论档案筛选"/);
  assert.match(page, /最新发布/);
  assert.match(page, /最近活跃/);
  assert.match(page, /page_size/);
  assert.match(experience, /AI 审核中/);
  assert.match(experience, /等待管理员排期/);
  assert.doesNotMatch(experience, /<dialog|role="dialog"/);
});

test("detail page provides reviewed answer composer and API wiring", async () => {
  const [detail, service] = await Promise.all([
    source("src/pages/PulseDiscussionDetailPage.vue"),
    source("src/services/pulse.js"),
  ]);

  assert.match(detail, /aria-label="发表回答"/);
  assert.match(detail, /提交审核中/);
  assert.match(detail, /pending/);
  assert.match(service, /\/pulse\/discussions\//);
  assert.match(service, /topic-proposals/);
});

test("pulse administration can review, schedule, and reject AI-approved topic proposals", async () => {
  const [manager, service] = await Promise.all([
    source("src/components/admin/PulseManager.vue"),
    source("src/services/pulse.js"),
  ]);

  assert.match(manager, /热门投稿/);
  assert.match(manager, /安排为每日讨论/);
  assert.match(manager, /拒绝投稿/);
  assert.match(manager, /scheduled_date/);
  assert.match(manager, /poll_options/);
  assert.match(service, /admin\/topic-proposals/);
  assert.match(service, /topic-proposals\/\$\{id\}\/schedule/);
  assert.match(service, /topic-proposals\/\$\{id\}\/reject/);
});

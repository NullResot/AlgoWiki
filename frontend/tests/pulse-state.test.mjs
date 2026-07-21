import test from "node:test";
import assert from "node:assert/strict";

import {
  createEmptyPulseState,
  getBindingCountdown,
  getPulseError,
  getRatingBand,
  normalizePulsePayload,
} from "../src/features/pulse/pulseState.js";
import * as pulseStateModule from "../src/features/pulse/pulseState.js";


const edition = {
  id: 9,
  date: "2026-07-19",
  question: { id: 4, title: "今日讨论", content_md: "说说你的看法", answers: [] },
  poll: {
    prompt: "你会先看题解吗？",
    selected_option_id: null,
    total_votes: 0,
    options: [
      { id: 1, text: "会", votes: 0, percentage: 0 },
      { id: 2, text: "不会", votes: 0, percentage: 0 },
    ],
  },
};


test("empty pulse state is safe before the first request", () => {
  const state = createEmptyPulseState();

  assert.equal(state.progress, 0);
  assert.equal(state.wallet.point, 0);
  assert.equal(state.edition, null);
  assert.equal(state.challenge, null);
});

test("rating bands expose the exact 300-point interval shown by ranking filters", () => {
  assert.deepEqual(getRatingBand(1799), {
    rating: 1799,
    min: 1500,
    max: 1799,
    label: "1500–1799",
  });
  assert.deepEqual(getRatingBand(1800), {
    rating: 1800,
    min: 1800,
    max: 2099,
    label: "1800–2099",
  });
  assert.equal(getRatingBand(null), null);
});


test("anonymous payload remains a public preview", () => {
  const state = normalizePulsePayload({ edition, me: null, previous_active_challenge: null });

  assert.equal(state.isAuthenticated, false);
  assert.equal(state.edition.question.title, "今日讨论");
  assert.equal(state.progress, 0);
  assert.equal(state.binding, null);
});


test("authenticated payload normalizes wallet progress and active challenge", () => {
  const payload = {
    edition,
    me: {
      progress: 2,
      wallet: { point: 7, reroll: 2, makeup: 1, super_makeup: 3 },
      binding: { id: 2, handle: "Tourist", is_active: true },
      challenge_mode: "A",
      challenge: {
        id: 19,
        mode: "A",
        status: "assigned",
        rerolls_remaining: 1,
        target: { contest_id: 700, index: "A", name: "Problem", rating: 1500 },
      },
      pending_makeup: {
        id: 5,
        target_date: "2026-07-18",
        status: "pending",
        assignment: { id: 21, mode: "A", status: "assigned" },
      },
      streak: { current: 4, longest: 8, signed_dates: [] },
    },
    previous_active_challenge: { id: 18, mode: "B", status: "assigned" },
  };

  const state = normalizePulsePayload(payload);

  assert.equal(state.isAuthenticated, true);
  assert.equal(state.progress, 2);
  assert.deepEqual(state.wallet, { point: 7, reroll: 2, makeup: 1, super_makeup: 3 });
  assert.equal(state.challenge.id, 19);
  assert.equal(state.pendingMakeup.assignment.id, 21);
  assert.equal(state.previousChallenge.id, 18);
  assert.equal(state.isModeLocked, true);
});


test("binding countdown expires at zero and exposes cooling state", () => {
  const now = Date.parse("2026-07-19T12:00:00+08:00");
  const active = getBindingCountdown(
    { expires_at: "2026-07-19T12:03:05+08:00" },
    now,
  );
  const expired = getBindingCountdown(
    { expires_at: "2026-07-19T11:59:59+08:00" },
    now,
  );
  const state = normalizePulsePayload({
    edition,
    me: {
      progress: 0,
      wallet: {},
      binding: {
        id: 2,
        handle: "Tourist",
        is_active: false,
        rebind_not_before: "2026-07-26T12:00:00+08:00",
      },
    },
  });

  assert.deepEqual(active, { expired: false, seconds: 185, label: "03:05" });
  assert.deepEqual(expired, { expired: true, seconds: 0, label: "00:00" });
  assert.equal(state.isCooling, true);
});


test("Codeforces outage is retryable while conflicts are refreshable", () => {
  const unavailable = getPulseError({
    response: { status: 503, data: { code: "codeforces_unavailable", detail: "稍后重试" } },
  });
  const conflict = getPulseError({
    response: { status: 409, data: { code: "mode_locked", detail: "模式已锁定" } },
  });

  assert.equal(unavailable.retryable, true);
  assert.equal(unavailable.refreshRequired, false);
  assert.equal(conflict.retryable, false);
  assert.equal(conflict.refreshRequired, true);
});


test("changing the authentication session invalidates the cached pulse snapshot", () => {
  const shouldRefreshPulseSession = pulseStateModule.shouldRefreshPulseSession;

  assert.equal(
    typeof shouldRefreshPulseSession,
    "function",
    "pulse state must expose an authentication-aware cache policy",
  );
  assert.equal(
    shouldRefreshPulseSession({
      initialized: true,
      loadedSessionKey: "anonymous",
      nextSessionKey: "token-user-a",
    }),
    true,
  );
  assert.equal(
    shouldRefreshPulseSession({
      initialized: true,
      loadedSessionKey: "token-user-a",
      nextSessionKey: "token-user-a",
    }),
    false,
  );
  assert.equal(
    shouldRefreshPulseSession({
      initialized: false,
      loadedSessionKey: "",
      nextSessionKey: "anonymous",
    }),
    true,
  );
});


test("Shanghai date comparison refreshes only after the business date changes", () => {
  assert.equal(
    pulseStateModule.getShanghaiDateKey(new Date("2026-07-19T15:59:59Z")),
    "2026-07-19",
  );
  assert.equal(
    pulseStateModule.getShanghaiDateKey(new Date("2026-07-19T16:00:00Z")),
    "2026-07-20",
  );
  assert.equal(
    pulseStateModule.shouldRefreshPulseDate(
      "2026-07-20",
      new Date("2026-07-20T08:00:00+08:00"),
    ),
    false,
  );
  assert.equal(
    pulseStateModule.shouldRefreshPulseDate(
      "2026-07-19",
      new Date("2026-07-20T08:00:00+08:00"),
    ),
    true,
  );
});

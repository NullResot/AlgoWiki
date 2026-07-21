import test from "node:test";
import assert from "node:assert/strict";
import * as pulseStateModule from "../src/features/pulse-demo/pulseDemoState.js";

import {
  createPulseDemoState,
  getPulseProgress,
  normalizePulseDemoState,
  reducePulseDemoState,
} from "../src/features/pulse-demo/pulseDemoState.js";

const DATE_KEY = "2026-07-19";

function createState() {
  return createPulseDemoState(DATE_KEY);
}

function dispatch(state, type, payload = {}) {
  return reducePulseDemoState(state, { type, ...payload });
}

test("new day starts at 0/3 and requests the first-visit sheet", () => {
  const state = createState();

  assert.equal(state.dateKey, DATE_KEY);
  assert.equal(getPulseProgress(state), 0);
  assert.equal(state.firstVisitSeen, false);
  assert.equal(state.points, 0);
});

test("dismissing the first-visit sheet persists without changing progress", () => {
  const state = dispatch(createState(), "dismiss-first-visit");

  assert.equal(state.firstVisitSeen, true);
  assert.equal(getPulseProgress(state), 0);
});

test("the first answer completes community progress and grants one reroll ticket", () => {
  const initialTickets = createState().tickets.reroll;
  let state = dispatch(createState(), "answer-question", { answer: "先按贡献拆分，再讨论复杂度边界。" });

  assert.equal(state.question.completed, true);
  assert.equal(state.question.answer, "先按贡献拆分，再讨论复杂度边界。");
  assert.equal(state.tickets.reroll, initialTickets + 1);
  assert.equal(getPulseProgress(state), 1);

  state = dispatch(state, "answer-question", { answer: "补充一个反例。" });
  assert.equal(state.tickets.reroll, initialTickets + 1);
});

test("challenge mode locks after choosing A or B", () => {
  let state = dispatch(createState(), "choose-challenge", { mode: "A" });
  state = dispatch(state, "choose-challenge", { mode: "B" });

  assert.equal(state.challenge.mode, "A");
  assert.equal(state.challenge.drawIndex, 0);
});

test("rerolls stay in the chosen mode and stop after two switches", () => {
  let state = dispatch(createState(), "answer-question", { answer: "换一题看看。" });
  state = dispatch(state, "choose-challenge", { mode: "B" });
  state = dispatch(state, "reroll-challenge");
  state = dispatch(state, "reroll-challenge");
  state = dispatch(state, "reroll-challenge");

  assert.equal(state.challenge.mode, "B");
  assert.equal(state.challenge.rerollsUsed, 2);
  assert.equal(state.challenge.drawIndex, 2);
  assert.equal(state.tickets.reroll, 0);
});

test("A completion gives one point and B completion gives three points", () => {
  let aState = dispatch(createState(), "choose-challenge", { mode: "A" });
  aState = dispatch(aState, "complete-challenge");
  aState = dispatch(aState, "complete-challenge");

  let bState = dispatch(createState(), "choose-challenge", { mode: "B" });
  bState = dispatch(bState, "complete-challenge");

  assert.equal(aState.points, 1);
  assert.equal(bState.points, 3);
  assert.equal(getPulseProgress(aState), 1);
  assert.equal(getPulseProgress(bState), 1);
});

test("poll accepts only the first valid option", () => {
  let state = dispatch(createState(), "vote-poll", { optionId: "readability" });
  state = dispatch(state, "vote-poll", { optionId: "speed" });

  assert.equal(state.poll.optionId, "readability");
  assert.equal(state.poll.completed, true);
  assert.equal(getPulseProgress(state), 1);
});

test("answer, challenge and poll produce a complete 3/3 pulse", () => {
  let state = dispatch(createState(), "answer-question", { answer: "今天的观察记录。" });
  state = dispatch(state, "choose-challenge", { mode: "A" });
  state = dispatch(state, "complete-challenge");
  state = dispatch(state, "vote-poll", { optionId: "readability" });

  assert.equal(getPulseProgress(state), 3);
  assert.equal(state.points, 1);
});

test("normalization rejects stale dates and reset returns a fresh day", () => {
  const stale = { ...createState(), dateKey: "2026-07-18", points: 99 };
  const normalized = normalizePulseDemoState(stale, DATE_KEY);
  let completed = dispatch(createState(), "answer-question", { answer: "临时状态。" });
  completed = dispatch(completed, "reset", { dateKey: DATE_KEY });

  assert.equal(normalized.dateKey, DATE_KEY);
  assert.equal(normalized.points, 0);
  assert.deepEqual(completed, createState());
});

test("normalization cannot mark signals complete without valid underlying data", () => {
  const corrupted = {
    ...createState(),
    question: { answer: "   ", completed: true },
    challenge: { mode: null, drawIndex: 0, rerollsUsed: 0, completed: true },
    poll: { optionId: "not-an-option", completed: true },
  };

  const normalized = normalizePulseDemoState(corrupted, DATE_KEY);

  assert.equal(normalized.question.completed, false);
  assert.equal(normalized.challenge.completed, false);
  assert.equal(normalized.poll.completed, false);
  assert.equal(getPulseProgress(normalized), 0);
});

test("local day helpers identify the date and exact time remaining before midnight", () => {
  const halfSecondBeforeMidnight = new Date(2026, 6, 19, 23, 59, 59, 500);

  assert.equal(pulseStateModule.getLocalDateKey(halfSecondBeforeMidnight), DATE_KEY);
  assert.equal(pulseStateModule.getMillisecondsUntilNextLocalDay(halfSecondBeforeMidnight), 500);
});

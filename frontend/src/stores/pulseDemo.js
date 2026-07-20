import { computed, ref } from "vue";
import { defineStore } from "pinia";

import { challengePools, pulsePoll } from "../features/pulse-demo/pulseDemoData";
import {
  PULSE_DEMO_STORAGE_KEY,
  createPulseDemoState,
  getLocalDateKey,
  getMillisecondsUntilNextLocalDay,
  getPulseProgress,
  normalizePulseDemoState,
  reducePulseDemoState,
} from "../features/pulse-demo/pulseDemoState";

export const usePulseDemoStore = defineStore("pulse-demo", () => {
  const state = ref(createPulseDemoState(getLocalDateKey()));
  const initialized = ref(false);
  let midnightTimer = null;

  const progressCount = computed(() => getPulseProgress(state.value));
  const isComplete = computed(() => progressCount.value === 3);
  const showFirstVisit = computed(() => initialized.value && !state.value.firstVisitSeen);
  const currentChallenge = computed(() => {
    const mode = state.value.challenge.mode;
    if (!mode) return null;
    const pool = challengePools[mode];
    return pool[state.value.challenge.drawIndex % pool.length];
  });
  const pollResults = computed(() => {
    const selectedId = state.value.poll.optionId;
    const options = pulsePoll.options.map((option) => ({
      ...option,
      votes: option.votes + (option.id === selectedId ? 1 : 0),
    }));
    const totalVotes = options.reduce((total, option) => total + option.votes, 0);
    return options.map((option) => ({
      ...option,
      percent: Math.round((option.votes / totalVotes) * 100),
    }));
  });

  function initialize() {
    const dateKey = getLocalDateKey();
    if (initialized.value) {
      if (state.value.dateKey !== dateKey) {
        state.value = normalizePulseDemoState(state.value, dateKey);
        persist();
      }
      return;
    }
    if (typeof window !== "undefined") {
      try {
        const saved = JSON.parse(window.localStorage.getItem(PULSE_DEMO_STORAGE_KEY) || "null");
        state.value = normalizePulseDemoState(saved, dateKey);
      } catch {
        state.value = createPulseDemoState(dateKey);
      }
    } else {
      state.value = createPulseDemoState(dateKey);
    }
    initialized.value = true;
    persist();
    scheduleMidnightRefresh();
  }

  function dispatch(type, payload = {}) {
    initialize();
    state.value = reducePulseDemoState(state.value, { type, ...payload });
    persist();
  }

  function answerQuestion(answer) {
    dispatch("answer-question", { answer });
  }

  function chooseChallenge(mode) {
    dispatch("choose-challenge", { mode });
  }

  function rerollChallenge() {
    dispatch("reroll-challenge");
  }

  function completeChallenge() {
    dispatch("complete-challenge");
  }

  function vote(optionId) {
    dispatch("vote-poll", { optionId });
  }

  function dismissFirstVisit() {
    dispatch("dismiss-first-visit");
  }

  function resetDemo() {
    dispatch("reset", { dateKey: getLocalDateKey() });
  }

  function persist() {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(PULSE_DEMO_STORAGE_KEY, JSON.stringify(state.value));
    } catch {
      // The Demo remains usable in memory when storage is unavailable.
    }
  }

  function scheduleMidnightRefresh() {
    if (typeof window === "undefined") return;
    window.clearTimeout(midnightTimer);
    midnightTimer = window.setTimeout(() => {
      const dateKey = getLocalDateKey();
      state.value = normalizePulseDemoState(state.value, dateKey);
      persist();
      scheduleMidnightRefresh();
    }, getMillisecondsUntilNextLocalDay() + 100);
  }

  return {
    state,
    initialized,
    progressCount,
    isComplete,
    showFirstVisit,
    currentChallenge,
    pollResults,
    initialize,
    answerQuestion,
    chooseChallenge,
    rerollChallenge,
    completeChallenge,
    vote,
    dismissFirstVisit,
    resetDemo,
  };
});

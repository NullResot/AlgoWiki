import { computed, onScopeDispose, ref } from "vue";
import { defineStore } from "pinia";

import { createEmptyPulseState, getBindingCountdown, getPulseError, normalizePulsePayload } from "../features/pulse/pulseState";
import pulseApi from "../services/pulse";

const FIRST_VISIT_PREFIX = "algowiki-pulse-visited";

function idempotencyKey(prefix) {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `${prefix}:${crypto.randomUUID()}`;
  }
  return `${prefix}:${Date.now()}:${Math.random().toString(16).slice(2)}`;
}

function millisecondsUntilShanghaiMidnight() {
  const now = new Date();
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(now);
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  const nextUtc = Date.UTC(Number(values.year), Number(values.month) - 1, Number(values.day) + 1, -8);
  return Math.max(1000, nextUtc - now.getTime());
}

export const usePulseStore = defineStore("pulse", () => {
  const state = ref(createEmptyPulseState());
  const initialized = ref(false);
  const loading = ref(false);
  const activeAction = ref("");
  const error = ref(null);
  const firstVisitSeen = ref(true);
  const rankings = ref([]);
  const atlas = ref({ current: 0, longest: 0, signed_dates: [] });
  const nowTick = ref(Date.now());
  let tickTimer = null;
  let midnightTimer = null;

  const progressCount = computed(() => state.value.progress);
  const isComplete = computed(() => progressCount.value === 3);
  const isAuthenticated = computed(() => state.value.isAuthenticated);
  const showFirstVisit = computed(
    () => initialized.value && Boolean(state.value.edition) && !firstVisitSeen.value,
  );
  const bindingCountdown = computed(() =>
    getBindingCountdown(state.value.pendingVerification, nowTick.value),
  );
  const currentChallenge = computed(() => state.value.challenge);
  const canReroll = computed(
    () =>
      Boolean(state.value.challenge) &&
      state.value.challenge.status === "assigned" &&
      Number(state.value.challenge.rerolls_remaining || 0) > 0 &&
      state.value.wallet.reroll > 0,
  );
  const pollResults = computed(() =>
    (state.value.edition?.poll?.options || []).map((option, index) => ({
      ...option,
      label: option.text,
      percent: Number(option.percentage || 0),
      tone: ["violet", "cyan", "gold", "mint", "rose"][index % 5],
    })),
  );

  function syncFirstVisit() {
    const date = state.value.edition?.date;
    if (!date || typeof window === "undefined") {
      firstVisitSeen.value = true;
      return;
    }
    firstVisitSeen.value = window.localStorage.getItem(`${FIRST_VISIT_PREFIX}:${date}`) === "1";
  }

  function startTimers() {
    if (typeof window === "undefined") return;
    window.clearInterval(tickTimer);
    tickTimer = window.setInterval(() => {
      nowTick.value = Date.now();
    }, 1000);
    window.clearTimeout(midnightTimer);
    midnightTimer = window.setTimeout(async () => {
      await fetchToday();
      startTimers();
    }, millisecondsUntilShanghaiMidnight() + 250);
  }

  async function fetchToday() {
    loading.value = true;
    error.value = null;
    try {
      state.value = normalizePulsePayload(await pulseApi.today());
      syncFirstVisit();
      return state.value;
    } catch (requestError) {
      error.value = getPulseError(requestError);
      throw requestError;
    } finally {
      loading.value = false;
    }
  }

  async function initialize() {
    if (initialized.value) return state.value;
    await fetchToday();
    initialized.value = true;
    startTimers();
    return state.value;
  }

  async function runAction(name, callback, { refresh = true } = {}) {
    activeAction.value = name;
    error.value = null;
    try {
      const result = await callback();
      if (refresh) await fetchToday();
      return result;
    } catch (requestError) {
      error.value = getPulseError(requestError);
      if (error.value.refreshRequired) {
        await fetchToday().catch(() => {});
      }
      throw requestError;
    } finally {
      activeAction.value = "";
    }
  }

  const answerQuestion = (content) => runAction("answer", () => pulseApi.answer(content));
  const vote = (optionId) => runAction("vote", () => pulseApi.vote(optionId));
  const startBinding = (handle) => runAction("bind-start", () => pulseApi.startBinding(handle));
  const verifyBinding = () => {
    const verificationId = state.value.pendingVerification?.id;
    if (!verificationId) return Promise.reject(new Error("没有待验证的绑定请求"));
    return runAction("bind-verify", () => pulseApi.verifyBinding(verificationId));
  };
  const selfUnbind = (password) => runAction("unbind", () => pulseApi.selfUnbind(password));
  const chooseChallenge = (mode) => runAction("choose", () => pulseApi.chooseChallenge(mode));
  const rerollChallenge = () => runAction("reroll", () => pulseApi.rerollChallenge());
  const checkChallenge = () => {
    const assignmentId = state.value.challenge?.id;
    if (!assignmentId) return Promise.reject(new Error("没有可检测的挑战"));
    return runAction("check", () => pulseApi.checkChallenge(assignmentId));
  };
  const checkAssignment = (assignmentId) => {
    if (!assignmentId) return Promise.reject(new Error("没有可检测的补签挑战"));
    return runAction("check-makeup", () => pulseApi.checkChallenge(assignmentId));
  };
  const createMakeup = (targetDate, kind) =>
    runAction("makeup", () => pulseApi.createMakeup(targetDate, kind));
  const redeem = (code) =>
    runAction("redeem", () => pulseApi.redeem(code, idempotencyKey("pulse-redeem")));

  async function loadAtlas() {
    atlas.value = await pulseApi.atlas();
    return atlas.value;
  }

  async function loadRankings(params = {}) {
    const data = await pulseApi.rankings(params);
    rankings.value = data.results || [];
    return rankings.value;
  }

  function dismissFirstVisit() {
    const date = state.value.edition?.date;
    firstVisitSeen.value = true;
    if (date && typeof window !== "undefined") {
      window.localStorage.setItem(`${FIRST_VISIT_PREFIX}:${date}`, "1");
    }
  }

  onScopeDispose(() => {
    if (typeof window === "undefined") return;
    window.clearInterval(tickTimer);
    window.clearTimeout(midnightTimer);
  });

  return {
    state,
    initialized,
    loading,
    activeAction,
    error,
    rankings,
    atlas,
    progressCount,
    isComplete,
    isAuthenticated,
    showFirstVisit,
    bindingCountdown,
    currentChallenge,
    canReroll,
    pollResults,
    initialize,
    fetchToday,
    answerQuestion,
    vote,
    startBinding,
    verifyBinding,
    selfUnbind,
    chooseChallenge,
    rerollChallenge,
    checkChallenge,
    checkAssignment,
    createMakeup,
    redeem,
    loadAtlas,
    loadRankings,
    dismissFirstVisit,
  };
});

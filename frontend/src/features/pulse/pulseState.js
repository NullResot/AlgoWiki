const EMPTY_WALLET = Object.freeze({
  point: 0,
  reroll: 0,
  makeup: 0,
  super_makeup: 0,
});

function nonNegativeInteger(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed >= 0 ? parsed : fallback;
}

export function createEmptyPulseState() {
  return {
    edition: null,
    isAuthenticated: false,
    progress: 0,
    wallet: { ...EMPTY_WALLET },
    binding: null,
    pendingVerification: null,
    challenge: null,
    pendingMakeup: null,
    previousChallenge: null,
    streak: { current: 0, longest: 0, signed_dates: [] },
    communityCompleted: false,
    pollCompleted: false,
    challengeCompleted: false,
    signed: false,
    challengeMode: "",
    isModeLocked: false,
    isCooling: false,
    serverTime: null,
  };
}

function normalizeSessionKey(value) {
  const key = String(value || "").trim();
  return key || "anonymous";
}

export function shouldRefreshPulseSession({
  initialized,
  loadedSessionKey,
  nextSessionKey,
}) {
  return (
    !initialized ||
    normalizeSessionKey(loadedSessionKey) !== normalizeSessionKey(nextSessionKey)
  );
}

export function getShanghaiDateKey(date = new Date()) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

export function shouldRefreshPulseDate(businessDate, date = new Date()) {
  return String(businessDate || "") !== getShanghaiDateKey(date);
}

export function normalizePulsePayload(payload) {
  const current = createEmptyPulseState();
  if (!payload || typeof payload !== "object") return current;
  current.edition = payload.edition && typeof payload.edition === "object" ? payload.edition : null;
  current.previousChallenge =
    payload.previous_active_challenge && typeof payload.previous_active_challenge === "object"
      ? payload.previous_active_challenge
      : null;
  current.serverTime = payload.server_time || null;

  const me = payload.me;
  if (!me || typeof me !== "object") return current;
  current.isAuthenticated = true;
  current.progress = Math.min(3, nonNegativeInteger(me.progress));
  current.wallet = {
    point: nonNegativeInteger(me.wallet?.point),
    reroll: nonNegativeInteger(me.wallet?.reroll),
    makeup: nonNegativeInteger(me.wallet?.makeup),
    super_makeup: nonNegativeInteger(me.wallet?.super_makeup),
  };
  current.binding = me.binding && typeof me.binding === "object" ? me.binding : null;
  current.pendingVerification =
    me.pending_verification && typeof me.pending_verification === "object"
      ? me.pending_verification
      : null;
  current.challenge = me.challenge && typeof me.challenge === "object" ? me.challenge : null;
  current.pendingMakeup =
    me.pending_makeup && typeof me.pending_makeup === "object" ? me.pending_makeup : null;
  current.streak = {
    current: nonNegativeInteger(me.streak?.current),
    longest: nonNegativeInteger(me.streak?.longest),
    signed_dates: Array.isArray(me.streak?.signed_dates) ? me.streak.signed_dates : [],
  };
  current.communityCompleted = Boolean(me.community_completed);
  current.pollCompleted = Boolean(me.poll_completed);
  current.challengeCompleted = Boolean(me.challenge_completed);
  current.signed = Boolean(me.signed);
  current.challengeMode = String(me.challenge_mode || current.challenge?.mode || "");
  current.isModeLocked = Boolean(current.challengeMode);
  const coolingUntil = Date.parse(current.binding?.rebind_not_before || "");
  current.isCooling = Boolean(
    current.binding && !current.binding.is_active && Number.isFinite(coolingUntil) && coolingUntil > Date.now(),
  );
  return current;
}

export function getBindingCountdown(verification, now = Date.now()) {
  const expiresAt = Date.parse(verification?.expires_at || "");
  const remaining = Number.isFinite(expiresAt) ? Math.max(0, Math.ceil((expiresAt - now) / 1000)) : 0;
  const minutes = Math.floor(remaining / 60);
  const seconds = remaining % 60;
  return {
    expired: remaining === 0,
    seconds: remaining,
    label: `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`,
  };
}

export function getPulseError(error) {
  const response = error?.response;
  const status = Number(response?.status || 0);
  const code = String(response?.data?.code || (status ? `http_${status}` : "network_error"));
  return {
    code,
    status,
    message: String(response?.data?.detail || error?.message || "请求失败，请稍后重试。"),
    retryable: !status || status === 503 || status === 429,
    refreshRequired: status === 409,
  };
}

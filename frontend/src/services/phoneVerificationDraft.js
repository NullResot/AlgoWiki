import { reactive } from "vue";

const legacyStorageKeys = [
  "algowiki_phone_verification_number",
  "algowiki_phone_verification_ticket",
  "algowiki_phone_verification_masked",
  "algowiki_phone_verification_expires",
];

if (typeof sessionStorage !== "undefined") {
  legacyStorageKeys.forEach((key) => sessionStorage.removeItem(key));
}

const draft = reactive({
  phone_number: "",
  verify_code: "",
  ticket_token: "",
  masked_phone: "",
  expires_at: 0,
  send_pending: false,
});
let generation = 0;
let ticketGeneration = 0;
let pendingSendGeneration = 0;
let expiryTimer;

export function getPhoneVerificationDraft() {
  if (draft.expires_at && Date.now() >= draft.expires_at) {
    expirePhoneVerificationDraft();
  }
  return draft;
}

export function beginPhoneVerificationRequest() {
  generation += 1;
  return generation;
}

export function beginPhoneVerificationSend() {
  const requestGeneration = beginPhoneVerificationRequest();
  pendingSendGeneration = requestGeneration;
  draft.send_pending = true;
  return requestGeneration;
}

export function finishPhoneVerificationSend(requestGeneration) {
  if (pendingSendGeneration !== requestGeneration) return;
  pendingSendGeneration = 0;
  draft.send_pending = false;
}

export function isPhoneVerificationGenerationCurrent(requestGeneration) {
  return requestGeneration === generation;
}

export function savePhoneVerificationDraft(phoneNumber, payload, requestGeneration) {
  if (!isPhoneVerificationGenerationCurrent(requestGeneration)) return false;
  const token = String(payload?.ticket_token || "");
  const seconds = Number(payload?.expires_in_seconds || 0);
  if (!token || !Number.isFinite(seconds) || seconds <= 0) {
    clearPhoneVerificationDraft();
    return false;
  }
  clearTimeout(expiryTimer);
  draft.phone_number = String(phoneNumber || "");
  draft.ticket_token = token;
  draft.masked_phone = String(payload?.masked_phone || "");
  draft.verify_code = "";
  draft.expires_at = Date.now() + seconds * 1000;
  ticketGeneration = requestGeneration;
  const expiresAt = draft.expires_at;
  const expireAtDeadline = () => {
    if (draft.expires_at !== expiresAt) return;
    const remaining = expiresAt - Date.now();
    if (remaining > 0) {
      expiryTimer = setTimeout(expireAtDeadline, remaining);
      expiryTimer?.unref?.();
      return;
    }
    expirePhoneVerificationDraft();
  };
  expiryTimer = setTimeout(expireAtDeadline, seconds * 1000);
  expiryTimer?.unref?.();
  return true;
}

function resetPhoneVerificationDraft(invalidateRequests) {
  if (invalidateRequests) {
    generation += 1;
    pendingSendGeneration = 0;
    draft.send_pending = false;
  }
  clearTimeout(expiryTimer);
  expiryTimer = undefined;
  ticketGeneration = 0;
  draft.phone_number = "";
  draft.verify_code = "";
  draft.ticket_token = "";
  draft.masked_phone = "";
  draft.expires_at = 0;
}

function expirePhoneVerificationDraft() {
  resetPhoneVerificationDraft(generation === ticketGeneration);
}

export function clearPhoneVerificationDraft() {
  resetPhoneVerificationDraft(true);
}

export function isSamePhoneVerificationPrincipal(previousUser, nextUser) {
  const previousId = Number(previousUser?.id);
  const nextId = Number(nextUser?.id);
  return Number.isInteger(previousId) && previousId > 0 && previousId === nextId;
}

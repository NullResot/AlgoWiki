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
});
let generation = 0;
let expiryTimer;

export function getPhoneVerificationDraft() {
  if (draft.expires_at && Date.now() >= draft.expires_at) {
    clearPhoneVerificationDraft();
  }
  return draft;
}

export function beginPhoneVerificationRequest() {
  generation += 1;
  return generation;
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
  expiryTimer = setTimeout(clearPhoneVerificationDraft, seconds * 1000);
  expiryTimer?.unref?.();
  return true;
}

export function clearPhoneVerificationDraft() {
  generation += 1;
  clearTimeout(expiryTimer);
  expiryTimer = undefined;
  draft.phone_number = "";
  draft.verify_code = "";
  draft.ticket_token = "";
  draft.masked_phone = "";
  draft.expires_at = 0;
}

export function isSamePhoneVerificationPrincipal(previousUser, nextUser) {
  const previousId = Number(previousUser?.id);
  const nextId = Number(nextUser?.id);
  return Number.isInteger(previousId) && previousId > 0 && previousId === nextId;
}

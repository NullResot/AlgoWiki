const legacyStorageKeys = [
  "algowiki_phone_verification_number",
  "algowiki_phone_verification_ticket",
  "algowiki_phone_verification_masked",
  "algowiki_phone_verification_expires",
];

if (typeof sessionStorage !== "undefined") {
  legacyStorageKeys.forEach((key) => sessionStorage.removeItem(key));
}

const draft = {
  phoneNumber: "",
  ticketToken: "",
  maskedPhone: "",
  expiresAt: 0,
};

export function getPhoneVerificationDraft() {
  if (draft.expiresAt && Date.now() >= draft.expiresAt) {
    clearPhoneVerificationDraft();
  }
  return { ...draft };
}

export function savePhoneVerificationDraft(phoneNumber, payload) {
  const token = String(payload?.ticket_token || "");
  if (!token) {
    clearPhoneVerificationDraft();
    return;
  }
  draft.phoneNumber = String(phoneNumber || "");
  draft.ticketToken = token;
  draft.maskedPhone = String(payload?.masked_phone || "");
  draft.expiresAt = Date.now() + Math.max(0, Number(payload?.expires_in_seconds || 0)) * 1000;
}

export function clearPhoneVerificationDraft() {
  draft.phoneNumber = "";
  draft.ticketToken = "";
  draft.maskedPhone = "";
  draft.expiresAt = 0;
}

export function isSamePhoneVerificationPrincipal(previousUser, nextUser) {
  const previousId = Number(previousUser?.id);
  const nextId = Number(nextUser?.id);
  return Number.isInteger(previousId) && previousId > 0 && previousId === nextId;
}

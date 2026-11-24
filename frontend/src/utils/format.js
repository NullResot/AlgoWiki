function pad2(value) {
  return String(value).padStart(2, "0");
}

export function formatDateTime(value, fallback = "-") {
  if (!value) return fallback;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())} ${pad2(date.getHours())}:${pad2(date.getMinutes())}`;
}

export function formatDate(value, fallback = "-") {
  if (!value) return fallback;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;
}

export function formatDurationZh(startValue, endValue) {
  if (!startValue || !endValue) return "-";
  const startMs = new Date(startValue).getTime();
  const endMs = new Date(endValue).getTime();
  if (!Number.isFinite(startMs) || !Number.isFinite(endMs) || endMs <= startMs) {
    return "-";
  }
  const totalMinutes = Math.round((endMs - startMs) / 60000);
  const days = Math.floor(totalMinutes / (24 * 60));
  const hours = Math.floor((totalMinutes % (24 * 60)) / 60);
  const minutes = totalMinutes % 60;
  const parts = [];
  if (days > 0) parts.push(`${days}天`);
  if (hours > 0) parts.push(`${hours}小时`);
  if (minutes > 0 || parts.length === 0) parts.push(`${minutes}分钟`);
  return parts.join(" ");
}

export function extractApiError(error, fallback = "操作失败，请稍后重试") {
  const payload = error?.response?.data;
  if (!payload) {
    return String(error?.message || "").trim() || fallback;
  }
  if (typeof payload === "string") {
    return payload.trim() || fallback;
  }
  if (typeof payload.detail === "string" && payload.detail.trim()) {
    return payload.detail.trim();
  }
  if (typeof payload.message === "string" && payload.message.trim()) {
    return payload.message.trim();
  }
  if (Array.isArray(payload)) {
    const joined = payload.map((item) => String(item || "").trim()).filter(Boolean).join("；");
    return joined || fallback;
  }
  if (typeof payload === "object") {
    const parts = [];
    for (const [key, value] of Object.entries(payload)) {
      if (key === "request_id" || key === "retry_after_seconds" || key === "code") continue;
      if (Array.isArray(value)) {
        const text = value.map((item) => String(item || "").trim()).filter(Boolean).join("；");
        if (text) parts.push(text);
      } else if (typeof value === "string" && value.trim()) {
        parts.push(value.trim());
      }
    }
    if (parts.length) return parts.join("；");
  }
  return fallback;
}

export function resolveSafeRedirect(raw) {
  const value = String(raw || "").trim();
  if (!value.startsWith("/") || value.startsWith("//")) {
    return null;
  }
  if (value.startsWith("/auth")) {
    return null;
  }
  return value;
}

export function maskContactPreview(value) {
  const text = String(value || "").trim();
  if (!text) return "-";
  if (text.includes("@")) {
    const [local, domain] = text.split("@", 2);
    if (!domain) return "***";
    const visible = local.length <= 2 ? local.slice(0, 1) : `${local.slice(0, 2)}***`;
    return `${visible}@${domain}`;
  }
  const digits = text.replace(/\s+/g, "");
  if (digits.length >= 7) {
    return `${digits.slice(0, 3)}****${digits.slice(-4)}`;
  }
  if (digits.length >= 3) {
    return `${digits.slice(0, 1)}***${digits.slice(-1)}`;
  }
  return "***";
}

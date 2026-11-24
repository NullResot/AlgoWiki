import axios from "axios";

const METHOD_OVERRIDE_HEADER = "X-HTTP-Method-Override";
const OVERRIDDEN_METHODS = new Set(["put", "patch", "delete"]);

const api = axios.create({
  baseURL: "/api",
  timeout: 15000,
});

export function isRequestCanceled(error) {
  return (
    axios.isCancel(error) ||
    error?.code === "ERR_CANCELED" ||
    error?.name === "CanceledError" ||
    error?.message === "canceled"
  );
}

function looksLikeHtmlDocument(value) {
  const text = String(value || "").trim().toLowerCase();
  if (!text) return false;
  return text.startsWith("<!doctype html") || text.startsWith("<html") || text.includes("<body");
}

function normalizeServerError(error) {
  if (isRequestCanceled(error)) {
    return error;
  }
  const response = error?.response;
  if (!response) {
    error.message = "网络连接异常，请检查网络后稍后重试。";
    return error;
  }

  const status = Number(response.status || 0);
  if (typeof response.data === "string" && looksLikeHtmlDocument(response.data)) {
    response.data = {
      detail: status >= 500 ? "服务暂时不可用，请稍后重试。" : `请求失败（HTTP ${status}）。`,
    };
  }
  return error;
}

function getRetryAfterSeconds(response) {
  const raw = response?.headers?.["retry-after"];
  const seconds = Number(raw);
  if (Number.isFinite(seconds) && seconds > 0) {
    return Math.ceil(seconds);
  }
  return null;
}

function normalizeRateLimitError(error) {
  const response = error?.response;
  if (!response || response.status !== 429) {
    return error;
  }

  const waitSeconds = getRetryAfterSeconds(response);
  const requestUrl = String(error?.config?.url || "");
  let detail = waitSeconds
    ? `操作过于频繁，请在 ${waitSeconds} 秒后重试。`
    : "操作过于频繁，请稍后再试。";

  if (requestUrl.includes("/auth/login/")) {
    detail = waitSeconds
      ? `登录尝试过于频繁，请在 ${waitSeconds} 秒后重试。`
      : "登录尝试过于频繁，请稍后再试。";
  } else if (requestUrl.includes("/auth/register")) {
    detail = waitSeconds
      ? `注册请求过于频繁，请在 ${waitSeconds} 秒后重试。`
      : "注册请求过于频繁，请稍后再试。";
  } else if (requestUrl.includes("/auth/password-reset")) {
    detail = waitSeconds
      ? `密码重置请求过于频繁，请在 ${waitSeconds} 秒后重试。`
      : "密码重置请求过于频繁，请稍后再试。";
  }

  if (typeof response.data === "string") {
    response.data = { detail };
  } else if (response.data && typeof response.data === "object") {
    response.data = {
      ...response.data,
      detail,
    };
  } else {
    response.data = { detail };
  }

  if (waitSeconds) {
    response.data.retry_after_seconds = waitSeconds;
  }
  return error;
}

api.interceptors.request.use((config) => {
  const method = String(config.method || "get").toLowerCase();
  if (OVERRIDDEN_METHODS.has(method)) {
    config.headers = {
      ...(config.headers || {}),
      [METHOD_OVERRIDE_HEADER]: method.toUpperCase(),
    };
    config.method = "post";
  }

  const token = localStorage.getItem("algowiki_token");
  if (token) {
    config.headers = {
      ...(config.headers || {}),
    };
    config.headers.Authorization = `Token ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (isRequestCanceled(error)) {
      throw error;
    }
    const config = error?.config;
    if (!config) throw normalizeServerError(error);

    const status = error?.response?.status || 0;
    if (status === 429) {
      throw normalizeRateLimitError(error);
    }

    const method = (config.method || "get").toLowerCase();

    if (status === 401) {
      const hasToken = Boolean(localStorage.getItem("algowiki_token"));
      if (hasToken) {
        localStorage.removeItem("algowiki_token");
        localStorage.removeItem("algowiki_user");
        window.dispatchEvent(new CustomEvent("algowiki:auth-invalid"));
      }

      // Public GET endpoints should recover after dropping stale token.
      if (method === "get" && hasToken && !config.__retryWithoutAuth) {
        const retryConfig = {
          ...config,
          __retryWithoutAuth: true,
          headers: { ...(config.headers || {}) },
        };
        if (retryConfig.headers.Authorization) {
          delete retryConfig.headers.Authorization;
        }
        return api.request(retryConfig);
      }
      throw normalizeServerError(error);
    }

    if (method !== "get") throw normalizeServerError(error);

    const isNetworkError = !error?.response;
    const canRetry = isNetworkError || status >= 500;
    const retryCount = Number(config.__retryCount || 0);
    if (!canRetry || retryCount >= 2) {
      throw normalizeServerError(error);
    }

    config.__retryCount = retryCount + 1;
    const retryDelayMs = retryCount === 0 ? 350 : 800;
    await new Promise((resolve) => window.setTimeout(resolve, retryDelayMs));
    if (isRequestCanceled(error)) {
      throw error;
    }
    return api.request(config);
  }
);

export default api;

import api from "../services/api.js";

let activeResolver = null;
let configPromise = null;
let configLoadedAt = 0;
const CONFIG_CACHE_TTL_MS = 60 * 1000;

export function getFallbackCaptchaConfig() {
  return {
    enabled: import.meta.env.VITE_CAPTCHA_ENABLED === "1",
    required_for_authenticated_users: true,
    turnstile_site_key: import.meta.env.VITE_TURNSTILE_SITE_KEY || "",
    secondary_enabled: import.meta.env.VITE_SECONDARY_CAPTCHA_ENABLED === "1",
    secondary_provider: import.meta.env.VITE_SECONDARY_CAPTCHA_PROVIDER || "geetest",
    geetest_captcha_id: import.meta.env.VITE_GEETEST_CAPTCHA_ID || "",
    token_ttl_seconds: 300,
  };
}

export async function getCaptchaConfig({ force = false } = {}) {
  const fresh = configPromise && Date.now() - configLoadedAt < CONFIG_CACHE_TTL_MS;
  if (!force && fresh) return configPromise;
  configLoadedAt = Date.now();
  configPromise = api
    .get("/captcha/config/")
    .then(({ data }) => ({
      ...getFallbackCaptchaConfig(),
      ...(data || {}),
    }))
    .catch(() => getFallbackCaptchaConfig());
  return configPromise;
}

export function requestCaptchaProof(scene) {
  if (!scene) {
    return Promise.reject(new Error("缺少验证场景参数"));
  }
  if (activeResolver) {
    return Promise.reject(new Error("已有安全验证正在进行中，请先完成当前验证。"));
  }
  return new Promise((resolve, reject) => {
    activeResolver = { scene, resolve, reject };
    window.dispatchEvent(
      new CustomEvent("algowiki:captcha-open", {
        detail: { scene },
      })
    );
  });
}

export function resolveCaptchaProof(payload) {
  if (!activeResolver) return;
  const resolver = activeResolver;
  activeResolver = null;
  resolver.resolve(payload);
}

export function rejectCaptchaProof(error) {
  if (!activeResolver) return;
  const resolver = activeResolver;
  activeResolver = null;
  const normalized = error instanceof Error ? error : new Error(String(error || "验证码已取消"));
  if (normalized.message === "验证码已取消" || !error) {
    normalized.isCaptchaCanceled = true;
    normalized.code = "CAPTCHA_CANCELED";
  }
  resolver.reject(normalized);
}

export function isCaptchaCanceled(error) {
  return Boolean(
    error?.isCaptchaCanceled ||
      error?.code === "CAPTCHA_CANCELED" ||
      String(error?.message || "").trim() === "验证码已取消"
  );
}

export async function getCaptchaProof(scene) {
  const config = await getCaptchaConfig();
  if (!config?.enabled) {
    return { scene, bypassed: true };
  }
  if (!config?.turnstile_site_key) {
    throw new Error("当前人机验证暂未配置完成，请联系管理员处理。");
  }
  return requestCaptchaProof(scene);
}

export function captchaErrorMessage(error, fallback = "验证未通过，请重试") {
  if (isCaptchaCanceled(error)) {
    return "已取消人机验证";
  }
  const data = error?.response?.data;
  if (data?.message) return data.message;
  if (data?.code === "CAPTCHA_REQUIRED") return "请先完成人机验证";
  if (data?.code === "CAPTCHA_INVALID") return "人机验证未通过，请重试";
  if (data?.code === "CAPTCHA_RATE_LIMITED") return "验证请求过于频繁，请稍后再试";
  if (data?.code === "CAPTCHA_PROVIDER_ERROR") return "验证服务暂时不可用，请稍后重试";
  if (data?.code === "CAPTCHA_DUPLICATED") return "本次验证已失效，请重新验证";
  return data?.detail || fallback || error?.message || "验证未通过，请重试";
}

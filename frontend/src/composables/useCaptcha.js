import api from "../services/api";

let activeResolver = null;
let configPromise = null;

export function getFallbackCaptchaConfig() {
  return {
    enabled: true,
    required_for_authenticated_users: true,
    turnstile_site_key: import.meta.env.VITE_TURNSTILE_SITE_KEY || "",
    secondary_enabled: import.meta.env.VITE_SECONDARY_CAPTCHA_ENABLED === "1",
    secondary_provider: import.meta.env.VITE_SECONDARY_CAPTCHA_PROVIDER || "geetest",
    geetest_captcha_id: import.meta.env.VITE_GEETEST_CAPTCHA_ID || "",
    token_ttl_seconds: 300,
  };
}

export async function getCaptchaConfig({ force = false } = {}) {
  if (!force && configPromise) return configPromise;
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
    return Promise.reject(new Error("captcha scene is required"));
  }
  if (activeResolver) {
    return Promise.reject(new Error("已有验证码正在进行中，请先完成当前验证。"));
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
  resolver.reject(error instanceof Error ? error : new Error(String(error || "验证码已取消")));
}

export async function getCaptchaProof(scene) {
  await getCaptchaConfig();
  return requestCaptchaProof(scene);
}

export function captchaErrorMessage(error, fallback = "验证码验证失败，请重新验证") {
  const data = error?.response?.data;
  if (data?.message) return data.message;
  if (data?.code === "CAPTCHA_REQUIRED") return "请先完成人机验证";
  if (data?.code === "CAPTCHA_INVALID") return "验证码校验失败，请重试";
  if (data?.code === "CAPTCHA_RATE_LIMITED") return "操作过于频繁，请稍后再试";
  if (data?.code === "CAPTCHA_PROVIDER_ERROR") return "验证码服务暂时不可用，请稍后重试";
  if (data?.code === "CAPTCHA_DUPLICATED") return "验证码已使用，请重新验证";
  return data?.detail || fallback || error?.message || "验证码验证失败，请重新验证";
}

import axios from "axios";

const api = axios.create({
  baseURL: "/api",
  timeout: 15000,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("algowiki_token");
  if (token) {
    config.headers.Authorization = `Token ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const config = error?.config;
    if (!config) throw error;

    const status = error?.response?.status || 0;
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
      throw error;
    }

    if ((config.method || "get").toLowerCase() !== "get") throw error;
    if (config.__retryOnce) throw error;

    const isNetworkError = !error?.response;
    const canRetry = isNetworkError || status >= 500;
    if (!canRetry) throw error;

    config.__retryOnce = true;
    await new Promise((resolve) => window.setTimeout(resolve, 250));
    return api.request(config);
  }
);

export default api;

import { createApp } from "vue";
import { createPinia } from "pinia";

import App from "./App.vue";
import router from "./router";
import "../node_modules/katex/dist/katex.min.css";
import "./assets/theme.css";
import "./assets/motion.css";

const ASSET_RELOAD_QUERY = "__asset_reload__";

if (typeof window !== "undefined") {
  window.addEventListener("vite:preloadError", (event) => {
    event.preventDefault();

    const currentUrl = new URL(window.location.href);
    if (currentUrl.searchParams.get(ASSET_RELOAD_QUERY) === "1") {
      return;
    }

    currentUrl.searchParams.set(ASSET_RELOAD_QUERY, "1");
    window.location.replace(currentUrl.toString());
  });

  const currentUrl = new URL(window.location.href);
  if (currentUrl.searchParams.get(ASSET_RELOAD_QUERY) === "1") {
    currentUrl.searchParams.delete(ASSET_RELOAD_QUERY);
    window.history.replaceState({}, document.title, `${currentUrl.pathname}${currentUrl.search}${currentUrl.hash}`);
  }
}

const app = createApp(App);
app.use(createPinia());
app.use(router);
app.mount("#app");

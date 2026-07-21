import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import legacy from "@vitejs/plugin-legacy";

const devProxyTarget = process.env.VITE_DEV_PROXY_TARGET || "http://127.0.0.1:8001";

export default defineConfig({
  plugins: [
    vue(),
    legacy({
      targets: [
        "Android >= 5",
        "iOS >= 11",
        "Chrome >= 49",
        "Safari >= 11",
      ],
      modernTargets: [
        "Chrome >= 58",
        "Safari >= 11",
        "iOS >= 11",
      ],
      renderLegacyChunks: true,
      modernPolyfills: true,
    }),
  ],
  build: {
    cssTarget: ["chrome58", "safari11"],
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: devProxyTarget,
        changeOrigin: true,
      },
      "/admin": {
        target: devProxyTarget,
        changeOrigin: true,
      },
    },
  },
});

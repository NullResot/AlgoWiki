import { defineStore } from "pinia";

let seed = 1;

export const useUiStore = defineStore("ui", {
  state: () => ({
    toasts: [],
  }),
  actions: {
    pushToast({ type = "info", message = "", title = "", duration = 2600 } = {}) {
      const id = seed++;
      this.toasts.push({ id, type, message, title });

      if (duration > 0) {
        window.setTimeout(() => {
          this.removeToast(id);
        }, duration);
      }

      return id;
    },
    removeToast(id) {
      this.toasts = this.toasts.filter((toast) => toast.id !== id);
    },
    success(message, title = "成功", duration = 2200) {
      this.pushToast({ type: "success", message, title, duration });
    },
    info(message, title = "提示", duration = 2600) {
      this.pushToast({ type: "info", message, title, duration });
    },
    error(message, title = "错误", duration = 3200) {
      this.pushToast({ type: "error", message, title, duration });
    },
  },
});

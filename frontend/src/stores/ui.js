import { defineStore } from "pinia";

let seed = 1;
const toastTimers = new Map();

function clearToastTimer(id) {
  const timer = toastTimers.get(id);
  if (timer && typeof window !== "undefined") {
    window.clearTimeout(timer);
  }
  toastTimers.delete(id);
}

export const useUiStore = defineStore("ui", {
  state: () => ({
    toasts: [],
    confirmDialog: null,
  }),
  actions: {
    scheduleToastRemoval(id, duration) {
      clearToastTimer(id);
      if (typeof window === "undefined" || duration <= 0) return;
      const timer = window.setTimeout(() => {
        toastTimers.delete(id);
        this.removeToast(id);
      }, duration);
      toastTimers.set(id, timer);
    },
    pauseToast(id) {
      const target = this.toasts.find((item) => item.id === id);
      if (!target || target.duration <= 0) return;
      clearToastTimer(id);
    },
    resumeToast(id) {
      const target = this.toasts.find((item) => item.id === id);
      if (!target || target.duration <= 0) return;
      this.scheduleToastRemoval(id, Math.min(target.duration, 1800));
    },
    pushToast({
      type = "info",
      message = "",
      title = "",
      duration = 2600,
      action = null,
    } = {}) {
      const text = String(message || "").trim();
      const heading = String(title || "").trim();
      const existing = this.toasts.find(
        (item) =>
          item.type === type &&
          item.message === text &&
          item.title === heading &&
          !item.action &&
          !action
      );
      if (existing) {
        existing.duration = duration;
        this.scheduleToastRemoval(existing.id, duration);
        return existing.id;
      }

      const id = seed++;
      this.toasts.push({
        id,
        type,
        message: text,
        title: heading,
        duration,
        action: action && typeof action.onClick === "function" ? action : null,
      });

      while (this.toasts.length > 4) {
        const oldest = this.toasts.shift();
        if (oldest) clearToastTimer(oldest.id);
      }

      this.scheduleToastRemoval(id, duration);
      return id;
    },
    removeToast(id) {
      clearToastTimer(id);
      this.toasts = this.toasts.filter((toast) => toast.id !== id);
    },
    success(message, title = "成功", duration = 2400, extra = {}) {
      return this.pushToast({ type: "success", message, title, duration, ...extra });
    },
    info(message, title = "提示", duration = 2600, extra = {}) {
      return this.pushToast({ type: "info", message, title, duration, ...extra });
    },
    error(message, title = "错误", duration = 3400, extra = {}) {
      return this.pushToast({ type: "error", message, title, duration, ...extra });
    },
    confirm({
      title = "请确认操作",
      message = "",
      confirmText = "确认",
      cancelText = "取消",
      tone = "default",
      requireText = "",
      requireLabel = "",
    } = {}) {
      if (this.confirmDialog?.resolve) {
        this.confirmDialog.resolve(false);
      }
      return new Promise((resolve) => {
        this.confirmDialog = {
          mode: "confirm",
          title,
          message,
          confirmText,
          cancelText,
          tone,
          requireText: String(requireText || ""),
          requireLabel: String(requireLabel || ""),
          choices: [],
          defaultChoice: "",
          inputLabel: "",
          inputPlaceholder: "",
          inputRequired: false,
          initialInput: "",
          resolve,
        };
      });
    },
    promptChoice({
      title = "请选择并说明",
      message = "",
      confirmText = "确认提交",
      cancelText = "取消",
      tone = "default",
      choices = [],
      defaultChoice = "",
      inputLabel = "",
      inputPlaceholder = "",
      inputRequired = false,
      initialInput = "",
    } = {}) {
      if (this.confirmDialog?.resolve) {
        this.confirmDialog.resolve(null);
      }
      return new Promise((resolve) => {
        this.confirmDialog = {
          mode: "prompt",
          title,
          message,
          confirmText,
          cancelText,
          tone,
          requireText: "",
          requireLabel: "",
          choices: Array.isArray(choices) ? choices : [],
          defaultChoice: String(defaultChoice || ""),
          inputLabel: String(inputLabel || ""),
          inputPlaceholder: String(inputPlaceholder || ""),
          inputRequired: Boolean(inputRequired),
          initialInput: String(initialInput || ""),
          resolve,
        };
      });
    },
    resolveConfirmDialog(result) {
      const active = this.confirmDialog;
      this.confirmDialog = null;
      if (!active?.resolve) return;
      active.resolve(result);
    },
  },
});

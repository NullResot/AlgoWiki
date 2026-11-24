import { onBeforeUnmount, onMounted } from "vue";
import { onBeforeRouteLeave } from "vue-router";

import { useUiStore } from "../stores/ui";

export function useUnsavedGuard(isDirtyGetter, options = {}) {
  const ui = useUiStore();
  const title = options.title || "离开当前编辑？";
  const message = options.message || "当前有尚未保存的内容，离开后这些更改将会丢失。";
  const confirmText = options.confirmText || "放弃更改并离开";
  const cancelText = options.cancelText || "继续编辑";

  function checkDirty() {
    return typeof isDirtyGetter === "function" ? Boolean(isDirtyGetter()) : Boolean(isDirtyGetter?.value);
  }

  async function confirmDiscard(custom = {}) {
    if (!checkDirty()) return true;
    return ui.confirm({
      title: custom.title || title,
      message: custom.message || message,
      confirmText: custom.confirmText || confirmText,
      cancelText: custom.cancelText || cancelText,
      tone: "warning",
    });
  }

  function handleBeforeUnload(event) {
    if (!checkDirty()) return;
    event.preventDefault();
    event.returnValue = "";
  }

  if (options.guardRoute !== false) {
    onBeforeRouteLeave(async () => {
      if (!checkDirty()) return true;
      return confirmDiscard();
    });
  }

  onMounted(() => {
    if (typeof window !== "undefined") {
      window.addEventListener("beforeunload", handleBeforeUnload);
    }
  });

  onBeforeUnmount(() => {
    if (typeof window !== "undefined") {
      window.removeEventListener("beforeunload", handleBeforeUnload);
    }
  });

  return {
    isDirty: checkDirty,
    confirmDiscard,
  };
}

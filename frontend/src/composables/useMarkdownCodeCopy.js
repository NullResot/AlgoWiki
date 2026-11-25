import { nextTick, onBeforeUnmount, onMounted, watch } from "vue";
import { useRouter } from "vue-router";

import { safeScrollIntoView } from "../utils/motion";

async function writeClipboardText(text) {
  if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return true;
  }
  if (typeof document === "undefined") return false;
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  textarea.style.pointerEvents = "none";
  document.body.appendChild(textarea);
  textarea.select();
  const ok = document.execCommand("copy");
  textarea.remove();
  return ok;
}

export function useMarkdownCodeCopy(containerRef, watchSource) {
  const router = useRouter();
  const resetTimers = new WeakMap();

  function attachCopyButtons() {
    const root = containerRef?.value;
    if (!root || typeof document === "undefined") return;

    const blocks = root.querySelectorAll("pre");
    blocks.forEach((pre) => {
      if (pre.dataset.copyAttached === "1") return;
      pre.dataset.copyAttached = "1";
      pre.classList.add("has-code-copy");

      const button = document.createElement("button");
      button.type = "button";
      button.className = "aw-code-copy-btn";
      button.setAttribute("aria-label", "复制代码块");
      button.textContent = "复制";

      button.addEventListener("click", async (event) => {
        event.preventDefault();
        event.stopPropagation();
        const codeNode = pre.querySelector("code");
        const rawText = codeNode ? codeNode.textContent || "" : pre.textContent || "";
        const text = rawText.replace(/\n$/, "");
        try {
          await writeClipboardText(text);
          button.classList.add("is-copied");
          button.textContent = "已复制 ✓";
          const prev = resetTimers.get(button);
          if (prev) window.clearTimeout(prev);
          const timer = window.setTimeout(() => {
            button.classList.remove("is-copied");
            button.textContent = "复制";
            resetTimers.delete(button);
          }, 1800);
          resetTimers.set(button, timer);
        } catch {
          button.textContent = "复制失败";
          window.setTimeout(() => {
            button.textContent = "复制";
          }, 1600);
        }
      });

      pre.appendChild(button);
    });
  }

  function handleContainerClick(event) {
    const target = event.target instanceof Element ? event.target.closest("a") : null;
    if (!target) return;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const rawHref = String(target.getAttribute("href") || "").trim();
    if (!rawHref) return;

    if (rawHref.startsWith("#")) {
      event.preventDefault();
      const anchorId = decodeURIComponent(rawHref.slice(1));
      if (!anchorId) return;
      const anchorEl = document.getElementById(anchorId);
      if (anchorEl) {
        safeScrollIntoView(anchorEl, { behavior: "smooth", block: "start" });
      }
      return;
    }

    if (rawHref.startsWith("/") && !rawHref.startsWith("//")) {
      event.preventDefault();
      router.push(rawHref);
    }
  }

  function syncBindings() {
    const root = containerRef?.value;
    if (!root) return;
    attachCopyButtons();
  }

  let boundEl = null;
  function bindClick(el) {
    if (boundEl && boundEl !== el) {
      boundEl.removeEventListener("click", handleContainerClick);
      boundEl = null;
    }
    if (el && boundEl !== el) {
      el.addEventListener("click", handleContainerClick);
      boundEl = el;
    }
  }

  onMounted(async () => {
    await nextTick();
    bindClick(containerRef?.value);
    syncBindings();
  });

  if (watchSource) {
    watch(
      watchSource,
      async () => {
        await nextTick();
        bindClick(containerRef?.value);
        syncBindings();
      },
      { flush: "post" }
    );
  }

  watch(
    () => containerRef?.value,
    async (el) => {
      await nextTick();
      bindClick(el);
      syncBindings();
    }
  );

  onBeforeUnmount(() => {
    if (boundEl) {
      boundEl.removeEventListener("click", handleContainerClick);
      boundEl = null;
    }
  });

  return {
    refreshCodeCopy: syncBindings,
  };
}

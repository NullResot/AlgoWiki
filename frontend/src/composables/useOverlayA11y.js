import { nextTick, onBeforeUnmount, watch } from "vue";

let lockCount = 0;
let prevHtmlOverflow = "";
let prevBodyOverflow = "";
const overlayStack = [];
let keyListenerAttached = false;
const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  'input:not([disabled]):not([type="hidden"])',
  "select:not([disabled])",
  "textarea:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(", ");

function lockBodyScroll() {
  if (typeof document === "undefined") return;
  if (lockCount === 0) {
    prevHtmlOverflow = document.documentElement.style.overflow;
    prevBodyOverflow = document.body.style.overflow;
    document.documentElement.style.overflow = "hidden";
    document.body.style.overflow = "hidden";
  }
  lockCount += 1;
}

function unlockBodyScroll() {
  if (typeof document === "undefined" || lockCount <= 0) return;
  lockCount -= 1;
  if (lockCount === 0) {
    document.documentElement.style.overflow = prevHtmlOverflow;
    document.body.style.overflow = prevBodyOverflow;
  }
}

function handleGlobalKeydown(event) {
  if (event.key !== "Escape") return;
  const top = overlayStack[overlayStack.length - 1];
  if (!top) return;
  event.preventDefault();
  top.onClose?.();
}

function syncKeyListener() {
  if (typeof window === "undefined") return;
  if (overlayStack.length > 0 && !keyListenerAttached) {
    window.addEventListener("keydown", handleGlobalKeydown);
    keyListenerAttached = true;
  } else if (overlayStack.length === 0 && keyListenerAttached) {
    window.removeEventListener("keydown", handleGlobalKeydown);
    keyListenerAttached = false;
  }
}

export function useOverlayA11y(isOpenOrOptions, onCloseArg, optionsArg = {}) {
  const isConfigObject =
    Boolean(isOpenOrOptions) &&
    typeof isOpenOrOptions === "object" &&
    typeof isOpenOrOptions !== "function" &&
    !("value" in isOpenOrOptions);
  const config = isConfigObject ? isOpenOrOptions : optionsArg || {};
  const isOpen = isConfigObject ? config.isOpen : isOpenOrOptions;
  const onClose = isConfigObject ? config.onClose : onCloseArg;
  const { lockScroll = true, closeOnEscape = true, containerRef = null } = config;
  let active = false;
  let previousFocus = null;
  const entry = {
    onClose: () => {
      if (closeOnEscape && typeof onClose === "function") {
        onClose();
      }
    },
  };

  function focusOverlayContainer() {
    if (!active || typeof document === "undefined") return;
    const container = containerRef?.value;
    if (!container || typeof container.contains !== "function") return;
    if (container.contains(document.activeElement)) return;
    const candidates = Array.from(container.querySelectorAll(FOCUSABLE_SELECTOR));
    const target = candidates.find(
      (node) => node instanceof HTMLElement && node.getClientRects().length > 0
    );
    if (target) {
      target.focus({ preventScroll: true });
      return;
    }
    if (typeof container.focus === "function") {
      if (!container.hasAttribute("tabindex")) {
        container.setAttribute("tabindex", "-1");
      }
      container.focus({ preventScroll: true });
    }
  }

  function activate() {
    if (active) return;
    active = true;
    if (typeof document !== "undefined" && document.activeElement instanceof HTMLElement) {
      previousFocus = document.activeElement;
    } else {
      previousFocus = null;
    }
    if (lockScroll) lockBodyScroll();
    if (closeOnEscape) {
      overlayStack.push(entry);
      syncKeyListener();
    }
    if (containerRef) {
      nextTick(() => {
        if (!active) return;
        focusOverlayContainer();
      });
    }
  }

  function deactivate(restoreFocus = true) {
    if (!active) return;
    active = false;
    if (lockScroll) unlockBodyScroll();
    const index = overlayStack.lastIndexOf(entry);
    if (index >= 0) {
      overlayStack.splice(index, 1);
      syncKeyListener();
    }
    const targetToRestore = previousFocus;
    previousFocus = null;
    if (restoreFocus && targetToRestore && typeof targetToRestore.focus === "function") {
      window.setTimeout(() => {
        if (targetToRestore.isConnected) {
          targetToRestore.focus({ preventScroll: true });
        }
      }, 0);
    }
  }

  watch(
    () => Boolean(typeof isOpen === "function" ? isOpen() : isOpen?.value),
    (open) => {
      if (open) activate();
      else deactivate(true);
    },
    { immediate: true }
  );

  onBeforeUnmount(() => {
    deactivate(false);
  });
}

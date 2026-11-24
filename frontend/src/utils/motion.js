export function prefersReducedMotion() {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function safeScrollBehavior(preferred = "smooth") {
  return prefersReducedMotion() ? "auto" : preferred;
}

export function safeScrollTo(options = {}) {
  if (typeof window === "undefined") return;
  const { behavior = "smooth", ...rest } = options;
  window.scrollTo({
    ...rest,
    behavior: safeScrollBehavior(behavior),
  });
}

export function safeScrollIntoView(element, options = {}) {
  if (!element || typeof element.scrollIntoView !== "function") return;
  const { behavior = "smooth", block = "nearest", inline = "nearest" } = options;
  element.scrollIntoView({
    block,
    inline,
    behavior: safeScrollBehavior(behavior),
  });
}

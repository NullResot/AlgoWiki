import { defineStore } from "pinia";

const STORAGE_KEY = "algowiki-theme";

export const THEME_OPTIONS = [
  {
    id: "modern",
    label: "Modern",
    name: "Modern Glass",
    description: "玻璃质感、流动渐变、轻盈卡片。",
  },
  {
    id: "academic",
    label: "Academic",
    name: "Clean Academic",
    description: "纸面排版、克制线条、长文优先。",
  },
  {
    id: "geek",
    label: "Geek",
    name: "Neo-Geek",
    description: "硬边框、高对比、极客工作台。",
  },
  {
    id: "midnight",
    label: "Midnight",
    name: "Eclipse Observatory",
    description: "真空黑观测台、脉冲光谱与暗舱层级。",
  },
];

function normalizeTheme(value) {
  const input = String(value || "").trim().toLowerCase();
  return THEME_OPTIONS.some((item) => item.id === input) ? input : "modern";
}

function applyThemeToDocument(themeId) {
  if (typeof document === "undefined") return;
  document.documentElement.dataset.theme = normalizeTheme(themeId);
}

export const useThemeStore = defineStore("theme", {
  state: () => ({
    currentTheme: "modern",
    initialized: false,
    temporaryRestoreTheme: null,
  }),
  getters: {
    options: () => THEME_OPTIONS,
    isTemporary: (state) => state.temporaryRestoreTheme !== null,
    activeTheme(state) {
      return THEME_OPTIONS.find((item) => item.id === state.currentTheme) || THEME_OPTIONS[0];
    },
  },
  actions: {
    init() {
      if (this.initialized) {
        applyThemeToDocument(this.currentTheme);
        return;
      }
      let nextTheme = "modern";
      if (typeof window !== "undefined") {
        try {
          nextTheme = normalizeTheme(window.localStorage.getItem(STORAGE_KEY));
        } catch {
          nextTheme = "modern";
        }
      }
      this.currentTheme = nextTheme;
      this.initialized = true;
      applyThemeToDocument(nextTheme);
    },
    setTheme(themeId) {
      const nextTheme = normalizeTheme(themeId);
      if (this.temporaryRestoreTheme !== null) {
        this.currentTheme = nextTheme;
        applyThemeToDocument(nextTheme);
        return;
      }
      this.currentTheme = nextTheme;
      applyThemeToDocument(nextTheme);
      if (typeof window !== "undefined") {
        try {
          window.localStorage.setItem(STORAGE_KEY, nextTheme);
        } catch {
          // Ignore storage write failures so switching remains available.
        }
      }
    },
    beginTemporaryTheme(themeId) {
      if (this.temporaryRestoreTheme === null) {
        this.temporaryRestoreTheme = this.currentTheme;
      }
      this.currentTheme = normalizeTheme(themeId);
      applyThemeToDocument(this.currentTheme);
    },
    endTemporaryTheme() {
      if (this.temporaryRestoreTheme === null) return;
      const restoreTheme = this.temporaryRestoreTheme;
      this.temporaryRestoreTheme = null;
      this.currentTheme = restoreTheme;
      applyThemeToDocument(restoreTheme);
    },
  },
});

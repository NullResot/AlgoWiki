import test from "node:test";
import assert from "node:assert/strict";
import { createPinia, setActivePinia } from "pinia";

import { useThemeStore } from "../src/stores/theme.js";

function installBrowserShim(storedTheme = "modern") {
  const storage = new Map([["algowiki-theme", storedTheme]]);
  globalThis.document = { documentElement: { dataset: {} } };
  globalThis.window = {
    localStorage: {
      getItem: (key) => storage.get(key) ?? null,
      setItem: (key, value) => storage.set(key, value),
    },
  };
  return storage;
}

function createTheme(storedTheme) {
  const storage = installBrowserShim(storedTheme);
  setActivePinia(createPinia());
  const theme = useThemeStore();
  theme.init();
  return { theme, storage };
}

test("midnight is a normal persistent theme outside temporary mode", () => {
  const { theme, storage } = createTheme("modern");
  theme.setTheme("midnight");

  assert.equal(theme.currentTheme, "midnight");
  assert.equal(storage.get("algowiki-theme"), "midnight");
  assert.equal(document.documentElement.dataset.theme, "midnight");
});

test("temporary midnight does not overwrite the stored preference", () => {
  const { theme, storage } = createTheme("academic");
  theme.beginTemporaryTheme("midnight");

  assert.equal(theme.currentTheme, "midnight");
  assert.equal(theme.isTemporary, true);
  assert.equal(storage.get("algowiki-theme"), "academic");
});

test("theme choices stay temporary until the pulse route exits", () => {
  const { theme, storage } = createTheme("geek");
  theme.beginTemporaryTheme("midnight");
  theme.setTheme("modern");

  assert.equal(theme.currentTheme, "modern");
  assert.equal(storage.get("algowiki-theme"), "geek");

  theme.endTemporaryTheme();

  assert.equal(theme.currentTheme, "geek");
  assert.equal(theme.isTemporary, false);
});

test("repeated temporary entry preserves the original restore target", () => {
  const { theme } = createTheme("academic");
  theme.beginTemporaryTheme("midnight");
  theme.beginTemporaryTheme("midnight");
  theme.endTemporaryTheme();

  assert.equal(theme.currentTheme, "academic");
});

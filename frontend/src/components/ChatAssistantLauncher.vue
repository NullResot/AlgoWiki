<template>
  <div v-if="config.enabled" class="assistant-root">
    <Transition name="assistant-teaser">
      <button
        v-if="showTeaser && !isOpen"
        type="button"
        class="assistant-teaser"
        :class="teaserClassName"
        :style="teaserStyle"
        @click="handleTeaserClick"
      >
        <span>{{ teaserText }}</span>
      </button>
    </Transition>

    <Transition name="assistant-panel">
      <section v-if="isOpen" class="assistant-panel" :style="panelStyle" @pointerdown.stop>
        <header class="assistant-header">
          <div class="assistant-header-copy">
            <div class="assistant-avatar" aria-hidden="true">
              <img :src="assistantPortraitUrl" alt="" draggable="false" />
            </div>
            <div>
              <p class="assistant-kicker">Site Assistant</p>
              <h3>{{ config.assistant_name }}</h3>
            </div>
          </div>

          <button type="button" class="assistant-close" aria-label="关闭助手" @click="closePanel">
            <svg viewBox="0 0 20 20" focusable="false" aria-hidden="true">
              <path
                d="M5.3 5.3a1 1 0 011.4 0L10 8.6l3.3-3.3a1 1 0 111.4 1.4L11.4 10l3.3 3.3a1 1 0 01-1.4 1.4L10 11.4l-3.3 3.3a1 1 0 01-1.4-1.4L8.6 10 5.3 6.7a1 1 0 010-1.4z"
                fill="currentColor"
              />
            </svg>
          </button>
        </header>

        <div class="assistant-info">
          <svg viewBox="0 0 20 20" focusable="false" aria-hidden="true">
            <path
              d="M10 1.7a8.3 8.3 0 110 16.6 8.3 8.3 0 010-16.6zm0 1.8a6.5 6.5 0 100 13 6.5 6.5 0 000-13zm0 8a.9.9 0 01.9.9v2.2a.9.9 0 11-1.8 0v-2.2a.9.9 0 01.9-.9zm0-4.5a1.1 1.1 0 110 2.2 1.1 1.1 0 010-2.2z"
              fill="currentColor"
            />
          </svg>
          <span>仅基于站内公开内容回答，并附上对应来源。</span>
        </div>

        <div ref="messageListRef" class="assistant-body">
          <article
            v-for="item in messages"
            :key="item.id"
            class="assistant-message"
            :class="`assistant-message--${item.role}`"
          >
            <div class="assistant-bubble">
              <section v-if="item.role === 'assistant'" class="markdown" v-html="renderMarkdown(item.content)"></section>
              <p v-else>{{ item.content }}</p>

              <div v-if="getCompactSources(item).length" class="assistant-sources">
                <strong>对应来源</strong>
                <a
                  v-for="source in getCompactSources(item)"
                  :key="`${item.id}-${source.url}-${source.title}`"
                  class="assistant-source"
                  :href="source.url"
                  :target="isInternalSourceUrl(source.url) ? undefined : '_blank'"
                  rel="noopener noreferrer"
                  :title="source.title"
                  @click="handleSourceClick(source, $event)"
                >
                  <span>{{ source.title }}</span>
                </a>
                <span v-if="getOverflowSourceCount(item) > 0" class="assistant-source assistant-source--overflow">
                  +{{ getOverflowSourceCount(item) }}
                </span>
              </div>
            </div>
          </article>

          <article v-if="loading" class="assistant-message assistant-message--assistant">
            <div class="assistant-bubble assistant-bubble--loading">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </article>
        </div>

        <div v-if="showSuggestions" class="assistant-suggestions">
          <button
            v-for="question in config.suggested_questions"
            :key="question"
            type="button"
            class="assistant-suggestion"
            @click="sendSuggested(question)"
          >
            {{ question }}
          </button>
        </div>

        <form class="assistant-footer" @submit.prevent="submitMessage()">
          <div class="assistant-composer">
            <textarea
              ref="inputRef"
              v-model="draft"
              class="assistant-input"
              rows="1"
              maxlength="1500"
              placeholder="输入你想了解的内容..."
              @input="handleComposerInput"
              @keydown="handleComposerKeydown"
            ></textarea>

            <button
              type="submit"
              class="assistant-send"
              :class="{ 'assistant-send--enabled': draft.trim() && !loading }"
              :disabled="loading || !draft.trim()"
              aria-label="发送消息"
            >
              <svg viewBox="0 0 20 20" focusable="false" aria-hidden="true">
                <path
                  d="M10 4.4a1 1 0 011 1v6.2l2.4-2.4a1 1 0 111.4 1.4l-4.1 4.1a1 1 0 01-1.4 0l-4.1-4.1a1 1 0 111.4-1.4L9 11.6V5.4a1 1 0 011-1z"
                  fill="currentColor"
                />
              </svg>
            </button>
          </div>

          <p class="assistant-meta">{{ helperText }}</p>
        </form>

        <button
          v-if="!isMobile"
          type="button"
          class="assistant-resize-handle"
          aria-label="调整对话框大小"
          @pointerdown.stop.prevent="startResize"
        >
          <span></span>
          <span></span>
          <span></span>
        </button>
      </section>
    </Transition>

    <button
      type="button"
      class="assistant-launcher"
      :style="launcherStyle"
      aria-label="打开 AlgoWiki 助手"
      @pointerdown="startDrag"
      @click="handleLauncherClick"
      @dragstart.prevent
    >
      <span class="assistant-launcher-icon" aria-hidden="true">
        <img :src="assistantPortraitUrl" alt="" draggable="false" />
      </span>
    </button>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import api from "../services/api";
import { renderMarkdown } from "../services/markdown";
import { useUiStore } from "../stores/ui";

const route = useRoute();
const router = useRouter();
const ui = useUiStore();
const assistantPortraitUrl = "/assistant-junior-sister.jpg";

const LAUNCHER_WIDTH = 60;
const LAUNCHER_HEIGHT = 60;
const DESKTOP_PANEL_WIDTH = 380;
const DESKTOP_PANEL_HEIGHT = 720;
const DESKTOP_PANEL_LAUNCHER_GAP = 10;
const MIN_PANEL_WIDTH = 320;
const MIN_PANEL_HEIGHT = 420;
const VIEWPORT_MARGIN = 16;
const TEASER_WIDTH = 280;
const TEASER_APPROX_HEIGHT = 76;
const TEASER_SHOW_DURATION_MS = 8000;
const TEASER_INITIAL_DELAY_MS = 1200;
const TEASER_REPEAT_INTERVAL_MS = 6 * 60 * 60 * 1000;
const STORAGE_KEYS = {
  session: "algowiki_assistant_session_id_v1",
  position: "algowiki_assistant_position_v1",
  size: "algowiki_assistant_panel_size_v1",
  teaserLastShown: "algowiki_assistant_teaser_last_shown_v1",
};

const config = reactive({
  enabled: false,
  assistant_name: "",
  welcome_message: "",
  teaser_message: "",
  suggested_questions: [],
});

const viewport = reactive({
  width: typeof window === "undefined" ? 1280 : window.innerWidth,
  height: typeof window === "undefined" ? 720 : window.innerHeight,
});

const position = reactive(loadLauncherPosition());
const panelSize = reactive(loadPanelSize());
const dragState = reactive({
  active: false,
  pointerId: null,
  originX: 0,
  originY: 0,
  offsetX: 0,
  offsetY: 0,
  moved: false,
});
const resizeState = reactive({
  active: false,
  originX: 0,
  originY: 0,
  startWidth: DESKTOP_PANEL_WIDTH,
  startHeight: DESKTOP_PANEL_HEIGHT,
});

const messages = ref([]);
const draft = ref("");
const loading = ref(false);
const isOpen = ref(false);
const showTeaser = ref(false);
const suppressNextClick = ref(false);
const inputRef = ref(null);
const messageListRef = ref(null);
const sessionId = ref(getOrCreateSessionId());
const teaserText = computed(
  () =>
    String(config.teaser_message || "").trim() ||
    "杂鱼师兄，想要更方便地了解AlgoWiki，可以点击询问小小丛雨我哦~"
);
let messageSeed = 1;
let teaserDelayTimer = null;
let teaserHideTimer = null;
let teaserPollTimer = null;

const launcherStyle = computed(() => ({
  left: `${position.x}px`,
  top: `${position.y}px`,
}));

const isMobile = computed(() => viewport.width <= 640);
const panelStyle = computed(() => {
  if (isMobile.value) {
    return {};
  }

  const width = clamp(panelSize.width, MIN_PANEL_WIDTH, Math.max(MIN_PANEL_WIDTH, viewport.width - VIEWPORT_MARGIN * 2));
  const height = clamp(
    panelSize.height,
    MIN_PANEL_HEIGHT,
    Math.max(MIN_PANEL_HEIGHT, viewport.height - 40)
  );
  const left = clamp(
    position.x + LAUNCHER_WIDTH - width + 8,
    VIEWPORT_MARGIN,
    viewport.width - width - VIEWPORT_MARGIN
  );
  const bottom = clamp(
    viewport.height - position.y + DESKTOP_PANEL_LAUNCHER_GAP,
    VIEWPORT_MARGIN,
    viewport.height - height - 24
  );

  return {
    width: `${width}px`,
    height: `${height}px`,
    left: `${left}px`,
    bottom: `${bottom}px`,
  };
});

const showSuggestions = computed(
  () =>
    !loading.value &&
    messages.value.filter((item) => item.role === "user" || !item.isWelcome).length <= 1 &&
    config.suggested_questions.length > 0
);

const teaserPlacement = computed(() => ({
  horizontal: position.x > viewport.width / 2 ? "left" : "right",
  vertical: position.y > viewport.height / 2 ? "top" : "bottom",
}));

const teaserClassName = computed(
  () => `assistant-teaser--${teaserPlacement.value.horizontal} assistant-teaser--${teaserPlacement.value.vertical}`
);

const teaserStyle = computed(() => {
  const width = Math.min(TEASER_WIDTH, Math.max(220, viewport.width - VIEWPORT_MARGIN * 2));
  const bubbleLeft =
    teaserPlacement.value.horizontal === "left"
      ? position.x - width - 14
      : position.x + LAUNCHER_WIDTH + 14;
  const bubbleTop =
    teaserPlacement.value.vertical === "top"
      ? position.y - TEASER_APPROX_HEIGHT - 16
      : position.y + LAUNCHER_HEIGHT + 16;

  return {
    width: `${width}px`,
    left: `${clamp(bubbleLeft, VIEWPORT_MARGIN, viewport.width - width - VIEWPORT_MARGIN)}px`,
    top: `${clamp(bubbleTop, 24, viewport.height - TEASER_APPROX_HEIGHT - 24)}px`,
  };
});

const helperText = computed(() => {
  const remaining = 1500 - String(draft.value || "").length;
  return `仅回答站内公开内容 · 剩余 ${remaining} 字`;
});

function clamp(value, min, max) {
  if (max < min) return min;
  return Math.min(Math.max(value, min), max);
}

function loadLauncherPosition() {
  const fallback = {
    x: typeof window === "undefined" ? 24 : Math.max(VIEWPORT_MARGIN, window.innerWidth - LAUNCHER_WIDTH - 28),
    y: typeof window === "undefined" ? 420 : Math.max(88, window.innerHeight - LAUNCHER_HEIGHT - 44),
  };

  if (typeof window === "undefined") {
    return fallback;
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEYS.position);
    if (!raw) return fallback;
    const parsed = JSON.parse(raw);
    return {
      x: Number.isFinite(parsed?.x) ? parsed.x : fallback.x,
      y: Number.isFinite(parsed?.y) ? parsed.y : fallback.y,
    };
  } catch {
    return fallback;
  }
}

function loadPanelSize() {
  const fallback = {
    width: DESKTOP_PANEL_WIDTH,
    height:
      typeof window === "undefined"
        ? DESKTOP_PANEL_HEIGHT
        : Math.min(DESKTOP_PANEL_HEIGHT, Math.max(MIN_PANEL_HEIGHT, window.innerHeight - 40)),
  };

  if (typeof window === "undefined") {
    return fallback;
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEYS.size);
    if (!raw) return fallback;
    const parsed = JSON.parse(raw);
    return {
      width: Number.isFinite(parsed?.width) ? parsed.width : fallback.width,
      height: Number.isFinite(parsed?.height) ? parsed.height : fallback.height,
    };
  } catch {
    return fallback;
  }
}

function persistLauncherPosition() {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEYS.position, JSON.stringify({ x: position.x, y: position.y }));
}

function persistPanelSize() {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEYS.size, JSON.stringify({ width: panelSize.width, height: panelSize.height }));
}

function getTeaserLastShownAt() {
  if (typeof window === "undefined") return 0;
  const raw = Number(window.localStorage.getItem(STORAGE_KEYS.teaserLastShown) || 0);
  return Number.isFinite(raw) ? raw : 0;
}

function persistTeaserLastShown(value = Date.now()) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEYS.teaserLastShown, String(value));
}

function clearTeaserTimers() {
  if (teaserDelayTimer) {
    window.clearTimeout(teaserDelayTimer);
    teaserDelayTimer = null;
  }
  if (teaserHideTimer) {
    window.clearTimeout(teaserHideTimer);
    teaserHideTimer = null;
  }
  if (teaserPollTimer) {
    window.clearInterval(teaserPollTimer);
    teaserPollTimer = null;
  }
}

function shouldShowTeaserNow() {
  if (!config.enabled || isOpen.value || !teaserText.value) return false;
  const lastShownAt = getTeaserLastShownAt();
  return !lastShownAt || Date.now() - lastShownAt >= TEASER_REPEAT_INTERVAL_MS;
}

function hideTeaser() {
  showTeaser.value = false;
  if (teaserHideTimer) {
    window.clearTimeout(teaserHideTimer);
    teaserHideTimer = null;
  }
}

function showTeaserNow() {
  if (!shouldShowTeaserNow()) return;
  showTeaser.value = true;
  persistTeaserLastShown();
  if (teaserHideTimer) {
    window.clearTimeout(teaserHideTimer);
  }
  teaserHideTimer = window.setTimeout(() => {
    hideTeaser();
  }, TEASER_SHOW_DURATION_MS);
}

function queueTeaser(delay = TEASER_INITIAL_DELAY_MS) {
  if (typeof window === "undefined") return;
  if (teaserDelayTimer) {
    window.clearTimeout(teaserDelayTimer);
    teaserDelayTimer = null;
  }
  if (!shouldShowTeaserNow()) return;
  teaserDelayTimer = window.setTimeout(() => {
    teaserDelayTimer = null;
    showTeaserNow();
  }, delay);
}

function getOrCreateSessionId() {
  if (typeof window === "undefined") {
    return "assistant-session-server";
  }

  const existing = window.localStorage.getItem(STORAGE_KEYS.session);
  if (existing) return existing;

  const generated =
    typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID()
      : `assistant-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  window.localStorage.setItem(STORAGE_KEYS.session, generated);
  return generated;
}

function seedWelcomeMessage() {
  messages.value = config.enabled
    ? [
        {
          id: messageSeed++,
          role: "assistant",
          content: config.welcome_message,
          sources: [],
          isWelcome: true,
        },
      ]
    : [];
}

function normalizeErrorText(error, fallback = "助手暂时不可用，请稍后再试。") {
  const payload = error?.response?.data;
  if (!payload) return fallback;
  if (typeof payload === "string") return payload;
  if (typeof payload.detail === "string") return payload.detail;
  return fallback;
}

function buildHistoryPayload() {
  return messages.value
    .filter((item) => item.role === "user" || (item.role === "assistant" && !item.isWelcome))
    .slice(-8)
    .map((item) => ({
      role: item.role,
      content: item.content,
    }));
}

function getCurrentPageTitle() {
  if (typeof document === "undefined") return "";
  const selectors = [
    "main .article-header h1",
    "main .qa-header h1",
    "main .zone-header h1",
    "main .extra-head .section-title",
    "main h1",
    "main .section-title",
  ];
  for (const selector of selectors) {
    const text = String(document.querySelector(selector)?.textContent || "")
      .replace(/\s+/g, " ")
      .trim();
    if (text) return text;
  }
  return String(document.title || "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 120);
}

function buildPageContextPayload() {
  const currentPath = String(route.fullPath || "").trim().slice(0, 255);
  const currentTitle = getCurrentPageTitle().slice(0, 120);
  return {
    current_path: currentPath,
    current_title: currentTitle,
  };
}

function normalizeSourceTitle(source) {
  return String(source?.title || "")
    .replace(/\s+/g, " ")
    .trim();
}

function getUniqueSources(item) {
  const unique = [];
  const seen = new Set();
  for (const source of Array.isArray(item?.sources) ? item.sources : []) {
    const title = normalizeSourceTitle(source);
    const url = String(source?.url || "").trim();
    if (!title || !url) continue;
    const key = `${url}::${title}`;
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push({
      ...source,
      title,
      url,
    });
  }
  return unique;
}

function getCompactSources(item) {
  return getUniqueSources(item).slice(0, 3);
}

function getOverflowSourceCount(item) {
  return Math.max(0, getUniqueSources(item).length - 3);
}

function isInternalSourceUrl(value) {
  const url = String(value || "").trim();
  return url.startsWith("/") && !url.startsWith("//");
}

async function handleSourceClick(source, event) {
  const url = String(source?.url || "").trim();
  if (!isInternalSourceUrl(url)) return;
  event.preventDefault();
  closePanel();
  await router.push(url);
  if (url.includes("#")) {
    window.setTimeout(() => {
      const hash = url.split("#", 2)[1] || "";
      const anchorId = decodeURIComponent(hash.split("?", 1)[0] || "");
      document.getElementById(anchorId)?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 120);
  }
}

function clampPanelSize() {
  panelSize.width = clamp(
    panelSize.width,
    MIN_PANEL_WIDTH,
    Math.max(MIN_PANEL_WIDTH, viewport.width - VIEWPORT_MARGIN * 2)
  );
  panelSize.height = clamp(
    panelSize.height,
    MIN_PANEL_HEIGHT,
    Math.max(MIN_PANEL_HEIGHT, viewport.height - 40)
  );
}

function adjustComposerHeight() {
  const node = inputRef.value;
  if (!node) return;
  node.style.height = "auto";
  node.style.height = `${Math.min(node.scrollHeight, 120)}px`;
}

async function loadAssistantConfig() {
  try {
    const { data } = await api.get("/assistant/config/");
    config.enabled = Boolean(data?.enabled);
    config.assistant_name = String(data?.assistant_name || "").trim() || "AlgoWiki 助手";
    config.welcome_message = String(data?.welcome_message || "").trim();
    config.teaser_message = String(data?.teaser_message || "").trim();
    config.suggested_questions = Array.isArray(data?.suggested_questions) ? data.suggested_questions : [];
    if (config.enabled) {
      seedWelcomeMessage();
    } else {
      messages.value = [];
    }
  } catch {
    config.enabled = false;
    messages.value = [];
  }
}

async function scrollToBottom() {
  await nextTick();
  const node = messageListRef.value;
  if (node) {
    node.scrollTop = node.scrollHeight;
  }
}

async function focusInput() {
  await nextTick();
  adjustComposerHeight();
  inputRef.value?.focus?.();
}

async function openPanel() {
  hideTeaser();
  isOpen.value = true;
  await focusInput();
  await scrollToBottom();
}

function closePanel() {
  isOpen.value = false;
}

async function handleTeaserClick() {
  await openPanel();
}

async function handleLauncherClick() {
  if (suppressNextClick.value) {
    suppressNextClick.value = false;
    return;
  }

  if (isOpen.value) {
    closePanel();
    return;
  }
  await openPanel();
}

function stopDrag() {
  if (typeof window === "undefined") return;
  window.removeEventListener("pointermove", handlePointerMove);
  window.removeEventListener("pointerup", handlePointerUp);
  window.removeEventListener("pointercancel", handlePointerUp);
}

function clampLauncherPosition() {
  position.x = clamp(position.x, VIEWPORT_MARGIN, viewport.width - LAUNCHER_WIDTH - VIEWPORT_MARGIN);
  position.y = clamp(position.y, 24, viewport.height - LAUNCHER_HEIGHT - VIEWPORT_MARGIN);
}

function startDrag(event) {
  if (event.button !== undefined && event.button !== 0) return;
  hideTeaser();
  dragState.active = true;
  dragState.pointerId = event.pointerId;
  dragState.originX = event.clientX;
  dragState.originY = event.clientY;
  dragState.offsetX = event.clientX - position.x;
  dragState.offsetY = event.clientY - position.y;
  dragState.moved = false;

  if (typeof window !== "undefined") {
    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
    window.addEventListener("pointercancel", handlePointerUp);
  }
}

function startResize(event) {
  if (isMobile.value) return;
  if (event.button !== undefined && event.button !== 0) return;
  resizeState.active = true;
  resizeState.originX = event.clientX;
  resizeState.originY = event.clientY;
  resizeState.startWidth = panelSize.width;
  resizeState.startHeight = panelSize.height;

  if (typeof window !== "undefined") {
    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
    window.addEventListener("pointercancel", handlePointerUp);
  }
}

function handlePointerMove(event) {
  if (resizeState.active) {
    panelSize.width = resizeState.startWidth + (resizeState.originX - event.clientX);
    panelSize.height = resizeState.startHeight + (resizeState.originY - event.clientY);
    clampPanelSize();
    return;
  }

  if (!dragState.active) return;
  const deltaX = Math.abs(event.clientX - dragState.originX);
  const deltaY = Math.abs(event.clientY - dragState.originY);
  if (deltaX > 4 || deltaY > 4) {
    dragState.moved = true;
  }
  position.x = event.clientX - dragState.offsetX;
  position.y = event.clientY - dragState.offsetY;
  clampLauncherPosition();
}

function handlePointerUp() {
  const wasDragging = dragState.active;
  const wasResizing = resizeState.active;
  if (!wasDragging && !wasResizing) return;

  if (wasDragging) {
    suppressNextClick.value = dragState.moved;
    dragState.active = false;
    dragState.pointerId = null;
    clampLauncherPosition();
    persistLauncherPosition();
  }

  if (wasResizing) {
    resizeState.active = false;
    clampPanelSize();
    persistPanelSize();
  }

  stopDrag();
}

function handleComposerInput() {
  adjustComposerHeight();
}

function handleComposerKeydown(event) {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    submitMessage();
  }
}

async function submitMessage(nextMessage = "") {
  const message = String(nextMessage || draft.value || "").trim();
  if (!message || loading.value || !config.enabled) return;

  const history = buildHistoryPayload();
  messages.value.push({
    id: messageSeed++,
    role: "user",
    content: message,
    sources: [],
    isWelcome: false,
  });
  draft.value = "";
  loading.value = true;
  await nextTick();
  adjustComposerHeight();
  await scrollToBottom();

  try {
    const { data } = await api.post("/assistant/chat/", {
      message,
      history,
      session_id: sessionId.value,
      ...buildPageContextPayload(),
    });
    messages.value.push({
      id: messageSeed++,
      role: "assistant",
      content: String(data?.answer || "").trim() || "当前没有可用回答。",
      sources: Array.isArray(data?.sources) ? data.sources : [],
      isWelcome: false,
    });
    await scrollToBottom();
  } catch (error) {
    const detail = normalizeErrorText(error);
    messages.value.push({
      id: messageSeed++,
      role: "assistant",
      content: detail,
      sources: [],
      isWelcome: false,
    });
    ui.error(detail);
    await scrollToBottom();
  } finally {
    loading.value = false;
    await focusInput();
  }
}

async function sendSuggested(question) {
  if (!question) return;
  await submitMessage(question);
}

function handleResize() {
  if (typeof window === "undefined") return;
  viewport.width = window.innerWidth;
  viewport.height = window.innerHeight;
  clampLauncherPosition();
  clampPanelSize();
  persistLauncherPosition();
  persistPanelSize();
}

function handleKeydown(event) {
  if (event.key === "Escape" && isOpen.value) {
    closePanel();
  }
}

watch(
  () => messages.value.length,
  async () => {
    await scrollToBottom();
  }
);

watch(
  () => isOpen.value,
  async (value) => {
    if (value) {
      hideTeaser();
      await focusInput();
      await scrollToBottom();
      return;
    }
    queueTeaser(900);
  }
);

watch(
  () => draft.value,
  async () => {
    await nextTick();
    adjustComposerHeight();
  }
);

watch(
  () => route.fullPath,
  () => {
    if (isOpen.value) return;
    queueTeaser(900);
  }
);

onMounted(async () => {
  clampLauncherPosition();
  clampPanelSize();
  await loadAssistantConfig();
  if (typeof window !== "undefined") {
    teaserPollTimer = window.setInterval(() => {
      if (!showTeaser.value && !isOpen.value) {
        queueTeaser(0);
      }
    }, 60 * 1000);
  }
  queueTeaser();
  await nextTick();
  adjustComposerHeight();
  if (typeof window !== "undefined") {
    window.addEventListener("resize", handleResize);
    window.addEventListener("keydown", handleKeydown);
  }
});

onBeforeUnmount(() => {
  stopDrag();
  clearTeaserTimers();
  if (typeof window !== "undefined") {
    window.removeEventListener("resize", handleResize);
    window.removeEventListener("keydown", handleKeydown);
  }
});
</script>

<style scoped>
.assistant-root {
  position: fixed;
  inset: 0;
  z-index: 70;
  pointer-events: none;
}

.assistant-panel {
  position: fixed;
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr) auto auto;
  overflow: hidden;
  border-radius: 2rem;
  border: 1px solid rgba(255, 255, 255, 0.42);
  background: rgba(255, 255, 255, 0.78);
  backdrop-filter: blur(28px) saturate(1.2);
  box-shadow:
    0 24px 80px -28px rgba(15, 23, 42, 0.35),
    inset 0 1px 0 rgba(255, 255, 255, 0.6);
  pointer-events: auto;
  font-size: 14px;
}

.assistant-teaser {
  position: fixed;
  z-index: 71;
  border: 1px solid rgba(255, 255, 255, 0.88);
  border-radius: 1.2rem;
  padding: 0.82rem 0.95rem;
  background: rgba(255, 255, 255, 0.96);
  color: #4d5671;
  font-size: 0.88rem;
  line-height: 1.45;
  text-align: left;
  box-shadow:
    0 22px 48px -28px rgba(15, 23, 42, 0.26),
    inset 0 1px 0 rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(18px) saturate(1.12);
  pointer-events: auto;
  cursor: pointer;
  transition:
    transform 0.18s ease,
    box-shadow 0.18s ease,
    border-color 0.18s ease;
}

.assistant-teaser:hover {
  transform: translateY(-1px);
  border-color: rgba(112, 132, 255, 0.28);
  box-shadow:
    0 26px 56px -30px rgba(15, 23, 42, 0.3),
    inset 0 1px 0 rgba(255, 255, 255, 0.95);
}

.assistant-teaser::after {
  content: "";
  position: absolute;
  width: 1rem;
  height: 1rem;
  background: rgba(255, 255, 255, 0.96);
  border-right: 1px solid rgba(255, 255, 255, 0.88);
  border-bottom: 1px solid rgba(255, 255, 255, 0.88);
  transform: rotate(45deg);
}

.assistant-teaser--left.assistant-teaser--top::after {
  right: 1rem;
  bottom: -0.34rem;
}

.assistant-teaser--right.assistant-teaser--top::after {
  left: 1rem;
  bottom: -0.34rem;
}

.assistant-teaser--left.assistant-teaser--bottom::after {
  right: 1rem;
  top: -0.34rem;
  transform: rotate(225deg);
}

.assistant-teaser--right.assistant-teaser--bottom::after {
  left: 1rem;
  top: -0.34rem;
  transform: rotate(225deg);
}

.assistant-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.85rem;
  padding: 1.05rem 1.2rem 0.75rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.16);
}

.assistant-header-copy {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  min-width: 0;
}

.assistant-avatar {
  width: 2.6rem;
  height: 2.6rem;
  border-radius: 999px;
  overflow: hidden;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #f6f7fb;
  box-shadow: 0 14px 30px -18px rgba(15, 23, 42, 0.28);
  flex: 0 0 auto;
}

.assistant-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.assistant-kicker {
  margin: 0 0 0.1rem;
  color: #8b8b92;
  font-size: 0.62rem;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.assistant-header h3 {
  margin: 0;
  color: #202127;
  font-size: clamp(1.12rem, 1.8vw, 1.34rem);
  line-height: 1.1;
  letter-spacing: -0.025em;
}

.assistant-close {
  width: 2.15rem;
  height: 2.15rem;
  border: 0;
  border-radius: 999px;
  background: rgba(229, 229, 234, 0.95);
  color: #8e8e93;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  transition:
    background-color 0.18s ease,
    color 0.18s ease,
    transform 0.18s ease;
}

.assistant-close:hover {
  background: rgba(209, 209, 214, 0.98);
  color: #53545a;
  transform: translateY(-1px);
}

.assistant-close svg {
  width: 0.92rem;
  height: 0.92rem;
}

.assistant-info {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.62rem 1.2rem;
  color: #8b8b92;
  font-size: 0.74rem;
  background: rgba(245, 245, 247, 0.62);
  border-bottom: 1px solid rgba(148, 163, 184, 0.14);
}

.assistant-info svg {
  width: 0.88rem;
  height: 0.88rem;
  flex: 0 0 auto;
}

.assistant-body {
  min-height: 0;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  padding: 1.1rem 1.15rem 0.85rem;
  scrollbar-width: thin;
  scrollbar-color: rgba(148, 163, 184, 0.78) transparent;
}

.assistant-body::-webkit-scrollbar {
  width: 8px;
}

.assistant-body::-webkit-scrollbar-track {
  background: transparent;
}

.assistant-body::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.78);
}

.assistant-message {
  display: flex;
  width: 100%;
  min-width: 0;
}

.assistant-message--assistant {
  justify-content: flex-start;
}

.assistant-message--user {
  justify-content: flex-end;
}

.assistant-bubble {
  width: min(100%, 85%);
  max-width: 100%;
  min-width: 0;
  padding: 0.8rem 0.95rem;
  border-radius: 1.22rem;
  background: rgba(233, 233, 235, 0.95);
  color: #202127;
  box-shadow: 0 10px 30px -24px rgba(15, 23, 42, 0.45);
  display: grid;
  gap: 0.72rem;
  word-break: break-word;
  overflow-wrap: anywhere;
  overflow: hidden;
  font-size: 0.9rem;
}

.assistant-message--assistant .assistant-bubble {
  border-top-left-radius: 0.52rem;
}

.assistant-message--user .assistant-bubble {
  background: linear-gradient(180deg, #1682ff 0%, #0a72f2 100%);
  color: #ffffff;
  border-top-right-radius: 0.52rem;
}

.assistant-bubble :deep(p),
.assistant-bubble :deep(ol),
.assistant-bubble :deep(ul),
.assistant-bubble :deep(pre),
.assistant-bubble :deep(blockquote) {
  margin: 0;
}

.assistant-bubble :deep(p),
.assistant-bubble :deep(li),
.assistant-bubble :deep(blockquote),
.assistant-bubble :deep(td),
.assistant-bubble :deep(th) {
  line-height: 1.48;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.assistant-bubble :deep(h1),
.assistant-bubble :deep(h2),
.assistant-bubble :deep(h3),
.assistant-bubble :deep(h4) {
  margin: 0;
  line-height: 1.28;
}

.assistant-bubble :deep(h1) {
  font-size: 1.02rem;
}

.assistant-bubble :deep(h2) {
  font-size: 0.96rem;
}

.assistant-bubble :deep(h3),
.assistant-bubble :deep(h4) {
  font-size: 0.91rem;
}

.assistant-bubble :deep(ol),
.assistant-bubble :deep(ul) {
  padding-left: 1.15rem;
}

.assistant-bubble :deep(.markdown) {
  min-width: 0;
  max-width: 100%;
  overflow-wrap: anywhere;
}

.assistant-bubble :deep(a) {
  overflow-wrap: anywhere;
  word-break: break-word;
}

.assistant-bubble :deep(table),
.assistant-bubble :deep(pre),
.assistant-bubble :deep(.katex-display),
.assistant-bubble :deep(img) {
  max-width: 100%;
}

.assistant-bubble :deep(table) {
  display: block;
  overflow-x: auto;
}

.assistant-bubble :deep(pre) {
  min-width: 0;
}

.assistant-bubble :deep(:not(pre) > code) {
  white-space: break-spaces;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.assistant-message--user .assistant-bubble :deep(a) {
  color: inherit;
}

.assistant-bubble--loading {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  width: auto;
  min-width: 4.8rem;
}

.assistant-bubble--loading span {
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 999px;
  background: #6486ff;
  opacity: 0.32;
  animation: assistant-pulse 1s infinite ease-in-out;
}

.assistant-bubble--loading span:nth-child(2) {
  animation-delay: 0.16s;
}

.assistant-bubble--loading span:nth-child(3) {
  animation-delay: 0.32s;
}

.assistant-sources {
  display: flex;
  flex-wrap: wrap;
  gap: 0.38rem;
  align-items: center;
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
  padding-top: 0.58rem;
  border-top: 1px solid rgba(148, 163, 184, 0.22);
}

.assistant-sources strong {
  display: none;
}

.assistant-message--user .assistant-sources strong {
  display: none;
}

.assistant-source {
  display: inline-flex;
  align-items: center;
  flex: 0 1 auto;
  max-width: 100%;
  min-width: 0;
  min-height: 1.78rem;
  padding: 0.24rem 0.6rem;
  border-radius: 999px;
  text-decoration: none;
  color: inherit;
  background: rgba(255, 255, 255, 0.5);
  border: 1px solid rgba(148, 163, 184, 0.2);
  transition:
    transform 0.16s ease,
    background-color 0.16s ease,
    border-color 0.16s ease;
}

.assistant-source:hover {
  transform: translateY(-1px);
  background: rgba(255, 255, 255, 0.68);
  border-color: rgba(59, 130, 246, 0.22);
}

.assistant-message--user .assistant-source {
  background: rgba(255, 255, 255, 0.14);
  border-color: rgba(255, 255, 255, 0.12);
}

.assistant-message--user .assistant-source:hover {
  background: rgba(255, 255, 255, 0.22);
  border-color: rgba(255, 255, 255, 0.24);
}

.assistant-source span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.68rem;
  font-weight: 700;
}

.assistant-source--overflow {
  cursor: default;
  justify-content: center;
}

.assistant-source--overflow:hover {
  transform: none;
}

.assistant-suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  padding: 0 1.15rem 0.75rem;
}

.assistant-suggestion {
  border: 1px solid rgba(209, 213, 219, 0.88);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.92);
  color: #4b5563;
  padding: 0.46rem 0.8rem;
  font-size: 0.74rem;
  line-height: 1.2;
  cursor: pointer;
  transition:
    border-color 0.18s ease,
    color 0.18s ease,
    background-color 0.18s ease,
    transform 0.18s ease;
}

.assistant-suggestion:hover {
  color: #0a72f2;
  border-color: rgba(10, 114, 242, 0.28);
  background: rgba(255, 255, 255, 0.98);
  transform: translateY(-1px);
}

.assistant-footer {
  padding: 0.25rem 1.15rem 0.95rem;
  background: rgba(255, 255, 255, 0.36);
  backdrop-filter: blur(12px);
}

.assistant-resize-handle {
  position: absolute;
  left: 0.72rem;
  bottom: 0.68rem;
  width: 1.7rem;
  height: 1.7rem;
  border: 0;
  padding: 0;
  display: inline-flex;
  align-items: flex-end;
  justify-content: center;
  gap: 0.14rem;
  background: transparent;
  pointer-events: auto;
  cursor: nesw-resize;
  opacity: 0.7;
  transition:
    opacity 0.18s ease,
    transform 0.18s ease;
}

.assistant-resize-handle:hover {
  opacity: 1;
  transform: translate(-1px, 1px);
}

.assistant-resize-handle span {
  width: 0.28rem;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.9);
  transform: rotate(38deg);
}

.assistant-resize-handle span:nth-child(1) {
  height: 0.46rem;
}

.assistant-resize-handle span:nth-child(2) {
  height: 0.66rem;
}

.assistant-resize-handle span:nth-child(3) {
  height: 0.9rem;
}

.assistant-composer {
  display: flex;
  align-items: flex-end;
  gap: 0.5rem;
  padding: 0.32rem;
  border: 1px solid rgba(209, 213, 219, 0.9);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.84),
    0 12px 28px -24px rgba(15, 23, 42, 0.4);
  transition:
    border-color 0.18s ease,
    box-shadow 0.18s ease;
}

.assistant-composer:focus-within {
  border-color: rgba(10, 114, 242, 0.24);
  box-shadow:
    0 0 0 4px rgba(10, 114, 242, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.84),
    0 12px 28px -24px rgba(15, 23, 42, 0.4);
}

.assistant-input {
  flex: 1 1 auto;
  min-height: 2.2rem;
  max-height: 7.5rem;
  border: 0;
  background: transparent;
  color: #202127;
  font-size: 0.88rem;
  line-height: 1.38;
  outline: none;
  resize: none;
  padding: 0.5rem 0.78rem;
}

.assistant-input::placeholder {
  color: #8b8b92;
}

.assistant-send {
  width: 2.35rem;
  height: 2.35rem;
  border: 0;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  color: #c5c8d2;
  background: #f3f4f8;
  transform: scale(0.95);
  transition:
    background-color 0.18s ease,
    color 0.18s ease,
    transform 0.18s ease,
    box-shadow 0.18s ease;
}

.assistant-send--enabled {
  background: linear-gradient(180deg, #1682ff 0%, #0a72f2 100%);
  color: #ffffff;
  transform: scale(1);
  box-shadow: 0 12px 24px -18px rgba(10, 114, 242, 0.95);
}

.assistant-send svg {
  width: 1.02rem;
  height: 1.02rem;
}

.assistant-meta {
  margin: 0.65rem 0 0;
  color: #8b8b92;
  font-size: 0.65rem;
  font-weight: 600;
  letter-spacing: 0.01em;
  text-align: center;
}

.assistant-launcher {
  position: fixed;
  width: 3.75rem;
  height: 3.75rem;
  border: 1px solid rgba(255, 255, 255, 0.82);
  border-radius: 999px;
  background:
    radial-gradient(circle at 30% 25%, rgba(255, 255, 255, 0.98) 0%, rgba(248, 250, 255, 0.94) 55%, rgba(236, 241, 255, 0.92) 100%);
  backdrop-filter: blur(20px) saturate(1.18);
  box-shadow:
    0 18px 42px -24px rgba(15, 23, 42, 0.34),
    inset 0 1px 0 rgba(255, 255, 255, 0.84);
  color: #4c60ff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: grab;
  pointer-events: auto;
  user-select: none;
  touch-action: none;
  isolation: isolate;
  transition:
    transform 0.18s ease,
    box-shadow 0.18s ease,
    border-color 0.18s ease;
}

.assistant-launcher::before {
  content: "";
  position: absolute;
  inset: 0.34rem;
  border-radius: 999px;
  background: radial-gradient(circle at 32% 30%, rgba(89, 128, 255, 0.18) 0%, rgba(89, 128, 255, 0.08) 48%, rgba(255, 255, 255, 0) 72%);
  z-index: 0;
}

.assistant-launcher::after {
  content: "";
  position: absolute;
  right: 0.55rem;
  top: 0.58rem;
  width: 0.42rem;
  height: 0.42rem;
  border-radius: 999px;
  background: linear-gradient(180deg, #77b2ff 0%, #4d66ff 100%);
  box-shadow: 0 0 0 0.14rem rgba(255, 255, 255, 0.8);
  z-index: 2;
}

.assistant-launcher:hover {
  transform: translateY(-2px) scale(1.02);
  border-color: rgba(77, 102, 255, 0.28);
  box-shadow:
    0 24px 50px -26px rgba(15, 23, 42, 0.38),
    inset 0 1px 0 rgba(255, 255, 255, 0.9);
}

.assistant-launcher:active {
  cursor: grabbing;
  transform: scale(0.98);
}

.assistant-launcher-icon {
  position: relative;
  z-index: 1;
  width: 2.22rem;
  height: 2.22rem;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #4c60ff;
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.96) 0%, rgba(236, 242, 255, 0.95) 100%);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.96),
    0 12px 26px -18px rgba(76, 96, 255, 0.42);
  overflow: hidden;
}

.assistant-launcher-icon img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.assistant-panel-enter-active,
.assistant-teaser-enter-active,
.assistant-panel-leave-active {
  transition:
    opacity 0.2s ease,
    transform 0.2s ease;
}

.assistant-panel-enter-from,
.assistant-panel-leave-to,
.assistant-teaser-enter-from,
.assistant-teaser-leave-to {
  opacity: 0;
  transform: translateY(12px) scale(0.985);
}

.assistant-teaser-enter-active,
.assistant-teaser-leave-active {
  transition:
    opacity 0.22s ease,
    transform 0.22s ease;
}

@keyframes assistant-pulse {
  0%,
  100% {
    opacity: 0.28;
    transform: translateY(0);
  }
  50% {
    opacity: 1;
    transform: translateY(-1px);
  }
}

@media (max-width: 640px) {
  .assistant-panel {
    left: 0.75rem;
    right: 0.75rem;
    bottom: 5.7rem;
    top: auto;
    width: auto;
    max-height: min(78vh, 44rem);
    border-radius: 1.8rem;
  }

  .assistant-header,
  .assistant-info,
  .assistant-body,
  .assistant-suggestions,
  .assistant-footer {
    padding-left: 1rem;
    padding-right: 1rem;
  }

  .assistant-header {
    padding-top: 0.95rem;
    padding-bottom: 0.7rem;
  }

  .assistant-bubble {
    width: min(100%, 92%);
  }

  .assistant-launcher {
    width: 3.35rem;
    height: 3.35rem;
  }

  .assistant-teaser {
    max-width: min(15rem, calc(100vw - 1.5rem));
    font-size: 0.8rem;
    padding: 0.74rem 0.82rem;
  }
}
</style>

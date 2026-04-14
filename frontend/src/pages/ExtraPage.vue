<template>
  <section class="extra-layout">
    <article class="extra-main" v-if="isTricksPanel">
      <div class="section-title">trick技巧</div>
      <p class="meta">
        {{
          auth.isManager
            ? "管理员提交会直接发布；支持 Markdown 文本，不提供图片上传。"
            : "提交后需管理员审核通过才会对全部用户展示；支持 Markdown 文本，不提供图片上传。"
        }}
      </p>

      <section class="trick-submit card" v-if="auth.isAuthenticated">
        <div class="trick-submit-head">
          <h4>提交 trick</h4>
          <span class="trick-submit-hint"
            >已选词条 {{ selectedTrickTerms.length }} 个 · 待审词条
            {{ trickForm.pending_term_names.length }} 个</span
          >
        </div>
        <input
          class="input"
          v-model="trickForm.title"
          placeholder="标题（可选，不填会按正文自动生成）"
        />
        <div class="term-picker">
          <div class="term-picker-head">
            <strong>词条</strong>
            <span class="meta">支持多选，用于 ACM 检索</span>
          </div>
          <input
            class="input"
            v-model="trickTermSearch"
            placeholder="搜索词条（如：前缀和 / 二分答案）"
          />
          <div class="term-options">
            <label
              v-for="term in filteredTrickTerms"
              :key="term.id"
              class="term-option"
            >
              <input
                type="checkbox"
                :value="term.id"
                :checked="trickForm.term_ids.includes(term.id)"
                @change="toggleTrickTerm(term.id)"
              />
              <span>{{ term.name }}</span>
            </label>
          </div>
          <div class="term-selected" v-if="selectedTrickTerms.length">
            <button
              type="button"
              v-for="term in selectedTrickTerms"
              :key="`selected-${term.id}`"
              class="term-chip term-chip-removable"
              @click="removeSelectedTrickTerm(term.id)"
            >
              {{ term.name }} ×
            </button>
          </div>
          <p v-else class="meta">当前未选择词条。</p>
          <div class="pending-term-builder">
            <input
              class="input"
              v-model="trickForm.pending_term_draft"
              placeholder="预输入待审核词条（审核通过后自动展示）"
              @keyup.enter.prevent="addPendingTermDraft"
            />
            <button
              class="btn add-tag-btn"
              type="button"
              @click="addPendingTermDraft"
            >
              + 添加
            </button>
          </div>
          <transition-group
            name="pending-term-fade"
            tag="div"
            class="term-selected"
            v-if="trickForm.pending_term_names.length"
          >
            <button
              type="button"
              v-for="(name, idx) in trickForm.pending_term_names"
              :key="`pending-${name}-${idx}`"
              class="term-chip term-chip-pending"
              @click="removePendingTerm(idx)"
            >
              {{ name }} · 待审 ×
            </button>
          </transition-group>
          <p v-else class="meta">未添加待审核词条，可用“+ 添加”预先录入。</p>
        </div>
        <div
          class="trick-editor-shell"
          :class="{ 'is-expanded': submitEditorExpanded }"
        >
          <div class="editor-toolbar">
            <span class="editor-toolbar-label">左侧编写，右侧实时预览</span>
            <button
              type="button"
              class="btn btn-mini"
              @click="submitEditorExpanded = !submitEditorExpanded"
            >
              {{ submitEditorExpanded ? "收起编写" : "展开编写" }}
            </button>
          </div>
          <div class="trick-editor-grid">
            <section class="trick-editor-pane">
              <header class="trick-editor-pane-head">Markdown 原文</header>
              <textarea
                class="textarea trick-editor-textarea"
                v-model="trickForm.content_md"
                placeholder="使用 Markdown 编写 trick 内容"
              ></textarea>
            </section>
            <section class="trick-editor-pane">
              <header class="trick-editor-pane-head">渲染预览</header>
              <div
                class="markdown trick-editor-preview"
                v-html="renderMarkdown(trickForm.content_md || '')"
              ></div>
            </section>
          </div>
        </div>
        <button
          class="btn btn-accent"
          :disabled="submittingTrick"
          @click="submitTrick"
        >
          {{ submittingTrick ? "提交中..." : "提交 trick" }}
        </button>
      </section>
      <p v-else class="meta">登录后可提交 trick。</p>

      <section class="trick-list card">
        <div class="trick-filters">
          <input
            class="input"
            v-model="trickFilters.search"
            placeholder="搜索 trick 标题或内容"
            @keyup.enter="loadTricks(1, false)"
          />
          <select
            class="select"
            v-model="trickFilters.termId"
            @change="loadTricks(1, false)"
          >
            <option value="">全部词条</option>
            <option
              v-for="term in sortedTrickTerms"
              :key="`filter-term-${term.id}`"
              :value="String(term.id)"
            >
              {{ term.name }}
            </option>
          </select>
          <button class="btn" @click="resetTrickFilters">重置</button>
        </div>
        <div class="trick-list-meta">
          <span>共 {{ trickMeta.count }} 条</span>
          <span v-if="trickFilters.search || trickFilters.termId"
            >当前为筛选结果</span
          >
        </div>
        <article class="trick-item" v-for="item in tricks" :key="item.id">
          <header class="trick-item-head">
            <h5
              class="trick-item-title"
              v-html="renderInlineMarkdown(item.title || '未命名 trick')"
            ></h5>
            <span class="trick-status-badge" v-if="showStatus(item)">{{
              statusText(item.status)
            }}</span>
          </header>
          <div class="trick-meta-row">
            <span>发布者：{{ item.author?.username || "-" }}</span>
            <span>发布时间：{{ formatTime(item.created_at) }}</span>
          </div>
          <div class="term-selected" v-if="item.terms?.length">
            <span
              v-for="term in sortTermItems(item.terms)"
              :key="`term-${item.id}-${term.id}`"
              class="term-chip"
              >{{ term.name }}</span
            >
          </div>

          <div
            class="trick-action-row"
            v-if="
              canEditTrick(item) ||
              canDeleteTrick(item) ||
              canModerateTrick(item)
            "
          >
            <span class="trick-status" v-if="showStatus(item)"
              >状态：{{ statusText(item.status) }}</span
            >
            <button
              class="btn btn-mini"
              v-if="canEditTrick(item)"
              @click="startEditTrick(item)"
            >
              {{ editingTrickId === item.id ? "取消编辑" : "编辑" }}
            </button>
            <button
              class="btn btn-mini"
              v-if="canDeleteTrick(item)"
              @click="deleteTrick(item)"
            >
              删除
            </button>
            <button
              class="btn btn-mini"
              v-if="canModerateTrick(item)"
              @click="setTrickStatus(item, 'approved')"
            >
              通过
            </button>
            <button
              class="btn btn-mini"
              v-if="canModerateTrick(item)"
              @click="setTrickStatus(item, 'rejected')"
            >
              拒绝
            </button>
          </div>

          <div v-if="editingTrickId === item.id" class="trick-edit-zone">
            <div class="trick-action-row">
              <span class="trick-status"
                >已选词条 {{ editSelectedTrickTerms.length }} 个 · 待审词条
                {{ editForm.pending_term_names.length }} 个</span
              >
              <button
                class="btn btn-mini"
                type="button"
                @click="editTagEditorVisible = !editTagEditorVisible"
              >
                {{ editTagEditorVisible ? "收起 tag 编辑" : "编辑 tag" }}
              </button>
            </div>
            <div class="term-picker" v-if="editTagEditorVisible">
              <div class="term-picker-head">
                <strong>词条</strong>
                <span class="meta">支持多选；可继续预输入待审核词条</span>
              </div>
              <input
                class="input"
                v-model="editTrickTermSearch"
                placeholder="搜索词条（如：前缀和 / 二分答案）"
              />
              <div class="term-options">
                <label
                  v-for="term in filteredEditTrickTerms"
                  :key="`edit-term-${term.id}`"
                  class="term-option"
                >
                  <input
                    type="checkbox"
                    :value="term.id"
                    :checked="editForm.term_ids.includes(term.id)"
                    @change="toggleEditTrickTerm(term.id)"
                  />
                  <span>{{ term.name }}</span>
                </label>
              </div>
              <div class="term-selected" v-if="editSelectedTrickTerms.length">
                <button
                  type="button"
                  v-for="term in editSelectedTrickTerms"
                  :key="`edit-selected-${term.id}`"
                  class="term-chip term-chip-removable"
                  @click="removeEditSelectedTrickTerm(term.id)"
                >
                  {{ term.name }} ×
                </button>
              </div>
              <p v-else class="meta">当前未选择词条。</p>
              <div class="pending-term-builder">
                <input
                  class="input"
                  v-model="editForm.pending_term_draft"
                  placeholder="预输入待审核词条（审核通过后自动展示）"
                  @keyup.enter.prevent="addEditPendingTermDraft"
                />
                <button
                  class="btn add-tag-btn"
                  type="button"
                  @click="addEditPendingTermDraft"
                >
                  + 添加
                </button>
              </div>
              <transition-group
                name="pending-term-fade"
                tag="div"
                class="term-selected"
                v-if="editForm.pending_term_names.length"
              >
                <button
                  type="button"
                  v-for="(name, idx) in editForm.pending_term_names"
                  :key="`edit-pending-${name}-${idx}`"
                  class="term-chip term-chip-pending"
                  @click="removeEditPendingTerm(idx)"
                >
                  {{ name }} · 待审 ×
                </button>
              </transition-group>
              <p v-else class="meta">
                未添加待审核词条，可用“+ 添加”预先录入。
              </p>
              <div
                class="term-selected"
                v-if="filteredOwnPendingTermNamesForEdit.length"
              >
                <button
                  type="button"
                  v-for="name in filteredOwnPendingTermNamesForEdit"
                  :key="`edit-own-pending-${name}`"
                  class="term-chip term-chip-pending"
                  @click="addEditPendingTermFromMine(name)"
                >
                  {{ name }} · 我的待审 +
                </button>
              </div>
              <p class="meta" v-else-if="ownPendingTermNames.length">
                当前搜索下没有可添加的我的待审词条。
              </p>
            </div>
            <div
              class="trick-editor-shell"
              :class="{ 'is-expanded': editEditorExpanded }"
            >
              <div class="editor-toolbar">
                <span class="editor-toolbar-label">左侧编写，右侧实时预览</span>
                <button
                  type="button"
                  class="btn btn-mini"
                  @click="editEditorExpanded = !editEditorExpanded"
                >
                  {{ editEditorExpanded ? "收起编写" : "展开编写" }}
                </button>
              </div>
              <div class="trick-editor-grid">
                <section class="trick-editor-pane">
                  <header class="trick-editor-pane-head">Markdown 原文</header>
                  <textarea
                    class="textarea trick-editor-textarea"
                    v-model="editForm.content_md"
                  ></textarea>
                </section>
                <section class="trick-editor-pane">
                  <header class="trick-editor-pane-head">渲染预览</header>
                  <div
                    class="markdown trick-editor-preview"
                    v-html="renderMarkdown(editForm.content_md || '')"
                  ></div>
                </section>
              </div>
            </div>
            <button
              class="btn btn-accent"
              :disabled="savingEdit"
              @click="saveEditTrick(item)"
            >
              {{ savingEdit ? "保存中..." : "保存修改" }}
            </button>
          </div>

          <div
            v-else
            class="markdown trick-markdown"
            v-html="renderMarkdown(item.content_md || '')"
          ></div>
        </article>

        <p v-if="!tricks.length" class="meta">暂无 trick 记录。</p>

        <div class="table-foot" v-if="trickMeta.next">
          <button
            class="btn"
            :disabled="trickMeta.loadingMore"
            @click="loadMoreTricks"
          >
            {{ trickMeta.loadingMore ? "加载中..." : "加载更多" }}
          </button>
        </div>
      </section>
    </article>

    <article v-else class="extra-main extra-main--page">
      <header class="extra-head">
        <div class="extra-head-copy">
          <div class="section-title">
            {{ page?.title || fallbackPageTitle }}
          </div>
          <p class="meta">{{ page?.description || fallbackPageDescription }}</p>
        </div>
        <div v-if="canEditPage" class="extra-head-actions">
          <button type="button" class="btn" @click="togglePageEditor">
            {{ showPageEditor ? "收起编辑" : "编辑页面" }}
          </button>
        </div>
      </header>

      <section v-if="canEditPage && showPageEditor" class="page-editor card">
        <div class="page-editor-grid">
          <input
            v-model.trim="pageForm.title"
            class="input"
            placeholder="页面标题"
          />
          <input
            v-model.trim="pageForm.description"
            class="input"
            placeholder="页面简介"
          />
        </div>
        <textarea
          v-model="pageForm.content_md"
          class="textarea"
          placeholder="使用 Markdown 编写页面内容"
        ></textarea>
        <div class="trick-action-row">
          <button
            type="button"
            class="btn btn-accent"
            :disabled="savingPage"
            @click="savePage"
          >
            {{ savingPage ? "保存中..." : "保存页面" }}
          </button>
          <button
            type="button"
            class="btn"
            :disabled="savingPage"
            @click="resetPageEditor"
          >
            重置
          </button>
        </div>
      </section>

      <section class="markdown page-markdown" v-html="htmlContent"></section>
    </article>
  </section>
</template>

<script setup>
import {
  computed,
  onBeforeUnmount,
  onMounted,
  reactive,
  ref,
  watch,
} from "vue";
import { useRoute } from "vue-router";

import api from "../services/api";
import { renderInlineMarkdown, renderMarkdown } from "../services/markdown";
import { useAuthStore } from "../stores/auth";
import { useUiStore } from "../stores/ui";

const props = defineProps({
  slug: {
    type: String,
    default: "",
  },
});

const route = useRoute();
const auth = useAuthStore();
const ui = useUiStore();

const page = ref(null);
const pageExists = ref(false);
const tricks = ref([]);
const trickTerms = ref([]);
const submittingTrick = ref(false);
const savingEdit = ref(false);
const savingPage = ref(false);
const editingTrickId = ref(null);
const showPageEditor = ref(false);
const trickTermSearch = ref("");
const editTrickTermSearch = ref("");
const submitEditorExpanded = ref(false);
const editEditorExpanded = ref(false);
const editTagEditorVisible = ref(false);
const ownPendingTermNames = ref([]);

const trickForm = reactive({
  title: "",
  content_md: "",
  term_ids: [],
  pending_term_draft: "",
  pending_term_names: [],
});

const editForm = reactive({
  content_md: "",
  term_ids: [],
  pending_term_draft: "",
  pending_term_names: [],
});

const pageForm = reactive({
  title: "",
  description: "",
  content_md: "",
});

const trickMeta = reactive({
  count: 0,
  next: "",
  loadingMore: false,
});

const trickFilters = reactive({
  search: "",
  termId: "",
});

const currentPageSlug = computed(() => {
  const propSlug = String(props.slug || "")
    .trim()
    .toLowerCase();
  if (propSlug) return propSlug;
  const routeSlug = String(route.params.slug || "")
    .trim()
    .toLowerCase();
  return routeSlug || "about";
});

const isTricksPanel = computed(() => currentPageSlug.value === "tricks");
const canEditPage = computed(() => !isTricksPanel.value && auth.isManager);
const fallbackPageTitle = computed(() => titleFromSlug(currentPageSlug.value));
const fallbackPageDescription = computed(() =>
  currentPageSlug.value === "about"
    ? "项目介绍与路线图。"
    : "当前页面暂未填写简介。",
);
const htmlContent = computed(() =>
  renderMarkdown(page.value?.content_md || ""),
);
const filteredTrickTerms = computed(() => {
  const keyword = trickTermSearch.value.trim().toLowerCase();
  const source = Array.isArray(trickTerms.value) ? trickTerms.value : [];
  if (!keyword) return source;
  return source.filter((item) =>
    String(item.name || "")
      .toLowerCase()
      .includes(keyword),
  );
});
const sortedTrickTerms = computed(() => sortTermItems(trickTerms.value));
const selectedTrickTerms = computed(() => {
  const selected = new Set(trickForm.term_ids);
  return sortTermItems(
    trickTerms.value.filter((term) => selected.has(term.id)),
  );
});
const filteredEditTrickTerms = computed(() => {
  const keyword = editTrickTermSearch.value.trim().toLowerCase();
  const source = Array.isArray(trickTerms.value) ? trickTerms.value : [];
  if (!keyword) return source;
  return source.filter((item) =>
    String(item.name || "")
      .toLowerCase()
      .includes(keyword),
  );
});
const editSelectedTrickTerms = computed(() => {
  const selected = new Set(editForm.term_ids);
  return sortTermItems(
    trickTerms.value.filter((term) => selected.has(term.id)),
  );
});
const filteredOwnPendingTermNamesForEdit = computed(() => {
  const keyword = editTrickTermSearch.value.trim().toLowerCase();
  const selectedNames = new Set(
    editSelectedTrickTerms.value.map((x) => String(x.name || "").toLowerCase()),
  );
  const chosenPendingNames = new Set(
    editForm.pending_term_names.map((x) => String(x || "").toLowerCase()),
  );
  return ownPendingTermNames.value.filter((name) => {
    const text = String(name || "").trim();
    if (!text) return false;
    const key = text.toLowerCase();
    if (selectedNames.has(key) || chosenPendingNames.has(key)) return false;
    if (!keyword) return true;
    return key.includes(keyword);
  });
});

const pinyinCollator = new Intl.Collator("zh-u-co-pinyin", {
  sensitivity: "base",
  numeric: true,
  ignorePunctuation: true,
});

function sortTermItems(items) {
  const source = Array.isArray(items) ? [...items] : [];
  source.sort((a, b) =>
    pinyinCollator.compare(String(a?.name || ""), String(b?.name || "")),
  );
  return source;
}

function titleFromSlug(slug) {
  if (slug === "about") return "关于 AlgoWiki";
  return String(slug || "新页面")
    .split(/[-_]/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")} ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

function statusText(status) {
  const map = {
    pending: "待审核",
    approved: "已通过",
    rejected: "已拒绝",
  };
  return map[status] || status || "-";
}

function showStatus(item) {
  return canEditTrick(item) || auth.isManager;
}

function canEditTrick(item) {
  if (!auth.user) return false;
  return auth.isManager || item.author?.id === auth.user.id;
}

function canDeleteTrick(item) {
  return canEditTrick(item);
}

function canModerateTrick(item) {
  return auth.isManager && item.status === "pending";
}

function nextPageFromUrl(url, fallback = 2) {
  if (!url) return fallback;
  try {
    return Number(
      new URL(url, window.location.origin).searchParams.get("page") ||
        String(fallback),
    );
  } catch {
    return fallback;
  }
}

function unpackListPayload(data, currentLength = 0) {
  if (Array.isArray(data)) {
    return { results: data, count: currentLength + data.length, next: "" };
  }
  return {
    results: Array.isArray(data?.results) ? data.results : [],
    count: Number.isFinite(data?.count) ? data.count : currentLength,
    next: typeof data?.next === "string" ? data.next : "",
  };
}

function getErrorText(error, fallback = "操作失败") {
  const payload = error?.response?.data;
  if (!payload) return fallback;
  if (typeof payload === "string") return payload;
  if (typeof payload.detail === "string") return payload.detail;
  return fallback;
}

function applyPageToForm(item) {
  pageForm.title = item?.title || fallbackPageTitle.value;
  pageForm.description = item?.description || "";
  pageForm.content_md = item?.content_md || "";
}

async function loadPage() {
  if (isTricksPanel.value) return;
  page.value = null;
  pageExists.value = false;
  try {
    const { data } = await api.get(`/pages/${currentPageSlug.value}/`);
    page.value = data;
    pageExists.value = true;
    applyPageToForm(data);
  } catch {
    page.value = {
      title: fallbackPageTitle.value,
      description: fallbackPageDescription.value,
      content_md: "",
    };
    applyPageToForm(page.value);
  }
}

function resetPageEditor() {
  applyPageToForm(page.value);
}

function togglePageEditor() {
  showPageEditor.value = !showPageEditor.value;
  if (showPageEditor.value) {
    resetPageEditor();
  }
}

async function savePage() {
  if (!canEditPage.value) return;
  const title = String(pageForm.title || "").trim();
  if (!title) {
    ui.info("请填写页面标题");
    return;
  }

  savingPage.value = true;
  try {
    let data;
    const payload = {
      title,
      description: String(pageForm.description || "").trim(),
      content_md: pageForm.content_md || "",
      access_level: "public",
      is_enabled: true,
    };

    if (pageExists.value) {
      ({ data } = await api.patch(`/pages/${currentPageSlug.value}/`, payload));
    } else {
      ({ data } = await api.post("/pages/", {
        ...payload,
        slug: currentPageSlug.value,
      }));
      pageExists.value = true;
    }

    page.value = data;
    applyPageToForm(data);
    showPageEditor.value = false;
    ui.success("页面已更新");
  } catch (error) {
    ui.error(getErrorText(error, "页面保存失败"));
  } finally {
    savingPage.value = false;
  }
}

async function loadTricks(pageNo = 1, append = false) {
  const params = {
    page: pageNo,
    order: "created_newest",
  };
  if (trickFilters.search.trim()) params.search = trickFilters.search.trim();
  if (trickFilters.termId) params.term = trickFilters.termId;
  const { data } = await api.get("/tricks/", { params });
  const parsed = unpackListPayload(data, tricks.value.length);
  tricks.value = append ? [...tricks.value, ...parsed.results] : parsed.results;
  trickMeta.count = parsed.count;
  trickMeta.next = parsed.next;
}

async function loadTrickTerms() {
  const all = [];
  let nextPath = "/trick-terms/?page_size=200";

  const normalizeNextPath = (nextValue) => {
    if (!nextValue) return "";
    try {
      const nextUrl = new URL(String(nextValue), window.location.origin);
      let path = nextUrl.pathname || "";
      if (path.startsWith("/api/")) {
        path = path.slice(4);
      }
      return `${path}${nextUrl.search}`;
    } catch {
      return "";
    }
  };

  try {
    while (nextPath) {
      const { data } = await api.get(nextPath);
      const parsed = unpackListPayload(data, all.length);
      all.push(...parsed.results);
      nextPath = normalizeNextPath(parsed.next);
    }
    trickTerms.value = all;
  } catch (error) {
    trickTerms.value = all;
    ui.error(getErrorText(error, "词条列表加载失败"));
  }
}

async function loadOwnPendingTermNames() {
  if (!auth.isAuthenticated) {
    ownPendingTermNames.value = [];
    return;
  }

  const all = [];
  let nextPath = "/trick-term-suggestions/?status=pending&page_size=200";

  const normalizeNextPath = (nextValue) => {
    if (!nextValue) return "";
    try {
      const nextUrl = new URL(String(nextValue), window.location.origin);
      let path = nextUrl.pathname || "";
      if (path.startsWith("/api/")) {
        path = path.slice(4);
      }
      return `${path}${nextUrl.search}`;
    } catch {
      return "";
    }
  };

  try {
    while (nextPath) {
      const { data } = await api.get(nextPath);
      const parsed = unpackListPayload(data, all.length);
      all.push(...parsed.results);
      nextPath = normalizeNextPath(parsed.next);
    }

    const uniqueNames = [];
    const seen = new Set();
    for (const item of all) {
      const name = String(item?.name || "").trim();
      if (!name) continue;
      const key = name.toLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);
      uniqueNames.push(name);
    }
    ownPendingTermNames.value = uniqueNames;
  } catch {
    ownPendingTermNames.value = [];
  }
}

function toggleTrickTerm(termId) {
  const value = Number(termId);
  if (!Number.isFinite(value)) return;
  if (trickForm.term_ids.includes(value)) {
    trickForm.term_ids = trickForm.term_ids.filter((id) => id !== value);
  } else {
    trickForm.term_ids = [...trickForm.term_ids, value];
  }
}

function removeSelectedTrickTerm(termId) {
  const value = Number(termId);
  if (!Number.isFinite(value)) return;
  trickForm.term_ids = trickForm.term_ids.filter((id) => id !== value);
}

function resetTrickFilters() {
  trickFilters.search = "";
  trickFilters.termId = "";
  loadTricks(1, false);
}

function addPendingTermDraft() {
  const name = String(trickForm.pending_term_draft || "").trim();
  if (!name) return;
  const key = name.toLowerCase();
  const selectedNames = new Set(
    selectedTrickTerms.value.map((x) => String(x.name || "").toLowerCase()),
  );
  const pendingNames = new Set(
    trickForm.pending_term_names.map((x) => String(x || "").toLowerCase()),
  );

  if (selectedNames.has(key) || pendingNames.has(key)) {
    ui.info("该词条已存在于已选或待审列表中");
    return;
  }
  if (name.length > 80) {
    ui.info("词条名称过长，请控制在 80 字以内");
    return;
  }

  trickForm.pending_term_names = [...trickForm.pending_term_names, name];
  trickForm.pending_term_draft = "";
}

function removePendingTerm(index) {
  if (index < 0 || index >= trickForm.pending_term_names.length) return;
  trickForm.pending_term_names = trickForm.pending_term_names.filter(
    (_, idx) => idx !== index,
  );
}

function toggleEditTrickTerm(termId) {
  const value = Number(termId);
  if (!Number.isFinite(value)) return;
  if (editForm.term_ids.includes(value)) {
    editForm.term_ids = editForm.term_ids.filter((id) => id !== value);
  } else {
    editForm.term_ids = [...editForm.term_ids, value];
  }
}

function removeEditSelectedTrickTerm(termId) {
  const value = Number(termId);
  if (!Number.isFinite(value)) return;
  editForm.term_ids = editForm.term_ids.filter((id) => id !== value);
}

function addEditPendingTermDraft() {
  const name = String(editForm.pending_term_draft || "").trim();
  if (!name) return;
  const key = name.toLowerCase();
  const selectedNames = new Set(
    editSelectedTrickTerms.value.map((x) => String(x.name || "").toLowerCase()),
  );
  const pendingNames = new Set(
    editForm.pending_term_names.map((x) => String(x || "").toLowerCase()),
  );

  if (selectedNames.has(key) || pendingNames.has(key)) {
    ui.info("该词条已存在于已选或待审列表中");
    return;
  }
  if (name.length > 80) {
    ui.info("词条名称过长，请控制在 80 字以内");
    return;
  }

  editForm.pending_term_names = [...editForm.pending_term_names, name];
  editForm.pending_term_draft = "";
}

function addEditPendingTermFromMine(name) {
  editForm.pending_term_draft = String(name || "").trim();
  addEditPendingTermDraft();
}

function removeEditPendingTerm(index) {
  if (index < 0 || index >= editForm.pending_term_names.length) return;
  editForm.pending_term_names = editForm.pending_term_names.filter(
    (_, idx) => idx !== index,
  );
}

function collectPendingTermsForSubmit() {
  const merged = [...trickForm.pending_term_names];
  const draft = String(trickForm.pending_term_draft || "").trim();
  if (!draft) return merged;

  const existing = new Set(
    merged.map((item) => String(item || "").toLowerCase()),
  );
  const selectedNames = new Set(
    selectedTrickTerms.value.map((x) => String(x.name || "").toLowerCase()),
  );
  const draftKey = draft.toLowerCase();
  if (
    !existing.has(draftKey) &&
    !selectedNames.has(draftKey) &&
    draft.length <= 80
  ) {
    merged.push(draft);
  }
  return merged;
}

function collectPendingTermsForEdit() {
  const merged = [...editForm.pending_term_names];
  const draft = String(editForm.pending_term_draft || "").trim();
  if (!draft) return merged;

  const existing = new Set(
    merged.map((item) => String(item || "").toLowerCase()),
  );
  const selectedNames = new Set(
    editSelectedTrickTerms.value.map((x) => String(x.name || "").toLowerCase()),
  );
  const draftKey = draft.toLowerCase();
  if (
    !existing.has(draftKey) &&
    !selectedNames.has(draftKey) &&
    draft.length <= 80
  ) {
    merged.push(draft);
  }
  return merged;
}

async function loadMoreTricks() {
  if (!trickMeta.next || trickMeta.loadingMore) return;
  trickMeta.loadingMore = true;
  try {
    await loadTricks(nextPageFromUrl(trickMeta.next), true);
  } finally {
    trickMeta.loadingMore = false;
  }
}

function startEditTrick(item) {
  if (editingTrickId.value === item.id) {
    editingTrickId.value = null;
    editForm.content_md = "";
    editForm.term_ids = [];
    editForm.pending_term_draft = "";
    editForm.pending_term_names = [];
    editTagEditorVisible.value = false;
    editTrickTermSearch.value = "";
    editEditorExpanded.value = false;
    return;
  }
  editingTrickId.value = item.id;
  editForm.content_md = item.content_md || "";
  editForm.term_ids = Array.isArray(item.terms)
    ? item.terms
        .map((term) => Number(term.id))
        .filter((id) => Number.isFinite(id))
    : [];
  editForm.pending_term_draft = "";
  editForm.pending_term_names = Array.isArray(item.pending_term_names)
    ? item.pending_term_names
    : [];
  editTagEditorVisible.value = false;
  editTrickTermSearch.value = "";
}

async function saveEditTrick(item) {
  if (!canEditTrick(item)) return;
  const content = editForm.content_md.trim();
  if (!content) {
    ui.info("内容不能为空");
    return;
  }
  if (savingEdit.value) return;

  savingEdit.value = true;
  try {
    const pendingTermNames = collectPendingTermsForEdit();
    await api.patch(`/tricks/${item.id}/`, {
      content_md: content,
      term_ids: editForm.term_ids,
      pending_term_names: pendingTermNames,
    });
    editingTrickId.value = null;
    editForm.content_md = "";
    editForm.term_ids = [];
    editForm.pending_term_draft = "";
    editForm.pending_term_names = [];
    editTagEditorVisible.value = false;
    editTrickTermSearch.value = "";
    editEditorExpanded.value = false;
    ui.success(auth.isManager ? "已更新 trick" : "已提交修改，等待审核");
    await loadTricks(1, false);
  } catch (error) {
    ui.error(getErrorText(error, "保存失败"));
  } finally {
    savingEdit.value = false;
  }
}

async function deleteTrick(item) {
  if (!canDeleteTrick(item)) return;
  if (!window.confirm("确认删除该 trick？")) return;
  try {
    await api.delete(`/tricks/${item.id}/`);
    ui.success("已删除");
    if (editingTrickId.value === item.id) {
      editingTrickId.value = null;
      editForm.content_md = "";
      editForm.term_ids = [];
      editForm.pending_term_draft = "";
      editForm.pending_term_names = [];
      editTagEditorVisible.value = false;
      editTrickTermSearch.value = "";
    }
    await loadTricks(1, false);
  } catch (error) {
    ui.error(getErrorText(error, "删除失败"));
  }
}

async function setTrickStatus(item, status) {
  if (!canModerateTrick(item)) return;
  try {
    await api.post(`/tricks/${item.id}/set-status/`, { status });
    ui.success(status === "approved" ? "已通过审核" : "已拒绝");
    await loadTricks(1, false);
  } catch (error) {
    ui.error(getErrorText(error, "审核操作失败"));
  }
}

async function submitTrick() {
  if (!auth.isAuthenticated) {
    ui.info("请先登录后再提交 trick");
    return;
  }
  if (submittingTrick.value) return;

  const content = trickForm.content_md.trim();
  if (!content) {
    ui.info("请填写 Markdown 内容");
    return;
  }

  submittingTrick.value = true;
  try {
    const pendingTermNames = collectPendingTermsForSubmit();
    const { data } = await api.post("/tricks/", {
      title: String(trickForm.title || "").trim(),
      content_md: content,
      term_ids: trickForm.term_ids,
      pending_term_names: pendingTermNames,
    });
    trickForm.title = "";
    trickForm.content_md = "";
    trickForm.term_ids = [];
    trickForm.pending_term_draft = "";
    trickForm.pending_term_names = [];
    if (data?.status === "pending") {
      ui.success("trick 提交成功，等待审核");
    } else {
      ui.success("trick 已发布");
    }
    await loadTricks(1, false);
    await loadTrickTerms();
  } catch (error) {
    ui.error(getErrorText(error, "trick 提交失败"));
  } finally {
    submittingTrick.value = false;
  }
}

watch(
  () => currentPageSlug.value,
  async () => {
    showPageEditor.value = false;
    if (isTricksPanel.value) {
      await loadTrickTerms();
      await loadOwnPendingTermNames();
      if (!tricks.value.length) {
        await loadTricks();
      }
      return;
    }
    await loadPage();
  },
  { immediate: true },
);

onMounted(async () => {
  if (isTricksPanel.value && !tricks.value.length) {
    await loadTrickTerms();
    await loadOwnPendingTermNames();
    await loadTricks();
  }

  const handleFocus = async () => {
    if (!isTricksPanel.value) return;
    await loadTrickTerms();
    await loadOwnPendingTermNames();
  };

  window.addEventListener("focus", handleFocus);
  onBeforeUnmount(() => {
    window.removeEventListener("focus", handleFocus);
  });
});
</script>

<style scoped>
.extra-layout {
  display: block;
}

.extra-main {
  border: 1px solid var(--hairline);
  border-radius: 16px;
  background: var(--surface);
  padding: 18px;
  box-shadow: var(--shadow-sm);
}

.extra-main--page {
  display: grid;
  gap: 14px;
}

.extra-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.extra-head-copy {
  min-width: 0;
}

.extra-head-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.page-editor {
  padding: 14px;
  display: grid;
  gap: 10px;
}

.page-editor-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.page-markdown {
  min-width: 0;
}

.page-markdown :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 10px;
}

.trick-submit {
  margin-top: 12px;
  padding: 14px;
  display: grid;
  gap: 8px;
}

.trick-submit-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.trick-submit-hint {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  color: var(--text-soft);
  background: color-mix(in srgb, var(--surface-strong) 90%, white 10%);
}

.term-picker {
  display: grid;
  gap: 8px;
  padding: 10px 12px;
  border: 1px solid var(--hairline);
  border-radius: 12px;
  background: color-mix(in srgb, var(--surface-strong) 92%, transparent);
}

.term-picker-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.term-options {
  max-height: 160px;
  overflow: auto;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
}

.term-option {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}

.term-selected {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.term-chip {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  color: var(--accent);
  background: color-mix(in srgb, var(--accent) 12%, var(--surface-strong));
}

.term-chip-removable {
  border: 1px solid color-mix(in srgb, var(--accent) 28%, transparent);
  cursor: pointer;
}

.term-chip-removable:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}

.term-chip-pending {
  border: 1px dashed color-mix(in srgb, var(--accent) 38%, transparent);
  cursor: pointer;
}

.pending-term-builder {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.pending-term-builder .input {
  flex: 1 1 280px;
}

.add-tag-btn {
  transition:
    transform 0.18s ease,
    box-shadow 0.18s ease;
}

.add-tag-btn:hover {
  transform: translateY(-1px) scale(1.02);
  box-shadow: var(--shadow-sm);
}

.pending-term-fade-enter-active,
.pending-term-fade-leave-active {
  transition: all 0.2s ease;
}

.pending-term-fade-enter-from,
.pending-term-fade-leave-to {
  opacity: 0;
  transform: translateY(6px) scale(0.98);
}

.trick-filters {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 220px auto;
  gap: 8px;
  margin-bottom: 10px;
}

.trick-list-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  color: var(--text-quiet);
  font-size: 12px;
  margin-bottom: 4px;
}

.trick-submit h4 {
  margin: 0;
  font-size: 20px;
}

.trick-list {
  margin-top: 12px;
  padding: 10px;
  display: grid;
  gap: 10px;
}

.trick-item {
  border: 1px solid color-mix(in srgb, var(--hairline) 84%, transparent);
  border-radius: 14px;
  padding: 12px 14px;
  background: color-mix(in srgb, var(--surface-strong) 94%, white 6%);
}

.trick-item:last-child {
  border-bottom: 1px solid color-mix(in srgb, var(--hairline) 84%, transparent);
}

.trick-item-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 4px;
}

.trick-item-title {
  margin: 0;
  font-size: 17px;
  line-height: 1.35;
  color: var(--text-strong);
}

.trick-status-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 12px;
  color: var(--accent);
  background: color-mix(in srgb, var(--accent) 10%, white 90%);
}

.trick-meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 8px;
}

.trick-action-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.trick-status {
  font-size: 12px;
  color: var(--muted);
  margin-right: 4px;
}

.trick-editor-shell {
  border: 1px solid color-mix(in srgb, var(--hairline) 88%, transparent);
  border-radius: 12px;
  padding: 8px;
  background: color-mix(in srgb, var(--surface-strong) 95%, white 5%);
  display: grid;
  gap: 8px;
}

.trick-editor-shell.is-expanded {
  position: fixed;
  z-index: 40;
  inset: 4vh 4vw;
  background: var(--surface);
  box-shadow: var(--shadow-lg);
  padding: 14px;
}

.editor-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.editor-toolbar-label {
  color: var(--muted);
  font-size: 12px;
}

.trick-editor-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 12px;
  min-width: 0;
}

.trick-editor-pane {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: 8px;
  min-width: 0;
}

.trick-editor-pane-head {
  color: var(--text-strong);
  font-size: 14px;
  font-weight: 700;
}

.trick-editor-textarea {
  min-height: 180px;
  height: 100%;
  resize: vertical;
  margin: 0;
}

.trick-editor-shell.is-expanded .trick-editor-textarea,
.trick-editor-shell.is-expanded .trick-editor-preview {
  min-height: calc(92vh - 170px);
}

.trick-editor-preview {
  border: 1px dashed color-mix(in srgb, var(--hairline) 88%, transparent);
  border-radius: 10px;
  padding: 10px;
  min-height: 180px;
  overflow: auto;
  background: color-mix(in srgb, var(--surface) 96%, white 4%);
  min-width: 0;
}

.trick-editor-shell.is-expanded .trick-editor-preview {
  background: var(--surface);
  border: 1px solid color-mix(in srgb, var(--hairline) 92%, transparent);
  box-shadow: inset 0 0 0 1px
    color-mix(in srgb, var(--surface-strong) 70%, transparent);
}

.trick-edit-zone {
  display: grid;
  gap: 8px;
}

.trick-markdown {
  max-width: 100%;
}

.trick-markdown :deep(img) {
  max-width: 100%;
  border-radius: 8px;
  height: auto;
}

.table-foot {
  margin-top: 6px;
}

@media (max-width: 720px) {
  .extra-main {
    padding: 14px;
  }

  .extra-head {
    flex-direction: column;
  }

  .extra-head-actions,
  .extra-head-actions .btn {
    width: 100%;
  }

  .page-editor-grid {
    grid-template-columns: 1fr;
  }

  .trick-editor-grid {
    grid-template-columns: 1fr;
  }

  .trick-submit,
  .trick-list {
    padding: 12px;
  }

  .term-options {
    grid-template-columns: 1fr;
  }

  .trick-filters {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 560px) {
  .trick-meta-row {
    display: grid;
    gap: 4px;
  }

  .trick-action-row {
    gap: 6px;
  }

  .trick-action-row .btn {
    flex: 1 1 calc(50% - 6px);
  }
}

.trick-submit,
.trick-list,
.page-editor {
  border: 1px solid color-mix(in srgb, var(--hairline) 88%, transparent);
  border-radius: 14px;
  background: color-mix(in srgb, var(--surface) 98%, white 2%);
  box-shadow: var(--shadow-sm);
  backdrop-filter: none;
  padding: 16px;
}

.trick-item {
  padding: 14px;
  border: 1px solid color-mix(in srgb, var(--hairline) 82%, transparent);
  border-radius: 14px;
  background: color-mix(in srgb, var(--surface-strong) 95%, white 5%);
}

.trick-item:last-child {
  border-bottom: 1px solid color-mix(in srgb, var(--hairline) 82%, transparent);
}

.page-markdown {
  padding-top: 12px;
}
</style>

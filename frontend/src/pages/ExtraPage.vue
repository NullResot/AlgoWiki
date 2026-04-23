<template>
  <section class="extra-layout">
    <article class="trick-space" v-if="isTricksPanel">
      <header class="trick-hero trick-hero--single-action">
        <button
          type="button"
          class="trick-hero-action"
          @click="toggleTrickComposer"
        >
          <span aria-hidden="true">＋</span>
          <span>提交 / 编辑 Trick</span>
        </button>
      </header>

      <section class="section-contributors-card">
        <ContributorsPanel
          :contributors="trickPageContributors"
          title="本页录入者"
          creator-badge-text="录入者"
          empty-text="当前页面暂无录入者"
        />
      </section>

      <Transition name="trick-form-reveal">
        <section v-if="showTrickForm" class="trick-submit card trick-submit-panel">
          <div class="trick-submit-head">
            <h4>提交 Trick</h4>
            <div class="trick-submit-head-actions">
              <span class="trick-submit-hint"
                >已选词条 {{ selectedTrickTerms.length }} 个 · 至少选择 1 个</span
              >
              <button
                type="button"
                class="btn btn-mini trick-collapse-btn"
                @click="showTrickForm = false"
              >
                收起
              </button>
            </div>
          </div>
          <input
            class="input"
            v-model="trickForm.title"
            placeholder="标题（必填）"
            required
            aria-label="Trick 标题"
          />
          <label class="trick-field-stack">
            <span class="trick-field-label">关键词（必填）</span>
            <input
              class="input"
              v-model="trickForm.keywords_text"
              placeholder="使用空格分隔，例如：lowbit 前缀和 位运算"
              required
            />
          </label>
          <div class="term-picker">
            <div class="term-picker-head">
              <strong>词条</strong>
              <span class="meta">固定分类，支持多选</span>
            </div>
            <input
              class="input"
              v-model="trickTermSearch"
              placeholder="搜索词条（如：数学 / 图论）"
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
            <p v-else class="meta">当前未选择词条，提交前至少选择 1 个。</p>
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
            class="btn btn-accent trick-submit-btn"
            :disabled="submittingTrick"
            @click="submitTrick"
          >
            {{ submittingTrick ? "提交中..." : "提交 trick" }}
          </button>
        </section>
      </Transition>

      <section class="trick-toolbar">
        <label class="trick-search-field">
          <span class="trick-search-icon" aria-hidden="true">⌕</span>
          <input
            class="trick-search-input"
            v-model="trickFilters.search"
            placeholder="搜索 trick 标题、关键词或内容"
            @keyup.enter="loadTricks(1, false)"
          />
        </label>
        <div class="trick-toolbar-actions">
          <select
            class="select trick-term-filter"
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
          <div class="trick-sort-switch" role="tablist" aria-label="排序方式">
            <button
              type="button"
              class="trick-sort-btn"
              :class="{ 'is-active': trickFilters.order === 'likes_desc' }"
              @click="setTrickOrder('likes_desc')"
            >
              点赞优先
            </button>
            <button
              type="button"
              class="trick-sort-btn"
              :class="{ 'is-active': trickFilters.order === 'created_newest' }"
              @click="setTrickOrder('created_newest')"
            >
              最新发布
            </button>
          </div>
          <button class="btn trick-reset-btn" @click="resetTrickFilters">
            重置
          </button>
        </div>
      </section>

      <div class="trick-list-meta">
        <span>共 {{ trickMeta.count }} 条</span>
        <span
          v-if="
            trickFilters.search ||
            trickFilters.termId ||
            trickFilters.order !== 'likes_desc'
          "
          >当前为筛选结果</span
        >
      </div>

      <section class="trick-grid">
        <article
          v-for="item in tricks"
          :key="item.id"
          class="trick-card"
          @click="openTrick(item)"
        >
          <div class="trick-card-head">
            <div class="trick-card-tags" v-if="item.terms?.length">
              <span
                v-for="term in visibleTrickTerms(item)"
                :key="`card-term-${item.id}-${term.id}`"
                :class="['trick-card-tag', trickTermToneClass(term)]"
              >
                {{ term.name }}
              </span>
              <span
                v-if="hiddenTrickTermCount(item) > 0"
                class="trick-card-tag trick-card-tag--muted"
              >
                +{{ hiddenTrickTermCount(item) }}
              </span>
            </div>
            <span class="trick-status-badge" v-if="showStatus(item)">{{
              statusText(item.status)
            }}</span>
          </div>

          <h5
            class="trick-card-title"
            v-html="renderInlineMarkdown(item.title || '未命名 trick')"
          ></h5>

          <div class="trick-card-keywords" v-if="item.keywords?.length">
            <span
              v-for="keyword in visibleTrickKeywords(item)"
              :key="`card-keyword-${item.id}-${keyword}`"
              class="trick-keyword-chip"
            >
              {{ keyword }}
            </span>
            <span
              v-if="hiddenTrickKeywordCount(item) > 0"
              class="trick-keyword-chip trick-keyword-chip--muted"
            >
              +{{ hiddenTrickKeywordCount(item) }}
            </span>
          </div>

          <footer class="trick-card-footer">
            <div class="trick-card-author">
              <span class="trick-card-author-icon" aria-hidden="true">◌</span>
              <span>{{ item.author?.username || "-" }}</span>
            </div>
            <button
              type="button"
              class="trick-card-like"
              :class="{ 'is-liked': Boolean(item.is_liked) }"
              :disabled="isTrickLikeBusy(item.id)"
              @click.stop="toggleTrickLike(item)"
            >
              <span aria-hidden="true">{{ item.is_liked ? "♥" : "♡" }}</span>
              <span>{{ item.like_count || 0 }}</span>
            </button>
          </footer>
        </article>
      </section>

      <p v-if="!tricks.length" class="meta trick-empty">暂无 trick 记录。</p>

      <div class="table-foot" v-if="trickMeta.next">
        <button
          class="btn"
          :disabled="trickMeta.loadingMore"
          @click="loadMoreTricks"
        >
          {{ trickMeta.loadingMore ? "加载中..." : "加载更多" }}
        </button>
      </div>

      <Teleport to="body">
        <div
          v-if="selectedTrick"
          class="trick-modal"
          @click.self="closeTrickModal"
        >
          <div class="trick-modal-backdrop" @click="closeTrickModal"></div>
          <article class="trick-modal-card">
            <header class="trick-modal-head">
              <div class="trick-modal-head-copy">
                <div class="trick-card-tags" v-if="selectedTrick.terms?.length">
                  <span
                    v-for="term in sortTermItems(selectedTrick.terms)"
                    :key="`modal-term-${selectedTrick.id}-${term.id}`"
                    :class="['trick-card-tag', trickTermToneClass(term)]"
                  >
                    {{ term.name }}
                  </span>
                </div>
                <span class="trick-status-badge" v-if="showStatus(selectedTrick)">{{
                  statusText(selectedTrick.status)
                }}</span>
              </div>
              <button
                type="button"
                class="trick-modal-close"
                @click="closeTrickModal"
              >
                ×
              </button>
            </header>

            <div class="trick-modal-body">
              <section class="trick-modal-overview">
                <h3
                  class="trick-modal-title"
                  v-html="renderInlineMarkdown(selectedTrick.title || '未命名 trick')"
                ></h3>

                <div class="trick-modal-meta">
                  <span>发布者：{{ selectedTrick.author?.username || "-" }}</span>
                  <span>发布时间：{{ formatTime(selectedTrick.created_at) }}</span>
                  <span>点赞：{{ selectedTrick.like_count || 0 }}</span>
                </div>

                <div
                  class="trick-card-keywords trick-modal-keywords"
                  v-if="selectedTrick.keywords?.length"
                >
                  <span
                    v-for="keyword in selectedTrick.keywords"
                    :key="`modal-keyword-${selectedTrick.id}-${keyword}`"
                    class="trick-keyword-chip"
                  >
                    {{ keyword }}
                  </span>
                </div>

                <div
                  class="trick-action-row trick-modal-manage"
                  v-if="
                    canEditTrick(selectedTrick) ||
                    canDeleteTrick(selectedTrick) ||
                    canModerateTrick(selectedTrick)
                  "
                >
                  <button
                    class="btn btn-mini"
                    v-if="canEditTrick(selectedTrick)"
                    @click.stop="startEditTrick(selectedTrick)"
                  >
                    {{
                      editingTrickId === selectedTrick.id ? "取消编辑" : "编辑"
                    }}
                  </button>
                  <button
                    class="btn btn-mini"
                    v-if="canDeleteTrick(selectedTrick)"
                    @click.stop="deleteTrick(selectedTrick)"
                  >
                    删除
                  </button>
                  <button
                    class="btn btn-mini"
                    v-if="canModerateTrick(selectedTrick)"
                    @click.stop="setTrickStatus(selectedTrick, 'approved')"
                  >
                    通过
                  </button>
                  <button
                    class="btn btn-mini"
                    v-if="canModerateTrick(selectedTrick)"
                    @click.stop="setTrickStatus(selectedTrick, 'rejected')"
                  >
                    拒绝
                  </button>
                </div>
              </section>

              <div
                v-if="editingTrickId === selectedTrick.id"
                class="trick-edit-zone trick-modal-editor"
              >
                <p
                  v-if="!auth.isManager && selectedTrick.status === 'approved'"
                  class="meta trick-edit-review-note"
                >
                  该 trick 当前已发布，保存修改后会重新进入待审核状态。
                </p>
                <label class="trick-field-stack">
                  <span class="trick-field-label">标题（必填）</span>
                  <input
                    class="input"
                    v-model="editForm.title"
                    placeholder="用简短语言概括 trick 的核心内容"
                    required
                  />
                </label>
                <label class="trick-field-stack">
                  <span class="trick-field-label">关键词（必填）</span>
                  <input
                    class="input"
                    v-model="editForm.keywords_text"
                    placeholder="使用空格分隔，例如：lowbit 前缀和 位运算"
                    required
                  />
                </label>
                <div class="trick-action-row">
                  <span class="trick-status"
                    >已选词条 {{ editSelectedTrickTerms.length }} 个 · 至少选择
                    1 个</span
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
                    <span class="meta">固定分类，支持多选</span>
                  </div>
                  <input
                    class="input"
                    v-model="editTrickTermSearch"
                    placeholder="搜索词条（如：数学 / 图论）"
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
                  <p v-else class="meta">当前未选择词条，保存前至少选择 1 个。</p>
                </div>
                <div
                  class="trick-editor-shell"
                  :class="{ 'is-expanded': editEditorExpanded }"
                >
                  <div class="editor-toolbar">
                    <span class="editor-toolbar-label"
                      >左侧编写，右侧实时预览</span
                    >
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
                  @click="saveEditTrick(selectedTrick)"
                >
                  {{ savingEdit ? "保存中..." : "保存修改" }}
                </button>
              </div>

              <section
                v-else
                class="markdown trick-detail-markdown"
                v-html="renderMarkdown(selectedTrick.content_md || '')"
              ></section>
            </div>

            <footer class="trick-modal-foot">
              <button
                type="button"
                class="trick-like-pill"
                :class="{ 'is-liked': Boolean(selectedTrick.is_liked) }"
                :disabled="isTrickLikeBusy(selectedTrick.id)"
                @click.stop="toggleTrickLike(selectedTrick)"
              >
                <span aria-hidden="true">{{
                  selectedTrick.is_liked ? "♥" : "♡"
                }}</span>
                <span
                  >{{ selectedTrick.is_liked ? "已点赞" : "点赞" }} ({{
                    selectedTrick.like_count || 0
                  }})</span
                >
              </button>
            </footer>
          </article>
        </div>
      </Teleport>

      <Teleport to="body">
        <div
          v-if="trickDeleteDialogVisible && trickDeleteDialogTarget"
          class="trick-delete-modal"
          @click.self="closeTrickDeleteDialog"
        >
          <div
            class="trick-delete-modal-backdrop"
            @click="closeTrickDeleteDialog"
          ></div>
          <article class="trick-delete-modal-card card">
            <header class="trick-delete-modal-head">
              <div class="trick-delete-modal-copy">
                <strong>删除 Trick</strong>
                <p class="meta">
                  不填写删除说明时，将直接删除；填写后会把说明发送到对应用户通知中。
                </p>
              </div>
              <button
                type="button"
                class="trick-modal-close"
                :disabled="deletingTrickId === trickDeleteDialogTarget.id"
                @click="closeTrickDeleteDialog"
              >
                ×
              </button>
            </header>
            <div class="trick-delete-modal-body">
              <p
                class="trick-delete-modal-title"
                v-html="
                  renderInlineMarkdown(
                    trickDeleteDialogTarget.title || '未命名 trick',
                  )
                "
              ></p>
              <PendingReviewNotePanel
                v-model="trickDeleteReviewNote"
                title="删除说明"
                hint="填写后会随删除通知发送给对应用户"
                empty-text="可选填写；留空时仅删除，不发送通知。"
                placeholder="可选填写删除说明；点击删除后会发送到对方的通知栏。"
              />
            </div>
            <footer class="trick-delete-modal-foot">
              <button
                type="button"
                class="btn"
                :disabled="deletingTrickId === trickDeleteDialogTarget.id"
                @click="closeTrickDeleteDialog"
              >
                取消
              </button>
              <button
                type="button"
                class="btn btn-danger"
                :disabled="deletingTrickId === trickDeleteDialogTarget.id"
                @click="confirmDeleteTrick"
              >
                {{
                  deletingTrickId === trickDeleteDialogTarget.id
                    ? "删除中..."
                    : "确认删除"
                }}
              </button>
            </footer>
          </article>
        </div>
      </Teleport>
    </article>

    <div v-else class="extra-docs-layout">
      <aside v-if="isDocsPanel" class="extra-doc-sidebar">
        <div class="extra-doc-sidebar-head">
          <span class="extra-doc-sidebar-kicker">文档</span>
          <strong>子页面</strong>
        </div>
        <button
          v-for="doc in resolvedDocPages"
          :key="doc.key"
          type="button"
          class="extra-doc-link"
          :class="{ 'extra-doc-link--active': doc.key === activeDocKey }"
          @click="selectDocPage(doc.key)"
        >
          {{ doc.label }}
        </button>
      </aside>

      <article class="extra-main extra-main--page">
        <header class="extra-head">
          <div class="extra-head-copy">
            <div class="section-title" v-html="renderedPageTitle"></div>
            <p
              v-if="renderedPageDescription"
              class="meta"
              v-html="renderedPageDescription"
            ></p>
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
    </div>
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
import { useRoute, useRouter } from "vue-router";

import ContributorsPanel from "../components/ContributorsPanel.vue";
import PendingReviewNotePanel from "../components/review/PendingReviewNotePanel.vue";
import { useDocumentNav } from "../composables/useDocumentNav";
import api from "../services/api";
import { renderInlineMarkdown, renderMarkdown } from "../services/markdown";
import { useAuthStore } from "../stores/auth";
import { useUiStore } from "../stores/ui";
import { aggregateCreatorContributors } from "../utils/contributors";
import { getTrickTermToneClass, sortFixedTrickTerms } from "../utils/trickTerms";

const props = defineProps({
  slug: {
    type: String,
    default: "",
  },
});

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const ui = useUiStore();
const { documentNav, loadDocumentNav } = useDocumentNav();

const fallbackDocPages = Object.freeze([
  {
    key: "about",
    slug: "about",
    label: "关于AlgoWiki",
    description: "开源、热爱、互助、友善",
    fallbackContent: "",
  },
  {
    key: "trick-guide",
    slug: "trick-guide",
    label: "trick 规范手册",
    description: "用于说明 trick 技巧条目的提交要求。",
    fallbackContent: "",
  },
  {
    key: "announcement-guide",
    slug: "announcement-guide",
    label: "公告手册",
    description: "用于说明赛事公告的编写范围与发布标准。",
    fallbackContent: "",
  },
  {
    key: "admin-guide",
    slug: "admin-guide",
    label: "管理员手册",
    description: "用于说明审核、管理与日常维护的基本原则。",
    fallbackContent: "",
  },
]);

const page = ref(null);
const pageExists = ref(false);
const tricks = ref([]);
const trickTerms = ref([]);
const submittingTrick = ref(false);
const savingEdit = ref(false);
const savingPage = ref(false);
const editingTrickId = ref(null);
const showPageEditor = ref(false);
const showTrickForm = ref(false);
const trickTermSearch = ref("");
const editTrickTermSearch = ref("");
const submitEditorExpanded = ref(false);
const editEditorExpanded = ref(false);
const editTagEditorVisible = ref(false);
const trickPageContributors = ref([]);
const selectedTrickId = ref(null);
const trickLikeBusyIds = ref([]);
const trickDeleteDialogVisible = ref(false);
const trickDeleteDialogTarget = ref(null);
const trickDeleteReviewNote = ref("");
const deletingTrickId = ref(null);

const trickForm = reactive({
  title: "",
  content_md: "",
  keywords_text: "",
  term_ids: [],
});

const editForm = reactive({
  title: "",
  content_md: "",
  keywords_text: "",
  term_ids: [],
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
  order: "likes_desc",
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
const isDocsPanel = computed(() => currentPageSlug.value === "about");
const resolvedDocPages = computed(() => {
  const navSource =
    documentNav.value.length > 0
      ? documentNav.value
      : fallbackDocPages.map((item, index) => ({
          id: item.key || `fallback-doc-${index}`,
          title: item.label,
          key: item.key,
          page_slug: item.slug,
          page_title: item.label,
          display_order: (index + 1) * 10,
          is_visible: true,
        }));

  return navSource
    .map((item) => {
      const fallback =
        fallbackDocPages.find(
          (entry) =>
            entry.key === String(item?.key || "").trim() ||
            entry.slug === String(item?.page_slug || item?.slug || "").trim(),
        ) || null;
      const key = String(item?.key || fallback?.key || "").trim().toLowerCase();
      const slug = String(
        item?.page_slug || item?.slug || fallback?.slug || key,
      )
        .trim()
        .toLowerCase();
      if (!key || !slug) return null;
      return {
        key,
        slug,
        label: String(
          item?.title || item?.page_title || fallback?.label || key,
        ).trim(),
        description: String(fallback?.description || "").trim(),
        fallbackContent: fallback?.fallbackContent || "",
      };
    })
    .filter((item) => item?.key && item?.slug);
});
const activeDocKey = computed(() => {
  if (!isDocsPanel.value) return currentPageSlug.value;
  const requestedKey = String(route.query.doc || "").trim().toLowerCase();
  const matched = resolvedDocPages.value.find((item) => item.key === requestedKey);
  return matched?.key || resolvedDocPages.value[0]?.key || "about";
});
const activeDoc = computed(
  () =>
    resolvedDocPages.value.find((item) => item.key === activeDocKey.value) ||
    resolvedDocPages.value[0] ||
    fallbackDocPages[0],
);
const pageRequestSlug = computed(() =>
  isDocsPanel.value ? activeDoc.value.slug : currentPageSlug.value,
);
const canEditPage = computed(() => !isTricksPanel.value && auth.isManager);
const fallbackPageTitle = computed(() =>
  isDocsPanel.value
    ? activeDoc.value.label
    : titleFromSlug(currentPageSlug.value),
);
const fallbackPageDescription = computed(() =>
  isDocsPanel.value
    ? activeDoc.value.description
    : currentPageSlug.value === "about"
      ? "项目介绍与路线图。"
      : "当前页面暂未填写简介。",
);
const fallbackPageContent = computed(() =>
  isDocsPanel.value ? activeDoc.value.fallbackContent : "",
);
const htmlContent = computed(() =>
  renderMarkdown(getEffectivePageContent(page.value)),
);
const renderedPageTitle = computed(() =>
  renderInlineMarkdown(
    pageExists.value ? page.value?.title || "" : fallbackPageTitle.value,
  ),
);
const renderedPageDescription = computed(() =>
  renderInlineMarkdown(
    pageExists.value
      ? page.value?.description || ""
      : fallbackPageDescription.value,
  ),
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
const selectedTrick = computed(
  () =>
    tricks.value.find((item) => Number(item?.id) === Number(selectedTrickId.value)) ||
    null,
);

function sortTermItems(items) {
  return sortFixedTrickTerms(items);
}

function getEffectivePageContent(item) {
  if (!pageExists.value) return fallbackPageContent.value;
  return item?.content_md || "";
}

function titleFromSlug(slug) {
  if (slug === "about") return "关于 AlgoWiki";
  if (slug === "trick-guide") return "trick 规范手册";
  if (slug === "announcement-guide") return "公告手册";
  if (slug === "admin-guide") return "管理员手册";
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

function visibleTrickTerms(item, limit = 2) {
  const terms = sortTermItems(item?.terms || []);
  return terms.slice(0, limit);
}

function hiddenTrickTermCount(item, limit = 2) {
  const total = Array.isArray(item?.terms) ? item.terms.length : 0;
  return Math.max(total - limit, 0);
}

function visibleTrickKeywords(item, limit = 4) {
  const keywords = Array.isArray(item?.keywords) ? item.keywords : [];
  return keywords.slice(0, limit);
}

function hiddenTrickKeywordCount(item, limit = 4) {
  const total = Array.isArray(item?.keywords) ? item.keywords.length : 0;
  return Math.max(total - limit, 0);
}

function trickTermToneClass(term) {
  return getTrickTermToneClass(term?.name);
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

function normalizeApiNextPath(nextValue) {
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
}

function resetEditTrickState() {
  editingTrickId.value = null;
  editForm.content_md = "";
  editForm.keywords_text = "";
  editForm.term_ids = [];
  editTagEditorVisible.value = false;
  editTrickTermSearch.value = "";
  editEditorExpanded.value = false;
}

function openTrick(item) {
  selectedTrickId.value = Number(item?.id) || null;
}

function closeTrickModal() {
  if (
    selectedTrickId.value &&
    editingTrickId.value &&
    Number(editingTrickId.value) === Number(selectedTrickId.value)
  ) {
    resetEditTrickState();
  }
  closeTrickDeleteDialog();
  selectedTrickId.value = null;
}

function openTrickDeleteDialog(item) {
  trickDeleteDialogTarget.value = item;
  trickDeleteReviewNote.value = "";
  trickDeleteDialogVisible.value = true;
}

function closeTrickDeleteDialog() {
  if (
    trickDeleteDialogTarget.value &&
    deletingTrickId.value &&
    Number(deletingTrickId.value) === Number(trickDeleteDialogTarget.value.id)
  ) {
    return;
  }
  trickDeleteDialogVisible.value = false;
  trickDeleteDialogTarget.value = null;
  trickDeleteReviewNote.value = "";
}

function toggleTrickComposer() {
  if (showTrickForm.value) {
    showTrickForm.value = false;
    return;
  }
  if (!auth.isAuthenticated) {
    ui.info("登录后可提交 trick");
    return;
  }
  showTrickForm.value = true;
}

function setTrickOrder(order) {
  const value = String(order || "").trim();
  if (!value || value === trickFilters.order) return;
  trickFilters.order = value;
  loadTricks(1, false);
}

function isTrickLikeBusy(trickId) {
  return trickLikeBusyIds.value.includes(Number(trickId));
}

function syncTrickRecord(record) {
  if (!record?.id) return;
  tricks.value = tricks.value.map((item) =>
    Number(item.id) === Number(record.id) ? { ...item, ...record } : item,
  );
}

async function toggleTrickLike(item) {
  const trickId = Number(item?.id);
  if (!Number.isFinite(trickId)) return;
  if (!auth.isAuthenticated) {
    ui.info("登录后可点赞 trick");
    return;
  }
  if (isTrickLikeBusy(trickId)) return;

  trickLikeBusyIds.value = [...trickLikeBusyIds.value, trickId];
  try {
    const action = item?.is_liked ? "unlike" : "like";
    const { data } = await api.post(`/tricks/${trickId}/${action}/`, {});
    syncTrickRecord(data);
  } catch (error) {
    ui.error(getErrorText(error, "点赞操作失败"));
  } finally {
    trickLikeBusyIds.value = trickLikeBusyIds.value.filter(
      (value) => value !== trickId,
    );
  }
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
  pageForm.description = item?.description || fallbackPageDescription.value;
  pageForm.content_md = getEffectivePageContent(item);
}

function selectDocPage(key) {
  if (!isDocsPanel.value) return;
  const targetKey = String(key || "").trim().toLowerCase();
  if (!resolvedDocPages.value.some((item) => item.key === targetKey)) return;
  const nextQuery = { ...route.query };
  if (targetKey === "about") {
    delete nextQuery.doc;
  } else {
    nextQuery.doc = targetKey;
  }
  router.replace({
    name: String(route.name || "extra"),
    params: route.params,
    query: nextQuery,
  });
}

async function loadPage() {
  if (isTricksPanel.value) return;
  page.value = null;
  pageExists.value = false;
  trickPageContributors.value = [];
  try {
    const { data } = await api.get(`/pages/${pageRequestSlug.value}/`);
    page.value = data;
    pageExists.value = true;
    applyPageToForm(data);
  } catch {
    page.value = null;
    applyPageToForm(null);
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
      ({ data } = await api.patch(`/pages/${pageRequestSlug.value}/`, payload));
    } else {
      ({ data } = await api.post("/pages/", {
        ...payload,
        slug: pageRequestSlug.value,
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

function buildTrickListParams(pageNo = 1) {
  const params = {
    page: pageNo,
    order: trickFilters.order || "likes_desc",
  };
  if (trickFilters.search.trim()) params.search = trickFilters.search.trim();
  if (trickFilters.termId) params.term = trickFilters.termId;
  return params;
}

function buildTrickContributorQuery() {
  return "/tricks/?page_size=200&order=created_newest";
}

async function loadTrickPageContributors() {
  const rows = [];
  let nextPath = buildTrickContributorQuery();

  try {
    while (nextPath) {
      const { data } = await api.get(nextPath);
      const parsed = unpackListPayload(data, rows.length);
      rows.push(...parsed.results);
      nextPath = normalizeApiNextPath(parsed.next);
    }
    trickPageContributors.value = aggregateCreatorContributors(rows, {
      userKey: "author",
    });
  } catch {
    trickPageContributors.value = [];
  }
}

async function loadTricks(pageNo = 1, append = false) {
  const params = buildTrickListParams(pageNo);
  const { data } = await api.get("/tricks/", { params });
  const parsed = unpackListPayload(data, tricks.value.length);
  tricks.value = append ? [...tricks.value, ...parsed.results] : parsed.results;
  trickMeta.count = parsed.count;
  trickMeta.next = parsed.next;
  if (
    selectedTrickId.value &&
    !tricks.value.some((item) => Number(item.id) === Number(selectedTrickId.value))
  ) {
    selectedTrickId.value = null;
  }
  if (!append && pageNo === 1) {
    await loadTrickPageContributors();
  }
}

async function loadTrickTerms() {
  const all = [];
  let nextPath = "/trick-terms/?page_size=200";

  try {
    while (nextPath) {
      const { data } = await api.get(nextPath);
      const parsed = unpackListPayload(data, all.length);
      all.push(...parsed.results);
      nextPath = normalizeApiNextPath(parsed.next);
    }
    trickTerms.value = sortTermItems(all);
  } catch (error) {
    trickTerms.value = sortTermItems(all);
    ui.error(getErrorText(error, "词条列表加载失败"));
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
  trickFilters.order = "likes_desc";
  loadTricks(1, false);
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
    resetEditTrickState();
    return;
  }
  editingTrickId.value = item.id;
  editForm.title = item.title || "";
  editForm.content_md = item.content_md || "";
  editForm.keywords_text = item.keywords_text || "";
  editForm.term_ids = Array.isArray(item.terms)
    ? item.terms
        .map((term) => Number(term.id))
        .filter((id) => Number.isFinite(id))
    : [];
  editTagEditorVisible.value = false;
  editTrickTermSearch.value = "";
}

async function saveEditTrick(item) {
  if (!canEditTrick(item)) return;
  const title = String(editForm.title || "").trim();
  const content = editForm.content_md.trim();
  const keywords = String(editForm.keywords_text || "").trim();
  if (!title) {
    ui.info("请填写标题");
    return;
  }
  if (!content) {
    ui.info("内容不能为空");
    return;
  }
  if (!keywords) {
    ui.info("请填写关键词");
    return;
  }
  if (!editForm.term_ids.length) {
    ui.info("请至少选择一个词条");
    return;
  }
  if (savingEdit.value) return;

  savingEdit.value = true;
  try {
    await api.patch(`/tricks/${item.id}/`, {
      title,
      content_md: content,
      keywords_text: keywords,
      term_ids: editForm.term_ids,
    });
    resetEditTrickState();
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
  if (auth.isManager) {
    openTrickDeleteDialog(item);
    return;
  }
  if (!window.confirm("确认删除该 trick？")) return;
  await performDeleteTrick(item);
}

async function confirmDeleteTrick() {
  if (!trickDeleteDialogTarget.value) return;
  await performDeleteTrick(trickDeleteDialogTarget.value, {
    review_note: trickDeleteReviewNote.value,
  });
}

async function performDeleteTrick(item, payload = {}) {
  try {
    deletingTrickId.value = item.id;
    const reviewNote = String(payload?.review_note || "").trim();
    await api.delete(`/tricks/${item.id}/`, {
      data: {
        review_note: reviewNote,
      },
    });
    ui.success(reviewNote ? "已删除并通知作者" : "已删除");
    deletingTrickId.value = null;
    if (editingTrickId.value === item.id) {
      resetEditTrickState();
    }
    if (selectedTrickId.value === item.id) {
      closeTrickModal();
    }
    closeTrickDeleteDialog();
    await loadTricks(1, false);
  } catch (error) {
    ui.error(getErrorText(error, "删除失败"));
  } finally {
    deletingTrickId.value = null;
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

  const title = String(trickForm.title || "").trim();
  const content = trickForm.content_md.trim();
  const keywords = String(trickForm.keywords_text || "").trim();
  if (!title) {
    ui.info("请填写标题");
    return;
  }
  if (!keywords) {
    ui.info("请填写关键词");
    return;
  }
  if (!content) {
    ui.info("请填写 Markdown 内容");
    return;
  }
  if (!trickForm.term_ids.length) {
    ui.info("请至少选择一个词条");
    return;
  }

  submittingTrick.value = true;
  try {
    const { data } = await api.post("/tricks/", {
      title,
      content_md: content,
      keywords_text: keywords,
      term_ids: trickForm.term_ids,
    });
    trickForm.title = "";
    trickForm.content_md = "";
    trickForm.keywords_text = "";
    trickForm.term_ids = [];
    if (data?.status === "pending") {
      ui.success("trick 提交成功，等待审核");
    } else {
      ui.success("trick 已发布");
    }
    showTrickForm.value = false;
    await loadTricks(1, false);
    await loadTrickTerms();
  } catch (error) {
    ui.error(getErrorText(error, "trick 提交失败"));
  } finally {
    submittingTrick.value = false;
  }
}

watch(
  () => [currentPageSlug.value, pageRequestSlug.value],
  async () => {
    showPageEditor.value = false;
    showTrickForm.value = false;
    selectedTrickId.value = null;
    resetEditTrickState();
    if (isTricksPanel.value) {
      await loadTrickTerms();
      await loadTricks(1, false);
      return;
    }
    if (isDocsPanel.value) {
      await loadDocumentNav();
    }
    await loadPage();
  },
  { immediate: true },
);

watch(
  () => Boolean(selectedTrickId.value || trickDeleteDialogVisible.value),
  (value) => {
    if (typeof document === "undefined") return;
    document.body.style.overflow = value ? "hidden" : "";
  },
);

watch(selectedTrick, (item) => {
  if (!item && selectedTrickId.value) {
    selectedTrickId.value = null;
  }
});

onMounted(async () => {
  const handleFocus = async () => {
    if (!isTricksPanel.value) return;
    await loadTrickTerms();
  };
  const handleKeydown = (event) => {
    if (event.key === "Escape" && trickDeleteDialogVisible.value) {
      closeTrickDeleteDialog();
      return;
    }
    if (event.key === "Escape" && selectedTrickId.value) {
      closeTrickModal();
    }
  };

  window.addEventListener("focus", handleFocus);
  window.addEventListener("keydown", handleKeydown);
  onBeforeUnmount(() => {
    window.removeEventListener("focus", handleFocus);
    window.removeEventListener("keydown", handleKeydown);
    document.body.style.overflow = "";
  });
});
</script>

<style scoped>
.extra-layout {
  display: block;
}

.extra-docs-layout {
  display: grid;
  grid-template-columns: minmax(220px, 260px) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.extra-doc-sidebar {
  position: sticky;
  top: 92px;
  display: grid;
  gap: 10px;
  padding: 14px;
  border: 1px solid var(--hairline);
  border-radius: 16px;
  background: color-mix(in srgb, var(--surface) 98%, white 2%);
  box-shadow: var(--shadow-sm);
}

.extra-doc-sidebar-head {
  display: grid;
  gap: 2px;
}

.extra-doc-sidebar-kicker {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-quiet);
}

.extra-doc-link {
  width: 100%;
  border: 1px solid color-mix(in srgb, var(--hairline) 86%, transparent);
  border-radius: 12px;
  background: color-mix(in srgb, var(--surface-strong) 92%, white 8%);
  padding: 10px 12px;
  text-align: left;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-soft);
  transition:
    border-color 0.18s ease,
    background-color 0.18s ease,
    color 0.18s ease,
    transform 0.18s ease;
}

.extra-doc-link:hover {
  transform: translateY(-1px);
  border-color: color-mix(in srgb, var(--accent) 18%, transparent);
  color: var(--text-strong);
}

.extra-doc-link--active {
  color: var(--accent);
  border-color: color-mix(in srgb, var(--accent) 28%, transparent);
  background: color-mix(in srgb, var(--accent) 12%, var(--surface-strong));
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

.trick-space {
  display: grid;
  gap: 16px;
}

.trick-hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
}

.trick-hero--single-action {
  justify-content: flex-end;
}

.trick-hero-copy {
  min-width: 0;
}

.trick-hero-meta {
  margin-top: 6px;
  max-width: 760px;
}

.trick-hero-action {
  border: none;
  border-radius: 999px;
  background: linear-gradient(135deg, #0b84ff, #0062cc);
  color: #fff;
  padding: 14px 22px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 700;
  box-shadow: 0 12px 28px rgba(11, 132, 255, 0.2);
  transition:
    transform 0.18s ease,
    box-shadow 0.18s ease,
    filter 0.18s ease;
}

.trick-hero-action:hover {
  transform: translateY(-1px);
  box-shadow: 0 16px 34px rgba(11, 132, 255, 0.24);
  filter: saturate(1.05);
}

.trick-submit-panel {
  margin-top: -2px;
}

.trick-toolbar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  padding: 10px 14px;
  border: 1px solid color-mix(in srgb, var(--hairline) 88%, transparent);
  border-radius: 24px;
  background: color-mix(in srgb, var(--surface) 98%, white 2%);
  box-shadow: var(--shadow-sm);
}

.trick-search-field {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 2px;
}

.trick-search-icon {
  flex: 0 0 auto;
  color: var(--text-quiet);
  font-size: 18px;
}

.trick-search-input {
  width: 100%;
  border: none;
  outline: none;
  background: transparent;
  font-size: 15px;
  color: var(--text-strong);
}

.trick-search-input::placeholder {
  color: var(--muted);
}

.trick-toolbar-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
}

.trick-term-filter {
  min-width: 136px;
}

.trick-sort-switch {
  display: inline-flex;
  align-items: center;
  padding: 4px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--surface-strong) 88%, white 12%);
  border: 1px solid color-mix(in srgb, var(--hairline) 86%, transparent);
}

.trick-sort-btn {
  border: none;
  background: transparent;
  color: var(--text-soft);
  padding: 8px 14px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 700;
  transition:
    background-color 0.18s ease,
    color 0.18s ease,
    box-shadow 0.18s ease;
}

.trick-sort-btn.is-active {
  background: #fff;
  color: var(--text-strong);
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.08);
}

.trick-reset-btn {
  border-radius: 14px;
}

.trick-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(248px, 1fr));
  gap: 16px;
}

.trick-card {
  min-height: 176px;
  border: 1px solid color-mix(in srgb, var(--hairline) 88%, transparent);
  border-radius: 24px;
  padding: 18px 20px;
  background:
    radial-gradient(circle at top right, rgba(11, 132, 255, 0.08), transparent 30%),
    color-mix(in srgb, var(--surface) 98%, white 2%);
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
  display: flex;
  flex-direction: column;
  gap: 14px;
  cursor: pointer;
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease,
    border-color 0.2s ease;
}

.trick-card:hover {
  transform: translateY(-2px);
  border-color: color-mix(in srgb, var(--accent) 20%, var(--hairline));
  box-shadow: 0 18px 38px rgba(15, 23, 42, 0.09);
}

.trick-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.trick-card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.trick-card-tag {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  color: #0b63d1;
  background: rgba(11, 132, 255, 0.12);
}

.trick-term-tone--default {
  color: #0b63d1;
  background: rgba(11, 132, 255, 0.12);
}

.trick-term-tone--math {
  color: #1d4ed8;
  background: rgba(59, 130, 246, 0.14);
}

.trick-term-tone--dp {
  color: #c2410c;
  background: rgba(251, 146, 60, 0.16);
}

.trick-term-tone--string {
  color: #b91c1c;
  background: rgba(248, 113, 113, 0.16);
}

.trick-term-tone--geometry {
  color: #4338ca;
  background: rgba(129, 140, 248, 0.18);
}

.trick-term-tone--ds {
  color: #047857;
  background: rgba(52, 211, 153, 0.16);
}

.trick-term-tone--graph {
  color: #7c3aed;
  background: rgba(196, 181, 253, 0.22);
}

.trick-term-tone--other {
  color: #475569;
  background: rgba(148, 163, 184, 0.18);
}

.trick-card-tag--muted {
  color: var(--text-soft);
  background: color-mix(in srgb, var(--surface-strong) 90%, white 10%);
}

.trick-card-title {
  margin: 0;
  font-size: clamp(18px, 1.8vw, 21px);
  line-height: 1.28;
  color: var(--text-strong);
  letter-spacing: -0.02em;
  word-break: break-word;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.trick-card-title :deep(p) {
  margin: 0;
}

.trick-card-keywords {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  min-height: 36px;
  align-content: flex-start;
}

.trick-keyword-chip {
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  padding: 5px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  color: #475569;
  background: rgba(148, 163, 184, 0.16);
  border: 1px solid rgba(148, 163, 184, 0.18);
  word-break: break-word;
}

.trick-keyword-chip--muted {
  color: var(--text-soft);
  background: color-mix(in srgb, var(--surface-strong) 90%, white 10%);
  border-color: color-mix(in srgb, var(--hairline) 82%, transparent);
}

.trick-card-footer {
  margin-top: auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: var(--text-soft);
  font-size: 14px;
}

.trick-card-author {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.trick-card-author span:last-child {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.trick-card-author-icon {
  color: var(--muted);
  font-size: 15px;
}

.trick-card-like {
  border: none;
  background: transparent;
  color: var(--text-soft);
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 700;
  padding: 0;
}

.trick-card-like.is-liked {
  color: #c03657;
}

.trick-card-like:disabled {
  opacity: 0.6;
  cursor: wait;
}

.trick-empty {
  padding: 8px 4px 0;
}

.trick-modal {
  position: fixed;
  inset: 0;
  z-index: 120;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.trick-modal-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(10, 18, 32, 0.26);
  backdrop-filter: blur(12px);
}

.trick-modal-card {
  position: relative;
  width: min(960px, 100%);
  max-height: min(88vh, 920px);
  overflow: hidden;
  border-radius: 32px;
  background: color-mix(in srgb, var(--surface) 98%, white 2%);
  box-shadow: 0 28px 90px rgba(15, 23, 42, 0.24);
  display: flex;
  flex-direction: column;
}

.trick-modal-head {
  position: sticky;
  top: 0;
  z-index: 2;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 22px 12px;
  background: color-mix(in srgb, var(--surface) 92%, white 8%);
  backdrop-filter: blur(16px);
  border-bottom: 1px solid color-mix(in srgb, var(--hairline) 88%, transparent);
}

.trick-modal-head-copy {
  min-width: 0;
  display: grid;
  gap: 8px;
}

.trick-modal-close {
  flex: 0 0 auto;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 999px;
  background: color-mix(in srgb, var(--surface-strong) 88%, white 12%);
  color: var(--text-soft);
  font-size: 24px;
  line-height: 1;
}

.trick-modal-body {
  flex: 1 1 auto;
  padding: 18px 26px 14px;
  display: grid;
  gap: 18px;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
}

.trick-modal-overview {
  display: grid;
  gap: 12px;
  min-width: 0;
}

.trick-modal-title {
  margin: 0;
  font-size: clamp(24px, 3vw, 34px);
  line-height: 1.18;
  letter-spacing: -0.03em;
  color: var(--text-strong);
}

.trick-modal-title :deep(p) {
  margin: 0;
}

.trick-modal-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  padding: 10px 12px;
  border-radius: 16px;
  background: color-mix(in srgb, var(--surface-soft) 76%, transparent);
  color: var(--text-soft);
  font-size: 14px;
}

.trick-modal-keywords {
  min-height: 0;
  gap: 6px;
  padding: 2px 0 0;
}

.trick-modal-manage {
  margin: 0;
  padding: 12px 14px;
  border-radius: 18px;
  border: 1px solid color-mix(in srgb, var(--hairline) 84%, transparent);
  background: color-mix(in srgb, var(--surface-soft) 84%, transparent);
  align-items: flex-start;
}

.trick-detail-markdown {
  min-width: 0;
}

.trick-detail-markdown :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 12px;
}

.trick-modal-editor {
  gap: 10px;
}

.trick-modal-foot {
  flex: 0 0 auto;
  display: flex;
  justify-content: center;
  padding: 12px 22px 16px;
  border-top: 1px solid color-mix(in srgb, var(--hairline) 82%, transparent);
  background: linear-gradient(
    180deg,
    color-mix(in srgb, var(--surface) 92%, white 8%),
    color-mix(in srgb, var(--surface) 98%, white 2%)
  );
  box-shadow: 0 -14px 30px rgba(15, 23, 42, 0.06);
}

.trick-delete-modal {
  position: fixed;
  inset: 0;
  z-index: 130;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.trick-delete-modal-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(10, 18, 32, 0.32);
  backdrop-filter: blur(12px);
}

.trick-delete-modal-card {
  position: relative;
  width: min(560px, 100%);
  display: grid;
  gap: 0;
  border-radius: 28px;
  background: color-mix(in srgb, var(--surface) 97%, white 3%);
  box-shadow: 0 28px 90px rgba(15, 23, 42, 0.28);
  overflow: hidden;
}

.trick-delete-modal-head,
.trick-delete-modal-foot {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 18px 22px;
}

.trick-delete-modal-head {
  border-bottom: 1px solid color-mix(in srgb, var(--hairline) 82%, transparent);
  background: color-mix(in srgb, var(--surface) 92%, white 8%);
}

.trick-delete-modal-copy {
  display: grid;
  gap: 6px;
}

.trick-delete-modal-copy strong {
  font-size: 18px;
  color: var(--text-strong);
}

.trick-delete-modal-copy .meta {
  margin: 0;
}

.trick-delete-modal-body {
  display: grid;
  gap: 14px;
  padding: 18px 22px;
}

.trick-delete-modal-title {
  margin: 0;
  padding: 12px 14px;
  border-radius: 16px;
  background: color-mix(in srgb, var(--surface-soft) 84%, transparent);
  color: var(--text-strong);
  font-size: 16px;
  line-height: 1.5;
}

.trick-delete-modal-title :deep(p) {
  margin: 0;
}

.trick-delete-modal-foot {
  justify-content: flex-end;
  border-top: 1px solid color-mix(in srgb, var(--hairline) 82%, transparent);
  background: color-mix(in srgb, var(--surface) 95%, white 5%);
}

.trick-like-pill {
  border: none;
  border-radius: 999px;
  padding: 12px 18px;
  background: color-mix(in srgb, var(--surface-strong) 88%, white 12%);
  color: var(--text-strong);
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 800;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
}

.trick-like-pill.is-liked {
  background: rgba(192, 54, 87, 0.12);
  color: #b62c4f;
}

.trick-like-pill:disabled {
  opacity: 0.65;
  cursor: wait;
}

.trick-submit {
  padding: 14px;
  display: grid;
  gap: 8px;
}

.trick-submit-toggle {
  margin-top: 12px;
}

.trick-share-btn {
  width: 100%;
  padding: 12px;
  font-size: 14px;
  font-weight: 600;
  border-style: dashed;
}

.trick-submit-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.trick-submit-head-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
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

.trick-field-stack {
  display: grid;
  gap: 6px;
}

.trick-field-label {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-strong);
}

.trick-collapse-btn {
  flex-shrink: 0;
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

.trick-form-reveal-enter-active,
.trick-form-reveal-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}

.trick-form-reveal-enter-from,
.trick-form-reveal-leave-to {
  opacity: 0;
  transform: translateY(-8px);
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

.section-contributors-card {
  margin-top: 12px;
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

.trick-edit-review-note {
  margin: 0;
}

.trick-form-reveal-enter-active,
.trick-form-reveal-leave-active {
  transition:
    opacity 0.25s ease,
    transform 0.25s ease;
}

.trick-form-reveal-enter-from,
.trick-form-reveal-leave-to {
  opacity: 0;
  transform: translateY(-8px);
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

  .extra-docs-layout {
    grid-template-columns: 1fr;
  }

  .extra-doc-sidebar {
    position: static;
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

  .trick-hero,
  .trick-toolbar {
    display: grid;
    grid-template-columns: 1fr;
  }

  .trick-hero {
    gap: 12px;
  }

  .trick-hero-action,
  .trick-toolbar-actions,
  .trick-toolbar-actions > * {
    width: 100%;
  }

  .trick-toolbar-actions {
    justify-content: stretch;
  }

  .trick-sort-switch {
    width: 100%;
    justify-content: stretch;
  }

  .trick-sort-btn {
    flex: 1 1 0;
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

  .trick-grid {
    grid-template-columns: 1fr;
  }

  .trick-modal {
    padding: 12px;
  }

  .trick-modal-card {
    width: 100%;
    max-height: 92vh;
    border-radius: 24px;
  }

  .trick-modal-head,
  .trick-modal-body,
  .trick-modal-foot {
    padding-left: 16px;
    padding-right: 16px;
  }

  .trick-delete-modal {
    padding: 12px;
  }

  .trick-delete-modal-head,
  .trick-delete-modal-body,
  .trick-delete-modal-foot {
    padding-left: 16px;
    padding-right: 16px;
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

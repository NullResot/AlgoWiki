<template>
  <section class="extra-layout">
    <article class="trick-space" v-if="isTricksPanel">
      <header class="trick-hero trick-hero--single-action">
        <button
          type="button"
          class="trick-hero-action"
          @click="toggleTrickComposer"
        >
          <span aria-hidden="true">{{ auth.isAuthenticated ? (showTrickForm ? "×" : "＋") : "→" }}</span>
          <span>{{ auth.isAuthenticated ? (showTrickForm ? "收起发布表单" : "提交 Trick") : "登录后提交 Trick" }}</span>
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

      <section
        v-if="auth.isAuthenticated && trickContributionSummary"
        class="trick-contribution-card card"
      >
        <div class="trick-contribution-head">
          <div>
            <p class="trick-contribution-kicker">我的 Trick 贡献值</p>
            <strong class="trick-contribution-score">{{
              trickContributionSummary.score ?? 0
            }}</strong>
          </div>
          <button
            type="button"
            class="btn btn-mini"
            :disabled="loadingTrickContribution"
            @click="toggleTrickContributionDetails"
          >
            {{
              showTrickContributionDetails ? "收起明细" : "查看贡献值明细"
            }}
          </button>
        </div>
        <div class="trick-contribution-meta">
          <span>
            点赞权限：
            {{
              trickContributionSummary.can_like
                ? "已开启"
                : `贡献值达到 ${trickContributionSummary.like_threshold} 后开启`
            }}
          </span>
          <span>
            点踩权限：
            {{
              trickContributionSummary.can_downvote
                ? "已开启"
                : `贡献值达到 ${trickContributionSummary.downvote_threshold} 后开启`
            }}
          </span>
          <span>
            删除审核阈值：{{ trickContributionSummary.delete_review_threshold }} 个点踩
          </span>
        </div>

        <Transition name="trick-form-reveal">
          <div
            v-if="showTrickContributionDetails"
            class="trick-contribution-detail"
          >
            <div
              v-for="item in trickContributionSummary.results || []"
              :key="`trick-contribution-${item.id}`"
              class="trick-contribution-row"
            >
              <div class="trick-contribution-row-main">
                <strong>{{ item.action_label || item.action_type }}</strong>
                <p class="meta">
                  {{ item.trick_title || "未关联 Trick" }} ·
                  {{ formatTime(item.created_at) }}
                </p>
              </div>
              <div class="trick-contribution-row-side">
                <span
                  class="trick-contribution-delta"
                  :class="{
                    'is-positive': Number(item.delta) > 0,
                    'is-negative': Number(item.delta) < 0,
                  }"
                >
                  {{ Number(item.delta) > 0 ? "+" : "" }}{{ item.delta }}
                </span>
                <span class="meta">变动后 {{ item.balance_after }}</span>
                <span v-if="item.is_rollback" class="trick-contribution-rollback"
                  >回滚 / 修正</span
                >
              </div>
            </div>
            <p
              v-if="!(trickContributionSummary.results || []).length"
              class="meta"
            >
              暂无贡献值明细。
            </p>
            <div
              v-if="trickContributionTotalPages > 1"
              class="trick-contribution-pagination"
            >
              <button
                type="button"
                class="btn btn-mini"
                :disabled="loadingTrickContribution || trickContributionPage <= 1"
                @click="loadTrickContributionPage(trickContributionPage - 1)"
              >
                上一页
              </button>
              <span class="meta">
                第 {{ trickContributionPage }} / {{ trickContributionTotalPages }} 页
              </span>
              <button
                type="button"
                class="btn btn-mini"
                :disabled="
                  loadingTrickContribution ||
                  trickContributionPage >= trickContributionTotalPages
                "
                @click="loadTrickContributionPage(trickContributionPage + 1)"
              >
                下一页
              </button>
            </div>
          </div>
        </Transition>
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
        <div class="trick-search-field">
          <span class="trick-search-icon" aria-hidden="true">⌕</span>
          <input
            class="trick-search-input"
            v-model="trickFilters.search"
            placeholder="搜索 trick 标题、关键词或内容"
            aria-label="搜索 trick"
            @keyup.enter="loadTricks(1)"
          />
          <button
            v-if="trickFilters.search"
            type="button"
            class="trick-search-clear"
            aria-label="清空搜索词"
            @click="clearTrickSearch"
          >
            ×
          </button>
          <button
            type="button"
            class="btn btn-mini trick-search-submit"
            :disabled="trickMeta.loading"
            @click="loadTricks(1)"
          >
            搜索
          </button>
        </div>
        <div class="trick-toolbar-actions">
          <select
            class="select trick-term-filter"
            v-model="trickFilters.termId"
            aria-label="按词条筛选"
            @change="loadTricks(1)"
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
              role="tab"
              :aria-selected="trickFilters.order === 'likes_desc'"
              class="trick-sort-btn"
              :class="{ 'is-active': trickFilters.order === 'likes_desc' }"
              @click="setTrickOrder('likes_desc')"
            >
              点赞优先
            </button>
            <button
              type="button"
              role="tab"
              :aria-selected="trickFilters.order === 'created_newest'"
              class="trick-sort-btn"
              :class="{ 'is-active': trickFilters.order === 'created_newest' }"
              @click="setTrickOrder('created_newest')"
            >
              最新发布
            </button>
          </div>
          <button
            v-if="auth.isAuthenticated"
            type="button"
            class="btn trick-master-filter-btn"
            :class="{ 'is-active': showMasteredTricks }"
            :disabled="trickMeta.loading"
            @click="toggleShowMasteredTricks"
          >
            {{ showMasteredTricks ? "隐藏已掌握的 trick" : "显示掌握的 trick" }}
          </button>
          <button
            v-if="hasActiveTrickFilters"
            type="button"
            class="btn trick-reset-btn"
            @click="resetTrickFilters"
          >
            重置
          </button>
        </div>
      </section>

      <div class="trick-list-meta tabular-nums">
        <span
          >共 {{ trickMeta.count }} 条 · 第 {{ trickMeta.page }} /
          {{ trickTotalPages }} 页 · 每页 {{ TRICK_PAGE_SIZE }} 条</span
        >
        <span
          v-if="hasActiveTrickFilters"
          >{{ showMasteredTricks ? "当前显示已掌握的 trick" : "当前为筛选结果" }}</span
        >
      </div>

      <SkeletonBlock
        v-if="trickMeta.loading && !tricks.length"
        :lines="5"
        :line-height="18"
        label="正在加载 Trick 列表"
      />

      <section
        v-else-if="tricks.length"
        class="trick-grid"
        :class="{ 'is-loading': trickMeta.loading }"
      >
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
              <span
                class="trick-status-badge trick-status-badge--warning"
                v-if="deleteVoteStatusText(item)"
                >{{ deleteVoteStatusText(item) }}</span
              >
              <span class="trick-status-badge" v-if="showStatus(item)">{{
                statusText(item.status)
              }}</span>
            </div>

          <h5 class="trick-card-heading">
            <button
              type="button"
              class="trick-card-title-btn"
              @click.stop="openTrick(item)"
            >
              <span
                class="trick-card-title"
                v-html="renderInlineMarkdown(item.title || '未命名 trick')"
              ></span>
            </button>
          </h5>

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

          <button
            type="button"
            class="trick-card-copy"
            :class="{ 'is-copied': copiedTrickId === item.id }"
            @click.stop="copyTrickMarkdown(item)"
          >
            {{ copiedTrickId === item.id ? "✓ 已复制 Markdown" : "一键复制 Markdown" }}
          </button>

          <footer class="trick-card-footer">
            <div class="trick-card-author">
              <span class="trick-card-author-icon" aria-hidden="true">◌</span>
              <span>{{ item.author?.username || "-" }}</span>
            </div>
            <button
              type="button"
              class="trick-card-like"
              :class="{
                'is-liked': Boolean(item.is_liked),
                'is-blocked': Boolean(getTrickLikeBlockedReason(item)),
              }"
              :title="getTrickLikeBlockedReason(item) || (item.is_liked ? '取消点赞' : '点赞')"
              :disabled="isTrickLikeBusy(item.id)"
              @click.stop="toggleTrickLike(item)"
            >
              <span aria-hidden="true">{{ item.is_liked ? "♥" : "♡" }}</span>
              <span class="tabular-nums">{{ item.like_count || 0 }}</span>
            </button>
          </footer>
        </article>
      </section>

      <EmptyErrorState
        v-if="!trickMeta.loading && !tricks.length"
        title="暂无符合条件的 Trick"
        :description="hasActiveTrickFilters ? '试试调整搜索词、筛选词条或重置过滤条件。' : '当前还没有已收录的 Trick，欢迎贡献第一条内容。'"
        :action-label="hasActiveTrickFilters ? '重置筛选' : ''"
        @action="resetTrickFilters"
      />

      <div
        class="trick-pagination"
        v-if="trickTotalPages > 1"
        aria-label="trick 分页"
      >
        <button
          type="button"
          class="trick-page-nav"
          :disabled="trickMeta.loading || trickMeta.page <= 1"
          @click="loadTrickPage(trickMeta.page - 1)"
        >
          上一页
        </button>
        <div class="trick-page-list" role="list" aria-label="页码">
          <template v-for="item in trickPageItems" :key="item.key">
            <span
              v-if="item.type === 'ellipsis'"
              class="trick-page-ellipsis"
              aria-hidden="true"
              >…</span
            >
            <button
              v-else
              type="button"
              class="trick-page-number"
              :class="{ 'is-active': item.page === trickMeta.page }"
              :disabled="trickMeta.loading || item.page === trickMeta.page"
              @click="loadTrickPage(item.page)"
            >
              {{ item.page }}
            </button>
          </template>
        </div>
        <button
          type="button"
          class="trick-page-nav"
          :disabled="trickMeta.loading || trickMeta.page >= trickTotalPages"
          @click="loadTrickPage(trickMeta.page + 1)"
        >
          下一页
        </button>
      </div>

      <Teleport to="body">
        <Transition name="aw-modal">
          <div
            v-if="selectedTrick"
            class="trick-modal"
            role="dialog"
            aria-modal="true"
            aria-label="Trick 详情"
            @click.self="requestCloseTrickModal"
          >
            <div class="trick-modal-backdrop" @click="requestCloseTrickModal"></div>
            <article ref="trickModalCardRef" class="trick-modal-card aw-modal-panel" tabindex="-1">
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
                  aria-label="关闭弹窗"
                  @click="requestCloseTrickModal"
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
                  <span v-if="deleteVoteStatusText(selectedTrick)">{{
                    deleteVoteStatusText(selectedTrick)
                  }}</span>
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
                    @click.stop="editingTrickId === selectedTrick.id ? cancelEditTrick() : startEditTrick(selectedTrick)"
                  >
                    {{
                      editingTrickId === selectedTrick.id ? "取消编辑" : "编辑"
                    }}
                  </button>
                  <button
                    class="btn btn-mini btn-danger"
                    v-if="canDeleteTrick(selectedTrick) && !canResolveDeleteReview(selectedTrick)"
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
                  <button
                    class="btn btn-mini"
                    v-if="canResolveDeleteReview(selectedTrick)"
                    @click.stop="resolveTrickDeleteReview(selectedTrick, 'keep')"
                  >
                    保留
                  </button>
                  <button
                    class="btn btn-mini btn-danger"
                    v-if="canResolveDeleteReview(selectedTrick)"
                    @click.stop="deleteTrick(selectedTrick)"
                  >
                    删除
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
                    {{ editTagEditorVisible ? "收起词条选择" : "编辑词条" }}
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
                ref="detailMarkdownRef"
                class="markdown trick-detail-markdown"
                v-html="renderMarkdown(selectedTrick.content_md || '')"
              ></section>
            </div>

            <footer class="trick-modal-foot">
              <button
                type="button"
                class="trick-like-pill trick-like-pill--copy"
                :class="{ 'is-copied': copiedTrickId === selectedTrick.id }"
                @click.stop="copyTrickMarkdown(selectedTrick)"
              >
                <span aria-hidden="true">{{ copiedTrickId === selectedTrick.id ? "✓" : "⎘" }}</span>
                <span>{{ copiedTrickId === selectedTrick.id ? "已复制 Markdown" : "复制 Markdown" }}</span>
              </button>
              <button
                v-if="
                  auth.isAuthenticated && selectedTrick.status === 'approved'
                "
                type="button"
                class="trick-like-pill trick-like-pill--mastery"
                :class="{ 'is-mastered': Boolean(selectedTrick.is_mastered) }"
                :disabled="
                  Boolean(selectedTrick.is_mastered) ||
                  isTrickMasteryBusy(selectedTrick.id)
                "
                @click.stop="masterTrick(selectedTrick)"
              >
                <span aria-hidden="true">✓</span>
                <span>{{ selectedTrick.is_mastered ? "已掌握" : "掌握" }}</span>
              </button>
              <button
                type="button"
                class="trick-like-pill"
                :class="{
                  'is-liked': Boolean(selectedTrick.is_liked),
                  'is-blocked': Boolean(getTrickLikeBlockedReason(selectedTrick)),
                }"
                :title="getTrickLikeBlockedReason(selectedTrick) || (selectedTrick.is_liked ? '取消点赞' : '点赞')"
                :disabled="isTrickLikeBusy(selectedTrick.id)"
                @click.stop="toggleTrickLike(selectedTrick)"
              >
                <span aria-hidden="true">{{
                  selectedTrick.is_liked ? "♥" : "♡"
                }}</span>
                <span class="tabular-nums"
                  >{{ selectedTrick.is_liked ? "已点赞" : "点赞" }} ({{
                    selectedTrick.like_count || 0
                  }})</span
                >
              </button>
              <button
                type="button"
                class="trick-like-pill trick-like-pill--downvote"
                :class="{
                  'is-downvoted': Boolean(selectedTrick.is_downvoted),
                  'is-blocked': Boolean(getTrickDownvoteBlockedReason(selectedTrick)),
                }"
                :title="getTrickDownvoteBlockedReason(selectedTrick) || (selectedTrick.is_downvoted ? '取消点踩' : '点踩')"
                :disabled="isTrickDownvoteBusy(selectedTrick.id)"
                @click.stop="toggleTrickDownvote(selectedTrick)"
              >
                <span aria-hidden="true">{{
                  selectedTrick.is_downvoted ? "⚑" : "⚐"
                }}</span>
                <span>{{
                  selectedTrick.is_downvoted ? "取消点踩" : "点踩"
                }}</span>
              </button>
            </footer>
            </article>
          </div>
        </Transition>
      </Teleport>

      <Teleport to="body">
        <Transition name="aw-modal">
          <div
            v-if="trickDeleteDialogVisible && trickDeleteDialogTarget"
            class="trick-delete-modal"
            role="dialog"
            aria-modal="true"
            aria-label="删除 Trick 确认"
            @click.self="closeTrickDeleteDialog"
          >
            <div
              class="trick-delete-modal-backdrop"
              @click="closeTrickDeleteDialog"
            ></div>
            <article class="trick-delete-modal-card aw-modal-panel card">
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
                  aria-label="关闭弹窗"
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
        </Transition>
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

        <Transition name="aw-collapse">
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
        </Transition>

        <FriendlyLinksPage v-if="isFriendlyLinksDoc" embedded />
        <SkeletonBlock
          v-else-if="pageLoading && !pageExists"
          :lines="6"
          :line-height="18"
          label="正在加载页面内容"
        />
        <EmptyErrorState
          v-else-if="pageError && !pageExists && !htmlContent"
          tone="error"
          title="页面内容加载失败"
          :description="pageError"
          action-label="重新加载"
          :busy="pageLoading"
          @action="loadPage"
        />
        <section
          v-else
          ref="pageMarkdownRef"
          class="markdown page-markdown"
          v-html="htmlContent"
        ></section>
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
import EmptyErrorState from "../components/EmptyErrorState.vue";
import PendingReviewNotePanel from "../components/review/PendingReviewNotePanel.vue";
import SkeletonBlock from "../components/SkeletonBlock.vue";
import { useDocumentNav } from "../composables/useDocumentNav";
import { useMarkdownCodeCopy } from "../composables/useMarkdownCodeCopy";
import { useOverlayA11y } from "../composables/useOverlayA11y";
import { useRequestControllers } from "../composables/useRequestControllers";
import FriendlyLinksPage from "./FriendlyLinksPage.vue";
import api, { isRequestCanceled } from "../services/api";
import { renderInlineMarkdown, renderMarkdown } from "../services/markdown";
import { useAuthStore } from "../stores/auth";
import { useUiStore } from "../stores/ui";
import { aggregateCreatorContributors } from "../utils/contributors";
import { extractApiError } from "../utils/format";
import { getTrickTermToneClass, sortFixedTrickTerms } from "../utils/trickTerms";

const TRICK_PAGE_SIZE = 20;

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
    key: "trick-regulation",
    slug: "trick-regulation",
    label: "Trick 页面贡献值与投票规则",
    description: "用于说明 Trick 页面的贡献值、投票权限与审核规则。",
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
  {
    key: "friendly-links",
    slug: "friendly-links",
    label: "友链",
    description: "AlgoWiki 相关站点与常用外部资源。",
    fallbackContent: "",
  },
]);

const requests = useRequestControllers();
const page = ref(null);
const pageExists = ref(false);
const pageLoading = ref(false);
const pageError = ref("");
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
const trickContributorsLoaded = ref(false);
const selectedTrickId = ref(null);
const trickModalCardRef = ref(null);
const copiedTrickId = ref(null);
const detailMarkdownRef = ref(null);
const pageMarkdownRef = ref(null);
const trickLikeBusyIds = ref([]);
const trickDownvoteBusyIds = ref([]);
const trickMasteryBusyIds = ref([]);
const showMasteredTricks = ref(false);
const trickContributionSummary = ref(null);
const trickContributionPage = ref(1);
const loadingTrickContribution = ref(false);
const showTrickContributionDetails = ref(false);
const trickDeleteDialogVisible = ref(false);
const trickDeleteDialogTarget = ref(null);
const trickDeleteReviewNote = ref("");
const deletingTrickId = ref(null);
let trickListRequestId = 0;
let trickSearchDebounceTimer = 0;
let trickCopyBadgeTimer = 0;
let suppressNextTrickSearchWatch = false;
const editOriginalSnapshot = ref("");

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
  page: 1,
  loading: false,
});

const trickFilters = reactive({
  search: "",
  termId: "",
  order: "likes_desc",
});

const hasActiveTrickFilters = computed(() =>
  Boolean(
    trickFilters.search.trim() ||
      trickFilters.termId ||
      trickFilters.order !== "likes_desc" ||
      showMasteredTricks.value,
  ),
);

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
const isFriendlyLinksDoc = computed(
  () => isDocsPanel.value && activeDoc.value.key === "friendly-links",
);
const canEditPage = computed(
  () => !isTricksPanel.value && !isFriendlyLinksDoc.value && auth.isManager,
);
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
const trickContributionTotalPages = computed(() => {
  const total = Number(trickContributionSummary.value?.total_pages || 1);
  return Number.isFinite(total) && total > 0 ? total : 1;
});
const trickTotalPages = computed(() => {
  const count = Number(trickMeta.count) || 0;
  return Math.max(1, Math.ceil(count / TRICK_PAGE_SIZE));
});
const trickPageItems = computed(() =>
  buildTrickPageItems(trickMeta.page || 1, trickTotalPages.value),
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
  if (slug === "trick-regulation") return "Trick 页面贡献值与投票规则";
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

function deleteVoteStatusText(item) {
  const value = String(item?.delete_vote_review_status || "").trim();
  if (value === "pending") return "删除审核中";
  if (value === "kept" && auth.isManager) return "已审核保留";
  return "";
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

async function copyTextToClipboard(text) {
  const normalized = String(text || "");
  if (!normalized) {
    throw new Error("empty");
  }

  if (
    typeof navigator !== "undefined" &&
    navigator.clipboard &&
    typeof navigator.clipboard.writeText === "function"
  ) {
    await navigator.clipboard.writeText(normalized);
    return;
  }

  if (typeof document === "undefined") {
    throw new Error("clipboard_unavailable");
  }

  const textarea = document.createElement("textarea");
  textarea.value = normalized;
  textarea.setAttribute("readonly", "readonly");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  textarea.style.pointerEvents = "none";
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();

  try {
    const succeeded = document.execCommand("copy");
    if (!succeeded) {
      throw new Error("copy_failed");
    }
  } finally {
    document.body.removeChild(textarea);
  }
}

async function copyTrickMarkdown(item) {
  const content = String(item?.content_md || "");
  if (!content.trim()) {
    ui.info("该 trick 暂无可复制的 Markdown 内容");
    return;
  }

  try {
    await copyTextToClipboard(content);
    copiedTrickId.value = item.id;
    if (trickCopyBadgeTimer) {
      window.clearTimeout(trickCopyBadgeTimer);
    }
    trickCopyBadgeTimer = window.setTimeout(() => {
      if (copiedTrickId.value === item.id) {
        copiedTrickId.value = null;
      }
      trickCopyBadgeTimer = 0;
    }, 1800);
    ui.success("已复制该 trick 的 Markdown 内容");
  } catch {
    ui.error("复制失败，请稍后重试");
  }
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

function canResolveDeleteReview(item) {
  return (
    auth.isManager &&
    String(item?.delete_vote_review_status || "").trim() === "pending"
  );
}

function getTrickLikeBlockedReason(item) {
  if (!auth.isAuthenticated) return "登录后可点赞 trick";
  if (item?.is_liked) return "";
  if (item?.author?.id === auth.user?.id) return "不能给自己的 trick 点赞";
  if (item?.status !== "approved") return "仅已通过的 trick 支持点赞";
  if (item?.delete_vote_review_status === "pending") {
    return "该 trick 正在删除审核中，暂不可新增点赞";
  }
  if (!trickContributionSummary.value?.can_like) {
    const threshold = trickContributionSummary.value?.like_threshold || 10;
    return `贡献值达到 ${threshold} 后才可点赞`;
  }
  return "";
}

function getTrickDownvoteBlockedReason(item) {
  if (!auth.isAuthenticated) return "登录后可点踩 trick";
  if (item?.is_downvoted) {
    if (item?.delete_vote_review_status && item?.delete_vote_review_status !== "none") {
      return "该 trick 当前已进入审核流程，暂不可取消点踩";
    }
    return "";
  }
  if (item?.author?.id === auth.user?.id) return "不能给自己的 trick 点踩";
  if (item?.status !== "approved") return "仅已通过的 trick 支持点踩";
  if (item?.delete_vote_review_status && item?.delete_vote_review_status !== "none") {
    return "该 trick 当前不可继续点踩";
  }
  if (!trickContributionSummary.value?.can_downvote) {
    const threshold = trickContributionSummary.value?.downvote_threshold || 10;
    return `贡献值达到 ${threshold} 后才可点踩`;
  }
  return "";
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

function buildTrickPageItems(currentPage, totalPages) {
  const pageCount = Math.max(1, Number(totalPages) || 1);
  const current = Math.min(Math.max(1, Number(currentPage) || 1), pageCount);
  if (pageCount <= 7) {
    return Array.from({ length: pageCount }, (_, index) => ({
      type: "page",
      key: `trick-page-${index + 1}`,
      page: index + 1,
    }));
  }

  const items = [{ type: "page", key: "trick-page-1", page: 1 }];
  const start = Math.max(2, current - 2);
  const end = Math.min(pageCount - 1, current + 2);
  if (start > 2) {
    items.push({ type: "ellipsis", key: `trick-page-ellipsis-left-${current}` });
  }
  for (let page = start; page <= end; page += 1) {
    items.push({
      type: "page",
      key: `trick-page-${page}`,
      page,
    });
  }
  if (end < pageCount - 1) {
    items.push({ type: "ellipsis", key: `trick-page-ellipsis-right-${current}` });
  }
  items.push({
    type: "page",
    key: `trick-page-${pageCount}`,
    page: pageCount,
  });
  return items;
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

function normalizePositiveId(value) {
  const id = Number.parseInt(String(value || "").trim(), 10);
  return Number.isInteger(id) && id > 0 ? id : null;
}

function isInvalidPageError(error) {
  const payload = error?.response?.data;
  const detail =
    typeof payload?.detail === "string"
      ? payload.detail
      : typeof payload === "string"
        ? payload
        : "";
  return /invalid page|无效页面/i.test(detail);
}

function currentEditSnapshot() {
  return JSON.stringify({
    title: String(editForm.title || ""),
    content_md: String(editForm.content_md || ""),
    keywords_text: String(editForm.keywords_text || ""),
    term_ids: [...editForm.term_ids].sort((a, b) => a - b),
  });
}

function isEditTrickDirty() {
  return Boolean(editingTrickId.value) && currentEditSnapshot() !== editOriginalSnapshot.value;
}

function resetEditTrickState() {
  editingTrickId.value = null;
  editForm.title = "";
  editForm.content_md = "";
  editForm.keywords_text = "";
  editForm.term_ids = [];
  editOriginalSnapshot.value = "";
  editTagEditorVisible.value = false;
  editTrickTermSearch.value = "";
  editEditorExpanded.value = false;
}

async function cancelEditTrick() {
  if (!editingTrickId.value) return true;
  if (isEditTrickDirty()) {
    const confirmed = await ui.confirm({
      title: "放弃未保存修改",
      message: "当前 Trick 编辑内容尚未保存，确定取消编辑吗？",
      confirmText: "放弃修改",
      cancelText: "继续编辑",
      tone: "danger",
    });
    if (!confirmed) return false;
  }
  resetEditTrickState();
  return true;
}

function openTrick(item) {
  selectedTrickId.value = Number(item?.id) || null;
  syncTrickQuery(selectedTrickId.value);
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
  if (!showMasteredTricks.value) {
    tricks.value = tricks.value.filter((item) => !item?.is_mastered);
  }
  selectedTrickId.value = null;
  syncTrickQuery(null);
}

async function requestCloseTrickModal() {
  if (
    selectedTrickId.value &&
    editingTrickId.value &&
    Number(editingTrickId.value) === Number(selectedTrickId.value) &&
    isEditTrickDirty()
  ) {
    const confirmed = await ui.confirm({
      title: "放弃未保存修改",
      message: "当前 Trick 仍有未保存修改，关闭弹窗会丢失本次编辑，确定关闭吗？",
      confirmText: "放弃并关闭",
      cancelText: "继续编辑",
      tone: "danger",
    });
    if (!confirmed) return;
  }
  closeTrickModal();
}

function handleSelectedTrickOverlayEscape() {
  if (editEditorExpanded.value) {
    editEditorExpanded.value = false;
    return;
  }
  requestCloseTrickModal();
}

function syncTrickQuery(trickId) {
  if (!isTricksPanel.value) return;
  const nextQuery = { ...route.query };
  const normalizedId = normalizePositiveId(trickId);
  if (normalizedId) nextQuery.trick = String(normalizedId);
  else delete nextQuery.trick;
  if (String(route.query.trick || "") === String(nextQuery.trick || "")) return;
  router.replace({ name: route.name || "competitions", params: route.params, query: nextQuery }).catch(() => {});
}

async function applyRouteTrickQuery(rawTrickId) {
  if (!isTricksPanel.value) return;
  const trickId = normalizePositiveId(rawTrickId);
  if (!trickId) return;
  if (tricks.value.some((item) => Number(item.id) === trickId)) {
    selectedTrickId.value = trickId;
    return;
  }
  try {
    const { data } = await api.get(`/tricks/${trickId}/`);
    if (!data?.id) return;
    tricks.value = [data, ...tricks.value.filter((item) => Number(item.id) !== Number(data.id))];
    selectedTrickId.value = Number(data.id);
  } catch (error) {
    selectedTrickId.value = null;
    ui.error(getErrorText(error, "目标 trick 暂时不可查看"));
  }
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
    router.push({ name: "auth", query: { redirect: route.fullPath } });
    return;
  }
  showTrickForm.value = true;
}

function clearTrickSearch() {
  suppressNextTrickSearchWatch = true;
  trickFilters.search = "";
  loadTricks(1);
}

function setTrickOrder(order) {
  const value = String(order || "").trim();
  if (!value || value === trickFilters.order) return;
  trickFilters.order = value;
  loadTricks(1);
}

function isTrickLikeBusy(trickId) {
  return trickLikeBusyIds.value.includes(Number(trickId));
}

function isTrickDownvoteBusy(trickId) {
  return trickDownvoteBusyIds.value.includes(Number(trickId));
}

function isTrickMasteryBusy(trickId) {
  return trickMasteryBusyIds.value.includes(Number(trickId));
}

function syncTrickRecord(record) {
  if (!record?.id) return;
  tricks.value = tricks.value.map((item) =>
    Number(item.id) === Number(record.id) ? { ...item, ...record } : item,
  );
}

async function masterTrick(item) {
  const trickId = Number(item?.id);
  if (!Number.isFinite(trickId)) return;
  if (!auth.isAuthenticated) {
    ui.info("登录后可标记已掌握");
    return;
  }
  if (item?.is_mastered || isTrickMasteryBusy(trickId)) return;

  trickMasteryBusyIds.value = [...trickMasteryBusyIds.value, trickId];
  try {
    const { data } = await api.post(`/tricks/${trickId}/master/`, {});
    syncTrickRecord(data);
    ui.success("已标记为掌握");
    if (!showMasteredTricks.value) {
      closeTrickModal();
      await loadTricks(1);
    }
  } catch (error) {
    ui.error(getErrorText(error, "标记掌握失败"));
  } finally {
    trickMasteryBusyIds.value = trickMasteryBusyIds.value.filter(
      (value) => value !== trickId,
    );
  }
}

async function toggleTrickLike(item) {
  const trickId = Number(item?.id);
  if (!Number.isFinite(trickId)) return;
  const blockedReason = getTrickLikeBlockedReason(item);
  if (blockedReason) {
    ui.info(blockedReason);
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

async function toggleTrickDownvote(item) {
  const trickId = Number(item?.id);
  if (!Number.isFinite(trickId)) return;
  const blockedReason = getTrickDownvoteBlockedReason(item);
  if (blockedReason) {
    ui.info(blockedReason);
    return;
  }
  if (isTrickDownvoteBusy(trickId)) return;
  trickDownvoteBusyIds.value = [...trickDownvoteBusyIds.value, trickId];
  try {
    const action = item?.is_downvoted ? "undownvote" : "downvote";
    const { data } = await api.post(`/tricks/${trickId}/${action}/`, {});
    syncTrickRecord(data);
    await loadTrickContribution(trickContributionPage.value);
    if (action === "undownvote") {
      ui.success("已取消点踩");
    } else if (data?.delete_vote_review_status === "pending") {
      ui.success("该 trick 已达到点踩阈值，现已进入删除审核。");
    } else {
      ui.success("已点踩该 trick");
    }
  } catch (error) {
    ui.error(getErrorText(error, item?.is_downvoted ? "取消点踩失败" : "点踩失败"));
  } finally {
    trickDownvoteBusyIds.value = trickDownvoteBusyIds.value.filter(
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
  const controller = requests.replace("extra-page");
  page.value = null;
  pageExists.value = false;
  pageError.value = "";
  pageLoading.value = true;
  trickPageContributors.value = [];
  try {
    const { data } = await api.get(`/pages/${pageRequestSlug.value}/`, {
      signal: controller.signal,
    });
    if (!requests.isCurrent("extra-page", controller)) return;
    page.value = data;
    pageExists.value = true;
    applyPageToForm(data);
  } catch (error) {
    if (isRequestCanceled(error) || !requests.isCurrent("extra-page", controller)) return;
    page.value = null;
    applyPageToForm(null);
    if (error?.response?.status !== 404) {
      pageError.value = extractApiError(error, "页面加载失败，请稍后重试");
    }
  } finally {
    if (requests.release("extra-page", controller)) {
      pageLoading.value = false;
    }
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
    page_size: TRICK_PAGE_SIZE,
    order: trickFilters.order || "likes_desc",
  };
  if (trickFilters.search.trim()) params.search = trickFilters.search.trim();
  if (trickFilters.termId) params.term = trickFilters.termId;
  if (showMasteredTricks.value && auth.isAuthenticated) {
    params.include_mastered = "1";
  }
  return params;
}

function buildTrickContributorQuery() {
  return "/tricks/?page_size=200&order=created_newest&include_mastered=1";
}

async function loadTrickPageContributors(force = false) {
  if (trickContributorsLoaded.value && !force) return;
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
    trickContributorsLoaded.value = true;
  } catch {
    trickPageContributors.value = [];
  }
}

async function loadTricks(pageNo = 1) {
  if (trickSearchDebounceTimer) {
    window.clearTimeout(trickSearchDebounceTimer);
    trickSearchDebounceTimer = 0;
  }
  const requestId = ++trickListRequestId;
  const targetPage = Math.max(
    1,
    Math.min(Math.floor(Number(pageNo) || 1), trickTotalPages.value || 1),
  );
  trickMeta.loading = true;
  try {
    const params = buildTrickListParams(targetPage);
    const { data } = await api.get("/tricks/", { params });
    if (requestId !== trickListRequestId) return;
    const parsed = unpackListPayload(data, tricks.value.length);
    tricks.value = parsed.results;
    trickMeta.count = parsed.count;
    trickMeta.page = targetPage;
    if (
      selectedTrickId.value &&
      !tricks.value.some((item) => Number(item.id) === Number(selectedTrickId.value))
    ) {
      selectedTrickId.value = null;
    }
    if (targetPage === 1 && !trickContributorsLoaded.value) {
      await loadTrickPageContributors();
    }
  } catch (error) {
    if (requestId !== trickListRequestId) return;
    if (targetPage > 1 && isInvalidPageError(error)) {
      ui.info("当前页已失效，已返回第一页");
      await loadTricks(1);
      return;
    }
    ui.error(getErrorText(error, "trick 列表加载失败"));
  } finally {
    if (requestId === trickListRequestId) {
      trickMeta.loading = false;
    }
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
  suppressNextTrickSearchWatch = true;
  trickFilters.search = "";
  trickFilters.termId = "";
  trickFilters.order = "likes_desc";
  showMasteredTricks.value = false;
  loadTricks(1);
}

function toggleShowMasteredTricks() {
  if (!auth.isAuthenticated) return;
  showMasteredTricks.value = !showMasteredTricks.value;
  closeTrickModal();
  loadTricks(1);
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

function loadTrickPage(pageNo) {
  const targetPage = Math.max(
    1,
    Math.min(Math.floor(Number(pageNo) || 1), trickTotalPages.value),
  );
  if (targetPage === trickMeta.page || trickMeta.loading) return;
  loadTricks(targetPage);
}

function startEditTrick(item) {
  if (editingTrickId.value === item.id) {
    cancelEditTrick();
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
  editOriginalSnapshot.value = currentEditSnapshot();
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
    trickContributorsLoaded.value = false;
    ui.success(auth.isManager ? "已更新 trick" : "已提交修改，等待审核");
    await loadTricks(1);
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
  const confirmed = await ui.confirm({
    title: "删除 Trick",
    message: `确认删除“${item?.title || "该 trick"}”吗？此操作不可撤销。`,
    confirmText: "确认删除",
    cancelText: "保留",
    tone: "danger",
  });
  if (!confirmed) return;
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
    trickContributorsLoaded.value = false;
    await loadTricks(1);
  } catch (error) {
    ui.error(getErrorText(error, "删除失败"));
  } finally {
    deletingTrickId.value = null;
  }
}

async function loadTrickContribution(pageNo = trickContributionPage.value) {
  if (!auth.isAuthenticated) {
    trickContributionSummary.value = null;
    trickContributionPage.value = 1;
    showTrickContributionDetails.value = false;
    return;
  }
  loadingTrickContribution.value = true;
  try {
    const page = Math.max(1, Number(pageNo) || 1);
    const { data } = await api.get("/me/trick-contribution/", {
      params: { page },
    });
    trickContributionPage.value = Number(data?.page || page);
    trickContributionSummary.value = data;
  } catch (error) {
    trickContributionSummary.value = null;
    trickContributionPage.value = 1;
    ui.error(getErrorText(error, "Trick 贡献值加载失败"));
  } finally {
    loadingTrickContribution.value = false;
  }
}

function loadTrickContributionPage(pageNo) {
  const nextPage = Math.max(
    1,
    Math.min(Number(pageNo) || 1, trickContributionTotalPages.value),
  );
  return loadTrickContribution(nextPage);
}

function toggleTrickContributionDetails() {
  if (!trickContributionSummary.value) return;
  showTrickContributionDetails.value = !showTrickContributionDetails.value;
  if (showTrickContributionDetails.value && trickContributionPage.value !== 1) {
    loadTrickContribution(1);
  }
}

async function setTrickStatus(item, status) {
  if (!canModerateTrick(item)) return;
  try {
    await api.post(`/tricks/${item.id}/set-status/`, { status });
    ui.success(status === "approved" ? "已通过审核" : "已拒绝");
    if (status === "approved") {
      trickContributorsLoaded.value = false;
      await loadTrickContribution();
    }
    await loadTricks(1);
  } catch (error) {
    ui.error(getErrorText(error, "审核操作失败"));
  }
}

async function resolveTrickDeleteReview(item, action) {
  if (!canResolveDeleteReview(item)) return;
  try {
    const { data } = await api.post(`/tricks/${item.id}/resolve-delete-review/`, {
      action,
      review_note: "",
    });
    syncTrickRecord(data);
    ui.success(action === "keep" ? "已保留该 trick" : "已完成删除审核");
    await loadTricks(1);
  } catch (error) {
    ui.error(getErrorText(error, "删除审核处理失败"));
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
    trickContributorsLoaded.value = false;
    await loadTricks(1);
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
    showMasteredTricks.value = false;
    showTrickContributionDetails.value = false;
    suppressNextTrickSearchWatch = true;
    trickFilters.search = "";
    trickFilters.termId = "";
    trickFilters.order = "likes_desc";
    trickContributorsLoaded.value = false;
    resetEditTrickState();
    if (isTricksPanel.value) {
      await Promise.all([
        loadTrickTerms(),
        loadTricks(1),
        loadTrickContribution(),
      ]);
      await applyRouteTrickQuery(route.query.trick);
      return;
    }
    trickContributionSummary.value = null;
    if (isDocsPanel.value) {
      await loadDocumentNav();
    }
    await loadPage();
  },
  { immediate: true },
);

watch(
  () => trickFilters.search,
  () => {
    if (!isTricksPanel.value) return;
    if (suppressNextTrickSearchWatch) {
      suppressNextTrickSearchWatch = false;
      return;
    }
    if (trickSearchDebounceTimer) {
      window.clearTimeout(trickSearchDebounceTimer);
    }
    trickSearchDebounceTimer = window.setTimeout(() => {
      trickSearchDebounceTimer = 0;
      loadTricks(1);
    }, 300);
  },
);

watch(
  () => route.query.trick,
  async (value) => {
    await applyRouteTrickQuery(value);
  },
);

useOverlayA11y(
  () => Boolean(selectedTrick.value),
  handleSelectedTrickOverlayEscape,
  { containerRef: trickModalCardRef },
);

useOverlayA11y(
  () => Boolean(trickDeleteDialogVisible.value && trickDeleteDialogTarget.value),
  closeTrickDeleteDialog,
);

useMarkdownCodeCopy(
  detailMarkdownRef,
  () => `${selectedTrick.value?.id || ""}:${selectedTrick.value?.content_md || ""}:${editingTrickId.value || ""}`,
);

useMarkdownCodeCopy(pageMarkdownRef, htmlContent);

watch(selectedTrick, (item) => {
  if (!item && selectedTrickId.value) {
    selectedTrickId.value = null;
  }
});

watch(
  () => auth.isAuthenticated,
  async (value) => {
    if (!isTricksPanel.value) return;
    if (!value) {
      trickContributionSummary.value = null;
      showTrickContributionDetails.value = false;
      showMasteredTricks.value = false;
      await loadTricks(1);
    } else {
      await Promise.all([loadTrickContribution(), loadTricks(1)]);
    }
    await applyRouteTrickQuery(route.query.trick);
  },
);

onMounted(async () => {
  const handleFocus = async () => {
    if (!isTricksPanel.value) return;
    await Promise.all([loadTrickTerms(), loadTrickContribution()]);
  };
  const handleKeydown = (event) => {
    if (
      event.key === "Escape" &&
      submitEditorExpanded.value &&
      !selectedTrickId.value &&
      !trickDeleteDialogVisible.value
    ) {
      submitEditorExpanded.value = false;
    }
  };

  window.addEventListener("focus", handleFocus);
  window.addEventListener("keydown", handleKeydown);
  onBeforeUnmount(() => {
    window.removeEventListener("focus", handleFocus);
    window.removeEventListener("keydown", handleKeydown);
    if (trickSearchDebounceTimer) {
      window.clearTimeout(trickSearchDebounceTimer);
      trickSearchDebounceTimer = 0;
    }
    if (trickCopyBadgeTimer) {
      window.clearTimeout(trickCopyBadgeTimer);
      trickCopyBadgeTimer = 0;
    }
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
  background: var(--accent-gradient);
  color: var(--accent-contrast, #fff);
  padding: 14px 22px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: var(--shadow-sm);
  transition:
    transform var(--dur-fast, 150ms) var(--ease-out, ease),
    box-shadow var(--dur-fast, 150ms) var(--ease-standard, ease),
    filter var(--dur-fast, 150ms) var(--ease-standard, ease);
}

.trick-hero-action:hover {
  transform: translateY(-1px);
  box-shadow: 0 16px 34px rgba(11, 132, 255, 0.24);
  filter: saturate(1.05);
}

.trick-contribution-card {
  display: grid;
  gap: 12px;
  padding: 18px 20px;
  border-radius: 24px;
}

.trick-contribution-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.trick-contribution-kicker {
  margin: 0 0 6px;
  color: var(--text-soft);
  font-size: 13px;
  font-weight: 700;
}

.trick-contribution-score {
  font-size: clamp(28px, 3vw, 40px);
  line-height: 1;
  color: var(--text-strong);
}

.trick-contribution-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 18px;
  color: var(--text-soft);
  font-size: 13px;
}

.trick-contribution-detail {
  display: grid;
  gap: 10px;
}

.trick-contribution-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 16px;
  border: 1px solid color-mix(in srgb, var(--hairline) 88%, transparent);
  background: color-mix(in srgb, var(--surface-soft) 90%, white 10%);
}

.trick-contribution-row-main {
  min-width: 0;
  display: grid;
  gap: 4px;
}

.trick-contribution-row-side {
  flex: 0 0 auto;
  display: grid;
  justify-items: end;
  gap: 4px;
}

.trick-contribution-delta {
  font-size: 18px;
  font-weight: 800;
  color: var(--text-strong);
}

.trick-contribution-delta.is-positive {
  color: color-mix(in srgb, var(--success, #16a34a) 84%, var(--text-strong));
}

.trick-contribution-delta.is-negative {
  color: color-mix(in srgb, var(--danger, #dc2626) 84%, var(--text-strong));
}

.trick-contribution-rollback {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 3px 8px;
  font-size: 11px;
  font-weight: 700;
  color: color-mix(in srgb, #d97706 82%, var(--text-strong));
  background: color-mix(in srgb, #f59e0b 16%, var(--surface-strong));
}

.trick-contribution-pagination {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  padding-top: 2px;
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
  background: var(--surface);
  box-shadow: var(--shadow-sm);
}

.trick-search-field {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 2px;
}

.trick-search-clear {
  flex: 0 0 auto;
  width: 24px;
  height: 24px;
  border: 0;
  border-radius: 999px;
  background: color-mix(in srgb, var(--text-quiet) 14%, transparent);
  color: var(--text-soft);
  font-size: 16px;
  line-height: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.trick-search-clear:hover {
  background: color-mix(in srgb, var(--text-quiet) 24%, transparent);
  color: var(--text-strong);
}

.trick-search-submit {
  flex: 0 0 auto;
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
  background: var(--surface-soft);
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
  cursor: pointer;
  transition:
    background-color var(--dur-fast, 150ms) var(--ease-standard, ease),
    color var(--dur-fast, 150ms) var(--ease-standard, ease),
    box-shadow var(--dur-fast, 150ms) var(--ease-standard, ease);
}

.trick-sort-btn.is-active {
  background: var(--surface-overlay);
  color: var(--text-strong);
  box-shadow: var(--shadow-sm);
}

.trick-reset-btn {
  border-radius: 14px;
}

.trick-master-filter-btn {
  border-radius: 14px;
}

.trick-master-filter-btn.is-active {
  color: color-mix(in srgb, var(--success, #10b981) 85%, var(--text-strong));
  border-color: color-mix(in srgb, var(--success, #10b981) 45%, var(--hairline));
  background: color-mix(in srgb, var(--success, #10b981) 14%, var(--surface-strong));
}

.trick-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 16px;
  justify-content: stretch;
  transition: opacity var(--dur-fast, 150ms) var(--ease-standard, ease);
}

.trick-grid.is-loading {
  opacity: 0.56;
  pointer-events: none;
}

.trick-card {
  min-height: 176px;
  border: 1px solid color-mix(in srgb, var(--hairline) 88%, transparent);
  border-radius: 24px;
  padding: 18px 20px;
  background:
    radial-gradient(circle at top right, color-mix(in srgb, var(--accent) 8%, transparent), transparent 34%),
    var(--surface);
  box-shadow: var(--shadow-sm);
  display: flex;
  flex-direction: column;
  gap: 14px;
  cursor: pointer;
  transition:
    transform var(--dur-fast, 150ms) var(--ease-out, ease),
    box-shadow var(--dur-fast, 150ms) var(--ease-standard, ease),
    border-color var(--dur-fast, 150ms) var(--ease-standard, ease);
}

@media (hover: hover) {
  .trick-card:hover {
    transform: translate3d(0, -2px, 0);
    border-color: color-mix(in srgb, var(--accent) 28%, var(--hairline));
    box-shadow: var(--shadow-md);
  }
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
  color: color-mix(in srgb, var(--accent) 85%, var(--text-strong));
  background: color-mix(in srgb, var(--accent) 12%, var(--surface-strong));
}

.trick-term-tone--default {
  color: color-mix(in srgb, #0b84ff 80%, var(--text-strong));
  background: color-mix(in srgb, #0b84ff 13%, var(--surface-strong));
}

.trick-term-tone--math {
  color: color-mix(in srgb, #3b82f6 82%, var(--text-strong));
  background: color-mix(in srgb, #3b82f6 14%, var(--surface-strong));
}

.trick-term-tone--dp {
  color: color-mix(in srgb, #ea580c 82%, var(--text-strong));
  background: color-mix(in srgb, #fb923c 16%, var(--surface-strong));
}

.trick-term-tone--string {
  color: color-mix(in srgb, #ef4444 82%, var(--text-strong));
  background: color-mix(in srgb, #f87171 15%, var(--surface-strong));
}

.trick-term-tone--geometry {
  color: color-mix(in srgb, #6366f1 82%, var(--text-strong));
  background: color-mix(in srgb, #818cf8 16%, var(--surface-strong));
}

.trick-term-tone--ds {
  color: color-mix(in srgb, #10b981 82%, var(--text-strong));
  background: color-mix(in srgb, #34d399 15%, var(--surface-strong));
}

.trick-term-tone--graph {
  color: color-mix(in srgb, #8b5cf6 82%, var(--text-strong));
  background: color-mix(in srgb, #c4b5fd 18%, var(--surface-strong));
}

.trick-term-tone--other {
  color: var(--text-soft);
  background: var(--surface-soft);
}

.trick-card-tag--muted {
  color: var(--text-soft);
  background: var(--surface-soft);
}

.trick-status-badge--warning {
  color: color-mix(in srgb, #d97706 82%, var(--text-strong));
  background: color-mix(in srgb, #fbbf24 18%, var(--surface-strong));
}

.trick-card-heading {
  margin: 0;
}

.trick-card-title-btn {
  appearance: none;
  border: 0;
  padding: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  width: 100%;
  display: block;
  cursor: pointer;
  border-radius: 8px;
}

.trick-card-title-btn:focus-visible {
  outline: 2px solid color-mix(in srgb, var(--accent) 82%, var(--text-strong));
  outline-offset: 3px;
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

.trick-card-copy {
  align-self: flex-start;
  border: 1px solid color-mix(in srgb, var(--hairline) 84%, transparent);
  border-radius: 999px;
  padding: 8px 12px;
  background: var(--surface-soft);
  color: var(--text-strong);
  font-size: 13px;
  font-weight: 700;
  line-height: 1;
  cursor: pointer;
  transition:
    background-color var(--dur-fast, 150ms) var(--ease-standard, ease),
    border-color var(--dur-fast, 150ms) var(--ease-standard, ease),
    color var(--dur-fast, 150ms) var(--ease-standard, ease),
    transform var(--dur-press, 90ms) var(--ease-out, ease);
}

.trick-card-copy:hover {
  background: var(--surface-strong);
  border-color: color-mix(in srgb, var(--accent) 28%, var(--hairline));
}

.trick-card-copy:active {
  transform: scale(0.96);
}

.trick-card-copy.is-copied {
  border-color: color-mix(in srgb, var(--success, #10b981) 45%, var(--hairline));
  background: color-mix(in srgb, var(--success, #10b981) 14%, var(--surface-strong));
  color: color-mix(in srgb, var(--success, #10b981) 85%, var(--text-strong));
}

.trick-keyword-chip {
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  padding: 5px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-soft);
  background: var(--surface-soft);
  border: 1px solid var(--hairline);
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
  padding: 4px 6px;
  border-radius: 999px;
  cursor: pointer;
  transition:
    background-color var(--dur-fast, 150ms) var(--ease-standard, ease),
    color var(--dur-fast, 150ms) var(--ease-standard, ease),
    transform var(--dur-press, 90ms) var(--ease-out, ease);
}

.trick-card-like:hover:not(:disabled) {
  background: color-mix(in srgb, var(--accent) 10%, transparent);
  color: var(--text-strong);
}

.trick-card-like:active:not(:disabled) {
  transform: scale(0.94);
}

.trick-card-like.is-liked {
  color: #e11d48;
}

.trick-card-like.is-blocked {
  opacity: 0.48;
  cursor: not-allowed;
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
  z-index: var(--z-modal, 1200);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.trick-modal-backdrop {
  position: absolute;
  inset: 0;
  background: color-mix(in srgb, #020617 48%, transparent);
  backdrop-filter: blur(10px);
}

.trick-modal-card {
  position: relative;
  width: min(960px, 100%);
  max-height: min(88vh, 920px);
  overflow: hidden;
  border-radius: 32px;
  border: 1px solid var(--panel-border-strong, var(--hairline));
  background: var(--surface-overlay, var(--surface));
  box-shadow: var(--shadow-md);
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
  background: var(--surface-overlay, var(--surface));
  backdrop-filter: blur(14px);
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
  border: 1px solid var(--hairline);
  border-radius: 999px;
  background: var(--surface-soft);
  color: var(--text-soft);
  font-size: 24px;
  line-height: 1;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition:
    background-color var(--dur-fast, 150ms) var(--ease-standard, ease),
    color var(--dur-fast, 150ms) var(--ease-standard, ease),
    transform var(--dur-press, 90ms) var(--ease-out, ease);
}

.trick-modal-close:hover:not(:disabled) {
  background: var(--surface-strong);
  color: var(--text-strong);
}

.trick-modal-close:active:not(:disabled) {
  transform: scale(0.92);
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
  flex-wrap: wrap;
  gap: 10px;
  padding: 12px 22px 16px;
  border-top: 1px solid color-mix(in srgb, var(--hairline) 82%, transparent);
  background: var(--surface-overlay, var(--surface));
  box-shadow: 0 -10px 24px rgba(15, 23, 42, 0.06);
}

.trick-like-pill--mastery {
  color: color-mix(in srgb, var(--success, #10b981) 84%, var(--text-strong));
  border-color: color-mix(in srgb, var(--success, #10b981) 38%, var(--hairline));
  background: color-mix(in srgb, var(--success, #10b981) 14%, var(--surface-strong));
}

.trick-like-pill--mastery.is-mastered {
  color: color-mix(in srgb, var(--success, #10b981) 90%, var(--text-strong));
  background: color-mix(in srgb, var(--success, #10b981) 22%, var(--surface-strong));
}

.trick-like-pill--copy.is-copied {
  border-color: color-mix(in srgb, var(--success, #10b981) 45%, var(--hairline));
  background: color-mix(in srgb, var(--success, #10b981) 14%, var(--surface-strong));
  color: color-mix(in srgb, var(--success, #10b981) 85%, var(--text-strong));
}

.trick-delete-modal {
  position: fixed;
  inset: 0;
  z-index: calc(var(--z-modal, 1200) + 20);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.trick-delete-modal-backdrop {
  position: absolute;
  inset: 0;
  background: color-mix(in srgb, #020617 52%, transparent);
  backdrop-filter: blur(10px);
}

.trick-delete-modal-card {
  position: relative;
  width: min(560px, 100%);
  display: grid;
  gap: 0;
  border-radius: 28px;
  border: 1px solid var(--panel-border-strong, var(--hairline));
  background: var(--surface-overlay, var(--surface));
  box-shadow: var(--shadow-md);
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
  background: var(--surface-overlay, var(--surface));
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
  background: var(--surface-overlay, var(--surface));
}

.trick-like-pill {
  border: 1px solid var(--hairline);
  border-radius: 999px;
  padding: 12px 18px;
  background: var(--surface-strong);
  color: var(--text-strong);
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 800;
  cursor: pointer;
  box-shadow: var(--shadow-sm);
  transition:
    background-color var(--dur-fast, 150ms) var(--ease-standard, ease),
    border-color var(--dur-fast, 150ms) var(--ease-standard, ease),
    transform var(--dur-press, 90ms) var(--ease-out, ease);
}

.trick-like-pill:active:not(:disabled) {
  transform: scale(0.96);
}

.trick-like-pill.is-blocked {
  opacity: 0.52;
  cursor: not-allowed;
}

.trick-like-pill--downvote {
  background: color-mix(in srgb, var(--danger, #dc2626) 12%, var(--surface-strong));
  border-color: color-mix(in srgb, var(--danger, #dc2626) 30%, var(--hairline));
  color: color-mix(in srgb, var(--danger, #dc2626) 84%, var(--text-strong));
}

.trick-like-pill--downvote.is-downvoted {
  background: color-mix(in srgb, var(--danger, #dc2626) 24%, var(--surface-strong));
  color: color-mix(in srgb, var(--danger, #dc2626) 92%, var(--text-strong));
}

.trick-like-pill.is-liked {
  background: color-mix(in srgb, #e11d48 15%, var(--surface-strong));
  border-color: color-mix(in srgb, #e11d48 35%, var(--hairline));
  color: color-mix(in srgb, #e11d48 84%, var(--text-strong));
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
  flex-wrap: wrap;
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
  background: color-mix(in srgb, var(--accent) 14%, var(--surface-strong));
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

.trick-pagination {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 6px;
}

.trick-page-list {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.trick-page-nav,
.trick-page-number {
  min-width: 40px;
  height: 36px;
  padding: 0 12px;
  border-radius: 12px;
  border: 1px solid color-mix(in srgb, var(--hairline) 90%, transparent);
  background: color-mix(in srgb, var(--surface) 98%, white 2%);
  color: var(--text-strong);
  font-size: 13px;
  font-weight: 700;
  transition:
    transform 0.15s ease,
    border-color 0.15s ease,
    background 0.15s ease,
    box-shadow 0.15s ease;
}

.trick-page-nav:hover:not(:disabled),
.trick-page-number:hover:not(:disabled) {
  border-color: color-mix(in srgb, var(--accent) 28%, var(--hairline));
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.08);
  transform: translateY(-1px);
}

.trick-page-nav:disabled,
.trick-page-number:disabled {
  cursor: not-allowed;
  opacity: 0.55;
  box-shadow: none;
}

.trick-page-number.is-active {
  background: color-mix(in srgb, var(--accent) 14%, var(--surface-strong));
  border-color: color-mix(in srgb, var(--accent) 34%, var(--hairline));
  color: var(--accent);
}

.trick-page-ellipsis {
  min-width: 24px;
  text-align: center;
  color: var(--muted);
  font-weight: 700;
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

  .trick-contribution-head,
  .trick-contribution-row {
    flex-direction: column;
  }

  .trick-contribution-row-side {
    justify-items: start;
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

@media (min-width: 1181px) and (max-width: 1440px) {
  .trick-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}

@media (min-width: 861px) and (max-width: 1180px) {
  .trick-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (min-width: 721px) and (max-width: 860px) {
  .trick-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
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

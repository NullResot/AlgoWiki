<template>
  <section class="review-layout">
    <header class="review-card review-shell-head">
      <div>
        <p class="review-kicker">{{ currentSectionConfig.label }}</p>
        <h1>审核台</h1>
        <p class="meta">{{ currentSectionConfig.description }}</p>
      </div>
      <button class="btn" type="button" @click="reloadCurrentSection">
        刷新当前分区
      </button>
    </header>

    <nav class="review-tabs" aria-label="审核分区">
      <RouterLink
        v-for="item in reviewSections"
        :key="item.key"
        :to="buildReviewRoute(item.key)"
        class="review-tab"
        :class="{ 'review-tab--active': item.key === currentSection }"
      >
        <div class="review-tab-head">
          <strong>{{ item.label }}</strong>
          <span class="review-tab-count">{{
            formatCount(counts[item.key])
          }}</span>
        </div>
        <span>{{ item.description }}</span>
      </RouterLink>
    </nav>

    <section class="review-card review-status-card">
      <div>
        <p class="review-kicker">审核记录</p>
        <p class="meta">切换查看当前分区的待审核、已通过和已驳回记录。</p>
      </div>
      <div class="review-status-tabs">
        <button
          v-for="statusItem in reviewStatusOptions"
          :key="statusItem.key"
          class="review-status-tab"
          :class="{
            'review-status-tab--active': currentReviewStatus === statusItem.key,
          }"
          type="button"
          @click="setReviewStatus(currentSection, statusItem.key)"
        >
          <span>{{ statusItem.label }}</span>
          <strong>{{ formatStatusCount(currentSection, statusItem.key) }}</strong>
        </button>
      </div>
    </section>

    <article v-if="currentSection === 'revisions'" class="review-card full">
      <h2>内容修订审核</h2>
      <p class="meta">{{ formatSectionStatusLine('revisions') }}</p>
      <div class="toolbar">
        <label v-if="isPendingMode" class="check-line"
          ><input
            type="checkbox"
            :checked="allPendingRevisionsChecked"
            @change="toggleSelectAllRevisions($event.target.checked)"
          />全选当前结果</label
        >
        <input
          v-model="revisionFilters.search"
          class="input"
          placeholder="搜索条目标题 / 说明"
          @keyup.enter="loadPendingRevisions"
        />
        <input
          v-if="isPendingMode"
          v-model="bulkRevisionReviewNote"
          class="input grow"
          placeholder="批量审核备注（可选）"
        />
        <button
          v-if="isPendingMode"
          class="btn btn-accent"
          type="button"
          @click="bulkReviewRevisions('approve')"
        >
          批量通过
        </button>
        <button
          v-if="isPendingMode"
          class="btn"
          type="button"
          @click="bulkReviewRevisions('reject')"
        >
          批量驳回
        </button>
      </div>
      <article
        v-for="item in pendingRevisions"
        :key="item.id"
        class="review-row"
      >
        <div class="review-main">
          <label v-if="isPendingMode" class="check-line"
            ><input
              type="checkbox"
              :value="item.id"
              v-model="selectedPendingRevisionIds"
            />选择</label
          >
          <strong>{{
            item.article_title || item.proposed_title || "未命名条目"
          }}</strong>
          <p class="meta">
            提议人：{{ item.proposer?.username || "-" }} · 提交时间：{{
              formatDateTime(item.created_at)
            }}
          </p>
          <p class="meta">修订说明：{{ item.reason || "无" }}</p>
          <div class="diff-preview" v-html="item._diffPreview"></div>
        </div>
        <div class="review-actions">
          <button
            class="btn btn-accent"
            type="button"
            @click="openRevisionDetail(item)"
          >
            进入审批页面
          </button>
          <ReviewRecordPanel
            v-if="!isPendingMode"
            :reviewer-name="getItemReviewerName(item)"
            :reviewed-at="getItemReviewedAt(item)"
            :existing-note="getItemReviewNote(item)"
            :loading="isAppendingReviewNote('revisions', item.id)"
            :on-submit="(note) => appendReviewNote('revisions', item, note)"
          />
        </div>
      </article>
      <p v-if="!pendingRevisions.length" class="meta">
        {{ formatSectionEmptyText('revisions') }}
      </p>
    </article>

    <article v-else-if="currentSection === 'practice'" class="review-card full">
      <h2>补题链接审核</h2>
      <p class="meta">{{ formatSectionStatusLine('practice') }}</p>
      <article
        v-for="item in pendingPracticeProposals"
        :key="item.id"
        class="review-row"
      >
        <div class="review-main">
          <strong>{{
            item.proposed_short_name ||
            item.proposed_official_name ||
            "未命名申请"
          }}</strong>
          <p class="meta">
            申请人：{{ item.proposer?.username || "-" }} · 提交时间：{{
              formatDateTime(item.created_at)
            }}
          </p>
          <p class="meta">
            {{ item.proposed_year || "-" }} ·
            {{ item.proposed_series || "-" }} · {{ item.proposed_stage || "-" }}
          </p>
          <p v-if="item.target_entry_summary" class="meta">
            目标条目：{{ item.target_entry_summary }}
          </p>
          <pre class="proposal-preview">{{
            item.practice_links_text || "-"
          }}</pre>
          <p class="meta">说明：{{ item.reason || "无" }}</p>
        </div>
        <div class="review-actions">
          <template v-if="isPendingMode">
            <PendingReviewNotePanel
              v-model="item._reviewNote"
              placeholder="可选填写审核批注"
            />
            <div class="review-action-buttons">
              <button
                class="btn btn-accent"
                type="button"
                :disabled="reviewingPracticeId === item.id"
                @click="reviewPractice(item, 'approve')"
              >
                通过
              </button>
              <button
                class="btn"
                type="button"
                :disabled="reviewingPracticeId === item.id"
                @click="reviewPractice(item, 'reject')"
              >
                驳回
              </button>
            </div>
          </template>
          <ReviewRecordPanel
            v-if="!isPendingMode"
            :reviewer-name="getItemReviewerName(item)"
            :reviewed-at="getItemReviewedAt(item)"
            :existing-note="getItemReviewNote(item)"
            :loading="isAppendingReviewNote('practice', item.id)"
            :on-submit="(note) => appendReviewNote('practice', item, note)"
          />
        </div>
      </article>
      <p v-if="!pendingPracticeProposals.length" class="meta">
        {{ formatSectionEmptyText('practice') }}
      </p>
    </article>

    <article v-else-if="currentSection === 'notices'" class="review-card full">
      <h2>赛事公告审核</h2>
      <p class="meta">{{ formatSectionStatusLine('notices') }}</p>
      <article v-for="item in pendingNotices" :key="item.id" class="review-row">
        <div class="review-main">
          <strong>{{ item.title || "未命名公告" }}</strong>
          <p class="meta">
            提交人：{{ item.created_by?.username || "-" }} ·
            {{ item.series_label || item.series || "-" }}
            <template v-if="item.year"> · {{ item.year }}</template>
            <template v-if="item.stage_label || item.stage">
              · {{ item.stage_label || item.stage }}</template
            >
            · 提交时间：{{ formatDateTime(item.created_at) }}
          </p>
          <div class="markdown trick-markdown" v-html="renderMarkdown(item.content_md || '')"></div>
        </div>
        <div class="review-actions">
          <template v-if="isPendingMode">
            <PendingReviewNotePanel
              v-model="item._reviewNote"
              placeholder="可选填写审核批注"
            />
            <div class="review-action-buttons">
              <button
                class="btn btn-accent"
                type="button"
                :disabled="reviewingNoticeId === item.id"
                @click="reviewCompetitionNotice(item, 'approve')"
              >
                通过
              </button>
              <button
                class="btn"
                type="button"
                :disabled="reviewingNoticeId === item.id"
                @click="reviewCompetitionNotice(item, 'reject')"
              >
                驳回
              </button>
            </div>
          </template>
          <ReviewRecordPanel
            v-if="!isPendingMode"
            :reviewer-name="getItemReviewerName(item)"
            :reviewed-at="getItemReviewedAt(item)"
            :existing-note="getItemReviewNote(item)"
            :loading="isAppendingReviewNote('notices', item.id)"
            :on-submit="(note) => appendReviewNote('notices', item, note)"
          />
        </div>
      </article>
      <p v-if="!pendingNotices.length" class="meta">
        {{ formatSectionEmptyText('notices') }}
      </p>
    </article>

    <article v-else-if="currentSection === 'schedules'" class="review-card full">
      <h2>锦标赛审核</h2>
      <p class="meta">{{ formatSectionStatusLine('schedules') }}</p>
      <article v-for="item in pendingSchedules" :key="item.id" class="review-row">
        <div class="review-main">
          <strong>{{ item.competition_type || "未命名赛事" }}</strong>
          <p class="meta">
            提交人：{{ item.created_by?.username || "-" }} ·
            {{ formatDateRange(item.event_date, item.end_date) }} ·
            {{ item.competition_time_range || "时间未填" }} ·
            {{ item.location || "地点未填" }}
          </p>
          <p class="meta">
            QQ群或链接：{{ item.qq_group || "-" }}
            <template v-if="item.announcement_title">
              · 关联公告：{{ item.announcement_title }}</template
            >
          </p>
        </div>
        <div class="review-actions">
          <template v-if="isPendingMode">
            <PendingReviewNotePanel
              v-model="item._reviewNote"
              placeholder="可选填写审核批注"
            />
            <div class="review-action-buttons">
              <button
                class="btn btn-accent"
                type="button"
                :disabled="reviewingScheduleId === item.id"
                @click="reviewCompetitionSchedule(item, 'approve')"
              >
                通过
              </button>
              <button
                class="btn"
                type="button"
                :disabled="reviewingScheduleId === item.id"
                @click="reviewCompetitionSchedule(item, 'reject')"
              >
                驳回
              </button>
            </div>
          </template>
          <ReviewRecordPanel
            v-if="!isPendingMode"
            :reviewer-name="getItemReviewerName(item)"
            :reviewed-at="getItemReviewedAt(item)"
            :existing-note="getItemReviewNote(item)"
            :loading="isAppendingReviewNote('schedules', item.id)"
            :on-submit="(note) => appendReviewNote('schedules', item, note)"
          />
        </div>
      </article>
      <p v-if="!pendingSchedules.length" class="meta">
        {{ formatSectionEmptyText('schedules') }}
      </p>
    </article>

    <article v-else-if="currentSection === 'tickets'" class="review-card full">
      <h2>工单审核</h2>
      <p class="meta">{{ formatSectionStatusLine('tickets') }}</p>
      <div class="toolbar">
        <select
          v-model="ticketFilters.kind"
          class="select"
          @change="loadPendingTickets"
        >
          <option value="">全部类型</option>
          <option value="issue">issue</option>
          <option value="request">request</option>
        </select>
        <input
          v-model="ticketFilters.author"
          class="input"
          placeholder="提交者用户名"
          @keyup.enter="loadPendingTickets"
        />
        <input
          v-model="ticketFilters.search"
          class="input grow"
          placeholder="搜索标题或内容"
          @keyup.enter="loadPendingTickets"
        />
        <button class="btn" type="button" @click="loadPendingTickets">
          筛选
        </button>
        <button class="btn" type="button" @click="resetTicketFilters">
          重置
        </button>
      </div>
      <article v-for="item in pendingTickets" :key="item.id" class="review-row">
        <div class="review-main">
          <strong>{{ item.title }}</strong>
          <p class="meta">
            {{ item.kind }} · {{ item.author?.username || "-" }} ·
            {{ formatDateTime(item.created_at) }}
          </p>
          <p class="meta">
            处理人：{{
              item.assignee?.username
                ? `${item.assignee.username} (${item.assignee.role})`
                : "未分派"
            }}
          </p>
          <p class="ticket-content">{{ item.content }}</p>
        </div>
        <div class="review-actions">
          <select v-if="isPendingMode" v-model="item._assignTo" class="select">
            <option value="">未分派</option>
            <option
              v-for="user in assigneeOptions"
              :key="`ticket-assignee-${item.id}-${user.id}`"
              :value="String(user.id)"
            >
              {{ user.username }} ({{ user.role }})
            </option>
          </select>
          <select v-if="isPendingMode" v-model="item._nextStatus" class="select">
            <option value="open">受理</option>
            <option value="in_progress">处理中</option>
            <option value="resolved">已解决</option>
            <option value="rejected">驳回</option>
          </select>
          <textarea
            v-if="isPendingMode"
            v-model="item._note"
            class="textarea"
            placeholder="处理备注（可选）"
          ></textarea>
          <button
            v-if="isPendingMode"
            class="btn btn-accent"
            type="button"
            @click="updateTicketStatus(item)"
          >
            提交处理
          </button>
          <ReviewRecordPanel
            v-if="!isPendingMode"
            :reviewer-name="getItemReviewerName(item)"
            :reviewed-at="getItemReviewedAt(item)"
            :existing-note="getItemReviewNote(item)"
            :loading="isAppendingReviewNote('tickets', item.id)"
            :on-submit="(note) => appendReviewNote('tickets', item, note)"
          />
        </div>
      </article>
      <p v-if="!pendingTickets.length" class="meta">
        {{ formatSectionEmptyText('tickets') }}
      </p>
    </article>

    <article v-else-if="currentSection === 'comments'" class="review-card full">
      <h2>评论审核</h2>
      <p class="meta">{{ formatSectionStatusLine('comments') }}</p>
      <div class="toolbar">
        <label v-if="isPendingMode" class="check-line"
          ><input
            type="checkbox"
            :checked="allPendingCommentsChecked"
            @change="toggleSelectAllComments($event.target.checked)"
          />全选当前结果</label
        >
        <input
          v-model="commentFilters.search"
          class="input"
          placeholder="搜索评论内容"
          @keyup.enter="loadPendingComments"
        />
        <input
          v-model="commentFilters.author"
          class="input"
          placeholder="评论用户名 / ID"
          @keyup.enter="loadPendingComments"
        />
        <input
          v-model="commentFilters.article"
          class="input"
          placeholder="条目 ID"
          @keyup.enter="loadPendingComments"
        />
        <input
          v-if="isPendingMode"
          v-model="bulkCommentReviewNote"
          class="input grow"
          placeholder="批量审核备注（可选）"
        />
        <button
          v-if="isPendingMode"
          class="btn btn-accent"
          type="button"
          @click="bulkReviewComments('approve')"
        >
          批量通过
        </button>
        <button
          v-if="isPendingMode"
          class="btn"
          type="button"
          @click="bulkReviewComments('reject')"
        >
          批量驳回
        </button>
      </div>
      <article
        v-for="item in pendingComments"
        :key="item.id"
        class="review-row"
      >
        <div class="review-main">
          <label v-if="isPendingMode" class="check-line"
            ><input
              type="checkbox"
              :value="item.id"
              v-model="selectedPendingCommentIds"
            />选择</label
          >
          <strong
            >评论 #{{ item.id }} ·
            {{ item.article_title || `条目 #${item.article}` }}</strong
          >
          <p class="meta">
            评论人：{{ item.author?.username || "-" }} · 提交时间：{{
              formatDateTime(item.created_at)
            }}
          </p>
          <p class="ticket-content">{{ item.content }}</p>
        </div>
        <div class="review-actions">
          <template v-if="isPendingMode">
            <PendingReviewNotePanel
              v-model="item._reviewNote"
              placeholder="可选填写审核批注"
            />
            <div class="review-action-buttons">
              <button
                class="btn btn-accent"
                type="button"
                :disabled="reviewingCommentId === item.id"
                @click="reviewComment(item, 'approve')"
              >
                通过
              </button>
              <button
                class="btn"
                type="button"
                :disabled="reviewingCommentId === item.id"
                @click="reviewComment(item, 'reject')"
              >
                驳回
              </button>
            </div>
          </template>
          <ReviewRecordPanel
            v-if="!isPendingMode"
            :reviewer-name="getItemReviewerName(item)"
            :reviewed-at="getItemReviewedAt(item)"
            :existing-note="getItemReviewNote(item)"
            :loading="isAppendingReviewNote('comments', item.id)"
            :on-submit="(note) => appendReviewNote('comments', item, note)"
          />
        </div>
      </article>
      <p v-if="!pendingComments.length" class="meta">
        {{ formatSectionEmptyText('comments') }}
      </p>
    </article>

    <article v-else-if="currentSection === 'tricks'" class="review-card full">
      <h2>trick 技巧审核</h2>
      <p class="meta">{{ formatSectionStatusLine('tricks') }}</p>
      <div class="toolbar">
        <input
          v-model="trickFilters.search"
          class="input grow"
          placeholder="搜索标题或内容"
          @keyup.enter="loadPendingTricks"
        />
        <select
          v-model="trickFilters.term"
          class="select"
          @change="loadPendingTricks"
        >
          <option value="">全部词条</option>
          <option
            v-for="term in trickTerms"
            :key="`review-trick-term-${term.id}`"
            :value="String(term.id)"
          >
            {{ term.name }}
          </option>
        </select>
        <button class="btn" type="button" @click="loadPendingTricks">
          筛选
        </button>
        <button class="btn" type="button" @click="resetTrickFilters">
          重置
        </button>
      </div>
      <article v-for="item in pendingTricks" :key="item.id" class="review-row">
        <div class="review-main">
          <strong v-html="renderInlineMarkdown(item.title || '未命名 trick')"></strong>
          <p class="meta">
            提交人：{{ item.author?.username || "-" }} · 提交时间：{{
              formatDateTime(item.created_at)
            }}
          </p>
          <p v-if="item.delete_vote_review_status === 'pending'" class="meta">
            当前为删除审核条目 · 点踩数 {{ item.downvote_count || 0 }} · 发起时间
            {{ formatDateTime(item.delete_vote_review_requested_at) }}
          </p>
          <div
            class="markdown trick-markdown"
            v-html="renderMarkdown(item.content_md || '')"
          ></div>
        </div>
        <div class="review-actions">
          <template v-if="isPendingMode">
            <PendingReviewNotePanel
              v-model="item._reviewNote"
              placeholder="可选填写审核批注"
            />
            <div class="review-action-buttons">
              <button
                class="btn btn-accent"
                type="button"
                :disabled="reviewingTrickId === item.id"
                @click="
                  item.delete_vote_review_status === 'pending'
                    ? resolveTrickDeleteReview(item, 'keep')
                    : reviewTrick(item, 'approved')
                "
              >
                {{
                  item.delete_vote_review_status === 'pending' ? "保留" : "通过"
                }}
              </button>
              <button
                class="btn"
                type="button"
                :disabled="reviewingTrickId === item.id"
                @click="
                  item.delete_vote_review_status === 'pending'
                    ? resolveTrickDeleteReview(item, 'delete')
                    : reviewTrick(item, 'rejected')
                "
              >
                {{
                  item.delete_vote_review_status === 'pending' ? "删除" : "驳回"
                }}
              </button>
            </div>
          </template>
          <ReviewRecordPanel
            v-if="!isPendingMode"
            :reviewer-name="getItemReviewerName(item)"
            :reviewed-at="getItemReviewedAt(item)"
            :existing-note="getItemReviewNote(item)"
            :loading="isAppendingReviewNote('tricks', item.id)"
            :on-submit="(note) => appendReviewNote('tricks', item, note)"
          />
        </div>
      </article>
      <p v-if="!pendingTricks.length" class="meta">
        {{ formatSectionEmptyText('tricks') }}
      </p>
    </article>

    <article
      v-else-if="currentSection === 'trick_terms'"
      class="review-card full"
    >
      <h2>trick 词条候选审核</h2>
      <p class="meta">{{ formatSectionStatusLine('trick_terms') }}</p>
      <article
        v-for="item in pendingTrickTermSuggestions"
        :key="item.id"
        class="review-row"
      >
        <div class="review-main">
          <strong>{{ item.name }}</strong>
          <p class="meta">
            提交人：{{ item.proposer?.username || "-" }} · 提交时间：{{
              formatDateTime(item.created_at)
            }}
          </p>
          <p class="meta" v-if="item.linked_tricks_count">
            关联 trick：{{ item.linked_tricks_count }} 条
          </p>
          <p class="meta" v-if="item.linked_tricks?.length">
            {{
              item.linked_tricks.map((x) => x.title || `#${x.id}`).join("、")
            }}
          </p>
        </div>
        <div class="review-actions">
          <template v-if="isPendingMode">
            <PendingReviewNotePanel
              v-model="item._reviewNote"
              placeholder="可选填写审核批注"
            />
            <div class="review-action-buttons">
              <button
                class="btn btn-accent"
                type="button"
                :disabled="reviewingTrickTermSuggestionId === item.id"
                @click="reviewTrickTermSuggestion(item, 'approved')"
              >
                通过
              </button>
              <button
                class="btn"
                type="button"
                :disabled="reviewingTrickTermSuggestionId === item.id"
                @click="reviewTrickTermSuggestion(item, 'rejected')"
              >
                驳回
              </button>
            </div>
          </template>
          <ReviewRecordPanel
            v-if="!isPendingMode"
            :reviewer-name="getItemReviewerName(item)"
            :reviewed-at="getItemReviewedAt(item)"
            :existing-note="getItemReviewNote(item)"
            :loading="isAppendingReviewNote('trick_terms', item.id)"
            :on-submit="(note) => appendReviewNote('trick_terms', item, note)"
          />
        </div>
      </article>
      <p v-if="!pendingTrickTermSuggestions.length" class="meta">
        {{ formatSectionEmptyText('trick_terms') }}
      </p>
    </article>

    <article
      v-else-if="currentSection === 'questions'"
      class="review-card full"
    >
      <h2>问答问题审核</h2>
      <p class="meta">{{ formatSectionStatusLine('questions') }}</p>
      <div class="toolbar">
        <label v-if="isPendingMode" class="check-line"
          ><input
            type="checkbox"
            :checked="allPendingQuestionsChecked"
            @change="toggleSelectAllQuestions($event.target.checked)"
          />全选当前结果</label
        >
        <input
          v-model="questionFilters.search"
          class="input"
          placeholder="按标题 / 内容搜索问题"
          @keyup.enter="loadPendingQuestions"
        />
        <input
          v-model="questionFilters.author"
          class="input"
          placeholder="提问用户名"
          @keyup.enter="loadPendingQuestions"
        />
        <select v-model="questionFilters.category" class="select">
          <option value="">全部分类</option>
          <option
            v-for="item in categories"
            :key="`question-category-${item.id}`"
            :value="String(item.id)"
          >
            {{ item.name }}
          </option>
        </select>
        <button
          v-if="isPendingMode"
          class="btn btn-accent"
          type="button"
          @click="bulkModerateQuestions('approve')"
        >
          批量通过
        </button>
        <button
          v-if="isPendingMode"
          class="btn"
          type="button"
          @click="bulkModerateQuestions('reject')"
        >
          批量驳回
        </button>
        <input
          v-if="isPendingMode"
          v-model="bulkQuestionReviewNote"
          class="input grow"
          placeholder="批量驳回批注（可选）"
        />
        <button class="btn" type="button" @click="resetQuestionFilters">
          重置
        </button>
      </div>
      <article
        v-for="item in pendingQuestions"
        :key="item.id"
        class="review-row"
      >
        <div class="review-main">
          <label v-if="isPendingMode" class="check-line"
            ><input
              type="checkbox"
              :value="item.id"
              v-model="selectedPendingQuestionIds"
            />选择</label
          >
          <strong>{{ item.title }}</strong>
          <p class="meta">
            提问者 {{ item.author?.username || "-" }} ·
            {{ formatDateTime(item.created_at) }} · 回答 {{ item.answers_count
            }}<span v-if="item.category_name">
              · 分类 {{ item.category_name }}</span
            >
          </p>
          <p class="ticket-content">{{ item.content_md }}</p>
        </div>
        <div class="review-actions">
          <template v-if="isPendingMode">
            <PendingReviewNotePanel
              v-model="item._reviewNote"
              placeholder="可选填写审核批注"
            />
            <div class="review-action-buttons">
              <button
                class="btn btn-accent"
                type="button"
                @click="reviewQuestion(item, 'approve')"
              >
                通过
              </button>
              <button
                class="btn"
                type="button"
                @click="reviewQuestion(item, 'reject')"
              >
                驳回
              </button>
            </div>
          </template>
          <ReviewRecordPanel
            v-if="!isPendingMode"
            :reviewer-name="getItemReviewerName(item)"
            :reviewed-at="getItemReviewedAt(item)"
            :existing-note="getItemReviewNote(item)"
            :loading="isAppendingReviewNote('questions', item.id)"
            :on-submit="(note) => appendReviewNote('questions', item, note)"
          />
        </div>
      </article>
      <p v-if="!pendingQuestions.length" class="meta">
        {{ formatSectionEmptyText('questions') }}
      </p>
    </article>

    <article v-else-if="currentSection === 'answers'" class="review-card full">
      <h2>问答回答审核</h2>
      <p class="meta">{{ formatSectionStatusLine('answers') }}</p>
      <div class="toolbar">
        <label v-if="isPendingMode" class="check-line"
          ><input
            type="checkbox"
            :checked="allPendingAnswersChecked"
            @change="toggleSelectAllAnswers($event.target.checked)"
          />全选当前结果</label
        >
        <input
          v-model="answerFilters.search"
          class="input grow"
          placeholder="按回答内容搜索"
          @keyup.enter="loadPendingAnswers"
        />
        <input
          v-model="answerFilters.author"
          class="input"
          placeholder="回答用户名"
          @keyup.enter="loadPendingAnswers"
        />
        <button
          v-if="isPendingMode"
          class="btn btn-accent"
          type="button"
          @click="bulkModerateAnswers('approve')"
        >
          批量通过
        </button>
        <button
          v-if="isPendingMode"
          class="btn"
          type="button"
          @click="bulkModerateAnswers('reject')"
        >
          批量驳回
        </button>
        <input
          v-if="isPendingMode"
          v-model="bulkAnswerReviewNote"
          class="input grow"
          placeholder="批量驳回批注（可选）"
        />
        <button class="btn" type="button" @click="resetAnswerFilters">
          重置
        </button>
      </div>
      <article v-for="item in pendingAnswers" :key="item.id" class="review-row">
        <div class="review-main">
          <label v-if="isPendingMode" class="check-line"
            ><input
              type="checkbox"
              :value="item.id"
              v-model="selectedPendingAnswerIds"
            />选择</label
          >
          <strong>{{ item.question_title || `问题 #${item.question}` }}</strong>
          <p class="meta">
            回答者 {{ item.author?.username || "-" }} ·
            {{ formatDateTime(item.created_at) }}
          </p>
          <p class="ticket-content">{{ item.content_md }}</p>
        </div>
        <div class="review-actions">
          <template v-if="isPendingMode">
            <PendingReviewNotePanel
              v-model="item._reviewNote"
              placeholder="可选填写审核批注"
            />
            <div class="review-action-buttons">
              <button
                class="btn btn-accent"
                type="button"
                @click="reviewAnswer(item, 'approve')"
              >
                通过
              </button>
              <button
                class="btn"
                type="button"
                @click="reviewAnswer(item, 'reject')"
              >
                驳回
              </button>
            </div>
          </template>
          <ReviewRecordPanel
            v-if="!isPendingMode"
            :reviewer-name="getItemReviewerName(item)"
            :reviewed-at="getItemReviewedAt(item)"
            :existing-note="getItemReviewNote(item)"
            :loading="isAppendingReviewNote('answers', item.id)"
            :on-submit="(note) => appendReviewNote('answers', item, note)"
          />
        </div>
      </article>
      <p v-if="!pendingAnswers.length" class="meta">
        {{ formatSectionEmptyText('answers') }}
      </p>
    </article>
  </section>
</template>

<script setup>
import { computed, reactive, ref, watch } from "vue";
import { RouterLink, useRouter } from "vue-router";

import PendingReviewNotePanel from "../components/review/PendingReviewNotePanel.vue";
import ReviewRecordPanel from "../components/review/ReviewRecordPanel.vue";
import api from "../services/api";
import { renderInlineMarkdown, renderMarkdown } from "../services/markdown";
import { renderUnifiedDiffHtml } from "../services/revisionDiff";
import { useUiStore } from "../stores/ui";
import { sortFixedTrickTerms } from "../utils/trickTerms";

const ui = useUiStore();
const router = useRouter();

const props = defineProps({
  section: {
    type: String,
    default: "revisions",
  },
});

const reviewSections = [
  {
    key: "revisions",
    label: "内容修订",
    description: "审核条目修订申请。",
    routeName: "review",
  },
  {
    key: "practice",
    label: "补题链接",
    description: "审核补题链接新增和修改申请。",
    routeName: "review-practice",
  },
  {
    key: "notices",
    label: "赛事公告",
    description: "审核普通用户提交的赛事公告。",
    routeName: "review-notices",
  },
  {
    key: "schedules",
    label: "锦标赛",
    description: "审核普通用户提交的赛事日程。",
    routeName: "review-schedules",
  },
  {
    key: "tickets",
    label: "工单",
    description: "处理问答区与站内工单。",
    routeName: "review-tickets",
  },
  {
    key: "comments",
    label: "评论",
    description: "审核条目评论。",
    routeName: "review-comments",
  },
  {
    key: "tricks",
    label: "trick 技巧",
    description: "审核 trick 投稿。",
    routeName: "review-tricks",
  },
  {
    key: "trick_terms",
    label: "trick 词条",
    description: "审核词条候选。",
    routeName: "review-trick-terms",
  },
  {
    key: "questions",
    label: "问题",
    description: "审核问答区问题。",
    routeName: "review-questions",
  },
  {
    key: "answers",
    label: "回答",
    description: "审核问答区回答。",
    routeName: "review-answers",
  },
].filter((item) => item.key !== "trick_terms");

const reviewStatusOptions = [
  { key: "pending", label: "待审核" },
  { key: "approved", label: "已通过" },
  { key: "rejected", label: "已驳回" },
];

const reviewSectionKeys = new Set(reviewSections.map((item) => item.key));
const reviewSectionMap = new Map(
  reviewSections.map((item) => [item.key, item]),
);

const counts = reactive({
  revisions: 0,
  practice: 0,
  notices: 0,
  schedules: 0,
  tickets: 0,
  comments: 0,
  tricks: 0,
  trick_terms: 0,
  questions: 0,
  answers: 0,
});
const historyCounts = reactive(
  Object.fromEntries(
    reviewSections.map((item) => [
      item.key,
      { pending: 0, approved: 0, rejected: 0 },
    ]),
  ),
);
const reviewStatuses = reactive(
  Object.fromEntries(reviewSections.map((item) => [item.key, "pending"])),
);

const categories = ref([]);
const assigneeOptions = ref([]);
const pendingRevisions = ref([]);
const pendingPracticeProposals = ref([]);
const pendingNotices = ref([]);
const pendingSchedules = ref([]);
const pendingTickets = ref([]);
const pendingComments = ref([]);
const pendingTricks = ref([]);
const pendingTrickTermSuggestions = ref([]);
const pendingQuestions = ref([]);
const pendingAnswers = ref([]);
const trickTerms = ref([]);

const selectedPendingRevisionIds = ref([]);
const selectedPendingCommentIds = ref([]);
const selectedPendingQuestionIds = ref([]);
const selectedPendingAnswerIds = ref([]);
const bulkRevisionReviewNote = ref("");
const bulkCommentReviewNote = ref("");
const bulkQuestionReviewNote = ref("");
const bulkAnswerReviewNote = ref("");
const reviewingPracticeId = ref(null);
const reviewingNoticeId = ref(null);
const reviewingScheduleId = ref(null);
const reviewingCommentId = ref(null);
const reviewingTrickId = ref(null);
const reviewingTrickTermSuggestionId = ref(null);
const appendingReviewNoteKey = ref("");

const revisionFilters = reactive({ search: "" });
const ticketFilters = reactive({ kind: "", author: "", search: "" });
const commentFilters = reactive({ search: "", author: "", article: "" });
const trickFilters = reactive({ search: "", term: "" });
const questionFilters = reactive({ search: "", author: "", category: "" });
const answerFilters = reactive({ search: "", author: "" });

const currentSection = computed(() => normalizeReviewSection(props.section));
const currentSectionConfig = computed(
  () => reviewSectionMap.get(currentSection.value) || reviewSections[0],
);
const currentReviewStatus = computed(
  () => reviewStatuses[currentSection.value] || "pending",
);
const currentHistoryCounts = computed(
  () =>
    historyCounts[currentSection.value] || {
      pending: 0,
      approved: 0,
      rejected: 0,
    },
);
const isPendingMode = computed(() => currentReviewStatus.value === "pending");

const allPendingRevisionsChecked = computed(
  () =>
    pendingRevisions.value.length > 0 &&
    selectedPendingRevisionIds.value.length === pendingRevisions.value.length,
);
const allPendingCommentsChecked = computed(
  () =>
    pendingComments.value.length > 0 &&
    selectedPendingCommentIds.value.length === pendingComments.value.length,
);
const allPendingQuestionsChecked = computed(
  () =>
    pendingQuestions.value.length > 0 &&
    selectedPendingQuestionIds.value.length === pendingQuestions.value.length,
);
const allPendingAnswersChecked = computed(
  () =>
    pendingAnswers.value.length > 0 &&
    selectedPendingAnswerIds.value.length === pendingAnswers.value.length,
);

function normalizeReviewSection(section) {
  const value = Array.isArray(section) ? section[0] : section;
  if (typeof value !== "string" || !reviewSectionKeys.has(value)) {
    return "revisions";
  }
  return value;
}

function buildReviewRoute(section) {
  const item = reviewSectionMap.get(normalizeReviewSection(section));
  return { name: item?.routeName || "review" };
}

function setReviewStatus(section, status) {
  const nextSection = normalizeReviewSection(section);
  const nextStatus = reviewStatusOptions.some((item) => item.key === status)
    ? status
    : "pending";
  reviewStatuses[nextSection] = nextStatus;
  reloadCurrentSection();
}

function getReviewStatusApiValues(section, reviewStatus) {
  if (reviewStatus === "pending") return ["pending"];

  switch (section) {
    case "tickets":
      return reviewStatus === "approved"
        ? ["open", "in_progress", "resolved"]
        : ["rejected"];
    case "comments":
      return reviewStatus === "approved" ? ["visible"] : ["hidden"];
    case "questions":
      return reviewStatus === "approved" ? ["open", "closed"] : ["hidden"];
    case "answers":
      return reviewStatus === "approved" ? ["visible"] : ["hidden"];
    default:
      return [reviewStatus];
  }
}

async function fetchGroupedCount(path, params = {}, statuses = []) {
  let total = 0;
  for (const status of statuses) {
    total += await fetchCount(path, { ...params, status });
  }
  return total;
}

async function fetchTrickPendingReviewCount(params = {}) {
  const [pendingCount, deleteReviewCount] = await Promise.all([
    fetchGroupedCount("/tricks/", params, ["pending"]),
    fetchCount("/tricks/", {
      ...params,
      delete_vote_review_status: "pending",
    }),
  ]);
  return pendingCount + deleteReviewCount;
}

async function fetchAllByStatuses(path, params = {}, statuses = []) {
  const merged = [];
  let total = 0;
  for (const status of statuses) {
    const payload = await fetchAllPages(path, { ...params, status });
    total += payload.count;
    merged.push(...payload.results);
  }
  merged.sort((left, right) => {
    const leftTime = new Date(
      left?.updated_at || left?.reviewed_at || left?.created_at || 0,
    ).getTime();
    const rightTime = new Date(
      right?.updated_at || right?.reviewed_at || right?.created_at || 0,
    ).getTime();
    return rightTime - leftTime;
  });
  return { results: merged, count: total };
}

function formatStatusCount(section, reviewStatus) {
  return formatCount(currentHistoryCounts.value?.[reviewStatus] || 0);
}

function formatSectionStatusLine(section) {
  const currentLabel =
    reviewStatusOptions.find((item) => item.key === currentReviewStatus.value)
      ?.label || "待审核";
  const count = historyCounts[section]?.[currentReviewStatus.value] || 0;
  return `${currentLabel} ${count} 条`;
}

function formatSectionEmptyText(section) {
  const currentLabel =
    reviewStatusOptions.find((item) => item.key === currentReviewStatus.value)
      ?.label || "待审核";
  return `当前没有${currentLabel}${currentSectionConfig.value?.label || section}记录。`;
}

function getItemReviewerName(item) {
  return (
    item?.reviewer?.username ||
    item?.assignee?.username ||
    item?.updated_by?.username ||
    item?.created_by?.username ||
    "-"
  );
}

function getItemReviewedAt(item) {
  return item?.reviewed_at || item?.updated_at || item?.created_at || null;
}

function getItemReviewNote(item) {
  return String(item?.review_note || item?.resolution_note || "").trim();
}

function buildAppendReviewNotePath(section, itemId) {
  const id = Number(itemId);
  if (!Number.isFinite(id) || id <= 0) return "";
  const mapping = {
    revisions: `/revisions/${id}/append-review-note/`,
    practice: `/competition-practice-proposals/${id}/append-review-note/`,
    notices: `/competition-notices/${id}/append-review-note/`,
    schedules: `/competition-schedules/${id}/append-review-note/`,
    tickets: `/issues/${id}/append-review-note/`,
    comments: `/comments/${id}/append-review-note/`,
    tricks: `/tricks/${id}/append-review-note/`,
    trick_terms: `/trick-term-suggestions/${id}/append-review-note/`,
    questions: `/questions/${id}/append-review-note/`,
    answers: `/answers/${id}/append-review-note/`,
  };
  return mapping[section] || "";
}

function isAppendingReviewNote(section, itemId) {
  return appendingReviewNoteKey.value === `${section}:${itemId}`;
}

function getErrorText(error, fallback = "操作失败") {
  const payload = error?.response?.data;
  if (!payload) return error?.message || fallback;
  if (typeof payload === "string") return payload;
  if (typeof payload.detail === "string") return payload.detail;
  if (Array.isArray(payload)) return payload.join("；");
  if (typeof payload === "object") {
    const parts = [];
    for (const [field, value] of Object.entries(payload)) {
      if (Array.isArray(value)) {
        parts.push(`${field}: ${value.join("，")}`);
      } else if (typeof value === "string") {
        parts.push(`${field}: ${value}`);
      }
    }
    if (parts.length) return parts.join("；");
  }
  return fallback;
}

function unpackListPayload(data) {
  if (Array.isArray(data)) {
    return { results: data, count: data.length, next: null };
  }
  return {
    results: Array.isArray(data?.results) ? data.results : [],
    count: Number.isFinite(data?.count) ? data.count : 0,
    next: data?.next || null,
  };
}

async function fetchCount(path, params = {}) {
  try {
    const { data } = await api.get(path, { params: { ...params, page: 1 } });
    return unpackListPayload(data).count;
  } catch {
    return 0;
  }
}

async function fetchAllPages(path, params = {}) {
  const merged = [];
  let page = 1;
  let totalCount = 0;

  while (page <= 50) {
    const { data } = await api.get(path, { params: { ...params, page } });
    const payload = unpackListPayload(data);
    totalCount = payload.count || totalCount;
    merged.push(...payload.results);
    if (!payload.next) break;
    page += 1;
  }

  return {
    results: merged,
    count: totalCount || merged.length,
  };
}

async function loadCounts() {
  const [
    revisions,
    practice,
    notices,
    schedules,
    tickets,
    comments,
    tricks,
    trickTermsPending,
    questions,
    answers,
  ] = await Promise.all([
    fetchCount("/revisions/", { status: "pending" }),
    fetchCount("/competition-practice-proposals/", { status: "pending" }),
    fetchCount("/competition-notices/", { include_hidden: 1, status: "pending" }),
    fetchCount("/competition-schedules/", { include_hidden: 1, status: "pending" }),
    fetchCount("/issues/", { status: "pending" }),
    fetchCount("/comments/", { status: "pending" }),
    fetchTrickPendingReviewCount({ include_all: 1 }),
    fetchCount("/trick-term-suggestions/", { status: "pending" }),
    fetchCount("/questions/", { status: "pending" }),
    fetchCount("/answers/", { status: "pending" }),
  ]);
  counts.revisions = revisions;
  counts.practice = practice;
  counts.notices = notices;
  counts.schedules = schedules;
  counts.tickets = tickets;
  counts.comments = comments;
  counts.tricks = tricks;
  counts.trick_terms = trickTermsPending;
  counts.questions = questions;
  counts.answers = answers;
}

async function loadCurrentHistoryCounts() {
  const section = currentSection.value;
  const loaders = {
    revisions: () =>
      Promise.all([
        fetchGroupedCount("/revisions/", {}, getReviewStatusApiValues(section, "pending")),
        fetchGroupedCount("/revisions/", {}, getReviewStatusApiValues(section, "approved")),
        fetchGroupedCount("/revisions/", {}, getReviewStatusApiValues(section, "rejected")),
      ]),
    practice: () =>
      Promise.all([
        fetchGroupedCount(
          "/competition-practice-proposals/",
          {},
          getReviewStatusApiValues(section, "pending"),
        ),
        fetchGroupedCount(
          "/competition-practice-proposals/",
          {},
          getReviewStatusApiValues(section, "approved"),
        ),
        fetchGroupedCount(
          "/competition-practice-proposals/",
          {},
          getReviewStatusApiValues(section, "rejected"),
        ),
      ]),
    notices: () =>
      Promise.all([
        fetchGroupedCount(
          "/competition-notices/",
          { include_hidden: 1 },
          getReviewStatusApiValues(section, "pending"),
        ),
        fetchGroupedCount(
          "/competition-notices/",
          { include_hidden: 1 },
          getReviewStatusApiValues(section, "approved"),
        ),
        fetchGroupedCount(
          "/competition-notices/",
          { include_hidden: 1 },
          getReviewStatusApiValues(section, "rejected"),
        ),
      ]),
    schedules: () =>
      Promise.all([
        fetchGroupedCount(
          "/competition-schedules/",
          { include_hidden: 1 },
          getReviewStatusApiValues(section, "pending"),
        ),
        fetchGroupedCount(
          "/competition-schedules/",
          { include_hidden: 1 },
          getReviewStatusApiValues(section, "approved"),
        ),
        fetchGroupedCount(
          "/competition-schedules/",
          { include_hidden: 1 },
          getReviewStatusApiValues(section, "rejected"),
        ),
      ]),
    tickets: () =>
      Promise.all([
        fetchGroupedCount("/issues/", {}, getReviewStatusApiValues(section, "pending")),
        fetchGroupedCount("/issues/", {}, getReviewStatusApiValues(section, "approved")),
        fetchGroupedCount("/issues/", {}, getReviewStatusApiValues(section, "rejected")),
      ]),
    comments: () =>
      Promise.all([
        fetchGroupedCount("/comments/", {}, getReviewStatusApiValues(section, "pending")),
        fetchGroupedCount("/comments/", {}, getReviewStatusApiValues(section, "approved")),
        fetchGroupedCount("/comments/", {}, getReviewStatusApiValues(section, "rejected")),
      ]),
    tricks: () =>
      Promise.all([
        fetchTrickPendingReviewCount({ include_all: 1 }),
        fetchGroupedCount(
          "/tricks/",
          { include_all: 1 },
          getReviewStatusApiValues(section, "approved"),
        ),
        fetchGroupedCount(
          "/tricks/",
          { include_all: 1 },
          getReviewStatusApiValues(section, "rejected"),
        ),
      ]),
    trick_terms: () =>
      Promise.all([
        fetchGroupedCount(
          "/trick-term-suggestions/",
          {},
          getReviewStatusApiValues(section, "pending"),
        ),
        fetchGroupedCount(
          "/trick-term-suggestions/",
          {},
          getReviewStatusApiValues(section, "approved"),
        ),
        fetchGroupedCount(
          "/trick-term-suggestions/",
          {},
          getReviewStatusApiValues(section, "rejected"),
        ),
      ]),
    questions: () =>
      Promise.all([
        fetchGroupedCount("/questions/", {}, getReviewStatusApiValues(section, "pending")),
        fetchGroupedCount("/questions/", {}, getReviewStatusApiValues(section, "approved")),
        fetchGroupedCount("/questions/", {}, getReviewStatusApiValues(section, "rejected")),
      ]),
    answers: () =>
      Promise.all([
        fetchGroupedCount("/answers/", {}, getReviewStatusApiValues(section, "pending")),
        fetchGroupedCount("/answers/", {}, getReviewStatusApiValues(section, "approved")),
        fetchGroupedCount("/answers/", {}, getReviewStatusApiValues(section, "rejected")),
      ]),
  };

  if (!loaders[section]) return;
  const [pending, approved, rejected] = await loaders[section]();
  historyCounts[section] = { pending, approved, rejected };
}

async function loadTrickTerms() {
  try {
    const { results } = await fetchAllPages("/trick-terms/");
    trickTerms.value = sortFixedTrickTerms(results);
  } catch (error) {
    ui.error(getErrorText(error, "trick 词条列表加载失败"));
  }
}

async function loadCategories() {
  try {
    const { data } = await api.get("/categories/", {
      params: { include_hidden: 1 },
    });
    categories.value = Array.isArray(data?.results)
      ? data.results
      : Array.isArray(data)
        ? data
        : [];
  } catch (error) {
    ui.error(getErrorText(error, "分类列表加载失败"));
  }
}

async function loadAssigneeOptions() {
  try {
    const { data } = await api.get("/users/assignees/");
    assigneeOptions.value = Array.isArray(data) ? data : data.results || [];
  } catch (error) {
    ui.error(getErrorText(error, "处理人列表加载失败"));
  }
}

async function loadPendingRevisions() {
  try {
    const params = {};
    if (revisionFilters.search.trim())
      params.search = revisionFilters.search.trim();
    const { results } = await fetchAllByStatuses(
      "/revisions/",
      params,
      getReviewStatusApiValues("revisions", currentReviewStatus.value),
    );
    pendingRevisions.value = results.map((item) => ({
      ...item,
      _diffPreview: renderUnifiedDiffHtml(
        item.article_content_md || "",
        item.proposed_content_md || "",
        { maxLines: 16 },
      ),
    }));
    syncSelectedIds(selectedPendingRevisionIds, pendingRevisions.value);
  } catch (error) {
    ui.error(getErrorText(error, "修订列表加载失败"));
  }
}

async function loadPendingPracticeProposals() {
  try {
    const { results } = await fetchAllByStatuses(
      "/competition-practice-proposals/",
      {},
      getReviewStatusApiValues("practice", currentReviewStatus.value),
    );
    pendingPracticeProposals.value = results.map((item) => ({
      ...item,
      _reviewNote: item._reviewNote || "",
    }));
  } catch (error) {
    ui.error(getErrorText(error, "补题链接申请加载失败"));
  }
}

async function loadPendingCompetitionNotices() {
  try {
    const { results } = await fetchAllByStatuses(
      "/competition-notices/",
      { include_hidden: 1, include_revisions: 1 },
      getReviewStatusApiValues("notices", currentReviewStatus.value),
    );
    pendingNotices.value = results.map((item) => ({
      ...item,
      _reviewNote: item._reviewNote || "",
    }));
  } catch (error) {
    ui.error(getErrorText(error, "赛事公告审核列表加载失败"));
  }
}

async function loadPendingCompetitionSchedules() {
  try {
    const { results } = await fetchAllByStatuses(
      "/competition-schedules/",
      { include_hidden: 1 },
      getReviewStatusApiValues("schedules", currentReviewStatus.value),
    );
    pendingSchedules.value = results.map((item) => ({
      ...item,
      _reviewNote: item._reviewNote || "",
    }));
  } catch (error) {
    ui.error(getErrorText(error, "锦标赛审核列表加载失败"));
  }
}

async function loadPendingTickets() {
  try {
    const params = {};
    if (ticketFilters.kind) params.kind = ticketFilters.kind;
    if (ticketFilters.author.trim())
      params.author = ticketFilters.author.trim();
    if (ticketFilters.search.trim())
      params.search = ticketFilters.search.trim();
    const { results } = await fetchAllByStatuses(
      "/issues/",
      params,
      getReviewStatusApiValues("tickets", currentReviewStatus.value),
    );
    pendingTickets.value = results.map((item) => ({
      ...item,
      _assignTo: item.assignee?.id ? String(item.assignee.id) : "",
      _nextStatus: "open",
      _note: item.resolution_note || "",
    }));
  } catch (error) {
    ui.error(getErrorText(error, "工单列表加载失败"));
  }
}

async function loadPendingComments() {
  try {
    const params = {};
    if (commentFilters.search.trim())
      params.search = commentFilters.search.trim();
    if (commentFilters.author.trim())
      params.author = commentFilters.author.trim();
    if (commentFilters.article.trim())
      params.article = commentFilters.article.trim();
    const { results } = await fetchAllByStatuses(
      "/comments/",
      params,
      getReviewStatusApiValues("comments", currentReviewStatus.value),
    );
    pendingComments.value = results.map((item) => ({
      ...item,
      _reviewNote: item._reviewNote || "",
    }));
    syncSelectedIds(selectedPendingCommentIds, pendingComments.value);
  } catch (error) {
    ui.error(getErrorText(error, "评论列表加载失败"));
  }
}

async function loadPendingTricks() {
  try {
    const params = {
      include_all: 1,
      order: "created_newest",
    };
    if (trickFilters.search.trim()) params.search = trickFilters.search.trim();
    if (trickFilters.term) params.term = trickFilters.term;
    let results = [];
    if (currentReviewStatus.value === "pending") {
      const [standardPayload, deleteReviewPayload] = await Promise.all([
        fetchAllByStatuses("/tricks/", params, ["pending"]),
        fetchAllPages("/tricks/", {
          ...params,
          delete_vote_review_status: "pending",
        }),
      ]);
      const mergedMap = new Map();
      [...standardPayload.results, ...deleteReviewPayload.results].forEach(
        (item) => {
          mergedMap.set(item.id, item);
        },
      );
      results = Array.from(mergedMap.values()).sort((left, right) => {
        const leftTime = new Date(
          left?.updated_at ||
            left?.delete_vote_review_requested_at ||
            left?.created_at ||
            0,
        ).getTime();
        const rightTime = new Date(
          right?.updated_at ||
            right?.delete_vote_review_requested_at ||
            right?.created_at ||
            0,
        ).getTime();
        return rightTime - leftTime;
      });
    } else {
      const payload = await fetchAllByStatuses(
        "/tricks/",
        params,
        getReviewStatusApiValues("tricks", currentReviewStatus.value),
      );
      results = payload.results;
    }
    pendingTricks.value = results.map((item) => ({
      ...item,
      _reviewNote: item._reviewNote || "",
    }));
  } catch (error) {
    ui.error(getErrorText(error, "trick 列表加载失败"));
  }
}

async function loadPendingTrickTermSuggestions() {
  try {
    const { results } = await fetchAllByStatuses(
      "/trick-term-suggestions/",
      {},
      getReviewStatusApiValues("trick_terms", currentReviewStatus.value),
    );
    pendingTrickTermSuggestions.value = results.map((item) => ({
      ...item,
      _reviewNote: item._reviewNote || "",
    }));
  } catch (error) {
    ui.error(getErrorText(error, "词条候选列表加载失败"));
  }
}

async function loadPendingQuestions() {
  try {
    const params = { order: "created_newest" };
    if (questionFilters.search.trim())
      params.search = questionFilters.search.trim();
    if (questionFilters.author.trim())
      params.author = questionFilters.author.trim();
    if (questionFilters.category) params.category = questionFilters.category;
    const { results } = await fetchAllByStatuses(
      "/questions/",
      params,
      getReviewStatusApiValues("questions", currentReviewStatus.value),
    );
    pendingQuestions.value = results.map((item) => ({
      ...item,
      _reviewNote: item._reviewNote || "",
    }));
    syncSelectedIds(selectedPendingQuestionIds, pendingQuestions.value);
  } catch (error) {
    ui.error(getErrorText(error, "问题列表加载失败"));
  }
}

async function loadPendingAnswers() {
  try {
    const params = { order: "latest" };
    if (answerFilters.search.trim())
      params.search = answerFilters.search.trim();
    if (answerFilters.author.trim())
      params.author = answerFilters.author.trim();
    const { results } = await fetchAllByStatuses(
      "/answers/",
      params,
      getReviewStatusApiValues("answers", currentReviewStatus.value),
    );
    pendingAnswers.value = results.map((item) => ({
      ...item,
      _reviewNote: item._reviewNote || "",
    }));
    syncSelectedIds(selectedPendingAnswerIds, pendingAnswers.value);
  } catch (error) {
    ui.error(getErrorText(error, "回答列表加载失败"));
  }
}

async function ensureLoaded(section) {
  switch (section) {
    case "revisions":
      await loadPendingRevisions();
      break;
    case "practice":
      await loadPendingPracticeProposals();
      break;
    case "notices":
      await loadPendingCompetitionNotices();
      break;
    case "schedules":
      await loadPendingCompetitionSchedules();
      break;
    case "tickets":
      await Promise.all([loadPendingTickets(), loadAssigneeOptions()]);
      break;
    case "comments":
      await loadPendingComments();
      break;
    case "tricks":
      await Promise.all([
        loadPendingTricks(),
        trickTerms.value.length ? Promise.resolve() : loadTrickTerms(),
      ]);
      break;
    case "trick_terms":
      await loadPendingTrickTermSuggestions();
      break;
    case "questions":
      await Promise.all([
        loadPendingQuestions(),
        categories.value.length ? Promise.resolve() : loadCategories(),
      ]);
      break;
    case "answers":
      await loadPendingAnswers();
      break;
    default:
      break;
  }
}

async function reloadCurrentSection() {
  await Promise.all([
    loadCounts(),
    loadCurrentHistoryCounts(),
    ensureLoaded(currentSection.value),
  ]);
}

function syncSelectedIds(target, list) {
  const valid = new Set(list.map((item) => item.id));
  target.value = target.value.filter((id) => valid.has(id));
}

function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDate(value) {
  if (!value) return "-";
  return String(value).slice(0, 10);
}

function formatDateRange(startValue, endValue) {
  const start = formatDate(startValue);
  const end = formatDate(endValue || startValue);
  if (start === "-" && end === "-") return "-";
  return `${start} - ${end}`;
}

function formatCount(value) {
  const count = Number(value || 0);
  return count > 99 ? "99+" : String(count);
}

function toggleSelectAllRevisions(checked) {
  selectedPendingRevisionIds.value = checked
    ? pendingRevisions.value.map((item) => item.id)
    : [];
}

function toggleSelectAllComments(checked) {
  selectedPendingCommentIds.value = checked
    ? pendingComments.value.map((item) => item.id)
    : [];
}

function toggleSelectAllQuestions(checked) {
  selectedPendingQuestionIds.value = checked
    ? pendingQuestions.value.map((item) => item.id)
    : [];
}

function toggleSelectAllAnswers(checked) {
  selectedPendingAnswerIds.value = checked
    ? pendingAnswers.value.map((item) => item.id)
    : [];
}

function resetTicketFilters() {
  ticketFilters.kind = "";
  ticketFilters.author = "";
  ticketFilters.search = "";
  loadPendingTickets();
}

function resetTrickFilters() {
  trickFilters.search = "";
  trickFilters.term = "";
  loadPendingTricks();
}

function resetQuestionFilters() {
  questionFilters.search = "";
  questionFilters.author = "";
  questionFilters.category = "";
  loadPendingQuestions();
}

function resetAnswerFilters() {
  answerFilters.search = "";
  answerFilters.author = "";
  loadPendingAnswers();
}

function openRevisionDetail(item) {
  router.push({ name: "review-revision", params: { id: item.id } });
}

function notifyBulkSummary(data, label) {
  const successCount = Number(data?.success || 0);
  const failedCount = Number(data?.failed || 0);
  if (successCount) ui.success(`${label}：成功 ${successCount} 条`);
  if (failedCount) ui.error(`${label}：失败 ${failedCount} 条`);
}

async function bulkReviewRevisions(action) {
  if (!selectedPendingRevisionIds.value.length) {
    ui.info("请先选择修订提议");
    return;
  }
  try {
    const { data } = await api.post("/revisions/bulk-review/", {
      ids: selectedPendingRevisionIds.value,
      action,
      review_note: bulkRevisionReviewNote.value || "",
    });
    notifyBulkSummary(
      data,
      action === "approve" ? "批量通过修订" : "批量驳回修订",
    );
    await reloadCurrentSection();
  } catch (error) {
    ui.error(getErrorText(error, "修订审核失败"));
  }
}

async function reviewPractice(item, action) {
  reviewingPracticeId.value = item.id;
  try {
    await api.post(`/competition-practice-proposals/${item.id}/${action}/`, {
      review_note: item._reviewNote || "",
    });
    ui.success(
      action === "approve" ? "补题链接申请已通过" : "补题链接申请已驳回",
    );
    await reloadCurrentSection();
  } catch (error) {
    ui.error(getErrorText(error, "补题链接审核失败"));
  } finally {
    reviewingPracticeId.value = null;
  }
}

async function reviewCompetitionNotice(item, action) {
  reviewingNoticeId.value = item.id;
  try {
    await api.post(`/competition-notices/${item.id}/${action}/`, {
      review_note: item._reviewNote || "",
    });
    ui.success(action === "approve" ? "赛事公告已通过" : "赛事公告已驳回");
    await reloadCurrentSection();
  } catch (error) {
    ui.error(getErrorText(error, "赛事公告审核失败"));
  } finally {
    reviewingNoticeId.value = null;
  }
}

async function reviewCompetitionSchedule(item, action) {
  reviewingScheduleId.value = item.id;
  try {
    await api.post(`/competition-schedules/${item.id}/${action}/`, {
      review_note: item._reviewNote || "",
    });
    ui.success(action === "approve" ? "锦标赛已通过" : "锦标赛已驳回");
    await reloadCurrentSection();
  } catch (error) {
    ui.error(getErrorText(error, "锦标赛审核失败"));
  } finally {
    reviewingScheduleId.value = null;
  }
}

async function updateTicketStatus(item) {
  try {
    await api.post(`/issues/${item.id}/set_status/`, {
      status: item._nextStatus,
      assign_to: item._assignTo || null,
      resolution_note: item._note || "",
    });
    ui.success("工单已处理");
    await reloadCurrentSection();
  } catch (error) {
    ui.error(getErrorText(error, "工单处理失败"));
  }
}

async function reviewComment(item, action) {
  reviewingCommentId.value = item.id;
  try {
    await api.post(`/comments/${item.id}/${action}/`, {
      review_note: item._reviewNote || "",
    });
    ui.success(action === "approve" ? "评论已通过" : "评论已驳回");
    await reloadCurrentSection();
  } catch (error) {
    ui.error(getErrorText(error, "评论审核失败"));
  } finally {
    reviewingCommentId.value = null;
  }
}

async function bulkReviewComments(action) {
  if (!selectedPendingCommentIds.value.length) {
    ui.info("请先选择评论");
    return;
  }
  try {
    const { data } = await api.post("/comments/bulk-review/", {
      ids: selectedPendingCommentIds.value,
      action,
      review_note: bulkCommentReviewNote.value || "",
    });
    notifyBulkSummary(
      data,
      action === "approve" ? "批量通过评论" : "批量驳回评论",
    );
    await reloadCurrentSection();
  } catch (error) {
    ui.error(getErrorText(error, "评论审核失败"));
  }
}

async function reviewTrick(item, status) {
  reviewingTrickId.value = item.id;
  try {
    await api.post(`/tricks/${item.id}/set-status/`, {
      status,
      review_note: item._reviewNote || "",
    });
    ui.success(status === "approved" ? "trick 已通过" : "trick 已驳回");
    await reloadCurrentSection();
  } catch (error) {
    ui.error(getErrorText(error, "trick 审核失败"));
  } finally {
    reviewingTrickId.value = null;
  }
}

async function resolveTrickDeleteReview(item, action) {
  reviewingTrickId.value = item.id;
  try {
    await api.post(`/tricks/${item.id}/resolve-delete-review/`, {
      action,
      review_note: item._reviewNote || "",
    });
    ui.success(action === "keep" ? "已决定保留 trick" : "已确认删除 trick");
    await reloadCurrentSection();
  } catch (error) {
    ui.error(getErrorText(error, "trick 删除审核失败"));
  } finally {
    reviewingTrickId.value = null;
  }
}

async function reviewTrickTermSuggestion(item, status) {
  reviewingTrickTermSuggestionId.value = item.id;
  try {
    await api.post(`/trick-term-suggestions/${item.id}/set-status/`, {
      status,
      review_note: item._reviewNote || "",
    });
    ui.success(status === "approved" ? "词条候选已通过" : "词条候选已驳回");
    await reloadCurrentSection();
  } catch (error) {
    ui.error(getErrorText(error, "词条候选审核失败"));
  } finally {
    reviewingTrickTermSuggestionId.value = null;
  }
}

async function reviewQuestion(item, action) {
  try {
    await api.post(`/questions/${item.id}/${action}/`, {
      review_note: item._reviewNote || "",
    });
    ui.success(action === "approve" ? "问题已通过" : "问题已驳回");
    await reloadCurrentSection();
  } catch (error) {
    ui.error(getErrorText(error, "问题审核失败"));
  }
}

async function bulkModerateQuestions(action) {
  if (!selectedPendingQuestionIds.value.length) {
    ui.info("请先选择问题");
    return;
  }
  try {
    const { data } = await api.post("/questions/bulk-moderate/", {
      ids: selectedPendingQuestionIds.value,
      action,
      review_note: bulkQuestionReviewNote.value || "",
    });
    notifyBulkSummary(
      data,
      action === "approve" ? "批量通过问题" : "批量驳回问题",
    );
    await reloadCurrentSection();
  } catch (error) {
    ui.error(getErrorText(error, "问题审核失败"));
  }
}

async function reviewAnswer(item, action) {
  try {
    await api.post(`/answers/${item.id}/${action}/`, {
      review_note: item._reviewNote || "",
    });
    ui.success(action === "approve" ? "回答已通过" : "回答已驳回");
    await reloadCurrentSection();
  } catch (error) {
    ui.error(getErrorText(error, "回答审核失败"));
  }
}

async function appendReviewNote(section, item, note) {
  const path = buildAppendReviewNotePath(section, item?.id);
  const payloadNote = String(note || "").trim();
  if (!path || !payloadNote) {
    ui.info("请先填写批注内容");
    return false;
  }

  appendingReviewNoteKey.value = `${section}:${item.id}`;
  try {
    await api.post(path, { note: payloadNote });
    ui.success("管理员批注已追加");
    await reloadCurrentSection();
    return true;
  } catch (error) {
    ui.error(getErrorText(error, "追加批注失败"));
    return false;
  } finally {
    appendingReviewNoteKey.value = "";
  }
}

async function bulkModerateAnswers(action) {
  if (!selectedPendingAnswerIds.value.length) {
    ui.info("请先选择回答");
    return;
  }
  try {
    const { data } = await api.post("/answers/bulk-moderate/", {
      ids: selectedPendingAnswerIds.value,
      action,
      review_note: bulkAnswerReviewNote.value || "",
    });
    notifyBulkSummary(
      data,
      action === "approve" ? "批量通过回答" : "批量驳回答案",
    );
    await reloadCurrentSection();
  } catch (error) {
    ui.error(getErrorText(error, "回答审核失败"));
  }
}

watch(
  () => props.section,
  async (value) => {
    const normalized = normalizeReviewSection(value);
    if (value !== normalized) {
      await router.replace(buildReviewRoute(normalized));
      return;
    }
    window.scrollTo({ top: 0, behavior: "auto" });
    await reloadCurrentSection();
  },
  { immediate: true },
);
</script>

<style scoped>
.review-layout {
  display: grid;
  gap: 16px;
}
.review-card {
  border: 1px solid var(--hairline);
  border-radius: 16px;
  background: var(--surface);
  padding: 14px;
  box-shadow: var(--shadow-sm);
}
.review-shell-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: start;
}
.review-kicker {
  margin: 0 0 4px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--accent);
}
.review-shell-head h1,
.review-card h2 {
  margin: 0 0 8px;
}
.review-tabs {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px;
}
.review-tab {
  border: 1px solid var(--hairline);
  border-radius: 14px;
  background: var(--surface);
  padding: 12px 14px;
  display: grid;
  gap: 6px;
}
.review-tab--active {
  border-color: color-mix(in srgb, var(--accent) 42%, transparent);
  background: color-mix(in srgb, var(--accent) 10%, var(--surface-strong));
}
.review-tab-head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
}
.review-tab-count {
  min-width: 34px;
  text-align: center;
  padding: 2px 10px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--accent) 14%, var(--surface-strong));
  font-weight: 700;
  color: var(--text-strong);
}
.review-status-card {
  display: grid;
  gap: 12px;
}
.review-status-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.review-status-tab {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 999px;
  border: 1px solid var(--hairline);
  background: var(--surface-soft);
  color: var(--text);
}
.review-status-tab--active {
  border-color: color-mix(in srgb, var(--accent) 45%, transparent);
  background: color-mix(in srgb, var(--accent) 14%, var(--surface-strong));
  color: var(--text-strong);
}
.toolbar,
.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.review-actions {
  display: grid;
  gap: 8px;
  align-content: start;
}
.review-action-buttons {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}
.review-action-buttons .btn {
  width: 100%;
  justify-content: center;
}
.check-line {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.grow {
  flex: 1 1 260px;
}
.review-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(280px, 320px);
  gap: 12px;
  padding: 11px 12px;
  margin-top: 10px;
  border-radius: 10px;
  background: var(--surface-soft);
}
.review-main {
  min-width: 0;
}
.ticket-content {
  margin: 8px 0 0;
  white-space: pre-wrap;
  line-height: 1.55;
}
.proposal-preview {
  margin: 8px 0;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--hairline);
  background: var(--surface-strong);
  white-space: pre-wrap;
  font-family: var(--font-mono);
  font-size: 13px;
}
.diff-preview {
  margin-top: 8px;
  max-height: 240px;
  overflow: auto;
  border-radius: 8px;
  border: 1px solid var(--hairline);
  background: var(--surface-strong);
}
.trick-markdown {
  margin-top: 8px;
}
.meta {
  color: var(--text-quiet);
}
@media (max-width: 1100px) {
  .review-shell-head,
  .review-row {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 640px) {
  .review-tabs {
    grid-template-columns: 1fr;
  }
  .review-action-buttons {
    grid-template-columns: 1fr;
  }
}
</style>

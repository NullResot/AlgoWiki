<template>
  <section v-if="profile" class="profile-layout">
    <article class="profile-main">
      <header class="profile-headline">
        <h1>&#x4E2A;&#x4EBA;&#x4E2D;&#x5FC3;</h1>
        <nav class="profile-tabs" aria-label="Profile sub pages">
          <button class="profile-tab" :class="{ 'is-active': activeTab === 'profile' }" @click="activeTab = 'profile'">
            &#x4E2A;&#x4EBA;&#x4FE1;&#x606F;
          </button>
          <button class="profile-tab" :class="{ 'is-active': activeTab === 'interaction' }" @click="activeTab = 'interaction'">
            &#x6211;&#x7684;&#x63D0;&#x95EE;/&#x56DE;&#x7B54;/&#x8BC4;&#x8BBA;
          </button>
          <button class="profile-tab" :class="{ 'is-active': activeTab === 'revision' }" @click="activeTab = 'revision'">
            &#x6211;&#x7684;&#x4FEE;&#x8BA2;&#x610F;&#x89C1;
          </button>
          <button class="profile-tab" :class="{ 'is-active': activeTab === 'issue' }" @click="activeTab = 'issue'">
            &#x6211;&#x7684; Issue / Request
          </button>
        </nav>
      </header>

      <section v-show="activeTab === 'profile'" class="tab-panel">
        <div class="profile-head">
          <img v-if="profile.user.avatar_url" class="avatar" :src="profile.user.avatar_url" alt="avatar" />
          <div>
            <h2>{{ profile.user.username }}</h2>
            <p class="meta">&#x89D2;&#x8272;&#xFF1A;{{ profile.user.role }}</p>
            <p class="meta">&#x5B66;&#x6821;&#xFF1A;{{ profile.user.school_name || "-" }}</p>
            <p class="bio">{{ profile.user.bio || "&#x6682;&#x65E0;&#x4E2A;&#x4EBA;&#x7B80;&#x4ECB;&#x3002;" }}</p>
          </div>
        </div>

        <section class="section-block">
          <h3>&#x6536;&#x85CF;&#x6761;&#x76EE;</h3>
          <div class="event-filters">
            <input
              class="input"
              v-model="starFilters.search"
              placeholder="搜索收藏内容"
              @keyup.enter="loadStarredArticles()"
            />
            <button class="btn btn-mini" @click="loadStarredArticles">筛选</button>
          </div>
          <p class="meta">Total {{ starredMeta.count }}</p>
          <article class="star-row" v-for="item in starredArticles" :key="item.id">
            <RouterLink class="star-link" :to="{ name: 'article', params: { id: item.id } }">
              {{ item.title }}
            </RouterLink>
            <button
              class="btn btn-mini"
              :disabled="unstarLoadingId === item.id"
              @click="unstarFromProfile(item)"
            >
              {{ unstarLoadingId === item.id ? "处理中..." : "取消收藏" }}
            </button>
          </article>
          <button v-if="starredMeta.next" class="btn" @click="loadMoreStarredArticles">
            {{ starredMeta.loadingMore ? "加载中..." : "加载更多" }}
          </button>
          <p v-if="!starredArticles.length" class="meta">暂无收藏条目。</p>
        </section>

        <section class="section-block">
          <h3>&#x8D44;&#x6599;&#x8BBE;&#x7F6E;</h3>
          <div class="settings-grid">
            <input class="input" v-model="profileForm.school_name" placeholder="学校" />
          </div>
          <input class="input" v-model="profileForm.avatar_url" placeholder="头像链接" />
          <textarea class="textarea" v-model="profileForm.bio" placeholder="个人简介"></textarea>
          <button class="btn btn-accent" :disabled="savingProfile" @click="saveProfile">
            {{ savingProfile ? "保存中..." : "保存资料" }}
          </button>
        </section>

        <section class="section-block">
          <h3>&#x90AE;&#x7BB1;&#x9A8C;&#x8BC1; / &#x4FEE;&#x6539;</h3>
          <p class="meta">
            当前邮箱：{{ profile.profile_settings?.email || "-" }}
            <span class="pill" :class="{ 'pill-success': profile.profile_settings?.email_verified }">
              {{ profile.profile_settings?.email_verified ? "已验证" : "未验证" }}
            </span>
          </p>
          <p v-if="profile.profile_settings?.pending_email" class="meta">
            待确认邮箱：{{ profile.profile_settings.pending_email }}
            <span v-if="profile.profile_settings?.pending_email_expires_at">
              （有效至 {{ formatTime(profile.profile_settings.pending_email_expires_at) }}）
            </span>
          </p>
          <div class="settings-grid">
            <input
              class="input"
              v-model="emailChangeForm.email"
              placeholder="新邮箱，或输入当前邮箱重新验证"
              @input="clearEmailChangeSession"
            />
            <input
              class="input"
              type="password"
              v-model="emailChangeForm.current_password"
              placeholder="当前密码"
              @input="clearEmailChangeSession"
            />
          </div>
          <div v-if="emailChangeTicket.token" class="email-verify-card">
            <p class="meta">验证码已发送至 {{ emailChangeTicket.masked_email }}。</p>
            <input class="input" v-model="emailChangeForm.code" placeholder="邮箱验证码" inputmode="numeric" />
          </div>
          <div class="settings-actions">
            <button class="btn" :disabled="sendingEmailCode" @click="sendEmailChangeCode">
              {{ sendingEmailCode ? "发送中..." : emailChangeTicket.token ? "重新发送验证码" : "发送验证码" }}
            </button>
            <button class="btn btn-accent" :disabled="changingEmail || !emailChangeTicket.token" @click="confirmEmailChange">
              {{ changingEmail ? "更新中..." : "确认邮箱" }}
            </button>
          </div>
        </section>

        <section class="section-block">
          <h3>&#x5BC6;&#x7801;&#x4FEE;&#x6539;</h3>
          <div class="settings-grid">
            <div class="password-field">
              <input
                class="input password-input"
                :type="passwordVisibility.old ? 'text' : 'password'"
                v-model="passwordForm.old_password"
                placeholder="当前密码"
                @input="clearPasswordChangeSession"
              />
              <button
                class="password-toggle"
                type="button"
                :aria-label="passwordVisibility.old ? '隐藏密码' : '显示密码'"
                :title="passwordVisibility.old ? '隐藏密码' : '显示密码'"
                @click="togglePasswordVisibility('old')"
              >
                {{ passwordVisibility.old ? "隐藏" : "显示" }}
              </button>
            </div>
            <div class="password-field">
              <input
                class="input password-input"
                :type="passwordVisibility.new ? 'text' : 'password'"
                v-model="passwordForm.new_password"
                placeholder="新密码（至少 8 位）"
                @input="clearPasswordChangeSession"
              />
              <button
                class="password-toggle"
                type="button"
                :aria-label="passwordVisibility.new ? '隐藏密码' : '显示密码'"
                :title="passwordVisibility.new ? '隐藏密码' : '显示密码'"
                @click="togglePasswordVisibility('new')"
              >
                {{ passwordVisibility.new ? "隐藏" : "显示" }}
              </button>
            </div>
          </div>
          <div class="password-field">
            <input
              class="input password-input"
              :type="passwordVisibility.confirm ? 'text' : 'password'"
              v-model="passwordForm.confirm_password"
              placeholder="确认新密码"
              @input="clearPasswordChangeSession"
            />
            <button
              class="password-toggle"
              type="button"
              :aria-label="passwordVisibility.confirm ? '隐藏密码' : '显示密码'"
              :title="passwordVisibility.confirm ? '隐藏密码' : '显示密码'"
              @click="togglePasswordVisibility('confirm')"
            >
              {{ passwordVisibility.confirm ? "隐藏" : "显示" }}
            </button>
          </div>
          <div v-if="passwordChangeTicket.token" class="email-verify-card">
            <p class="meta">验证码已发送至 {{ passwordChangeTicket.masked_email }}。</p>
            <input class="input" v-model="passwordForm.code" placeholder="邮箱验证码" inputmode="numeric" />
          </div>
          <div class="settings-actions">
            <button class="btn" :disabled="sendingPasswordCode" @click="sendPasswordChangeCode">
              {{ sendingPasswordCode ? "发送中..." : passwordChangeTicket.token ? "重新发送验证码" : "发送验证码" }}
            </button>
            <button class="btn btn-accent" :disabled="changingPassword || !passwordChangeTicket.token" @click="changePassword">
              {{ changingPassword ? "更新中..." : "确认修改密码" }}
            </button>
          </div>
        </section>

        <div class="stats-grid">
          <div class="stat-item" v-for="(value, key) in profile.stats" :key="key">
            <strong>{{ value }}</strong>
            <span>{{ key }}</span>
          </div>
        </div>

        <section class="section-block">
          <h3>&#x8D21;&#x732E;&#x5386;&#x53F2;</h3>
          <div class="event-filters">
            <select class="select" v-model="eventFilters.event_type" @change="loadMyEvents()">
              <option value="">全部事件</option>
              <option value="star">收藏</option>
              <option value="comment">评论</option>
              <option value="issue">Issue/Request</option>
              <option value="revision">修订</option>
              <option value="question">提问</option>
              <option value="answer">回答</option>
              <option value="announcement">公告</option>
              <option value="admin">管理操作</option>
            </select>
            <button class="btn btn-mini" @click="loadMyEvents">筛选</button>
          </div>
          <div class="event" v-for="item in myEvents" :key="item.id">
            <span class="pill">{{ formatEventType(item.event_type) }}</span>
            <span class="event-target">{{ item.target_type }} #{{ item.target_id }}</span>
            <span class="meta">{{ formatTime(item.created_at) }}</span>
          </div>
          <button v-if="myEventsMeta.next" class="btn" @click="loadMoreMyEvents">
            {{ myEventsMeta.loadingMore ? "加载中..." : "加载更多" }}
          </button>
          <p v-if="!myEvents.length" class="meta">暂无记录。</p>
        </section>

        <section class="section-block">
          <h3>&#x8D26;&#x53F7;&#x5B89;&#x5168;&#x8BB0;&#x5F55;</h3>
          <p v-if="securitySchemaOutdated" class="meta">安全表结构较旧，请先执行数据库迁移。</p>
          <div class="event-filters">
            <select class="select" v-model="securitySummaryWindow">
              <option :value="24">最近 24 小时</option>
              <option :value="72">最近 72 小时</option>
              <option :value="168">最近 7 天</option>
            </select>
            <button class="btn btn-mini" :disabled="securitySummaryLoading" @click="loadMySecuritySummary">
              {{ securitySummaryLoading ? "刷新中..." : "刷新" }}
            </button>
          </div>
          <div class="security-summary-grid" v-if="mySecuritySummary">
            <div class="security-summary-item">
              <strong>{{ mySecuritySummary.totals?.events ?? 0 }}</strong>
              <span>事件数</span>
            </div>
            <div class="security-summary-item">
              <strong>{{ mySecuritySummary.totals?.login_failed ?? 0 }}</strong>
              <span>登录失败</span>
            </div>
            <div class="security-summary-item">
              <strong>{{ mySecuritySummary.totals?.login_locked ?? 0 }}</strong>
              <span>登录锁定</span>
            </div>
            <div class="security-summary-item">
              <strong>{{ mySecuritySummary.totals?.password_changed ?? 0 }}</strong>
              <span>密码修改</span>
            </div>
          </div>
          <p class="meta" v-if="mySecuritySummary?.since">统计起点：{{ formatTime(mySecuritySummary.since) }}</p>
          <div class="event-filters">
            <select class="select" v-model="securityEventFilters.event_type" @change="loadMySecurityEvents()">
              <option value="">全部事件类型</option>
              <option value="login_success">登录成功</option>
              <option value="login_failed">登录失败</option>
              <option value="login_locked">登录锁定</option>
              <option value="login_denied">登录拒绝</option>
              <option value="register_code_sent">注册验证码发送</option>
              <option value="register_success">注册成功</option>
              <option value="logout">退出登录</option>
              <option value="password_change_requested">密码修改验证码</option>
              <option value="password_changed">密码修改</option>
              <option value="password_reset_requested">找回密码验证码</option>
              <option value="password_reset_completed">找回密码完成</option>
              <option value="email_change_requested">邮箱验证码发送</option>
              <option value="email_changed">邮箱变更</option>
            </select>
            <select class="select" v-model="securityEventFilters.success" @change="loadMySecurityEvents()">
              <option value="">全部结果</option>
              <option value="1">成功</option>
              <option value="0">失败</option>
            </select>
          </div>
          <p class="meta">Total {{ mySecurityEventsMeta.count }}</p>
          <div class="event" v-for="item in mySecurityEvents" :key="item.id">
            <span class="pill">{{ formatSecurityEventType(item.event_type) }}</span>
            <span class="event-target">{{ item.ip_address || "-" }} | {{ item.success ? "成功" : "失败" }}</span>
            <span class="meta">{{ formatTime(item.created_at) }}</span>
            <span class="meta" v-if="item.detail">{{ item.detail }}</span>
          </div>
          <button v-if="mySecurityEventsMeta.next" class="btn" @click="loadMoreMySecurityEvents">
            {{ mySecurityEventsMeta.loadingMore ? "加载中..." : "加载更多" }}
          </button>
          <p v-if="!mySecurityEvents.length" class="meta">暂无安全记录。</p>
        </section>
      </section>

      <section v-show="activeTab === 'interaction'" class="tab-panel">
        <section class="section-block">
          <h3>&#x6211;&#x7684;&#x63D0;&#x95EE;</h3>
          <p class="meta">Total {{ myQuestionsMeta.count }}</p>
          <article class="history-row" v-for="item in myQuestions" :key="item.id">
            <strong>{{ item.title }}</strong>
            <div class="meta">{{ formatModerationStatus(item.status) }} | {{ formatTime(item.created_at) }}</div>
          </article>
          <button v-if="myQuestionsMeta.next" class="btn" @click="loadMoreMyQuestions">
            {{ myQuestionsMeta.loadingMore ? "Loading..." : "Load More" }}
          </button>
          <p v-if="!myQuestions.length" class="meta">No question records.</p>
        </section>

        <section class="section-block">
          <h3>&#x6211;&#x7684;&#x56DE;&#x7B54;</h3>
          <p class="meta">Total {{ myAnswersMeta.count }}</p>
          <article class="history-row" v-for="item in myAnswers" :key="item.id">
            <strong>{{ item.question_title || `Question #${item.question}` }}</strong>
            <div class="meta">
              {{ formatModerationStatus(item.status) }} | {{ item.is_accepted ? "Accepted" : "Not Accepted" }} | {{ formatTime(item.created_at) }}
            </div>
          </article>
          <button v-if="myAnswersMeta.next" class="btn" @click="loadMoreMyAnswers">
            {{ myAnswersMeta.loadingMore ? "Loading..." : "Load More" }}
          </button>
          <p v-if="!myAnswers.length" class="meta">No answer records.</p>
        </section>

        <section class="section-block">
          <h3>&#x6211;&#x7684;&#x8BC4;&#x8BBA;</h3>
          <p class="meta">Total {{ myCommentsMeta.count }}</p>
          <article class="history-row" v-for="item in myComments" :key="item.id">
            <strong>{{ item.article_title || `Article #${item.article}` }}</strong>
            <div class="meta">{{ formatModerationStatus(item.status) }} | {{ formatTime(item.created_at) }}</div>
            <p class="meta">{{ item.content }}</p>
            <button
              v-if="item.status !== 'hidden'"
              class="btn btn-mini"
              :disabled="deletingMyCommentId === item.id"
              @click="deleteMyComment(item)"
            >
              {{ deletingMyCommentId === item.id ? "Processing..." : "Delete" }}
            </button>
          </article>
          <button v-if="myCommentsMeta.next" class="btn" @click="loadMoreMyComments">
            {{ myCommentsMeta.loadingMore ? "Loading..." : "Load More" }}
          </button>
          <p v-if="!myComments.length" class="meta">No comment records.</p>
        </section>
      </section>

      <section v-show="activeTab === 'revision'" class="tab-panel">
        <section class="section-block">
          <h3>&#x6211;&#x7684;&#x4FEE;&#x8BA2;&#x610F;&#x89C1;</h3>
          <p class="meta">Total {{ myRevisionsMeta.count }} | Pending {{ pendingRevisionCount }}/5</p>
          <div class="revision-filters">
            <select class="select" v-model="revisionFilters.status" @change="loadMyRevisions()">
              <option value="">All Status</option>
              <option value="pending">pending</option>
              <option value="approved">approved</option>
              <option value="rejected">rejected</option>
            </select>
            <input
              class="input"
              v-model="revisionFilters.search"
              placeholder="Search title or note"
              @keyup.enter="loadMyRevisions()"
            />
            <button class="btn" @click="loadMyRevisions">Filter</button>
            <button class="btn" @click="resetRevisionFilters">Reset</button>
          </div>
          <article
            class="history-row revision-row"
            :class="{ 'is-expanded': expandedRevisionId === item.id }"
            v-for="item in myRevisions"
            :key="item.id"
          >
            <button class="revision-card-trigger" @click="toggleRevisionDetails(item.id)">
              <strong>{{ item.article_title || item.proposed_title || `Article #${item.article}` }}</strong>
              <div class="meta">{{ formatModerationStatus(item.status) }} | {{ formatTime(item.created_at) }}</div>
              <p class="meta">
                {{ (item.reason || item.proposed_summary || item.proposed_content_md || "").slice(0, 120) || "No description." }}
              </p>
            </button>

            <div v-if="expandedRevisionId === item.id" class="revision-detail" @click.stop>
              <template v-if="editingRevisionId === item.id">
                <input class="input" v-model="revisionEditForm.proposed_title" placeholder="Proposed title" />
                <textarea class="textarea" v-model="revisionEditForm.proposed_summary" placeholder="Proposed summary"></textarea>
                <textarea
                  class="textarea revision-editor-content"
                  v-model="revisionEditForm.proposed_content_md"
                  placeholder="Markdown content"
                ></textarea>
                <textarea class="textarea" v-model="revisionEditForm.reason" placeholder="Reason"></textarea>
                <div class="revision-actions">
                  <button
                    class="btn btn-mini"
                    :disabled="savingRevisionEditId === item.id"
                    @click="saveRevisionEdit(item)"
                  >
                    {{ savingRevisionEditId === item.id ? "Saving..." : "Save Changes" }}
                  </button>
                  <button class="btn btn-mini" :disabled="savingRevisionEditId === item.id" @click="cancelRevisionEdit">
                    Discard
                  </button>
                </div>
              </template>
              <template v-else>
                <p class="meta"><strong>Proposed title:</strong> {{ item.proposed_title || "-" }}</p>
                <p class="meta"><strong>Proposed summary:</strong> {{ item.proposed_summary || "-" }}</p>
                <p class="meta" v-if="item.reason"><strong>Reason:</strong> {{ item.reason }}</p>
                <p class="meta" v-if="item.review_note"><strong>Review note:</strong> {{ item.review_note }}</p>
                <p class="meta"><strong>Submitted markdown:</strong></p>
                <pre class="revision-content-preview">{{ item.proposed_content_md }}</pre>
                <div class="revision-actions" v-if="item.status === 'pending'">
                  <button class="btn btn-mini" @click="startEditRevision(item)">Edit</button>
                  <button
                    class="btn btn-mini"
                    :disabled="cancellingRevisionId === item.id"
                    @click="cancelRevision(item)"
                  >
                    {{ cancellingRevisionId === item.id ? "Cancelling..." : "Cancel Proposal" }}
                  </button>
                </div>
              </template>
            </div>
          </article>
          <button v-if="myRevisionsMeta.next" class="btn" @click="loadMoreMyRevisions">
            {{ myRevisionsMeta.loadingMore ? "Loading..." : "Load More" }}
          </button>
          <p v-if="!myRevisions.length" class="meta">No revision records.</p>
        </section>
      </section>

      <section v-show="activeTab === 'issue'" class="tab-panel">
        <section class="section-block my-issues">
          <h3>&#x6211;&#x7684; Issue / Request</h3>
          <p class="meta">Total {{ issuesMeta.count }}</p>
          <div class="issue-form">
            <select class="select" v-model="issueForm.kind">
              <option value="issue">Issue</option>
              <option value="request">Request</option>
            </select>
            <select class="select" v-model="issueForm.visibility">
              <option value="public">公开</option>
              <option value="private">个人</option>
            </select>
            <input class="input" v-model="issueForm.title" placeholder="Title" />
            <textarea class="textarea" v-model="issueForm.content" placeholder="Description"></textarea>
            <button class="btn" @click="submitIssue">Submit</button>
          </div>

          <div class="issue-filters">
            <select class="select" v-model="issueFilters.scope" @change="loadIssues()">
              <option value="mine">我的</option>
              <option value="all">全部</option>
            </select>
            <select class="select" v-model="issueFilters.kind" @change="loadIssues()">
              <option value="">All Types</option>
              <option value="issue">Issue</option>
              <option value="request">Request</option>
            </select>
            <select class="select" v-model="issueFilters.visibility" @change="loadIssues()">
              <option value="">全部可见性</option>
              <option value="private">个人</option>
              <option value="public">公开</option>
            </select>
            <select class="select" v-model="issueFilters.status" @change="loadIssues()">
              <option value="">All Status</option>
              <option value="pending">pending</option>
              <option value="open">open</option>
              <option value="in_progress">in_progress</option>
              <option value="resolved">resolved</option>
              <option value="rejected">rejected</option>
            </select>
            <input class="input" v-model="issueFilters.search" placeholder="Search title or description" @keyup.enter="loadIssues()" />
            <button class="btn" @click="loadIssues">Filter</button>
            <button class="btn" @click="resetIssueFilters">Reset</button>
          </div>

          <article class="issue-row" v-for="item in issues" :key="item.id">
            <strong>{{ item.title }}</strong>
            <div class="meta">
              {{ item.kind }} | {{ formatIssueVisibility(item.visibility) }} | {{ formatModerationStatus(item.status) }} | {{ formatTime(item.created_at) }}
            </div>
            <p class="meta" v-if="issueFilters.scope === 'all' && item.author">
              Author: {{ item.author.username }}
            </p>
            <p class="meta" v-if="item.related_article_title">Related Article: {{ item.related_article_title }}</p>
            <p class="issue-note" v-if="item.resolution_note">Note: {{ item.resolution_note }}</p>
          </article>
          <button v-if="issuesMeta.next" class="btn" @click="loadMoreIssues">
            {{ issuesMeta.loadingMore ? "Loading..." : "Load More" }}
          </button>
          <p v-if="!issues.length" class="meta">No Issue / Request records.</p>
        </section>
      </section>
    </article>
  </section>
</template>



<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { RouterLink } from "vue-router";

import api from "../services/api";
import { useAuthStore } from "../stores/auth";
import { useUiStore } from "../stores/ui";

const auth = useAuthStore();
const ui = useUiStore();
const profile = ref(null);
const issues = ref([]);
const myQuestions = ref([]);
const myAnswers = ref([]);
const myComments = ref([]);
const myRevisions = ref([]);
const myEvents = ref([]);
const mySecurityEvents = ref([]);
const mySecuritySummary = ref(null);
const starredArticles = ref([]);
const activeTab = ref("profile");
const expandedRevisionId = ref(null);
const editingRevisionId = ref(null);
const savingProfile = ref(false);
const changingPassword = ref(false);
const sendingPasswordCode = ref(false);
const sendingEmailCode = ref(false);
const changingEmail = ref(false);
const securitySummaryLoading = ref(false);
const unstarLoadingId = ref(null);
const deletingMyCommentId = ref(null);
const savingRevisionEditId = ref(null);
const cancellingRevisionId = ref(null);
const securitySummaryWindow = ref(24);
const securitySchemaOutdated = ref(false);
const pendingRevisionTotal = ref(0);

const issuesMeta = reactive({
  count: 0,
  next: "",
  loadingMore: false,
});

const myQuestionsMeta = reactive({
  count: 0,
  next: "",
  loadingMore: false,
});

const myAnswersMeta = reactive({
  count: 0,
  next: "",
  loadingMore: false,
});

const myCommentsMeta = reactive({
  count: 0,
  next: "",
  loadingMore: false,
});

const myRevisionsMeta = reactive({
  count: 0,
  next: "",
  loadingMore: false,
});

const myEventsMeta = reactive({
  count: 0,
  next: "",
  loadingMore: false,
});

const mySecurityEventsMeta = reactive({
  count: 0,
  next: "",
  loadingMore: false,
});

const starredMeta = reactive({
  count: 0,
  next: "",
  loadingMore: false,
});

const issueForm = reactive({
  kind: "issue",
  visibility: "public",
  title: "",
  content: "",
});

const issueFilters = reactive({
  scope: "mine",
  kind: "",
  visibility: "",
  status: "",
  search: "",
});

const eventFilters = reactive({
  event_type: "",
});

const securityEventFilters = reactive({
  event_type: "",
  success: "",
});

const revisionFilters = reactive({
  status: "",
  search: "",
});

const revisionEditForm = reactive({
  proposed_title: "",
  proposed_summary: "",
  proposed_content_md: "",
  reason: "",
});

const starFilters = reactive({
  search: "",
});

const profileForm = reactive({
  school_name: "",
  bio: "",
  avatar_url: "",
});

const emailChangeForm = reactive({
  email: "",
  current_password: "",
  code: "",
});

const emailChangeTicket = reactive({
  token: "",
  masked_email: "",
  expires_in_seconds: 0,
});

const passwordChangeTicket = reactive({
  token: "",
  masked_email: "",
  expires_in_seconds: 0,
});

const passwordForm = reactive({
  old_password: "",
  new_password: "",
  confirm_password: "",
  code: "",
});

const passwordVisibility = reactive({
  old: false,
  new: false,
  confirm: false,
});

const pendingRevisionCount = computed(() => pendingRevisionTotal.value);

function formatTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function formatModerationStatus(value) {
  const map = {
    pending: "审核中",
    approved: "通过",
    rejected: "驳回",
    visible: "已展示",
    hidden: "已隐藏",
    open: "open",
    in_progress: "in_progress",
    resolved: "resolved",
  };
  return map[value] || value || "-";
}

function formatIssueVisibility(value) {
  const map = {
    private: "个人",
    public: "公开",
  };
  return map[value] || value || "-";
}

function nextPageFromUrl(url, fallback = 2) {
  if (!url) return fallback;
  try {
    return Number(new URL(url, window.location.origin).searchParams.get("page") || String(fallback));
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

function isSchemaOutdatedError(error) {
  return error?.response?.data?.code === "schema_outdated";
}

function applyProfileForm(data) {
  profileForm.school_name = data?.school_name || "";
  profileForm.bio = data?.bio || "";
  profileForm.avatar_url = data?.avatar_url || "";
}

function clearEmailChangeSession() {
  emailChangeTicket.token = "";
  emailChangeTicket.masked_email = "";
  emailChangeTicket.expires_in_seconds = 0;
  emailChangeForm.code = "";
}

function applyEmailChangeDefaults(data) {
  const pendingEmail = data?.pending_email || "";
  emailChangeForm.email = pendingEmail || data?.email || "";
  emailChangeForm.current_password = "";
  clearEmailChangeSession();
}

function clearPasswordChangeSession() {
  passwordChangeTicket.token = "";
  passwordChangeTicket.masked_email = "";
  passwordChangeTicket.expires_in_seconds = 0;
  passwordForm.code = "";
}

function resetPasswordVisibility() {
  passwordVisibility.old = false;
  passwordVisibility.new = false;
  passwordVisibility.confirm = false;
}

function togglePasswordVisibility(key) {
  if (!(key in passwordVisibility)) return;
  passwordVisibility[key] = !passwordVisibility[key];
}

function clearRevisionEditForm() {
  revisionEditForm.proposed_title = "";
  revisionEditForm.proposed_summary = "";
  revisionEditForm.proposed_content_md = "";
  revisionEditForm.reason = "";
}

function toggleRevisionDetails(revisionId) {
  if (expandedRevisionId.value === revisionId) {
    expandedRevisionId.value = null;
    editingRevisionId.value = null;
    clearRevisionEditForm();
    return;
  }
  expandedRevisionId.value = revisionId;
  editingRevisionId.value = null;
  clearRevisionEditForm();
}

function startEditRevision(item) {
  if (!item || item.status !== "pending") return;
  expandedRevisionId.value = item.id;
  editingRevisionId.value = item.id;
  revisionEditForm.proposed_title = item.proposed_title || item.article_title || "";
  revisionEditForm.proposed_summary = item.proposed_summary || "";
  revisionEditForm.proposed_content_md = item.proposed_content_md || "";
  revisionEditForm.reason = item.reason || "";
}

function cancelRevisionEdit() {
  editingRevisionId.value = null;
  clearRevisionEditForm();
}

async function loadProfile() {
  const { data } = await api.get("/me/");
  profile.value = data;
  const settings = data.profile_settings || data.user || {};
  applyProfileForm(settings);
  applyEmailChangeDefaults(settings);
}

async function loadIssues(page = 1, append = false) {
  const params = { page };
  if (issueFilters.scope !== "all") params.mine = 1;
  if (issueFilters.kind) params.kind = issueFilters.kind;
  if (issueFilters.visibility) params.visibility = issueFilters.visibility;
  if (issueFilters.status) params.status = issueFilters.status;
  if (issueFilters.search.trim()) params.search = issueFilters.search.trim();
  const { data } = await api.get("/issues/", { params });
  const parsed = unpackListPayload(data, issues.value.length);
  issues.value = append ? [...issues.value, ...parsed.results] : parsed.results;
  issuesMeta.count = parsed.count;
  issuesMeta.next = parsed.next;
}

async function loadMyQuestions(page = 1, append = false) {
  const { data } = await api.get("/questions/mine/", { params: { page } });
  const parsed = unpackListPayload(data, myQuestions.value.length);
  myQuestions.value = append ? [...myQuestions.value, ...parsed.results] : parsed.results;
  myQuestionsMeta.count = parsed.count;
  myQuestionsMeta.next = parsed.next;
}

async function loadMyAnswers(page = 1, append = false) {
  const { data } = await api.get("/answers/mine/", { params: { page } });
  const parsed = unpackListPayload(data, myAnswers.value.length);
  myAnswers.value = append ? [...myAnswers.value, ...parsed.results] : parsed.results;
  myAnswersMeta.count = parsed.count;
  myAnswersMeta.next = parsed.next;
}

async function loadMyComments(page = 1, append = false) {
  const { data } = await api.get("/comments/mine/", { params: { page } });
  const parsed = unpackListPayload(data, myComments.value.length);
  myComments.value = append ? [...myComments.value, ...parsed.results] : parsed.results;
  myCommentsMeta.count = parsed.count;
  myCommentsMeta.next = parsed.next;
}

async function loadMyRevisions(page = 1, append = false) {
  const params = { page };
  if (auth.user?.id) params.proposer = auth.user.id;
  if (revisionFilters.status) params.status = revisionFilters.status;
  if (revisionFilters.search.trim()) params.search = revisionFilters.search.trim();
  const { data } = await api.get("/revisions/", { params });
  const parsed = unpackListPayload(data, myRevisions.value.length);
  myRevisions.value = append ? [...myRevisions.value, ...parsed.results] : parsed.results;
  myRevisionsMeta.count = parsed.count;
  myRevisionsMeta.next = parsed.next;
  if (!append) {
    await loadMyRevisionPendingCount();
    if (expandedRevisionId.value && !myRevisions.value.some((item) => item.id === expandedRevisionId.value)) {
      expandedRevisionId.value = null;
      cancelRevisionEdit();
    }
  }
}

async function loadMyRevisionPendingCount() {
  const params = { page: 1, status: "pending" };
  if (auth.user?.id) params.proposer = auth.user.id;
  const { data } = await api.get("/revisions/", { params });
  const parsed = unpackListPayload(data, 0);
  pendingRevisionTotal.value = parsed.count;
}

async function loadMyEvents(page = 1, append = false) {
  const params = { page };
  if (eventFilters.event_type) params.event_type = eventFilters.event_type;
  const { data } = await api.get("/me/events/", { params });
  const parsed = unpackListPayload(data, myEvents.value.length);
  myEvents.value = append ? [...myEvents.value, ...parsed.results] : parsed.results;
  myEventsMeta.count = parsed.count;
  myEventsMeta.next = parsed.next;
}

async function loadMySecurityEvents(page = 1, append = false) {
  try {
    const params = { page };
    if (securityEventFilters.event_type) params.event_type = securityEventFilters.event_type;
    if (securityEventFilters.success) params.success = securityEventFilters.success;
    const { data } = await api.get("/me/security-events/", { params });
    const parsed = unpackListPayload(data, mySecurityEvents.value.length);
    mySecurityEvents.value = append ? [...mySecurityEvents.value, ...parsed.results] : parsed.results;
    mySecurityEventsMeta.count = parsed.count;
    mySecurityEventsMeta.next = parsed.next;
  } catch (error) {
    if (isSchemaOutdatedError(error)) {
      securitySchemaOutdated.value = true;
      mySecurityEvents.value = [];
      mySecurityEventsMeta.count = 0;
      mySecurityEventsMeta.next = "";
      return;
    }
    throw error;
  }
}

async function loadMySecuritySummary() {
  securitySummaryLoading.value = true;
  try {
    const { data } = await api.get("/me/security-summary/", {
      params: { window_hours: securitySummaryWindow.value },
    });
    mySecuritySummary.value = data;
  } catch (error) {
    if (isSchemaOutdatedError(error)) {
      securitySchemaOutdated.value = true;
      mySecuritySummary.value = null;
      return;
    }
    ui.error(getErrorText(error, "安全概览加载失败"));
  } finally {
    securitySummaryLoading.value = false;
  }
}

async function loadStarredArticles(page = 1, append = false) {
  const params = { page };
  if (starFilters.search.trim()) params.search = starFilters.search.trim();
  const { data } = await api.get("/articles/starred/", { params });
  const parsed = unpackListPayload(data, starredArticles.value.length);
  starredArticles.value = append ? [...starredArticles.value, ...parsed.results] : parsed.results;
  starredMeta.count = parsed.count;
  starredMeta.next = parsed.next;
}

async function loadMoreIssues() {
  if (!issuesMeta.next || issuesMeta.loadingMore) return;
  issuesMeta.loadingMore = true;
  try {
    await loadIssues(nextPageFromUrl(issuesMeta.next), true);
  } finally {
    issuesMeta.loadingMore = false;
  }
}

async function loadMoreMyQuestions() {
  if (!myQuestionsMeta.next || myQuestionsMeta.loadingMore) return;
  myQuestionsMeta.loadingMore = true;
  try {
    await loadMyQuestions(nextPageFromUrl(myQuestionsMeta.next), true);
  } finally {
    myQuestionsMeta.loadingMore = false;
  }
}

async function loadMoreMyAnswers() {
  if (!myAnswersMeta.next || myAnswersMeta.loadingMore) return;
  myAnswersMeta.loadingMore = true;
  try {
    await loadMyAnswers(nextPageFromUrl(myAnswersMeta.next), true);
  } finally {
    myAnswersMeta.loadingMore = false;
  }
}

async function loadMoreMyComments() {
  if (!myCommentsMeta.next || myCommentsMeta.loadingMore) return;
  myCommentsMeta.loadingMore = true;
  try {
    await loadMyComments(nextPageFromUrl(myCommentsMeta.next), true);
  } finally {
    myCommentsMeta.loadingMore = false;
  }
}

async function loadMoreMyEvents() {
  if (!myEventsMeta.next || myEventsMeta.loadingMore) return;
  myEventsMeta.loadingMore = true;
  try {
    await loadMyEvents(nextPageFromUrl(myEventsMeta.next), true);
  } finally {
    myEventsMeta.loadingMore = false;
  }
}

async function loadMoreMySecurityEvents() {
  if (!mySecurityEventsMeta.next || mySecurityEventsMeta.loadingMore) return;
  mySecurityEventsMeta.loadingMore = true;
  try {
    await loadMySecurityEvents(nextPageFromUrl(mySecurityEventsMeta.next), true);
  } finally {
    mySecurityEventsMeta.loadingMore = false;
  }
}

async function loadMoreMyRevisions() {
  if (!myRevisionsMeta.next || myRevisionsMeta.loadingMore) return;
  myRevisionsMeta.loadingMore = true;
  try {
    await loadMyRevisions(nextPageFromUrl(myRevisionsMeta.next), true);
  } finally {
    myRevisionsMeta.loadingMore = false;
  }
}

async function loadMoreStarredArticles() {
  if (!starredMeta.next || starredMeta.loadingMore) return;
  starredMeta.loadingMore = true;
  try {
    await loadStarredArticles(nextPageFromUrl(starredMeta.next), true);
  } finally {
    starredMeta.loadingMore = false;
  }
}

function resetIssueFilters() {
  issueFilters.scope = "mine";
  issueFilters.kind = "";
  issueFilters.visibility = "";
  issueFilters.status = "";
  issueFilters.search = "";
  loadIssues(1, false);
}

function resetRevisionFilters() {
  revisionFilters.status = "";
  revisionFilters.search = "";
  expandedRevisionId.value = null;
  cancelRevisionEdit();
  loadMyRevisions(1, false);
}

async function saveRevisionEdit(item) {
  if (!item?.id || savingRevisionEditId.value) return;
  if (!revisionEditForm.proposed_title.trim() || !revisionEditForm.proposed_content_md.trim()) {
    ui.info("Title and markdown content are required.");
    return;
  }

  savingRevisionEditId.value = item.id;
  try {
    const payload = {
      proposed_title: revisionEditForm.proposed_title.trim(),
      proposed_summary: revisionEditForm.proposed_summary.trim(),
      proposed_content_md: revisionEditForm.proposed_content_md,
      reason: revisionEditForm.reason.trim(),
    };
    await api.patch(`/revisions/${item.id}/`, payload);
    ui.success("Revision proposal updated.");
    cancelRevisionEdit();
    await loadMyRevisions(1, false);
    expandedRevisionId.value = item.id;
  } catch (error) {
    ui.error(getErrorText(error, "Failed to update revision proposal"));
  } finally {
    savingRevisionEditId.value = null;
  }
}

async function cancelRevision(item) {
  if (!item?.id || item.status !== "pending" || cancellingRevisionId.value) return;
  if (!window.confirm("Cancel this pending revision proposal?")) return;

  cancellingRevisionId.value = item.id;
  try {
    await api.delete(`/revisions/${item.id}/`);
    ui.success("Revision proposal cancelled.");
    if (expandedRevisionId.value === item.id) {
      expandedRevisionId.value = null;
      cancelRevisionEdit();
    }
    await loadMyRevisions(1, false);
  } catch (error) {
    ui.error(getErrorText(error, "Failed to cancel revision proposal"));
  } finally {
    cancellingRevisionId.value = null;
  }
}

async function saveProfile() {
  if (savingProfile.value) return;
  savingProfile.value = true;
  try {
    const payload = {
      school_name: profileForm.school_name.trim(),
      bio: profileForm.bio.trim(),
      avatar_url: profileForm.avatar_url.trim(),
    };
    const { data } = await api.patch("/me/", payload);
    if (profile.value) {
      profile.value.user = data.user || profile.value.user;
      profile.value.profile_settings = data.profile_settings || payload;
    }
    applyProfileForm(data.profile_settings || data.user || {});
    if (auth.user && data.user) {
      auth.applyAuth(auth.token, data.user);
    }
    ui.success("个人资料已更新");
  } catch (error) {
    ui.error(getErrorText(error, "保存资料失败"));
  } finally {
    savingProfile.value = false;
  }
}

async function sendEmailChangeCode() {
  if (sendingEmailCode.value) return;
  if (!emailChangeForm.email.trim() || !emailChangeForm.current_password) {
    ui.info("请填写目标邮箱和当前密码");
    return;
  }

  sendingEmailCode.value = true;
  try {
    const { data } = await api.post("/me/email-code/", {
      email: emailChangeForm.email.trim(),
      current_password: emailChangeForm.current_password,
    });
    emailChangeTicket.token = data.ticket_token || "";
    emailChangeTicket.masked_email = data.masked_email || "";
    emailChangeTicket.expires_in_seconds = Number(data.expires_in_seconds || 0);
    emailChangeForm.code = "";
    if (profile.value?.profile_settings) {
      profile.value.profile_settings.pending_email = emailChangeForm.email.trim();
    }
    ui.success(`验证码已发送至 ${emailChangeTicket.masked_email}`);
  } catch (error) {
    ui.error(getErrorText(error, "邮箱验证码发送失败"));
  } finally {
    sendingEmailCode.value = false;
  }
}

async function confirmEmailChange() {
  if (changingEmail.value) return;
  if (!emailChangeTicket.token || !emailChangeForm.code.trim()) {
    ui.info("请先发送验证码并填写收到的验证码");
    return;
  }

  changingEmail.value = true;
  try {
    const { data } = await api.post("/me/change-email/", {
      ticket_token: emailChangeTicket.token,
      code: emailChangeForm.code.trim(),
    });
    if (profile.value) {
      profile.value.user = data.user || profile.value.user;
      profile.value.profile_settings = data.profile_settings || profile.value.profile_settings;
    }
    applyEmailChangeDefaults(data.profile_settings || {});
    if (auth.user && data.user) {
      auth.applyAuth(auth.token, data.user);
    }
    ui.success("邮箱已更新并验证");
  } catch (error) {
    ui.error(getErrorText(error, "邮箱确认失败"));
  } finally {
    changingEmail.value = false;
  }
}

async function sendPasswordChangeCode() {
  if (sendingPasswordCode.value) return;
  if (!passwordForm.old_password || !passwordForm.new_password || !passwordForm.confirm_password) {
    ui.info("请完整填写密码信息");
    return;
  }

  sendingPasswordCode.value = true;
  try {
    const { data } = await api.post("/me/change-password-code/", {
      old_password: passwordForm.old_password,
      new_password: passwordForm.new_password,
      confirm_password: passwordForm.confirm_password,
    });
    passwordChangeTicket.token = data.ticket_token || "";
    passwordChangeTicket.masked_email = data.masked_email || "";
    passwordChangeTicket.expires_in_seconds = Number(data.expires_in_seconds || 0);
    passwordForm.code = "";
    ui.success(`验证码已发送至 ${passwordChangeTicket.masked_email}`);
  } catch (error) {
    ui.error(getErrorText(error, "密码验证码发送失败"));
  } finally {
    sendingPasswordCode.value = false;
  }
}

async function submitIssue() {
  if (!issueForm.title.trim() || !issueForm.content.trim()) {
    ui.info("请填写标题和问题描述");
    return;
  }
  try {
    const { data } = await api.post("/issues/", {
      kind: issueForm.kind,
      visibility: issueForm.visibility,
      title: issueForm.title.trim(),
      content: issueForm.content.trim(),
    });
    issueForm.title = "";
    issueForm.content = "";
    if (data?.status === "pending") {
      ui.success("Issue/Request 已提交（审核中）");
    } else {
      ui.success("Issue/Request 已提交");
    }
    await loadIssues(1, false);
  } catch (error) {
    ui.error(getErrorText(error, "提交失败"));
  }
}

async function deleteMyComment(item) {
  if (!item?.id || deletingMyCommentId.value) return;
  deletingMyCommentId.value = item.id;
  try {
    await api.delete(`/comments/${item.id}/`);
    ui.success("评论已删除");
    await Promise.all([loadProfile(), loadMyComments()]);
  } catch (error) {
    ui.error(getErrorText(error, "删除评论失败"));
  } finally {
    deletingMyCommentId.value = null;
  }
}

async function unstarFromProfile(item) {
  if (!item?.id || unstarLoadingId.value) return;
  unstarLoadingId.value = item.id;
  try {
    await api.post(`/articles/${item.id}/unstar/`);
    ui.success("已取消收藏");
    await Promise.all([loadProfile(), loadStarredArticles()]);
  } catch (error) {
    ui.error(getErrorText(error, "取消收藏失败"));
  } finally {
    unstarLoadingId.value = null;
  }
}

async function changePassword() {
  if (changingPassword.value) return;
  if (!passwordChangeTicket.token || !passwordForm.code.trim()) {
    ui.info("请先发送验证码并填写收到的验证码");
    return;
  }

  changingPassword.value = true;
  try {
    const { data } = await api.post("/me/change-password/", {
      ticket_token: passwordChangeTicket.token,
      code: passwordForm.code.trim(),
    });
    const nextUser = auth.user || profile.value?.user || null;
    if (data?.token && nextUser) {
      auth.applyAuth(data.token, nextUser);
    }
    passwordForm.old_password = "";
    passwordForm.new_password = "";
    passwordForm.confirm_password = "";
    clearPasswordChangeSession();
    resetPasswordVisibility();
    ui.success("密码修改成功");
    await Promise.all([loadMySecurityEvents(), loadMySecuritySummary()]);
  } catch (error) {
    ui.error(getErrorText(error, "密码修改失败"));
  } finally {
    changingPassword.value = false;
  }
}

function formatEventType(value) {
  const labels = {
    star: "收藏",
    comment: "评论",
    issue: "Issue/Request",
    revision: "修订",
    question: "提问",
    answer: "回答",
    announcement: "公告",
    admin: "管理操作",
  };
  return labels[value] || value || "未知事件";
}

function formatSecurityEventType(value) {
  const labels = {
    login_success: "登录成功",
    login_failed: "登录失败",
    login_locked: "登录锁定",
    login_denied: "登录拒绝",
    register_code_sent: "注册验证码发送",
    register_success: "注册成功",
    logout: "退出登录",
    password_change_requested: "密码修改验证码",
    password_changed: "密码修改",
    password_reset_requested: "找回密码验证码",
    password_reset_completed: "找回密码完成",
    email_change_requested: "邮箱验证码发送",
    email_changed: "邮箱变更",
    user_banned: "账号封禁",
    user_unbanned: "账号解封",
    user_soft_deleted: "账号软删除",
    user_reactivated: "账号恢复",
    user_role_changed: "角色变更",
  };
  return labels[value] || value || "未知事件";
}

onMounted(async () => {
  try {
    await Promise.all([
      loadProfile(),
      loadIssues(),
      loadMyQuestions(),
      loadMyAnswers(),
      loadMyComments(),
      loadMyRevisions(),
      loadMyEvents(),
      loadMySecurityEvents(),
      loadMySecuritySummary(),
      loadStarredArticles(),
    ]);
  } catch (error) {
    ui.error(getErrorText(error, "个人中心加载失败"));
  }
});
</script>

<style scoped>
.profile-layout {
  display: block;
}

.profile-main {
  border: 1px solid var(--hairline);
  border-radius: 16px;
  background: var(--surface);
  padding: 18px;
  box-shadow: var(--shadow-sm);
}

.profile-headline {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
}

.profile-main h1 {
  font-size: 34px;
  margin: 0;
}

.profile-main h2 {
  font-size: 28px;
}

.profile-tabs {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.profile-tab {
  border: 1px solid var(--hairline);
  background: var(--surface-strong);
  color: var(--text-soft);
  border-radius: 999px;
  padding: 7px 14px;
  font-size: 14px;
  line-height: 1;
  cursor: pointer;
  transition: all 0.2s ease;
}

.profile-tab:hover {
  border-color: var(--hairline-strong);
  color: var(--text-strong);
}

.profile-tab.is-active {
  border-color: color-mix(in srgb, var(--accent) 35%, transparent);
  background: color-mix(in srgb, var(--accent) 12%, var(--surface-strong));
  color: var(--accent);
  font-weight: 600;
}

.tab-panel {
  margin-top: 14px;
}

.profile-head {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  border: 1px solid var(--hairline);
  border-radius: 12px;
  background: var(--surface-soft);
  padding: 12px;
}

.avatar {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  object-fit: cover;
  border: 1px solid var(--hairline);
}

.bio {
  margin: 8px 0 0;
  color: var(--text);
  font-size: 17px;
}

.section-block {
  margin-top: 14px;
  padding: 12px;
  border: 1px solid var(--hairline);
  border-radius: 12px;
  background: var(--surface-soft);
}

.section-block h3 {
  margin-bottom: 10px;
  font-size: 24px;
}

.settings-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 8px;
}

.section-block .input,
.section-block .textarea {
  margin-bottom: 8px;
}

.settings-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.email-verify-card {
  margin-bottom: 8px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--hairline);
  background: var(--surface-strong);
}

.password-field {
  position: relative;
}

.password-input {
  padding-right: 64px;
}

.password-toggle {
  position: absolute;
  top: 50%;
  right: 14px;
  transform: translateY(-50%);
  border: 0;
  background: transparent;
  padding: 0;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-soft);
  cursor: pointer;
}

.password-toggle:hover {
  color: var(--accent);
}

.pill {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 12px;
  margin-left: 8px;
  background: var(--surface-strong);
  color: var(--text-soft);
}

.pill-success {
  background: color-mix(in srgb, var(--accent) 16%, var(--surface-strong));
  color: var(--accent);
}

.stats-grid {
  margin-top: 14px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.stat-item {
  border: 1px solid var(--hairline);
  border-radius: 10px;
  padding: 11px;
  background: var(--surface-soft);
  box-shadow: var(--shadow-sm);
  display: grid;
  gap: 4px;
}

.stat-item strong {
  font-size: 22px;
}

.stat-item span {
  color: var(--muted);
  font-size: 14px;
}

.history-row {
  margin-top: 10px;
  padding: 11px 12px;
  border-radius: 10px;
  background: var(--surface-strong);
  border: 1px solid var(--hairline);
}

.revision-row {
  padding: 0;
  overflow: hidden;
}

.revision-card-trigger {
  border: 0;
  width: 100%;
  margin: 0;
  padding: 11px 12px;
  text-align: left;
  background: transparent;
  display: grid;
  gap: 4px;
  cursor: pointer;
}

.revision-row.is-expanded .revision-card-trigger {
  border-bottom: 1px solid var(--hairline);
}

.revision-detail {
  padding: 10px 12px 12px;
  display: grid;
  gap: 8px;
}

.revision-editor-content {
  min-height: 220px;
}

.revision-content-preview {
  margin: 0;
  border: 1px solid var(--content-code-border);
  border-radius: 10px;
  background: linear-gradient(180deg, var(--content-code-bg-top), var(--content-code-bg));
  color: var(--content-code-text);
  padding: 10px;
  white-space: pre-wrap;
  font-family: var(--font-mono);
  line-height: 1.45;
  max-height: 260px;
  overflow: auto;
  box-shadow: var(--content-code-shadow);
}

.revision-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.my-issues {
  margin-top: 0;
}

.my-issues h3 {
  margin-bottom: 10px;
  font-size: 24px;
}

.issue-form {
  display: grid;
  gap: 8px;
}

.issue-filters {
  margin-top: 10px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.issue-filters .select {
  width: 160px;
}

.issue-filters .input {
  width: min(320px, 100%);
}

.revision-filters {
  margin-top: 10px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.revision-filters .select {
  width: 180px;
}

.revision-filters .input {
  width: min(320px, 100%);
}

.issue-row {
  margin-top: 10px;
  padding: 11px 12px;
  border-radius: 10px;
  background: var(--surface-strong);
  border: 1px solid var(--hairline);
}

.issue-note {
  margin-top: 6px;
  color: var(--text);
}

.event {
  padding: 9px 0;
  display: grid;
  gap: 2px;
}

.event:first-of-type {
  border-top: 0;
}

.event-filters {
  margin-bottom: 8px;
  display: flex;
  gap: 8px;
  align-items: center;
}

.event-filters .select {
  flex: 1;
  min-width: 0;
}

.event-filters .input {
  flex: 1;
  min-width: 0;
  margin: 0;
}

.security-summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 8px;
}

.security-summary-item {
  border: 1px solid var(--hairline);
  border-radius: 10px;
  padding: 8px;
  background: var(--surface-strong);
  display: grid;
  gap: 2px;
}

.security-summary-item strong {
  font-size: 18px;
}

.security-summary-item span {
  color: var(--muted);
  font-size: 12px;
}

.event-target {
  font-size: 13px;
  color: var(--text-quiet);
}

.star-link {
  display: block;
  color: var(--accent);
  font-size: 14px;
  line-height: 1.4;
}

.star-row {
  margin-top: 8px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
}

@media (max-width: 760px) {
  .profile-main h1 {
    font-size: 30px;
  }

  .settings-grid {
    grid-template-columns: 1fr;
  }

  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .issue-filters .select,
  .issue-filters .input,
  .revision-filters .select,
  .revision-filters .input {
    width: 100%;
  }

  .security-summary-grid {
    grid-template-columns: 1fr;
  }

  .profile-tab {
    width: 100%;
    justify-content: center;
  }
}

@media (max-width: 560px) {
  .profile-head {
    flex-direction: column;
  }

  .stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>


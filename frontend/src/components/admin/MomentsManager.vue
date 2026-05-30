<template>
  <section class="manager-stack">
    <header class="section-head">
      <div>
        <h2>动态社区管理</h2>
        <p class="meta">管理手机号验证动态、评论、举报、热门前十、验证记录和一键开关。</p>
      </div>
      <div class="toolbar">
        <button class="btn" type="button" :disabled="loading" @click="loadAll">{{ loading ? "刷新中..." : "刷新" }}</button>
        <button class="btn btn-accent" type="button" :disabled="savingSettings" @click="saveSettings">
          {{ savingSettings ? "保存中..." : "保存设置" }}
        </button>
      </div>
    </header>

    <section class="stats-grid">
      <article v-for="item in statsCards" :key="item.label" class="stat-card">
        <strong>{{ item.value }}</strong>
        <span>{{ item.label }}</span>
      </article>
    </section>

    <section class="settings-panel">
      <div class="panel-title">
        <h3>全局开关</h3>
        <span class="meta">默认关闭，管理员可随时一键控制发布、评论和热门榜。</span>
      </div>
      <div class="switch-grid">
        <label v-for="item in switchItems" :key="item.key" class="switch-line">
          <input v-model="settingsForm[item.key]" type="checkbox" />
          <span>{{ item.label }}</span>
        </label>
      </div>
      <div class="form-grid">
        <label>
          <span>每日发帖上限</span>
          <input v-model.number="settingsForm.daily_post_limit" class="input" type="number" min="1" />
        </label>
        <label>
          <span>每日评论上限</span>
          <input v-model.number="settingsForm.daily_comment_limit" class="input" type="number" min="1" />
        </label>
        <label>
          <span>每条最多图片</span>
          <input v-model.number="settingsForm.max_images_per_post" class="input" type="number" min="0" max="9" />
        </label>
        <label>
          <span>单图大小 MB</span>
          <input v-model.number="settingsForm.max_image_size_mb" class="input" type="number" min="1" max="20" />
        </label>
        <label>
          <span>热门窗口天数</span>
          <input v-model.number="settingsForm.hot_window_days" class="input" type="number" min="1" />
        </label>
        <label>
          <span>热门前十数量</span>
          <input v-model.number="settingsForm.hot_limit" class="input" type="number" min="1" max="10" />
        </label>
        <label>
          <span>新用户人工复核条数</span>
          <input v-model.number="settingsForm.new_user_manual_review_count" class="input" type="number" min="0" max="50" />
        </label>
        <label>
          <span>举报自动隐藏阈值</span>
          <input v-model.number="settingsForm.auto_hide_report_threshold" class="input" type="number" min="1" />
        </label>
      </div>
      <label class="rules-block">
        <span>规范说明</span>
        <textarea v-model.trim="settingsForm.rules_summary" class="textarea" rows="4"></textarea>
      </label>
    </section>

    <section class="card-block">
      <div class="panel-title">
        <h3>动态列表</h3>
        <div class="filter-row">
          <select v-model="filters.status" class="select compact" @change="loadMoments">
            <option value="">全部状态</option>
            <option v-for="item in momentStatusOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
          </select>
          <input v-model.trim="filters.search" class="input compact" placeholder="搜索内容/用户" @keyup.enter="loadMoments" />
          <button class="btn btn-mini" type="button" @click="loadMoments">筛选</button>
        </div>
      </div>
      <div class="table-shell">
        <div class="table-row table-head">
          <span>作者</span>
          <span>内容</span>
          <span>状态</span>
          <span>互动</span>
          <span>操作</span>
        </div>
        <div v-for="item in moments" :key="item.id" class="table-row">
          <span>{{ item.author?.username || "-" }}</span>
          <span class="ellipsis" :title="item.content">{{ item.content }}</span>
          <span>{{ labelMap.momentStatus[item.status] || item.status }}</span>
          <span>{{ item.like_count || 0 }} / {{ item.favorite_count || 0 }} / {{ item.comment_count || 0 }} / {{ item.report_count || 0 }}</span>
          <span class="action-inline">
            <select v-model="momentActions[item.id]" class="select compact">
              <option value="">选择</option>
              <option value="approve">通过</option>
              <option value="reject">驳回</option>
              <option value="hide">隐藏</option>
              <option value="restore">恢复</option>
              <option value="hot_on">允许热门</option>
              <option value="hot_off">禁止热门</option>
              <option value="feature_on">设为精选</option>
              <option value="feature_off">取消精选</option>
              <option value="lock_comments">锁定评论</option>
              <option value="unlock_comments">解锁评论</option>
              <option value="delete">删除</option>
            </select>
            <button class="btn btn-mini" type="button" @click="applyMomentAction(item)">执行</button>
          </span>
        </div>
      </div>
      <p v-if="!moments.length" class="empty">暂无动态。</p>
    </section>

    <section class="card-block">
      <div class="panel-title">
        <h3>评论管理</h3>
        <div class="filter-row">
          <select v-model="filters.commentStatus" class="select compact" @change="loadComments">
            <option value="">全部状态</option>
            <option value="pending">待审</option>
            <option value="visible">可见</option>
            <option value="rejected">驳回</option>
            <option value="hidden">隐藏</option>
            <option value="deleted">删除</option>
          </select>
          <button class="btn btn-mini" type="button" @click="loadComments">刷新</button>
        </div>
      </div>
      <div class="table-shell">
        <div class="table-row table-head">
          <span>作者</span>
          <span>评论</span>
          <span>所属动态</span>
          <span>状态</span>
          <span>操作</span>
        </div>
        <div v-for="item in comments" :key="item.id" class="table-row">
          <span>{{ item.author?.username || "-" }}</span>
          <span class="ellipsis" :title="item.content">{{ item.content }}</span>
          <span class="ellipsis">{{ item.moment_summary || item.moment?.content || `#${item.moment}` }}</span>
          <span>{{ labelMap.commentStatus[item.status] || item.status }}</span>
          <span class="action-inline">
            <select v-model="commentActions[item.id]" class="select compact">
              <option value="">选择</option>
              <option value="approve">通过</option>
              <option value="reject">驳回</option>
              <option value="hide">隐藏</option>
              <option value="restore">恢复</option>
              <option value="delete">删除</option>
            </select>
            <button class="btn btn-mini" type="button" @click="applyCommentAction(item)">执行</button>
          </span>
        </div>
      </div>
    </section>

    <section class="card-block">
      <div class="panel-title">
        <h3>举报中心</h3>
        <div class="filter-row">
          <select v-model="filters.reportStatus" class="select compact" @change="loadReports">
            <option value="">全部状态</option>
            <option value="pending">待处理</option>
            <option value="resolved">已处理</option>
            <option value="rejected">已驳回</option>
          </select>
          <button class="btn btn-mini" type="button" @click="loadReports">刷新</button>
        </div>
      </div>
      <div class="table-shell">
        <div class="table-row table-head">
          <span>举报对象</span>
          <span>原因</span>
          <span>状态</span>
          <span>说明</span>
          <span>操作</span>
        </div>
        <div v-for="item in reports" :key="item.id" class="table-row">
          <span>{{ reportTargetLabel(item) }}</span>
          <span>{{ labelMap.reportReason[item.reason] || item.reason }}</span>
          <span>{{ labelMap.reportStatus[item.status] || item.status }}</span>
          <span class="ellipsis" :title="item.description">{{ item.description || "-" }}</span>
          <span class="action-inline">
            <select v-model="reportActions[item.id]" class="select compact">
              <option value="">选择</option>
              <option value="resolve">已处理</option>
              <option value="reject">驳回</option>
            </select>
            <button class="btn btn-mini" type="button" @click="applyReportAction(item)">执行</button>
          </span>
        </div>
      </div>
    </section>

    <section class="card-block">
      <div class="panel-title">
        <div>
          <h3>手机号验证</h3>
          <p class="meta">用户通过阿里云短信认证服务完成验证；管理员只处理异常拒绝、撤销和必要的超管手动通过。</p>
        </div>
        <div class="filter-row">
          <select v-model="filters.phoneStatus" class="select compact" @change="loadVerifications">
            <option value="">全部状态</option>
            <option value="pending">认证中</option>
            <option value="verified">已验证</option>
            <option value="rejected">未通过</option>
            <option value="revoked">撤销</option>
          </select>
          <button class="btn btn-mini" type="button" @click="loadVerifications">刷新</button>
        </div>
      </div>
      <div class="table-shell">
        <div class="table-row table-head">
          <span>用户</span>
          <span>手机号</span>
          <span>状态</span>
          <span>第三方流水</span>
          <span>操作</span>
        </div>
        <div v-for="item in verifications" :key="item.id" class="table-row">
          <span>{{ item.user?.username || "-" }}</span>
          <span>{{ item.phone_masked || "-" }} / {{ item.phone_last4 || "-" }}</span>
          <span>{{ labelMap.phoneStatus[item.status] || item.status }}</span>
          <span class="ellipsis" :title="formatVerificationTrace(item)">{{ formatVerificationTrace(item) }}</span>
          <span class="action-inline">
            <select v-model="verificationActions[item.id]" class="select compact">
              <option value="">选择</option>
              <option value="approve">手动通过</option>
              <option value="reject">异常拒绝</option>
              <option value="revoke">撤销</option>
            </select>
            <button class="btn btn-mini" type="button" @click="applyVerificationAction(item)">执行</button>
          </span>
        </div>
      </div>
    </section>

    <section class="card-block">
      <div class="panel-title">
        <h3>权限限制</h3>
        <div class="filter-row">
          <input v-model.trim="restrictionForm.username" class="input compact" placeholder="用户名" />
          <button class="btn btn-mini btn-accent" type="button" @click="loadRestriction">载入</button>
        </div>
      </div>
      <div class="form-grid">
        <label>
          <span>用户 ID</span>
          <input v-model.number="restrictionForm.user" class="input" type="number" min="1" />
        </label>
        <label>
          <span>临时禁言至</span>
          <input v-model="restrictionForm.muted_until" class="input" type="datetime-local" />
        </label>
      </div>
      <div class="switch-grid">
        <label v-for="item in restrictionSwitchItems" :key="item.key" class="switch-line">
          <input v-model="restrictionForm[item.key]" type="checkbox" />
          <span>{{ item.label }}</span>
        </label>
      </div>
      <label class="rules-block">
        <span>限制原因</span>
        <textarea v-model.trim="restrictionForm.reason" class="textarea" rows="3"></textarea>
      </label>
      <div class="toolbar">
        <button class="btn btn-accent" type="button" :disabled="savingRestriction" @click="saveRestriction">
          {{ savingRestriction ? "保存中..." : "保存限制" }}
        </button>
      </div>
    </section>

    <section class="card-block">
      <div class="panel-title">
        <h3>审计日志</h3>
        <button class="btn btn-mini" type="button" @click="loadAuditLogs">刷新</button>
      </div>
      <div class="table-shell">
        <div class="table-row table-head">
          <span>时间</span>
          <span>事件</span>
          <span>对象</span>
          <span>操作人</span>
          <span>详情</span>
        </div>
        <div v-for="item in auditLogs" :key="item.id" class="table-row">
          <span>{{ formatDateTime(item.created_at) }}</span>
          <span>{{ labelMap.auditEvent[item.event_type] || item.event_type }}</span>
          <span>{{ item.target_type || "-" }}{{ item.target_id ? ` #${item.target_id}` : "" }}</span>
          <span>{{ item.actor?.username || "-" }}</span>
          <span class="ellipsis" :title="JSON.stringify(item.payload || {})">{{ JSON.stringify(item.payload || {}) }}</span>
        </div>
      </div>
    </section>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";

import api from "../../services/api";
import { useUiStore } from "../../stores/ui";

const ui = useUiStore();

const loading = ref(false);
const savingSettings = ref(false);
const savingRestriction = ref(false);
const moments = ref([]);
const comments = ref([]);
const reports = ref([]);
const verifications = ref([]);
const auditLogs = ref([]);

const settingsForm = reactive({
  is_enabled: false,
  publishing_enabled: false,
  commenting_enabled: false,
  reactions_enabled: true,
  favorites_enabled: true,
  hot_list_enabled: false,
  featured_feed_enabled: false,
  require_real_name: true,
  require_manual_review_for_new_users: true,
  new_user_manual_review_count: 3,
  daily_post_limit: 20,
  daily_comment_limit: 80,
  max_images_per_post: 9,
  max_image_size_mb: 5,
  max_text_length: 2000,
  max_comment_length: 500,
  auto_hide_report_threshold: 3,
  hot_window_days: 7,
  hot_limit: 10,
  hot_like_weight: 2,
  hot_favorite_weight: 3,
  hot_comment_weight: 2,
  hot_report_penalty: 10,
  rules_summary: "",
});

const filters = reactive({
  status: "",
  search: "",
  commentStatus: "",
  reportStatus: "",
  phoneStatus: "",
});

const momentActions = reactive({});
const commentActions = reactive({});
const reportActions = reactive({});
const verificationActions = reactive({});

const restrictionForm = reactive({
  user: null,
  username: "",
  can_post: true,
  can_comment: true,
  can_react: true,
  can_upload_images: true,
  can_enter_hot: true,
  muted_until: "",
  reason: "",
});

const switchItems = [
  { key: "is_enabled", label: "启用动态模块" },
  { key: "publishing_enabled", label: "允许发布动态" },
  { key: "commenting_enabled", label: "允许评论" },
  { key: "reactions_enabled", label: "允许点赞互动" },
  { key: "favorites_enabled", label: "允许收藏" },
  { key: "hot_list_enabled", label: "启用热门前十" },
  { key: "featured_feed_enabled", label: "启用站内精选" },
  { key: "require_real_name", label: "强制手机号验证" },
  { key: "require_manual_review_for_new_users", label: "新用户先审后发" },
];

const restrictionSwitchItems = [
  { key: "can_post", label: "允许发帖" },
  { key: "can_comment", label: "允许评论" },
  { key: "can_react", label: "允许点赞收藏" },
  { key: "can_upload_images", label: "允许发图" },
  { key: "can_enter_hot", label: "允许进热门" },
];

const momentStatusOptions = [
  { value: "pending", label: "待审" },
  { value: "published", label: "已发布" },
  { value: "rejected", label: "驳回" },
  { value: "hidden", label: "隐藏" },
  { value: "deleted", label: "删除" },
];

const labelMap = {
  momentStatus: { pending: "待审", published: "已发布", rejected: "驳回", hidden: "隐藏", deleted: "删除" },
  commentStatus: { pending: "待审", visible: "可见", rejected: "驳回", hidden: "隐藏", deleted: "删除" },
  reportStatus: { pending: "待处理", resolved: "已处理", rejected: "已驳回" },
  reportReason: {
    spam: "垃圾信息",
    porn: "色情",
    political: "涉政",
    violence: "暴力",
    abuse: "辱骂",
    privacy: "隐私",
    cheating: "作弊",
    irrelevant: "无关",
    other: "其他",
  },
  phoneStatus: {
    unverified: "未验证",
    pending: "认证中",
    verified: "已验证",
    rejected: "未通过",
    revoked: "撤销",
  },
  auditEvent: {
    create: "创建",
    update: "更新",
    approve: "通过",
    reject: "驳回",
    hide: "隐藏",
    delete: "删除",
    restore: "恢复",
    report: "举报",
    restrict: "限制",
    config: "配置",
    hot: "热门",
    verify: "验证",
  },
};

const statsCards = ref([
  { label: "动态总数", value: 0 },
  { label: "待审核动态", value: 0 },
  { label: "待审核评论", value: 0 },
  { label: "待处理举报", value: 0 },
  { label: "手机号待验证", value: 0 },
  { label: "已验证手机号", value: 0 },
]);

function getErrorText(error, fallback = "操作失败") {
  const payload = error?.response?.data;
  if (!payload) return error?.message || fallback;
  if (typeof payload === "string") return payload;
  if (typeof payload.detail === "string") return payload.detail;
  return fallback;
}

function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function extractRows(data) {
  return Array.isArray(data?.results) ? data.results : Array.isArray(data) ? data : [];
}

async function loadOverview() {
  const { data } = await api.get("/moments/overview/");
  const totals = data?.totals || {};
  statsCards.value = [
    { label: "动态总数", value: totals.moments || 0 },
    { label: "待审核动态", value: totals.pending || 0 },
    { label: "待审核评论", value: totals.comments_pending || 0 },
    { label: "待处理举报", value: totals.reports_pending || 0 },
    { label: "手机号待验证", value: totals.phone_pending || 0 },
    { label: "已验证手机号", value: totals.phone_verified || 0 },
  ];
  Object.assign(settingsForm, data?.settings || {});
}

async function loadMoments() {
  const params = { include_all: 1 };
  if (filters.status) params.status = filters.status;
  if (filters.search) params.search = filters.search;
  const { data } = await api.get("/moments/", { params });
  moments.value = extractRows(data);
}

async function loadComments() {
  const params = { };
  if (filters.commentStatus) params.status = filters.commentStatus;
  const { data } = await api.get("/moment-comments/", { params });
  comments.value = extractRows(data);
}

async function loadReports() {
  const params = {};
  if (filters.reportStatus) params.status = filters.reportStatus;
  const { data } = await api.get("/moment-reports/", { params });
  reports.value = extractRows(data);
}

async function loadVerifications() {
  const params = {};
  if (filters.phoneStatus) params.status = filters.phoneStatus;
  const { data } = await api.get("/phone-verifications/", { params });
  verifications.value = extractRows(data);
}

async function loadAuditLogs() {
  const { data } = await api.get("/moment-audit-logs/");
  auditLogs.value = extractRows(data);
}

async function loadRestriction() {
  const userId = await resolveRestrictionUser();
  if (!userId) {
    return;
  }
  try {
    const { data } = await api.get("/moment-restrictions/", {
      params: { user: userId, search: restrictionForm.username || "" },
    });
    const matched = extractRows(data).find((item) => item.user?.id === userId);
    if (matched) {
      Object.assign(restrictionForm, matched, { user: matched.user?.id || userId, username: matched.user?.username || restrictionForm.username });
      if (matched.muted_until) {
        restrictionForm.muted_until = new Date(matched.muted_until).toISOString().slice(0, 16);
      }
      ui.success("限制信息已载入");
      return;
    }
    ui.info("未找到该用户的限制记录，将按当前表单新建");
  } catch (error) {
    ui.error(getErrorText(error, "限制信息加载失败"));
  }
}

async function resolveRestrictionUser() {
  const currentUserId = Number(restrictionForm.user || 0);
  if (currentUserId) return currentUserId;
  const username = String(restrictionForm.username || "").trim();
  if (!username) {
    ui.info("请先填写用户名或用户 ID");
    return null;
  }
  try {
    const { data } = await api.get("/users/", { params: { search: username } });
    const rows = extractRows(data);
    const matched =
      rows.find((item) => String(item.username || "").toLowerCase() === username.toLowerCase()) ||
      rows[0];
    if (!matched?.id) {
      ui.info("未找到该用户");
      return null;
    }
    restrictionForm.user = matched.id;
    restrictionForm.username = matched.username || username;
    return matched.id;
  } catch (error) {
    ui.error(getErrorText(error, "用户查询失败"));
    return null;
  }
}

async function loadAll() {
  loading.value = true;
  try {
    await Promise.all([
      loadOverview(),
      loadMoments(),
      loadComments(),
      loadReports(),
      loadVerifications(),
      loadAuditLogs(),
    ]);
  } catch (error) {
    ui.error(getErrorText(error, "动态管理数据加载失败"));
  } finally {
    loading.value = false;
  }
}

async function saveSettings() {
  savingSettings.value = true;
  try {
    await api.patch("/moment-settings/current/", settingsForm);
    ui.success("动态设置已保存");
    await loadOverview();
  } catch (error) {
    ui.error(getErrorText(error, "设置保存失败"));
  } finally {
    savingSettings.value = false;
  }
}

async function applyMomentAction(item) {
  const action = momentActions[item.id];
  if (!action) return;
  try {
    if (action === "delete") {
      await api.delete(`/moments/${item.id}/`);
    } else if (action === "approve") {
      await api.post(`/moments/${item.id}/approve/`, {});
    } else if (action === "reject") {
      await api.post(`/moments/${item.id}/reject/`, {});
    } else if (action === "hide") {
      await api.post(`/moments/${item.id}/hide/`, {});
    } else if (action === "restore") {
      await api.post(`/moments/${item.id}/restore/`, {});
    } else if (action === "hot_on") {
      await api.post(`/moments/${item.id}/set-hot/`, { allow_hot: true });
    } else if (action === "hot_off") {
      await api.post(`/moments/${item.id}/set-hot/`, { allow_hot: false });
    } else if (action === "feature_on") {
      await api.post(`/moments/${item.id}/set-hot/`, { is_featured: true });
    } else if (action === "feature_off") {
      await api.post(`/moments/${item.id}/set-hot/`, { is_featured: false });
    } else if (action === "lock_comments") {
      await api.post(`/moments/${item.id}/lock-comments/`, { locked: true });
    } else if (action === "unlock_comments") {
      await api.post(`/moments/${item.id}/lock-comments/`, { locked: false });
    }
    momentActions[item.id] = "";
    ui.success("操作已执行");
    await loadAll();
  } catch (error) {
    ui.error(getErrorText(error, "动态操作失败"));
  }
}

async function applyCommentAction(item) {
  const action = commentActions[item.id];
  if (!action) return;
  try {
    if (action === "delete") {
      await api.delete(`/moment-comments/${item.id}/`);
    } else if (action === "approve") {
      await api.post(`/moment-comments/${item.id}/approve/`, {});
    } else if (action === "reject") {
      await api.post(`/moment-comments/${item.id}/reject/`, {});
    } else if (action === "hide") {
      await api.post(`/moment-comments/${item.id}/hide/`, {});
    } else if (action === "restore") {
      await api.post(`/moment-comments/${item.id}/restore/`, {});
    }
    commentActions[item.id] = "";
    ui.success("操作已执行");
    await loadAll();
  } catch (error) {
    ui.error(getErrorText(error, "评论操作失败"));
  }
}

async function applyReportAction(item) {
  const action = reportActions[item.id];
  if (!action) return;
  try {
    if (action === "resolve") {
      await api.post(`/moment-reports/${item.id}/resolve/`, { resolution_action: "resolved" });
    } else if (action === "reject") {
      await api.post(`/moment-reports/${item.id}/reject/`, {});
    }
    reportActions[item.id] = "";
    ui.success("举报已处理");
    await loadAll();
  } catch (error) {
    ui.error(getErrorText(error, "举报处理失败"));
  }
}

async function applyVerificationAction(item) {
  const action = verificationActions[item.id];
  if (!action) return;
  try {
    if (action === "approve") {
      await api.post(`/phone-verifications/${item.id}/approve/`, { manual_override: "CONFIRM" });
    } else if (action === "reject") {
      await api.post(`/phone-verifications/${item.id}/reject/`, {});
    } else if (action === "revoke") {
      await api.post(`/phone-verifications/${item.id}/revoke/`, {});
    }
    verificationActions[item.id] = "";
    ui.success("手机号验证状态已更新");
    await loadAll();
  } catch (error) {
    ui.error(getErrorText(error, "手机号验证状态更新失败"));
  }
}

function formatVerificationTrace(item) {
  const pieces = [
    item.provider || "-",
    item.provider_out_id || "-",
    item.provider_biz_id || "-",
    item.provider_request_id || "-",
    item.provider_status_message || "",
  ].filter(Boolean);
  return pieces.join(" / ");
}

function reportTargetLabel(item) {
  const typeLabel = item.target_type === "comment" ? "评论" : "动态";
  const target = item.target_summary || item.moment?.content || item.comment?.content || `#${item.moment || item.comment || "-"}`;
  return `${typeLabel}：${target}`;
}

async function saveRestriction() {
  const userId = await resolveRestrictionUser();
  if (!userId) {
    return;
  }
  savingRestriction.value = true;
  try {
    const payload = {
      user: userId,
      username: restrictionForm.username,
      can_post: restrictionForm.can_post,
      can_comment: restrictionForm.can_comment,
      can_react: restrictionForm.can_react,
      can_upload_images: restrictionForm.can_upload_images,
      can_enter_hot: restrictionForm.can_enter_hot,
      reason: restrictionForm.reason,
      muted_until: restrictionForm.muted_until ? new Date(restrictionForm.muted_until).toISOString() : null,
    };
    await api.post("/moment-restrictions/for-user/", payload);
    ui.success("用户限制已保存");
    await loadAll();
  } catch (error) {
    ui.error(getErrorText(error, "保存限制失败"));
  } finally {
    savingRestriction.value = false;
  }
}

onMounted(() => {
  loadAll();
});
</script>

<style scoped>
.manager-stack {
  display: grid;
  gap: 14px;
}

.section-head,
.panel-title,
.toolbar,
.filter-row,
.action-inline {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.section-head,
.panel-title {
  justify-content: space-between;
}

.stats-grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(6, minmax(0, 1fr));
}

.stat-card,
.settings-panel,
.card-block {
  border: 1px solid var(--hairline);
  border-radius: 16px;
  background: var(--surface-strong);
  box-shadow: var(--shadow-sm);
  padding: 14px;
}

.stat-card {
  display: grid;
  gap: 4px;
}

.stat-card strong {
  font-size: 24px;
}

.switch-grid,
.form-grid {
  display: grid;
  gap: 10px;
}

.switch-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin: 12px 0;
}

.form-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.rules-block {
  display: grid;
  gap: 6px;
  margin-top: 12px;
}

.rules-block span,
.form-grid label span {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-soft);
}

.input,
.select,
.textarea {
  width: 100%;
  border: 1px solid var(--hairline);
  border-radius: 12px;
  background: var(--surface);
  color: var(--text-strong);
  font: inherit;
  padding: 10px 12px;
}

.textarea {
  min-height: 120px;
  resize: vertical;
}

.compact {
  max-width: 180px;
}

.table-shell {
  display: grid;
  gap: 8px;
  overflow-x: auto;
}

.table-row {
  display: grid;
  grid-template-columns: 120px minmax(220px, 1fr) 90px 140px 220px;
  gap: 10px;
  align-items: center;
  min-width: 920px;
  border: 1px solid var(--hairline);
  border-radius: 12px;
  padding: 10px 12px;
}

.table-head {
  border-color: transparent;
  background: var(--surface-muted);
  font-size: 13px;
  font-weight: 800;
  color: var(--text-soft);
}

.ellipsis {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.empty {
  color: var(--text-quiet);
  text-align: center;
}

@media (max-width: 1180px) {
  .stats-grid,
  .switch-grid,
  .form-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .table-row {
    grid-template-columns: 110px minmax(180px, 1fr) 80px 110px 180px;
  }
}

@media (max-width: 760px) {
  .stats-grid,
  .switch-grid,
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>

<template>
  <section class="manager-stack">
    <header class="section-head">
      <div>
        <h2>邀请管理</h2>
        <p class="meta">查看邀请码来源、被邀请用户状态和贡献奖励。大量同校注册不拦截，异常账号由管理员手动回滚。</p>
      </div>
      <button class="btn" type="button" :disabled="loading" @click="loadRecords">
        {{ loading ? "刷新中..." : "刷新" }}
      </button>
    </header>

    <div class="toolbar">
      <input v-model.trim="filters.search" class="input grow" placeholder="搜索邀请人、被邀请人、学校或邀请码" @keyup.enter="loadRecords" />
      <select v-model="filters.status" class="select">
        <option value="">全部状态</option>
        <option value="pending">待生效</option>
        <option value="effective">已生效</option>
        <option value="rolled_back">已回滚</option>
        <option value="rejected">已拒绝</option>
      </select>
      <button class="btn" type="button" @click="loadRecords">筛选</button>
      <button class="btn" type="button" @click="resetFilters">重置</button>
    </div>

    <section class="invite-admin-grid">
      <article v-for="item in records" :key="item.id" class="invite-admin-card">
        <div class="invite-admin-main">
          <div class="invite-admin-head">
            <span class="status-pill" :class="`status-pill--${item.status}`">{{ statusLabel(item.status) }}</span>
            <p class="meta">
              邀请码 {{ item.code_snapshot || "-" }} · 奖励 {{ item.reward_delta || 0 }} · 创建 {{ formatDateTime(item.created_at) }}
            </p>
          </div>
          <div class="invite-pair">
            <template v-for="(member, memberIndex) in pairMembers(item)" :key="member.key">
              <span v-if="memberIndex > 0" class="pair-arrow" aria-hidden="true">→</span>
              <div class="user-mini-card">
                <img
                  class="user-mini-avatar"
                  :src="member.user?.avatar_url || DEFAULT_AVATAR_URL"
                  :alt="`${member.user?.username || '用户'} 头像`"
                  width="36"
                  height="36"
                  loading="lazy"
                  @error="handleAvatarError"
                />
                <div class="user-mini-copy">
                  <span>{{ member.label }}</span>
                  <strong>{{ member.user?.username || "已注销用户" }}</strong>
                  <small>{{ member.user?.school_name || "未填写学校" }}</small>
                </div>
              </div>
            </template>
          </div>
          <p v-if="item.review_note" class="meta">备注：{{ item.review_note }}</p>
        </div>
        <div class="invite-actions">
          <button class="btn btn-mini" type="button" :disabled="actingId === item.id || item.status !== 'pending'" @click="runAction(item, 'activate')">
            手动生效
          </button>
          <button class="btn btn-mini" type="button" :disabled="actingId === item.id || item.status === 'rolled_back'" @click="runAction(item, 'rollback')">
            回滚
          </button>
          <button class="btn btn-mini danger" type="button" :disabled="actingId === item.id || item.status === 'rejected'" @click="runAction(item, 'reject')">
            拒绝
          </button>
        </div>
      </article>
    </section>

    <button v-if="meta.next" class="btn" type="button" :disabled="loadingMore" @click="loadMore">
      {{ loadingMore ? "加载中..." : "加载更多" }}
    </button>
    <p v-if="!records.length && !loading" class="meta">当前没有匹配的邀请记录。</p>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";

import api from "../../services/api";
import { useUiStore } from "../../stores/ui";

const ui = useUiStore();
const records = ref([]);
const loading = ref(false);
const loadingMore = ref(false);
const actingId = ref(null);
const DEFAULT_AVATAR_URL = "/wiki-assets/default-avatar.svg";

const filters = reactive({
  search: "",
  status: "",
});

const meta = reactive({
  count: 0,
  next: "",
  page: 1,
});

function pairMembers(item) {
  return [
    { key: "inviter", label: "邀请人", user: item?.inviter || null },
    { key: "invitee", label: "被邀请人", user: item?.invitee || null },
  ];
}

function handleAvatarError(event) {
  const image = event?.target;
  if (!image || image.dataset.fallbackApplied === "1") return;
  image.dataset.fallbackApplied = "1";
  image.src = DEFAULT_AVATAR_URL;
}

function unpackListPayload(data) {
  if (Array.isArray(data)) {
    return { results: data, count: data.length, next: "" };
  }
  return {
    results: Array.isArray(data?.results) ? data.results : [],
    count: Number(data?.count || 0),
    next: data?.next || "",
  };
}

function nextPageFromUrl(value) {
  try {
    const url = new URL(value, window.location.origin);
    return Number(url.searchParams.get("page") || 1);
  } catch {
    return meta.page + 1;
  }
}

function statusLabel(value) {
  const labels = {
    pending: "待生效",
    effective: "已生效",
    rolled_back: "已回滚",
    rejected: "已拒绝",
  };
  return labels[value] || value || "未知";
}

function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false });
}

async function loadRecords(page = 1, append = false) {
  loading.value = !append;
  loadingMore.value = append;
  try {
    const params = { page };
    if (filters.search) params.search = filters.search;
    if (filters.status) params.status = filters.status;
    const { data } = await api.get("/invitations/", { params });
    const parsed = unpackListPayload(data);
    records.value = append ? [...records.value, ...parsed.results] : parsed.results;
    meta.count = parsed.count;
    meta.next = parsed.next;
    meta.page = page;
  } catch (error) {
    ui.error(error?.response?.data?.detail || "邀请记录加载失败");
  } finally {
    loading.value = false;
    loadingMore.value = false;
  }
}

function resetFilters() {
  filters.search = "";
  filters.status = "";
  loadRecords();
}

function loadMore() {
  if (!meta.next) return;
  loadRecords(nextPageFromUrl(meta.next), true);
}

async function runAction(item, action) {
  const confirmText = {
    activate: "确认手动生效这条邀请？被邀请用户需要已完成手机号验证。",
    rollback: "确认回滚这条邀请贡献？",
    reject: "确认拒绝这条邀请记录？",
  }[action];
  if (!window.confirm(confirmText)) return;
  actingId.value = item.id;
  try {
    await api.post(`/invitations/${item.id}/${action}/`, { review_note: `admin ${action}` });
    await loadRecords(meta.page || 1, false);
    ui.success("邀请记录已更新");
  } catch (error) {
    ui.error(error?.response?.data?.detail || "操作失败");
  } finally {
    actingId.value = null;
  }
}

onMounted(loadRecords);
</script>

<style scoped>
.manager-stack {
  display: grid;
  gap: 12px;
}

.section-head,
.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.section-head {
  justify-content: space-between;
  align-items: start;
}

.section-head h2,
.meta {
  margin: 0;
}

.section-head .meta {
  margin-top: 4px;
}

.meta {
  color: var(--text-quiet);
  font-size: 13px;
}

.grow {
  flex: 1 1 260px;
  min-width: 0;
}

.toolbar .select {
  width: auto;
  min-width: 128px;
}

.invite-admin-grid {
  display: grid;
  gap: 10px;
}

.invite-admin-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 14px;
  align-items: center;
  padding: 12px 14px;
  border: 1px solid var(--hairline);
  border-radius: 14px;
  background: var(--surface-soft);
}

.invite-admin-main {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.invite-admin-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
}

.invite-pair {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  gap: 10px;
  align-items: center;
}

.pair-arrow {
  color: var(--text-soft);
  font-weight: 800;
}

.user-mini-card {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border: 1px solid var(--hairline);
  border-radius: 12px;
  background: var(--surface);
}

.user-mini-avatar {
  width: 36px;
  height: 36px;
  flex: 0 0 36px;
  border-radius: 50%;
  object-fit: cover;
  display: block;
}

.user-mini-copy {
  min-width: 0;
  display: grid;
  gap: 1px;
}

.user-mini-copy span,
.user-mini-copy small {
  color: var(--text-soft);
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-mini-copy strong {
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.invite-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.btn-mini {
  min-height: 28px;
  padding: 4px 10px;
  font-size: 13px;
}

.btn.danger {
  color: #b91c1c;
  border-color: color-mix(in srgb, #dc2626 30%, var(--hairline));
}

.status-pill {
  width: fit-content;
  border: 1px solid var(--hairline);
  border-radius: 999px;
  padding: 3px 9px;
  color: var(--text-soft);
  font-size: 12px;
  font-weight: 800;
  line-height: 1.3;
}

.status-pill--effective {
  border-color: color-mix(in srgb, #16a34a 34%, var(--hairline));
  color: #15803d;
}

.status-pill--rolled_back,
.status-pill--rejected {
  border-color: color-mix(in srgb, #dc2626 34%, var(--hairline));
  color: #b91c1c;
}

@media (max-width: 760px) {
  .invite-admin-card {
    grid-template-columns: 1fr;
  }

  .invite-pair {
    grid-template-columns: 1fr;
  }

  .pair-arrow {
    display: none;
  }

  .invite-actions {
    justify-content: flex-start;
  }
}
</style>

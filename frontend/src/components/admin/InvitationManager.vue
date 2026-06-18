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
          <span class="status-pill" :class="`status-pill--${item.status}`">{{ statusLabel(item.status) }}</span>
          <div class="invite-pair">
            <UserMiniCard label="邀请人" :user="item.inviter" />
            <span class="pair-arrow">→</span>
            <UserMiniCard label="被邀请人" :user="item.invitee" />
          </div>
          <p class="meta">
            邀请码 {{ item.code_snapshot || "-" }} · 奖励 {{ item.reward_delta || 0 }} · 创建 {{ formatDateTime(item.created_at) }}
          </p>
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
import { h, onMounted, reactive, ref } from "vue";

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

const UserMiniCard = {
  props: {
    label: { type: String, required: true },
    user: { type: Object, default: null },
  },
  setup(props) {
    return () =>
      h("div", { class: "user-mini-card" }, [
        h("img", {
          class: "user-mini-avatar",
          src: props.user?.avatar_url || DEFAULT_AVATAR_URL,
          alt: `${props.user?.username || "用户"} 头像`,
        }),
        h("div", { class: "user-mini-copy" }, [
          h("span", props.label),
          h("strong", props.user?.username || "已注销用户"),
          h("small", props.user?.school_name || "未填写学校"),
        ]),
      ]);
  },
};

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
.invite-admin-grid {
  display: grid;
  gap: 12px;
}

.invite-admin-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 16px;
  align-items: center;
  padding: 14px;
  border: 1px solid var(--hairline);
  border-radius: 14px;
  background: var(--surface);
}

.invite-admin-main {
  display: grid;
  gap: 10px;
  min-width: 0;
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
  padding: 10px;
  border: 1px solid var(--hairline);
  border-radius: 12px;
  background: var(--surface-strong);
}

.user-mini-avatar {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  object-fit: cover;
}

.user-mini-copy {
  min-width: 0;
  display: grid;
  gap: 2px;
}

.user-mini-copy span,
.user-mini-copy small {
  color: var(--text-soft);
  font-size: 12px;
}

.user-mini-copy strong {
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

.status-pill {
  width: fit-content;
  border: 1px solid var(--hairline);
  border-radius: 999px;
  padding: 4px 8px;
  color: var(--text-soft);
  font-size: 12px;
  font-weight: 800;
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

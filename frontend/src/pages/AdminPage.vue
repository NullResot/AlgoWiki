<template>
  <section class="admin-shell">
    <header class="admin-card admin-shell-head">
      <div class="admin-shell-copy">
        <p class="admin-kicker">{{ currentSectionConfig.label }}</p>
        <h1>AlgoWiki 管理台</h1>
        <p class="meta">{{ currentSectionConfig.description }}</p>
        <p class="meta admin-shell-note">
          当前管理页包含用户管理、竞赛 Wiki 页面管理、赛事专区页面管理、文档页面管理、动态图文社区、图库管理、删除内容归档、AI 助手管理和审计日志。
        </p>
      </div>
      <div class="admin-shell-actions">
        <a class="btn" href="/admin/" target="_blank" rel="noopener">打开 Django 后台</a>
      </div>
    </header>

    <section class="admin-card pending-overview">
      <div class="pending-overview-head">
        <div>
          <p class="admin-kicker">PENDING</p>
          <h2>待处理摘要</h2>
          <p class="meta">汇总审核、举报、图片、手机号验证等需要管理员介入的队列。</p>
        </div>
        <div class="pending-total">
          <span>总待处理</span>
          <strong>{{ pendingSummary.total }}</strong>
        </div>
      </div>
      <p v-if="overviewLoading" class="meta">待处理摘要加载中...</p>
      <div v-else class="pending-grid">
        <RouterLink
          v-for="item in visiblePendingItems"
          :key="item.key"
          class="pending-card"
          :class="`pending-card--${item.severity || 'normal'}`"
          :to="item.url || { name: 'admin' }"
        >
          <span>{{ item.label }}</span>
          <strong>{{ item.count }}</strong>
        </RouterLink>
      </div>
      <p v-if="!overviewLoading && !visiblePendingItems.length" class="meta">当前没有待处理事项。</p>
    </section>

    <nav class="admin-nav-panels" aria-label="管理分区">
      <section v-for="group in adminSectionGroups" :key="group.label" class="admin-nav-group">
        <p class="admin-nav-group-title">{{ group.label }}</p>
        <div class="admin-nav-grid">
          <RouterLink
            v-for="item in group.items"
            :key="item.key"
            :to="buildAdminSectionRoute(item.key)"
            class="admin-nav-link"
            :class="{ 'admin-nav-link--active': item.key === currentSection }"
          >
            <div class="admin-nav-top">
              <strong>{{ item.label }}</strong>
            </div>
            <span class="admin-nav-desc">{{ item.description }}</span>
          </RouterLink>
        </div>
      </section>
    </nav>

    <section class="admin-layout">
      <article v-if="currentSection === 'users'" class="admin-card full">
        <UserManager />
      </article>

      <article v-else-if="currentSection === 'competition-wiki'" class="admin-card full">
        <WikiPageManager />
      </article>

      <article v-else-if="currentSection === 'competition-zone'" class="admin-card full">
        <CompetitionZoneManager />
      </article>

      <article v-else-if="currentSection === 'document-pages'" class="admin-card full">
        <DocumentPageManager />
      </article>

      <article v-else-if="currentSection === 'announcements'" class="admin-card full">
        <AnnouncementManager />
      </article>

      <article v-else-if="currentSection === 'image-gallery'" class="admin-card full admin-card--gallery">
        <ImageGalleryManager />
      </article>

      <article v-else-if="currentSection === 'moments'" class="admin-card full">
        <MomentsManager />
      </article>

      <article v-else-if="currentSection === 'deleted-content'" class="admin-card full">
        <DeletedContentManager />
      </article>

      <article v-else-if="currentSection === 'assistant'" class="admin-card full">
        <AIAssistantManager />
      </article>

      <article v-else-if="currentSection === 'ai-moderation'" class="admin-card full">
        <AIModerationManager />
      </article>

      <article v-else-if="currentSection === 'captcha'" class="admin-card full">
        <CaptchaManager />
      </article>

      <article v-else-if="currentSection === 'invitations'" class="admin-card full">
        <InvitationManager />
      </article>

      <article v-else-if="currentSection === 'site-visits' && auth.isSuperAdmin" class="admin-card full">
        <SiteVisitStatsManager />
      </article>

      <article v-else-if="currentSection === 'site-visits'" class="admin-card full">
        <h2>无权查看网站访问量</h2>
        <p class="meta">该审计数据仅超级管理员可见。</p>
      </article>

      <article v-else-if="currentSection === 'events'" class="admin-card full">
        <EventLogManager />
      </article>

      <article v-else-if="currentSection === 'security'" class="admin-card full">
        <SecurityLogManager />
      </article>
    </section>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { RouterLink, useRouter } from "vue-router";

import api from "../services/api";
import AnnouncementManager from "../components/admin/AnnouncementManager.vue";
import AIAssistantManager from "../components/admin/AIAssistantManager.vue";
import AIModerationManager from "../components/admin/AIModerationManager.vue";
import CaptchaManager from "../components/admin/CaptchaManager.vue";
import CompetitionZoneManager from "../components/admin/CompetitionZoneManager.vue";
import DeletedContentManager from "../components/admin/DeletedContentManager.vue";
import DocumentPageManager from "../components/admin/DocumentPageManager.vue";
import EventLogManager from "../components/admin/EventLogManager.vue";
import ImageGalleryManager from "../components/admin/ImageGalleryManager.vue";
import InvitationManager from "../components/admin/InvitationManager.vue";
import MomentsManager from "../components/admin/MomentsManager.vue";
import SecurityLogManager from "../components/admin/SecurityLogManager.vue";
import SiteVisitStatsManager from "../components/admin/SiteVisitStatsManager.vue";
import UserManager from "../components/admin/UserManager.vue";
import WikiPageManager from "../components/admin/WikiPageManager.vue";
import { useAuthStore } from "../stores/auth";
import { useUiStore } from "../stores/ui";

const props = defineProps({
  section: {
    type: String,
    default: "users",
  },
});

const router = useRouter();
const auth = useAuthStore();
const ui = useUiStore();
const overview = ref(null);
const overviewLoading = ref(false);

const adminSections = [
  {
    key: "users",
    label: "用户管理",
    description: "筛选用户并执行封禁、恢复、删除和角色调整。",
    routeName: "admin",
  },
  {
    key: "competition-wiki",
    label: "竞赛 Wiki 页面管理",
    description: "管理竞赛 Wiki 标题下级菜单的显示、顺序、隐藏、删除和新增。",
    routeName: "manage-competition-wiki",
  },
  {
    key: "competition-zone",
    label: "赛事专区页面管理",
    description: "管理赛事专区下级菜单入口、顺序、隐藏、删除和新增。",
    routeName: "manage-competition-zone",
  },
  {
    key: "document-pages",
    label: "文档页面管理",
    description: "管理文档页左侧子页面的新增、移动、隐藏、删除和重命名。",
    routeName: "manage-document-pages",
  },
  {
    key: "announcements",
    label: "公告管理",
    description: "发布、定时、撤回和归档站内公告，控制首页、弹窗、横幅与通知。",
    routeName: "manage-announcements",
  },
  {
    key: "image-gallery",
    label: "图库管理",
    description: "上传站内图片、复制 Markdown 链接，并管理回收站。",
    routeName: "manage-image-gallery",
  },
  {
    key: "moments",
    label: "动态社区管理",
    description: "管理实名动态、评论、举报、热门前十、AI 审核和一键关闭。",
    routeName: "manage-moments",
  },
  {
    key: "deleted-content",
    label: "删除内容归档",
    description: "查看站内被删除或隐藏的 Trick、公告、锦标赛等内容快照。",
    routeName: "manage-deleted-content",
  },
  {
    key: "assistant",
    label: "AI 助手管理",
    description: "管理 AI 模型配置、调用限制和展示开关。",
    routeName: "manage-assistant",
  },
  {
    key: "ai-moderation",
    label: "AI 审核管理",
    description: "配置评论、工单、动态和动态评论的 AI 自动审核规则，并查看审核记录。",
    routeName: "manage-ai-moderation",
  },
  {
    key: "captcha",
    label: "验证码管理",
    description: "查看 Turnstile、二次验证配置状态、失败原因、风险 IP 和验证码审计日志。",
    routeName: "manage-captcha",
  },
  {
    key: "invitations",
    label: "邀请管理",
    description: "查看邀请码来源、被邀请用户、手机号验证后的贡献生效与回滚。",
    routeName: "manage-invitations",
  },
  {
    key: "site-visits",
    label: "网站访问量",
    description: "查看今日、本周、本月与累计访问趋势。",
    routeName: "manage-site-visits",
    superadminOnly: true,
  },
  {
    key: "events",
    label: "操作日志",
    description: "查看站内操作事件并导出日志。",
    routeName: "manage-events",
  },
  {
    key: "security",
    label: "安全日志",
    description: "查看登录与账户安全事件。",
    routeName: "manage-security",
  },
];

const adminSectionKeys = new Set(adminSections.map((item) => item.key));
const adminSectionMap = new Map(adminSections.map((item) => [item.key, item]));

const adminSectionGroups = computed(() => [
  {
    label: "基础管理",
    items: ["users", "competition-wiki", "competition-zone", "document-pages", "announcements", "image-gallery", "moments", "deleted-content", "assistant", "ai-moderation"].map((key) =>
      adminSectionMap.get(key)
    ),
  },
  {
    label: "审计日志",
    items: ["captcha", "invitations", "site-visits", "events", "security"]
      .map((key) => adminSectionMap.get(key))
      .filter((item) => item && (!item.superadminOnly || auth.isSuperAdmin)),
  },
]);

function normalizeAdminSection(rawSection) {
  const section = Array.isArray(rawSection) ? rawSection[0] : rawSection;
  if (typeof section !== "string" || !section.trim()) {
    return "users";
  }
  return adminSectionKeys.has(section) ? section : "users";
}

function buildAdminSectionRoute(section) {
  const item = adminSectionMap.get(section);
  return { name: item?.routeName || "admin" };
}

const currentSection = computed(() => normalizeAdminSection(props.section));
const currentSectionConfig = computed(
  () => adminSections.find((item) => item.key === currentSection.value) || adminSections[0]
);
const pendingSummary = computed(() => overview.value?.pending_summary || { total: 0, items: [] });
const visiblePendingItems = computed(() =>
  (pendingSummary.value.items || []).filter((item) => Number(item?.count || 0) > 0)
);

async function loadOverview() {
  overviewLoading.value = true;
  try {
    const { data } = await api.get("/admin/overview/");
    overview.value = data || null;
  } catch (error) {
    ui.error(error?.response?.data?.detail || "管理摘要加载失败");
  } finally {
    overviewLoading.value = false;
  }
}

watch(
  () => props.section,
  async (value) => {
    const normalized = normalizeAdminSection(value);
    if (value !== normalized) {
      await router.replace(buildAdminSectionRoute(normalized));
      return;
    }
    window.scrollTo({ top: 0, behavior: "auto" });
  },
  { immediate: true }
);

onMounted(() => {
  loadOverview();
});
</script>

<style scoped>
.admin-shell {
  display: grid;
  gap: 16px;
}

.admin-card {
  border: 1px solid var(--hairline);
  border-radius: 18px;
  background: var(--surface);
  box-shadow: var(--shadow-sm);
  padding: 16px;
}

.admin-card--gallery {
  padding: 0;
  overflow: hidden;
}

.admin-shell-head {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 16px;
  align-items: start;
}

.admin-shell-copy {
  min-width: 0;
  display: grid;
  gap: 4px;
}

.admin-kicker {
  margin: 0 0 4px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--accent);
}

.admin-shell-head h1 {
  margin: 0;
  font-size: clamp(32px, 4vw, 42px);
}

.admin-shell-note,
.meta {
  margin: 0;
  color: var(--text-quiet);
}

.admin-shell-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.pending-overview {
  display: grid;
  gap: 14px;
}

.pending-overview-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.pending-overview h2 {
  margin: 0 0 4px;
  color: var(--text-strong);
  font-size: 24px;
}

.pending-total {
  min-width: 118px;
  border: 1px solid var(--hairline);
  border-radius: 14px;
  background: var(--surface-strong);
  padding: 10px 12px;
  display: grid;
  gap: 4px;
  text-align: right;
}

.pending-total span {
  color: var(--text-quiet);
  font-size: 12px;
}

.pending-total strong {
  color: var(--text-strong);
  font-size: 28px;
  line-height: 1;
}

.pending-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 10px;
}

.pending-card {
  border: 1px solid var(--hairline);
  border-radius: 13px;
  background: var(--surface-strong);
  color: inherit;
  text-decoration: none;
  padding: 11px 12px;
  display: grid;
  gap: 6px;
  transition:
    border-color 0.18s ease,
    transform 0.18s ease,
    background 0.18s ease;
}

.pending-card:hover {
  transform: translateY(-1px);
  border-color: color-mix(in srgb, var(--accent) 30%, var(--hairline));
  background: color-mix(in srgb, var(--accent) 8%, var(--surface-strong));
}

.pending-card span {
  color: var(--text-soft);
  font-size: 13px;
}

.pending-card strong {
  color: var(--text-strong);
  font-size: 22px;
}

.pending-card--warning {
  border-color: color-mix(in srgb, #d97706 28%, var(--hairline));
}

.pending-card--danger {
  border-color: color-mix(in srgb, #dc2626 32%, var(--hairline));
}

.admin-nav-panels {
  display: grid;
  gap: 12px;
}

.admin-nav-group {
  display: grid;
  gap: 8px;
}

.admin-nav-group-title {
  margin: 0;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-quiet);
}

.admin-nav-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px;
}

.admin-nav-link {
  border: 1px solid var(--hairline);
  border-radius: 14px;
  background: var(--surface);
  box-shadow: var(--shadow-sm);
  padding: 12px 14px;
  display: grid;
  gap: 8px;
  transition: transform 0.18s ease, border-color 0.18s ease, background 0.18s ease;
}

.admin-nav-link:hover {
  transform: translateY(-1px);
  border-color: color-mix(in srgb, var(--accent) 28%, transparent);
}

.admin-nav-link--active {
  border-color: color-mix(in srgb, var(--accent) 42%, transparent);
  background: color-mix(in srgb, var(--accent) 10%, var(--surface-strong));
}

.admin-nav-top strong {
  font-size: 16px;
  color: var(--text-strong);
}

.admin-nav-desc {
  font-size: 13px;
  color: var(--text-soft);
  line-height: 1.55;
}

.admin-layout {
  display: grid;
}

.full {
  width: 100%;
}

@media (max-width: 900px) {
  .admin-shell-head {
    grid-template-columns: 1fr;
  }

  .pending-overview-head {
    flex-direction: column;
  }

  .pending-total {
    width: 100%;
    text-align: left;
  }
}
</style>

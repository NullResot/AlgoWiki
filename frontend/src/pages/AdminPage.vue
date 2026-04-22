<template>
  <section class="admin-shell">
    <header class="admin-card admin-shell-head">
      <div class="admin-shell-copy">
        <p class="admin-kicker">{{ currentSectionConfig.label }}</p>
        <h1>AlgoWiki 管理台</h1>
        <p class="meta">{{ currentSectionConfig.description }}</p>
        <p class="meta admin-shell-note">
          当前管理页包含用户管理、竞赛 Wiki 页面管理、赛事专区页面管理、文档页面管理、删除内容归档、AI 助手管理、操作日志和安全日志。
        </p>
      </div>
      <div class="admin-shell-actions">
        <a class="btn" href="/admin/" target="_blank" rel="noopener">打开 Django 后台</a>
      </div>
    </header>

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
      <article v-if="auth.isSuperAdmin" class="admin-card full">
        <SiteVisitStatsManager />
      </article>

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

      <article v-else-if="currentSection === 'deleted-content'" class="admin-card full">
        <DeletedContentManager />
      </article>

      <article v-else-if="currentSection === 'assistant'" class="admin-card full">
        <AIAssistantManager />
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
import { computed, watch } from "vue";
import { RouterLink, useRouter } from "vue-router";

import AIAssistantManager from "../components/admin/AIAssistantManager.vue";
import CompetitionZoneManager from "../components/admin/CompetitionZoneManager.vue";
import DeletedContentManager from "../components/admin/DeletedContentManager.vue";
import DocumentPageManager from "../components/admin/DocumentPageManager.vue";
import EventLogManager from "../components/admin/EventLogManager.vue";
import SecurityLogManager from "../components/admin/SecurityLogManager.vue";
import SiteVisitStatsManager from "../components/admin/SiteVisitStatsManager.vue";
import UserManager from "../components/admin/UserManager.vue";
import WikiPageManager from "../components/admin/WikiPageManager.vue";
import { useAuthStore } from "../stores/auth";

const props = defineProps({
  section: {
    type: String,
    default: "users",
  },
});

const router = useRouter();
const auth = useAuthStore();

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
    key: "deleted-content",
    label: "删除内容归档",
    description: "查看站内被删除或隐藏的 Trick、问答、公告、锦标赛等内容快照。",
    routeName: "manage-deleted-content",
  },
  {
    key: "assistant",
    label: "AI 助手管理",
    description: "管理 AI 模型配置、调用限制和展示开关。",
    routeName: "manage-assistant",
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

const adminSectionGroups = [
  {
    label: "基础管理",
    items: ["users", "competition-wiki", "competition-zone", "document-pages", "deleted-content", "assistant"].map((key) =>
      adminSectionMap.get(key)
    ),
  },
  {
    label: "审计日志",
    items: ["events", "security"].map((key) => adminSectionMap.get(key)),
  },
];

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
}
</style>

<template>
  <section class="home-redesign">
    <div class="home-inner">
      <section class="hero-block">
        <div class="hero-kicker">ALGO WIKI</div>
        <h1 class="hero-title">
          欢迎来到
          <br />
          AlgoWiki!
        </h1>
        <p class="hero-subtitle">竞赛信息，一站就够</p>
      </section>

      <section class="feature-grid">
        <article class="feature-card feature-card--main">
          <div class="team-head">
            <div>
              <h2>Team</h2>
            </div>
            <button v-if="canEditTeam" type="button" class="team-manage-btn" @click="toggleTeamEditor">
              {{ myTeamMember ? "修改" : "添加" }}
            </button>
          </div>

          <form v-if="canEditTeam && showTeamEditor" class="team-editor" @submit.prevent="submitMyTeamMember">
            <ImageUploadHelper label="上传头像" @uploaded="onTeamAvatarUploaded" />
            <input
              v-model.trim="teamForm.avatar_url"
              class="team-input"
              placeholder="头像链接（例如 https://...）"
            />
            <input
              v-model.trim="teamForm.display_id"
              class="team-input"
              placeholder="ID（例如 Null_Resot）"
            />
            <input
              v-model.trim="teamForm.profile_url"
              class="team-input"
              placeholder="主页链接（例如 https://github.com/xxx）"
            />
            <button type="submit" class="team-submit-btn" :disabled="savingTeamMember">
              {{ savingTeamMember ? "提交中..." : myTeamMember ? "保存修改" : "确认添加" }}
            </button>
          </form>

          <div class="team-grid">
            <a
              v-for="member in displayTeamMembers"
              :key="member.id"
              :href="member.profile_url"
              target="_blank"
              rel="noopener noreferrer"
              class="team-member-card"
            >
              <img class="team-avatar" :src="resolveAvatar(member.avatar_url)" :alt="member.display_id" />
              <span class="team-id">{{ member.display_id }}</span>
            </a>
          </div>
        </article>

        <article class="feature-card feature-card--side feature-card--support">
          <span class="support-chip">
            <span class="support-chip-icon" aria-hidden="true">★</span>
            支持开源
          </span>
          <h3>喜欢这个项目?</h3>
          <p>如果它帮到了你，欢迎到 GitHub 给项目点一个 Star，支持持续更新与维护。</p>
          <a
            class="support-btn"
            :href="starRepoUrl"
            target="_blank"
            rel="noopener noreferrer"
          >
            <span class="support-btn-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" focusable="false" aria-hidden="true">
                <path
                  d="M12 .5a12 12 0 0 0-3.79 23.39c.6.11.82-.26.82-.58v-2.22c-3.34.73-4.04-1.42-4.04-1.42-.54-1.39-1.33-1.75-1.33-1.75-1.08-.75.08-.73.08-.73 1.2.08 1.83 1.24 1.83 1.24 1.06 1.84 2.79 1.31 3.47 1 .1-.79.42-1.31.76-1.61-2.66-.31-5.46-1.35-5.46-5.99 0-1.33.47-2.41 1.24-3.27-.13-.31-.54-1.56.12-3.26 0 0 1.01-.33 3.31 1.25a11.4 11.4 0 0 1 6.03 0c2.3-1.58 3.31-1.25 3.31-1.25.66 1.7.25 2.95.12 3.26.77.86 1.24 1.94 1.24 3.27 0 4.66-2.81 5.67-5.49 5.98.43.38.81 1.12.81 2.26v3.35c0 .32.22.7.83.58A12 12 0 0 0 12 .5z"
                />
              </svg>
            </span>
            <span>前往 GitHub 点亮 Star</span>
          </a>
        </article>
      </section>

      <section class="announcement-board" id="announcement-feed">
        <header class="announcement-head">
          <h2>最新公告</h2>
          <button type="button" class="view-all" @click="viewAllAnnouncements">
            查看全部 >
          </button>
        </header>

        <div v-if="announcementHistory.length > 0" class="announcement-list">
          <article class="announcement-item" v-for="(item, index) in announcementHistory" :key="item.id">
            <div class="item-side">
              <span class="item-tag" :class="{ 'item-tag--update': index > 0 }">{{ index === 0 ? "NEW" : "UPDATE" }}</span>
              <time class="item-date">{{ formatDateTime(item.created_at) }}</time>
            </div>

            <div class="item-main">
              <h3>{{ item.title }}</h3>
              <p>{{ summarizeText(item.content_md, 132) }}</p>
              <div class="item-meta">
                <span class="item-meta-key">发布者</span>
                <span>{{ getAuthor(item) }}</span>
              </div>
            </div>

            <span class="item-arrow">›</span>
          </article>
        </div>
        <p v-else class="empty-state">暂无已发布公告记录。</p>
      </section>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";

import api from "../services/api";
import ImageUploadHelper from "../components/ImageUploadHelper.vue";
import { useAuthStore } from "../stores/auth";
import { useUiStore } from "../stores/ui";

const router = useRouter();
const auth = useAuthStore();
const ui = useUiStore();
const announcementHistory = ref([]);
const teamMembers = ref([]);
const myTeamMember = ref(null);
const savingTeamMember = ref(false);
const showTeamEditor = ref(false);
const teamForm = reactive({
  avatar_url: "",
  display_id: "",
  profile_url: "",
});

function onTeamAvatarUploaded(payload) {
  if (payload?.url) {
    teamForm.avatar_url = payload.url;
  }
}
const fallbackTeamMember = {
  id: "fallback-null-resot",
  display_id: "Null_Resot",
  avatar_url: "/wiki-assets/resot.png",
  profile_url: "https://github.com/NullResot",
};
const starRepoUrl = "https://github.com/NullResot/AlgoWiki";
const canEditTeam = computed(() => auth.isManager);
const displayTeamMembers = computed(() => {
  const list = Array.isArray(teamMembers.value) ? [...teamMembers.value] : [];
  const hasNullResot = list.some((item) => String(item?.display_id || "").toLowerCase() === "null_resot");
  if (!hasNullResot) {
    list.unshift(fallbackTeamMember);
  }
  return list;
});

async function loadAnnouncementHistory() {
  const { data } = await api.get("/announcements/published-history/", {
    params: { limit: 8 },
  });
  announcementHistory.value = Array.isArray(data) ? data : [];
}

async function loadTeamMembers() {
  const { data } = await api.get("/team-members/");
  teamMembers.value = Array.isArray(data?.results) ? data.results : Array.isArray(data) ? data : [];
}

function applyMyTeamMemberToForm(item) {
  teamForm.avatar_url = item?.avatar_url || "";
  teamForm.display_id = item?.display_id || "";
  teamForm.profile_url = item?.profile_url || "";
}

async function loadMyTeamMember() {
  if (!auth.isAuthenticated || !canEditTeam.value) {
    myTeamMember.value = null;
    showTeamEditor.value = false;
    applyMyTeamMemberToForm(null);
    return;
  }
  const { data } = await api.get("/team-members/mine/");
  myTeamMember.value = data?.member || null;
  applyMyTeamMemberToForm(myTeamMember.value);
}

async function viewAllAnnouncements() {
  await router.push({ name: "announcements" });
}

function toPlainText(value) {
  return String(value || "")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, "[图片]")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/`{1,3}/g, "")
    .replace(/^#{1,6}\s*/gm, "")
    .replace(/\r\n/g, "\n")
    .trim();
}

function summarizeText(value, limit = 96) {
  const text = toPlainText(value).replace(/\n+/g, " ").replace(/\s+/g, " ").trim();
  if (text.length <= limit) {
    return text;
  }
  return `${text.slice(0, limit)}...`;
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

function getAuthor(item) {
  return item?.created_by?.username || "system";
}

function resolveAvatar(value) {
  const source = String(value || "").trim();
  if (!source) return "/wiki-assets/resot.png";
  return source;
}

function toggleTeamEditor() {
  showTeamEditor.value = !showTeamEditor.value;
}

async function submitMyTeamMember() {
  if (!canEditTeam.value) return;
  const hasExisting = Boolean(myTeamMember.value);
  const payload = {
    avatar_url: String(teamForm.avatar_url || "").trim(),
    display_id: String(teamForm.display_id || "").trim(),
    profile_url: String(teamForm.profile_url || "").trim(),
  };
  if (!payload.display_id || !payload.profile_url) {
    ui.error("请填写 ID 和主页链接。");
    return;
  }

  savingTeamMember.value = true;
  try {
    await api.post("/team-members/mine/", payload);
    await Promise.all([loadTeamMembers(), loadMyTeamMember()]);
    showTeamEditor.value = false;
    ui.success(hasExisting ? "Team 信息已更新。" : "Team 信息已添加。");
  } finally {
    savingTeamMember.value = false;
  }
}

watch(
  () => [auth.isAuthenticated, auth.user?.role],
  async () => {
    await loadMyTeamMember();
  },
  { deep: false }
);

onMounted(async () => {
  await Promise.all([loadAnnouncementHistory(), loadTeamMembers(), loadMyTeamMember()]);
});
</script>

<style scoped>
.home-redesign {
  width: 100%;
  background: var(--surface-page);
}

.home-inner {
  width: 100%;
  max-width: 1420px;
  margin: 0 auto;
  padding: 10px clamp(14px, 2.4vw, 28px) 30px;
}

.hero-block {
  text-align: center;
  padding: clamp(18px, 3.2vw, 42px) 0 clamp(12px, 2.6vw, 24px);
  animation: fade-in-up 0.8s cubic-bezier(0.2, 0.8, 0.2, 1);
}

.hero-kicker {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  padding: 5px 12px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.12em;
  color: var(--text-soft);
  background: var(--surface-chip);
  border: 1px solid var(--panel-border);
}

.hero-title {
  margin-top: 18px;
  font-family: var(--font-display);
  font-size: clamp(46px, 8.4vw, 124px);
  line-height: 0.96;
  letter-spacing: -0.03em;
  font-weight: 700;
  color: var(--text-strong);
}

.hero-subtitle {
  margin: 16px auto 0;
  max-width: 740px;
  font-size: clamp(16px, 1.8vw, 34px);
  font-weight: 500;
  line-height: 1.34;
  color: var(--text-quiet);
}

.feature-grid {
  margin-top: 14px;
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
  gap: clamp(14px, 1.7vw, 24px);
}

.feature-card {
  border-radius: var(--radius-lg);
  background: var(--surface);
  border: 1px solid var(--panel-border);
  box-shadow: var(--card-shadow);
  transition: transform 260ms ease, box-shadow 260ms ease;
}

.feature-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--card-shadow-hover);
}

.feature-card--main {
  position: relative;
  overflow: hidden;
  padding: clamp(20px, 2.2vw, 30px);
  min-height: 250px;
}

.feature-card--main::after {
  content: "";
  position: absolute;
  top: -120px;
  right: -120px;
  width: 300px;
  height: 300px;
  border-radius: 50%;
  background: var(--surface-highlight);
  filter: blur(24px);
}

.feature-card--main h2 {
  font-size: clamp(28px, 2.6vw, 44px);
  font-weight: 700;
  line-height: 1.1;
}

.feature-card--main p {
  margin: 10px 0 0;
  color: var(--text-quiet);
  font-size: clamp(16px, 1.25vw, 22px);
}

.team-head {
  position: relative;
  z-index: 1;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 14px;
}

.team-manage-btn {
  border: 0;
  border-radius: 999px;
  padding: 10px 20px;
  background: var(--accent-gradient);
  color: var(--accent-contrast);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 200ms ease, box-shadow 200ms ease, background-color 200ms ease;
  box-shadow: var(--accent-shadow);
}

.team-manage-btn:hover {
  transform: translateY(-1px);
}

.team-editor {
  margin-top: 16px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr)) auto;
  gap: 10px;
}

.team-input {
  border: 1px solid var(--input-border);
  border-radius: 12px;
  padding: 10px 12px;
  font-size: 14px;
  background: var(--input-bg);
  color: var(--text);
}

.team-input:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--input-focus);
}

.team-submit-btn {
  border: 0;
  border-radius: 12px;
  background: var(--accent-gradient);
  color: var(--accent-contrast);
  padding: 10px 16px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: var(--accent-shadow);
}

.team-submit-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.team-grid {
  margin-top: 12px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(132px, 1fr));
  gap: 12px;
}

.team-member-card {
  border-radius: var(--radius-md);
  border: 1px solid var(--panel-border-strong);
  background: var(--surface-strong);
  padding: 14px 10px 12px;
  display: grid;
  justify-items: center;
  gap: 10px;
  text-decoration: none;
  color: var(--text-strong);
  transition: transform 220ms ease, box-shadow 220ms ease, border-color 220ms ease;
}

.team-member-card:hover {
  transform: translateY(-2px);
  border-color: color-mix(in srgb, var(--accent) 30%, transparent);
  box-shadow: var(--shadow-md);
}

.team-avatar {
  width: 62px;
  height: 62px;
  border-radius: 999px;
  object-fit: cover;
  border: 2px solid var(--panel-border);
  background: var(--surface-soft);
}

.team-id {
  font-size: 14px;
  font-weight: 600;
  line-height: 1.2;
  text-align: center;
  word-break: break-word;
}

.feature-card--side {
  padding: clamp(18px, 1.9vw, 26px);
  min-height: clamp(220px, 20vw, 250px);
  text-align: center;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: center;
  align-self: center;
}

.feature-card--support {
  text-align: left;
  align-items: flex-start;
  justify-content: flex-start;
  gap: 14px;
  padding: clamp(20px, 2vw, 28px);
  transition: transform 200ms ease, box-shadow 200ms ease, border-color 200ms ease;
}

.feature-card--support:hover {
  transform: translateY(-3px);
  box-shadow: var(--card-shadow-hover);
  border-color: color-mix(in srgb, var(--accent) 22%, transparent);
}

.support-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border-radius: 999px;
  padding: 6px 12px;
  background: var(--surface-warning);
  color: var(--surface-warning-text);
  font-size: 12px;
  font-weight: 600;
}

.support-chip-icon {
  font-size: 14px;
  line-height: 1;
}

.feature-card--support h3 {
  margin: 4px 0 0;
  font-size: clamp(24px, 1.6vw, 30px);
  line-height: 1.12;
}

.feature-card--support p {
  margin: 0;
  color: var(--text-soft);
  font-size: clamp(15px, 0.95vw, 17px);
  line-height: 1.5;
}

.support-btn {
  margin-top: 4px;
  width: 100%;
  border-radius: 999px;
  padding: 10px 16px;
  background: var(--accent-gradient);
  color: var(--accent-contrast);
  font-size: clamp(15px, 0.9vw, 17px);
  font-weight: 600;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  transition: filter 200ms ease, box-shadow 200ms ease, transform 200ms ease;
}

.feature-card--support:hover .support-btn {
  filter: brightness(1.04);
  box-shadow: var(--accent-shadow);
}

.support-btn:active {
  transform: translateY(1px);
}

.support-btn-icon {
  display: inline-flex;
  width: 18px;
  height: 18px;
}

.support-btn-icon svg {
  width: 100%;
  height: 100%;
  fill: currentColor;
}

.announcement-board {
  margin-top: clamp(18px, 2vw, 28px);
}

.announcement-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 16px;
  padding: 0 2px;
}

.announcement-head h2 {
  font-size: clamp(28px, 2.2vw, 42px);
  letter-spacing: -0.02em;
}

.view-all {
  border: 0;
  background: transparent;
  color: var(--accent);
  font-size: clamp(16px, 1vw, 18px);
  font-weight: 600;
  cursor: pointer;
}

.view-all:hover {
  text-decoration: underline;
}

.announcement-list {
  display: grid;
  gap: 14px;
}

.announcement-item {
  border-radius: var(--radius-lg);
  background: var(--surface-strong);
  border: 1px solid var(--panel-border);
  box-shadow: var(--shadow-sm);
  padding: 14px 16px;
  display: grid;
  grid-template-columns: 150px minmax(0, 1fr) 26px;
  gap: 16px;
  align-items: center;
  transition: transform 220ms ease, box-shadow 220ms ease, border-color 220ms ease;
}

.announcement-item:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
  border-color: color-mix(in srgb, var(--accent) 18%, transparent);
}

.item-side {
  display: grid;
  gap: 8px;
}

.item-tag {
  width: fit-content;
  border-radius: 999px;
  padding: 4px 12px;
  font-size: 13px;
  line-height: 1;
  letter-spacing: 0.06em;
  font-weight: 700;
  color: var(--accent);
  background: var(--accent-soft);
}

.item-tag--update {
  color: var(--text-soft);
  background: var(--label-bg);
}

.item-date {
  color: var(--label-text);
  font-size: 14px;
  line-height: 1.35;
}

.item-main h3 {
  margin: 0;
  color: var(--text-strong);
  font-size: clamp(20px, 1.45vw, 28px);
  line-height: 1.2;
  transition: color 220ms ease;
}

.announcement-item:hover .item-main h3 {
  color: var(--accent);
}

.item-main p {
  margin: 6px 0 10px;
  color: var(--text-soft);
  font-size: clamp(15px, 1vw, 18px);
  line-height: 1.5;
}

.item-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--label-text);
  font-size: 14px;
}

.item-meta-key {
  border-radius: 8px;
  padding: 1px 8px;
  background: var(--label-bg);
}

.item-arrow {
  justify-self: end;
  color: var(--accent);
  font-size: 34px;
  line-height: 1;
  opacity: 0;
  transform: translateX(-10px);
  transition: opacity 220ms ease, transform 220ms ease;
}

.announcement-item:hover .item-arrow {
  opacity: 1;
  transform: translateX(0);
}

.empty-state {
  margin: 0;
  border-radius: var(--radius-lg);
  background: var(--surface);
  border: 1px solid var(--panel-border);
  padding: 18px;
  color: var(--text-quiet);
}

@keyframes fade-in-up {
  from {
    opacity: 0;
    transform: translateY(20px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 1200px) {
  .home-inner {
    max-width: 1100px;
  }

  .hero-title {
    font-size: clamp(42px, 8vw, 98px);
  }

  .feature-card--main {
    min-height: 220px;
  }

  .feature-card--side h3 {
    font-size: clamp(24px, 2vw, 34px);
  }

  .announcement-item {
    grid-template-columns: 118px minmax(0, 1fr) 24px;
  }

  .item-main h3 {
    font-size: clamp(22px, 1.7vw, 30px);
  }

  .item-main p {
    font-size: clamp(16px, 1.1vw, 20px);
  }
}

@media (max-width: 900px) {
  .home-inner {
    padding: 10px 10px 24px;
  }

  .hero-title {
    font-size: clamp(36px, 12vw, 72px);
  }

  .hero-subtitle {
    font-size: clamp(15px, 4.9vw, 24px);
  }

  .feature-grid {
    margin-top: 22px;
    grid-template-columns: 1fr;
  }

  .feature-card {
    border-radius: var(--radius-lg);
  }

  .feature-card--main {
    min-height: auto;
    padding: 16px;
  }

  .feature-card--main h2 {
    font-size: clamp(28px, 7vw, 42px);
  }

  .feature-card--main p {
    font-size: clamp(16px, 4.5vw, 22px);
  }

  .team-head {
    flex-direction: column;
    align-items: flex-start;
  }

  .team-manage-btn {
    width: 100%;
  }

  .team-editor {
    grid-template-columns: 1fr;
  }

  .team-grid {
    grid-template-columns: repeat(auto-fill, minmax(116px, 1fr));
  }

  .feature-card--side {
    padding: 20px;
    min-height: auto;
    align-self: stretch;
  }

  .feature-card--support {
    gap: 12px;
    padding: 18px;
  }

  .support-chip {
    font-size: 15px;
    padding: 6px 12px;
  }

  .support-chip-icon {
    font-size: 13px;
  }

  .feature-card--support h3 {
    margin-top: 4px;
    font-size: clamp(24px, 6.2vw, 30px);
  }

  .feature-card--support p {
    font-size: clamp(14px, 3.8vw, 17px);
  }

  .support-btn {
    width: 100%;
    font-size: 15px;
    padding: 10px 12px;
  }

  .support-btn-icon {
    width: 16px;
    height: 16px;
  }

  .announcement-board {
    margin-top: 24px;
  }

  .announcement-head h2 {
    font-size: clamp(28px, 8vw, 38px);
  }

  .view-all {
    font-size: 14px;
  }

  .announcement-item {
    grid-template-columns: 1fr;
    border-radius: 22px;
    padding: 14px;
    gap: 10px;
  }

  .item-side {
    grid-template-columns: auto 1fr;
    align-items: center;
    gap: 8px;
  }

  .item-date {
    font-size: 13px;
  }

  .item-main h3 {
    font-size: clamp(22px, 6vw, 30px);
  }

  .item-main p {
    font-size: clamp(15px, 4.2vw, 20px);
  }

  .item-arrow {
    display: none;
  }
}

@media (max-width: 600px) {
  .home-inner {
    padding: 6px 10px 20px;
  }

  .hero-block {
    padding-top: 18px;
  }

  .hero-kicker {
    font-size: 11px;
  }

  .team-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
  }

  .team-member-card {
    padding: 12px 8px 10px;
    border-radius: var(--radius-md);
  }

  .team-avatar {
    width: 56px;
    height: 56px;
  }

  .team-id {
    font-size: 13px;
  }

  .announcement-head {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }

  .announcement-item {
    border-radius: var(--radius-lg);
    padding: 12px;
  }

  .item-side {
    grid-template-columns: 1fr;
    gap: 6px;
  }

  .item-meta {
    font-size: 13px;
    flex-wrap: wrap;
  }
}
</style>

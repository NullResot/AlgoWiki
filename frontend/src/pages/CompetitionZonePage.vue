<template>
  <section class="competition-zone">
    <header class="zone-header">
      <h1>{{ activeSection?.title || "赛事专区" }}</h1>
      <section
        v-if="activeBuiltinView !== 'calendar'"
        class="zone-description markdown"
        v-html="activeSectionDescriptionHtml"
      ></section>
    </header>

    <section v-if="activeBuiltinView === 'schedule'" class="zone-block">
      <div class="zone-contributors">
        <ContributorsPanel
          :contributors="schedulePageContributors"
          title="本页录入者"
          creator-badge-text="录入者"
          empty-text="当前页面暂无录入者"
        />
      </div>
      <div class="toolbar">
        <div class="year-tabs">
          <button
            v-for="year in scheduleYears"
            :key="`year-${year}`"
            type="button"
            class="btn btn-mini"
            :class="{ 'btn-accent': Number(year) === Number(activeScheduleYear) }"
            @click="activeScheduleYear = Number(year)"
          >
            {{ year }} 年
          </button>
        </div>
        <button type="button" class="btn" :disabled="loadingSchedules" @click="loadSchedules">
          {{ loadingSchedules ? "刷新中..." : "刷新" }}
        </button>
      </div>

      <section v-if="canSubmitCompetition" ref="scheduleEditorRef" class="editor-card">
        <h2>{{ editingScheduleId ? "修改赛事时刻表" : canManageCompetition ? "新增赛事时刻表" : "提交赛事时刻表" }}</h2>
        <div class="form-grid form-grid--schedule">
          <input v-model="scheduleForm.event_date" class="input" type="date" />
          <input v-model.trim="scheduleForm.competition_time_range" class="input" placeholder="比赛时间" />
          <input v-model.trim="scheduleForm.competition_type" class="input" placeholder="比赛名称" />
          <input v-model.trim="scheduleForm.location" class="input" placeholder="地点" />
          <input v-model.trim="scheduleForm.qq_group" class="input" placeholder="QQ群号或链接" />
          <select v-model="scheduleForm.announcement" class="select">
            <option value="">不关联公告</option>
            <option v-for="item in noticeOptions" :key="item.id" :value="String(item.id)">
              {{ item.title }}
            </option>
          </select>
        </div>
        <div class="action-row">
          <button type="button" class="btn btn-accent" :disabled="savingSchedule" @click="submitSchedule">
            {{ savingSchedule ? "提交中..." : editingScheduleId ? "保存修改" : canManageCompetition ? "新增记录" : "提交审核" }}
          </button>
          <button v-if="editingScheduleId" type="button" class="btn" :disabled="savingSchedule" @click="resetScheduleForm">
            取消修改
          </button>
        </div>
      </section>

      <div v-if="loadingSchedules" class="meta">赛事时刻表加载中...</div>
      <div v-else-if="!scheduleRows.length" class="meta">当前年份暂无赛事时刻表。</div>
      <div v-else class="schedule-table-wrap">
        <table class="schedule-table">
          <thead>
            <tr>
              <th>日期</th>
              <th>比赛时间</th>
              <th>比赛名称</th>
              <th>地点</th>
              <th>QQ群或链接</th>
              <th>关联公告</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in scheduleRows" :key="row.id" :class="{ 'schedule-row--muted': row.is_past }">
              <td>{{ formatDate(row.event_date) }}</td>
              <td>{{ row.competition_time_range || "-" }}</td>
              <td class="schedule-table__title">{{ row.competition_type || "-" }}</td>
              <td>{{ row.location || "-" }}</td>
              <td>{{ row.qq_group || "-" }}</td>
              <td>
                <button v-if="row.announcement" type="button" class="btn btn-mini" @click="openNoticeFromSchedule(row)">
                  {{ row.announcement_title || "查看公告" }}
                </button>
                <span v-else class="meta">-</span>
              </td>
              <td>
                <div class="table-actions">
                  <template v-if="canManageCompetition">
                    <button type="button" class="btn btn-mini" @click="startEditSchedule(row)">编辑</button>
                    <button type="button" class="btn btn-mini" @click="removeSchedule(row)">删除</button>
                  </template>
                  <span v-else class="meta">-</span>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section v-else-if="activeBuiltinView === 'notice'" class="zone-block">
      <div class="zone-contributors">
        <ContributorsPanel
          :contributors="noticePageContributors"
          title="本页录入者"
          creator-badge-text="录入者"
          empty-text="当前页面暂无录入者"
        />
      </div>

      <div class="notice-layout">
        <aside class="notice-filter">
          <h3>赛事筛选</h3>
          <div class="chips">
            <button
              v-for="item in seriesFilterOptions"
              :key="item.key"
              type="button"
              class="btn btn-mini"
              :class="{ 'btn-accent': item.key === activeSeries }"
              @click="activeSeries = item.key"
            >
              {{ item.name }}
            </button>
          </div>
          <template v-if="needsYearStage">
            <label class="filter-label">年份</label>
            <div class="chips">
              <button
                v-for="year in seriesYears"
                :key="`notice-year-${year}`"
                type="button"
                class="btn btn-mini"
                :class="{ 'btn-accent': String(year) === String(activeNoticeYear) }"
                @click="activeNoticeYear = year"
              >
                {{ year === FILTER_ALL ? STAGE_LABELS.all : year }}
              </button>
            </div>
            <label class="filter-label">阶段</label>
            <div class="chips">
              <button
                v-for="stage in stageOptions"
                :key="stage.key"
                type="button"
                class="btn btn-mini"
                :class="{ 'btn-accent': stage.key === activeStage }"
                @click="activeStage = stage.key"
              >
                {{ stage.name }}
              </button>
            </div>
          </template>
        </aside>

        <div class="notice-main">
        <section v-if="canSubmitCompetition" ref="noticeEditorRef" class="editor-card">
          <h2>{{ editingNoticeId ? "修改赛事公告" : canManageCompetition ? "发布赛事公告" : "提交赛事公告" }}</h2>
          <div class="form-grid form-grid--notice">
            <select v-model="noticeForm.series" class="select" @change="normalizeNoticeForm">
              <option v-for="item in seriesOptions" :key="item.key" :value="item.key">{{ item.name }}</option>
            </select>
            <input
              v-if="isSeriesWithYear(noticeForm.series)"
              v-model.number="noticeForm.year"
              class="input"
              type="number"
              min="2000"
              max="2099"
              placeholder="年份"
            />
            <select v-if="isSeriesWithYear(noticeForm.series)" v-model="noticeForm.stage" class="select">
              <option v-for="item in nestedStageOptions" :key="item.key" :value="item.key">{{ item.name }}</option>
            </select>
            <input v-model.trim="noticeForm.title" class="input form-span" placeholder="公告标题" />
          </div>
          <textarea v-model="noticeForm.content_md" class="textarea notice-textarea" placeholder="Markdown 公告内容"></textarea>
          <label v-if="canManageCompetition" class="switch-line">
            <input type="checkbox" v-model="noticeForm.is_visible" />
            <span>对外显示</span>
          </label>
          <div class="action-row">
            <button type="button" class="btn btn-accent" :disabled="savingNotice" @click="submitNotice">
              {{ savingNotice ? "提交中..." : editingNoticeId ? "保存修改" : canManageCompetition ? "发布公告" : "提交审核" }}
            </button>
            <button v-if="editingNoticeId" type="button" class="btn" :disabled="savingNotice" @click="resetNoticeForm">
              取消修改
            </button>
          </div>
        </section>

        <div class="list-card">
          <div class="toolbar">
            <h2>公告列表</h2>
            <button type="button" class="btn" :disabled="loadingNotices" @click="loadNotices">
              {{ loadingNotices ? "刷新中..." : "刷新" }}
            </button>
          </div>
          <div v-if="loadingNotices" class="meta">赛事公告加载中...</div>
          <div v-else-if="!noticeRows.length" class="meta">当前筛选条件下暂无公告。</div>
          <div v-else class="notice-list">
            <article
              v-for="item in noticeRows"
              :key="item.id"
              class="notice-row"
              :class="{ 'notice-row--active': item.id === activeNoticeId }"
            >
              <button type="button" class="notice-main-btn" @click="openNoticeDetail(item.id)">
                <strong>{{ item.title }}</strong>
                <span class="meta">{{ formatDateTime(item.published_at || item.created_at) }} · {{ stageText(item.stage) }}</span>
              </button>
              <div v-if="canManageCompetition" class="table-actions">
                <button type="button" class="btn btn-mini" @click="startEditNotice(item)">编辑</button>
                <button type="button" class="btn btn-mini" @click="removeNotice(item)">删除</button>
              </div>
            </article>
          </div>
        </div>

          <article v-if="activeNotice" class="detail-card">
            <h2>{{ activeNotice.title }}</h2>
            <p class="meta">
              {{ seriesText(activeNotice.series) }}
              <template v-if="isSeriesWithYear(activeNotice.series)"> · {{ activeNotice.year }} · {{ stageText(activeNotice.stage) }}</template>
              · {{ formatDateTime(activeNotice.published_at || activeNotice.created_at) }}
            </p>
            <section class="markdown" v-html="renderMarkdown(activeNotice.content_md || '')"></section>
          </article>
        </div>
      </div>
    </section>

    <CompetitionPracticePanel v-else-if="activeBuiltinView === 'practice'" />
    <CompetitionCalendarPage v-else-if="activeBuiltinView === 'calendar'" />
    <ExtraPage v-else-if="activeBuiltinView === 'tricks'" slug="tricks" />
    <QaPage v-else-if="activeBuiltinView === 'qa'" />
    <ExtraPage v-else-if="activeCustomPageSlug" :slug="activeCustomPageSlug" />
    <div v-else class="meta">当前分区暂未配置内容。</div>
  </section>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useRequestControllers } from "../composables/useRequestControllers";
import { useCompetitionZoneNav } from "../composables/useCompetitionZoneNav";
import CompetitionPracticePanel from "../components/CompetitionPracticePanel.vue";
import ContributorsPanel from "../components/ContributorsPanel.vue";
import api, { isRequestCanceled } from "../services/api";
import { renderMarkdown } from "../services/markdown";
import { useAuthStore } from "../stores/auth";
import { useUiStore } from "../stores/ui";
import { aggregateCreatorContributors } from "../utils/contributors";
import CompetitionCalendarPage from "./CompetitionCalendarPage.vue";
import ExtraPage from "./ExtraPage.vue";
import QaPage from "./QaPage.vue";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const ui = useUiStore();
const requests = useRequestControllers();
const { competitionZoneNav, loadCompetitionZoneNav } = useCompetitionZoneNav();

const FALLBACK_ZONE_SECTIONS = [
  { key: "calendar", title: "比赛日历表", target_type: "builtin", builtin_view: "calendar", page_slug: "" },
  { key: "tricks", title: "trick技巧", target_type: "builtin", builtin_view: "tricks", page_slug: "" },
  { key: "schedule", title: "赛事时刻表", target_type: "builtin", builtin_view: "schedule", page_slug: "" },
  { key: "notice", title: "赛事公告", target_type: "builtin", builtin_view: "notice", page_slug: "" },
  { key: "qa", title: "问答", target_type: "builtin", builtin_view: "qa", page_slug: "" },
];

const FILTER_ALL = "all";
const SERIES_LABELS = { icpc: "ICPC", ccpc: "CCPC", lanqiao: "蓝桥杯", tianti: "天梯赛" };
const STAGE_LABELS = { all: "全部", general: "通用", regional: "区域赛", invitational: "邀请赛", provincial: "省赛", network: "网络赛" };
const nestedStageOptions = [
  { key: "regional", name: STAGE_LABELS.regional },
  { key: "invitational", name: STAGE_LABELS.invitational },
  { key: "provincial", name: STAGE_LABELS.provincial },
  { key: "network", name: STAGE_LABELS.network },
];

const resolvedZoneSections = computed(() => (competitionZoneNav.value.length ? competitionZoneNav.value : FALLBACK_ZONE_SECTIONS));
const activeTab = ref("calendar");
const canManageCompetition = computed(() => auth.isSchoolOrHigher);
const canSubmitCompetition = computed(() => auth.isAuthenticated);
const activeSection = computed(() => resolvedZoneSections.value.find((item) => item.key === activeTab.value) || resolvedZoneSections.value[0] || null);
const activeBuiltinView = computed(() => (activeSection.value?.target_type === "builtin" ? String(activeSection.value.builtin_view || "").trim() : ""));
const activeCustomPageSlug = computed(() => (activeSection.value?.target_type === "page" ? String(activeSection.value.page_slug || "").trim() : ""));
const activeSectionDescription = computed(() => {
  const mapping = {
    calendar: "集中查看近期编程竞赛时间安排。",
    tricks: "整理赛时技巧、经验与踩坑记录。",
    schedule: "维护赛事时刻表与对应公告入口。",
    notice: "发布并归档各类赛事公告。",
    qa: "针对赛事相关问题进行提问与回答。",
    practice: "整理补题链接与练习入口。",
  };
  return mapping[activeBuiltinView.value] || "当前分区为管理员可配置的自定义页面。";
});
const activeSectionDescriptionHtml = computed(() => {
  if (activeBuiltinView.value === "tricks") {
    return renderMarkdown(
      "提交tirck前务必查阅[trick规范手册](https://www.algowiki.cn/extra/about?doc=trick-guide)了解规范",
    );
  }
  if (activeBuiltinView.value === "notice") {
    return renderMarkdown(
      "填写公告前，请先查阅 [赛事公告规范手册](https://www.algowiki.cn/extra/about?doc=announcement-guide) 了解规范",
    );
  }
  if (activeBuiltinView.value === "schedule") {
    return renderMarkdown("更全面的群聊收集以及比赛榜单可跳转到 [ACMer.info](https://acmer.info/)");
  }
  return renderMarkdown(activeSectionDescription.value || "");
});

const scheduleYears = ref([new Date().getFullYear()]);
const activeScheduleYear = ref(new Date().getFullYear());
const scheduleRows = ref([]);
const allScheduleRows = ref([]);
const noticeOptions = ref([]);
const loadingSchedules = ref(false);
const savingSchedule = ref(false);
const editingScheduleId = ref(null);
const scheduleEditorRef = ref(null);
const initialScheduleAnnouncementId = ref(null);
const scheduleForm = reactive({ event_date: "", competition_time_range: "", competition_type: "", location: "", qq_group: "", announcement: "" });

const seriesOptions = ref([]);
const activeSeries = ref(FILTER_ALL);
const activeNoticeYear = ref(FILTER_ALL);
const activeStage = ref(FILTER_ALL);
const noticeRows = ref([]);
const activeNoticeId = ref(null);
const pendingNoticeId = ref(null);
const loadingNotices = ref(false);
const savingNotice = ref(false);
const editingNoticeId = ref(null);
const noticeEditorRef = ref(null);
const noticeForm = reactive({ title: "", content_md: "", series: "icpc", year: new Date().getFullYear(), stage: "regional", is_visible: true });

const activeNotice = computed(() => noticeRows.value.find((item) => item.id === activeNoticeId.value) || null);
const schedulePageContributors = computed(() =>
  aggregateCreatorContributors(allScheduleRows.value, { userKey: "created_by" }),
);
const noticePageContributors = computed(() =>
  aggregateCreatorContributors(noticeOptions.value, {
    userKey: "created_by",
    getTime: (item) => item?.published_at || item?.created_at || null,
  }),
);
const seriesFilterOptions = computed(() => [{ key: FILTER_ALL, name: STAGE_LABELS.all }, ...seriesOptions.value]);
const needsYearStage = computed(() => activeSeries.value === FILTER_ALL || isSeriesWithYear(activeSeries.value));
const seriesYears = computed(() => {
  const years = seriesOptions.value.flatMap((item) => item?.years || []).map(Number).filter(Number.isFinite);
  const sorted = [...new Set(years)].sort((a, b) => b - a);
  return [FILTER_ALL, ...(sorted.length ? sorted : [new Date().getFullYear()])];
});
const stageOptions = computed(() => {
  if (activeSeries.value === FILTER_ALL || isSeriesWithYear(activeSeries.value)) {
    return [{ key: FILTER_ALL, name: STAGE_LABELS.all }, ...nestedStageOptions];
  }
  return [{ key: FILTER_ALL, name: STAGE_LABELS.all }, { key: "general", name: STAGE_LABELS.general }];
});

function normalizeZoneTab(value) {
  const key = String(value || "").trim();
  return resolvedZoneSections.value.some((item) => item.key === key) ? key : resolvedZoneSections.value[0]?.key || "calendar";
}
function normalizePositiveId(value) {
  const normalized = Number.parseInt(String(value || "").trim(), 10);
  return Number.isInteger(normalized) && normalized > 0 ? normalized : null;
}
function findSectionKeyByBuiltinView(builtinView, fallbackKey = "calendar") {
  return resolvedZoneSections.value.find((item) => item.target_type === "builtin" && item.builtin_view === builtinView)?.key || fallbackKey;
}
function syncZoneTabToRoute(tab) {
  const normalized = normalizeZoneTab(tab);
  const nextQuery = { ...route.query, tab: normalized };
  if (normalized !== findSectionKeyByBuiltinView("notice", "notice")) delete nextQuery.notice;
  if (normalized !== findSectionKeyByBuiltinView("qa", "qa")) delete nextQuery.question;
  if (
    String(route.query.tab || "").trim() === String(nextQuery.tab || "").trim() &&
    String(route.query.notice || "").trim() === String(nextQuery.notice || "").trim() &&
    String(route.query.question || "").trim() === String(nextQuery.question || "").trim()
  ) {
    return;
  }
  router.replace({ name: "competitions", query: nextQuery }).catch(() => {});
}
function syncNoticeQuery(noticeId) {
  const normalizedId = normalizePositiveId(noticeId);
  const nextQuery = { ...route.query, tab: findSectionKeyByBuiltinView("notice", "notice") };
  if (normalizedId) nextQuery.notice = String(normalizedId);
  else delete nextQuery.notice;
  delete nextQuery.question;
  if (
    String(route.query.tab || "").trim() === String(nextQuery.tab || "").trim() &&
    String(route.query.notice || "").trim() === String(nextQuery.notice || "").trim()
  ) {
    return;
  }
  router.replace({ name: "competitions", query: nextQuery }).catch(() => {});
}
function getErrorText(error, fallback = "操作失败") {
  const payload = error?.response?.data;
  if (!payload) return fallback;
  if (typeof payload === "string") return payload;
  if (typeof payload?.detail === "string") return payload.detail;
  return fallback;
}
function extractRows(data) {
  if (Array.isArray(data)) return data;
  return Array.isArray(data?.results) ? data.results : [];
}
function nextPageFromUrl(url) {
  if (!url) return null;
  try {
    const parsed = new URL(url, window.location.origin);
    const page = Number(parsed.searchParams.get("page"));
    return Number.isFinite(page) && page > 0 ? page : null;
  } catch {
    return null;
  }
}
async function fetchAll(path, params = {}, signal) {
  const rows = [];
  let page = 1;
  while (page) {
    const { data } = await api.get(path, { params: { ...params, page }, signal });
    rows.push(...extractRows(data));
    page = Array.isArray(data) ? null : nextPageFromUrl(data?.next);
  }
  return rows;
}
function formatDate(value) {
  if (!value) return "-";
  return String(value).slice(0, 10);
}
function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")} ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}
function isSeriesWithYear(series) { return series === "icpc" || series === "ccpc"; }
function normalizeStageValue(stage) { return stage || "general"; }
function stageText(stage) { return STAGE_LABELS[normalizeStageValue(stage)] || stage || "-"; }
function seriesText(series) { return SERIES_LABELS[series] || series || "-"; }
function normalizeDateInputValue(value) { return value ? String(value).slice(0, 10) : ""; }

function resetScheduleForm() {
  editingScheduleId.value = null;
  initialScheduleAnnouncementId.value = null;
  scheduleForm.event_date = "";
  scheduleForm.competition_time_range = "";
  scheduleForm.competition_type = "";
  scheduleForm.location = "";
  scheduleForm.qq_group = "";
  scheduleForm.announcement = "";
}
async function loadScheduleYears() {
  const controller = requests.replace("schedule-years");
  try {
    const rows = await fetchAll("/competition-schedules/", {}, controller.signal);
    if (!requests.isCurrent("schedule-years", controller)) return;
    allScheduleRows.value = rows;
    const years = rows.map((item) => Number(String(item.event_date || "").slice(0, 4))).filter(Number.isFinite);
    scheduleYears.value = [...new Set(years)].sort((a, b) => b - a);
    if (!scheduleYears.value.length) scheduleYears.value = [new Date().getFullYear()];
    if (!scheduleYears.value.includes(Number(activeScheduleYear.value))) activeScheduleYear.value = scheduleYears.value[0];
  } catch (error) {
    if (isRequestCanceled(error) || !requests.isCurrent("schedule-years", controller)) return;
    allScheduleRows.value = [];
    throw error;
  } finally {
    requests.release("schedule-years", controller);
  }
}
async function loadSchedules() {
  const controller = requests.replace("schedules");
  loadingSchedules.value = true;
  try {
    const nextRows = await fetchAll("/competition-schedules/", { year: Number(activeScheduleYear.value) }, controller.signal);
    if (!requests.isCurrent("schedules", controller)) return;
    scheduleRows.value = nextRows;
  } catch (error) {
    if (isRequestCanceled(error) || !requests.isCurrent("schedules", controller)) return;
    scheduleRows.value = [];
    ui.error(getErrorText(error, "赛事时刻表加载失败"));
  } finally {
    if (requests.release("schedules", controller)) {
      loadingSchedules.value = false;
    }
  }
}
function startEditSchedule(row) {
  editingScheduleId.value = row.id;
  initialScheduleAnnouncementId.value = row.announcement ? Number(row.announcement) : null;
  scheduleForm.event_date = normalizeDateInputValue(row.event_date);
  scheduleForm.competition_time_range = row.competition_time_range || "";
  scheduleForm.competition_type = row.competition_type || "";
  scheduleForm.location = row.location || "";
  scheduleForm.qq_group = row.qq_group || "";
  scheduleForm.announcement = row.announcement ? String(row.announcement) : "";
  nextTick(() => scheduleEditorRef.value?.scrollIntoView({ behavior: "smooth", block: "start" }));
}
async function submitSchedule() {
  if (!canSubmitCompetition.value) return;
  const eventDate = normalizeDateInputValue(scheduleForm.event_date);
  if (!eventDate || !String(scheduleForm.competition_type || "").trim() || !String(scheduleForm.location || "").trim()) {
    ui.info("请完整填写日期、比赛名称和地点。");
    return;
  }
  const payload = {
    event_date: eventDate,
    competition_time_range: String(scheduleForm.competition_time_range || "").trim(),
    competition_type: String(scheduleForm.competition_type || "").trim(),
    location: String(scheduleForm.location || "").trim(),
    qq_group: String(scheduleForm.qq_group || "").trim(),
    announcement: scheduleForm.announcement ? Number(scheduleForm.announcement) : null,
  };
  savingSchedule.value = true;
  try {
    if (editingScheduleId.value) await api.patch(`/competition-schedules/${editingScheduleId.value}/`, payload);
    else {
      const { data } = await api.post("/competition-schedules/", payload);
      ui.success(data?.status === "pending" ? "赛事时刻表已提交，等待管理员审核" : "赛事时刻表已新增");
    }
    if (editingScheduleId.value) ui.success("赛事时刻表已更新");
    resetScheduleForm();
    await Promise.all([loadScheduleYears(), loadSchedules()]);
  } catch (error) {
    ui.error(getErrorText(error, "赛事时刻表提交失败"));
  } finally {
    savingSchedule.value = false;
  }
}
async function removeSchedule(row) {
  if (!canManageCompetition.value || !window.confirm(`确认删除赛事记录「${row.competition_type}」？`)) return;
  try {
    await api.delete(`/competition-schedules/${row.id}/`);
    ui.success("赛事记录已删除");
    if (editingScheduleId.value === row.id) resetScheduleForm();
    await Promise.all([loadScheduleYears(), loadSchedules()]);
  } catch (error) {
    ui.error(getErrorText(error, "赛事记录删除失败"));
  }
}
async function loadNoticeTaxonomy() {
  const controller = requests.replace("notice-taxonomy");
  try {
    const { data } = await api.get("/competition-notices/taxonomy/", {
      signal: controller.signal,
    });
    if (!requests.isCurrent("notice-taxonomy", controller)) return;
    const incoming = Array.isArray(data?.series) ? data.series : [];
    seriesOptions.value = incoming.length
      ? incoming.map((item) => ({ ...item, name: SERIES_LABELS[item.key] || item.name || item.key }))
      : [{ key: "icpc", name: "ICPC", years: [new Date().getFullYear()] }, { key: "ccpc", name: "CCPC", years: [new Date().getFullYear()] }];
  } catch (error) {
    if (isRequestCanceled(error) || !requests.isCurrent("notice-taxonomy", controller)) return;
    throw error;
  } finally {
    requests.release("notice-taxonomy", controller);
  }
}
function normalizeNoticeForm() {
  if (!isSeriesWithYear(noticeForm.series)) {
    noticeForm.year = null;
    noticeForm.stage = "general";
  } else if (!nestedStageOptions.some((item) => item.key === noticeForm.stage)) {
    noticeForm.stage = nestedStageOptions[0].key;
  }
}
function normalizeNoticeFilter() {
  if (!needsYearStage.value) {
    activeNoticeYear.value = FILTER_ALL;
    activeStage.value = "general";
    return;
  }
  if (!seriesYears.value.map(String).includes(String(activeNoticeYear.value))) activeNoticeYear.value = FILTER_ALL;
  if (!stageOptions.value.some((item) => item.key === activeStage.value)) activeStage.value = FILTER_ALL;
}
async function loadNoticeOptions() {
  if (!canSubmitCompetition.value) return;
  const controller = requests.replace("notice-options");
  try {
    const nextOptions = await fetchAll(
      "/competition-notices/",
      { include_hidden: canManageCompetition.value ? 1 : 0, order: "oldest" },
      controller.signal,
    );
    if (!requests.isCurrent("notice-options", controller)) return;
    noticeOptions.value = nextOptions;
  } catch (error) {
    if (isRequestCanceled(error) || !requests.isCurrent("notice-options", controller)) return;
    noticeOptions.value = [];
  } finally {
    requests.release("notice-options", controller);
  }
}
async function loadNotices() {
  const controller = requests.replace("notices");
  loadingNotices.value = true;
  try {
    const params = { include_hidden: canManageCompetition.value ? 1 : 0 };
    if (activeSeries.value !== FILTER_ALL) params.series = activeSeries.value;
    if (needsYearStage.value && activeNoticeYear.value !== FILTER_ALL) params.year = Number(activeNoticeYear.value);
    if (activeStage.value && activeStage.value !== FILTER_ALL) params.stage = activeStage.value;
    const nextRows = await fetchAll("/competition-notices/", params, controller.signal);
    if (!requests.isCurrent("notices", controller)) return;
    noticeRows.value = nextRows;
    activeNoticeId.value = noticeRows.value.find((item) => item.id === pendingNoticeId.value)?.id || noticeRows.value[0]?.id || null;
    pendingNoticeId.value = null;
  } catch (error) {
    if (isRequestCanceled(error) || !requests.isCurrent("notices", controller)) return;
    noticeRows.value = [];
    activeNoticeId.value = null;
    ui.error(getErrorText(error, "赛事公告加载失败"));
  } finally {
    if (requests.release("notices", controller)) {
      loadingNotices.value = false;
    }
  }
}
async function applyRouteNoticeQuery(rawNoticeId) {
  const noticeId = normalizePositiveId(rawNoticeId);
  pendingNoticeId.value = noticeId;
  if (!noticeId) {
    requests.cancel("notice-detail");
    return;
  }

  const existing = noticeRows.value.find((item) => Number(item.id) === noticeId);
  if (existing) {
    requests.cancel("notice-detail");
    activeNoticeId.value = existing.id;
    pendingNoticeId.value = null;
    return;
  }

  const controller = requests.replace("notice-detail");
  try {
    const { data } = await api.get(`/competition-notices/${noticeId}/`, {
      signal: controller.signal,
    });
    if (!requests.isCurrent("notice-detail", controller)) return;
    if (!data?.id) {
      pendingNoticeId.value = null;
      return;
    }
    if (data.series) activeSeries.value = data.series;
    if (data.year) activeNoticeYear.value = Number(data.year);
    if (data.stage) activeStage.value = normalizeStageValue(data.stage);
    if (activeBuiltinView.value === "notice") {
      await loadNotices();
    }
  } catch (error) {
    if (isRequestCanceled(error) || !requests.isCurrent("notice-detail", controller)) return;
    pendingNoticeId.value = null;
  } finally {
    requests.release("notice-detail", controller);
  }
}
function openNoticeDetail(id) {
  activeNoticeId.value = id;
  syncNoticeQuery(id);
}
function openNoticeFromSchedule(row) {
  activeTab.value = findSectionKeyByBuiltinView("notice", "notice");
  if (row.announcement_series) activeSeries.value = row.announcement_series;
  if (row.announcement_year) activeNoticeYear.value = Number(row.announcement_year);
  if (row.announcement_stage) activeStage.value = normalizeStageValue(row.announcement_stage);
  pendingNoticeId.value = Number(row.announcement);
  syncNoticeQuery(row.announcement);
  loadNotices();
}
function resetNoticeForm() {
  editingNoticeId.value = null;
  noticeForm.title = "";
  noticeForm.content_md = "";
  noticeForm.series = seriesOptions.value[0]?.key || "icpc";
  noticeForm.year = new Date().getFullYear();
  noticeForm.stage = "regional";
  noticeForm.is_visible = true;
  normalizeNoticeForm();
}
function startEditNotice(item) {
  editingNoticeId.value = item.id;
  noticeForm.title = item.title || "";
  noticeForm.content_md = item.content_md || "";
  noticeForm.series = item.series || "icpc";
  noticeForm.year = item.year ?? new Date().getFullYear();
  noticeForm.stage = normalizeStageValue(item.stage);
  noticeForm.is_visible = Boolean(item.is_visible);
  nextTick(() => noticeEditorRef.value?.scrollIntoView({ behavior: "smooth", block: "start" }));
}
async function submitNotice() {
  if (!canSubmitCompetition.value || !String(noticeForm.title || "").trim() || !String(noticeForm.content_md || "").trim()) {
    ui.info("请填写公告标题和正文内容。");
    return;
  }
  const payload = {
    title: String(noticeForm.title || "").trim(),
    content_md: noticeForm.content_md || "",
    series: noticeForm.series,
    year: isSeriesWithYear(noticeForm.series) ? Number(noticeForm.year) : null,
    stage: isSeriesWithYear(noticeForm.series) ? noticeForm.stage : "general",
    is_visible: canManageCompetition.value ? Boolean(noticeForm.is_visible) : false,
  };
  savingNotice.value = true;
  try {
    const { data } = editingNoticeId.value
      ? await api.patch(`/competition-notices/${editingNoticeId.value}/`, payload)
      : await api.post("/competition-notices/", payload);
    ui.success(
      editingNoticeId.value
        ? "赛事公告已更新"
        : data?.status === "pending"
          ? "赛事公告已提交，等待管理员审核"
          : "赛事公告已发布",
    );
    pendingNoticeId.value = data?.id || null;
    resetNoticeForm();
    await Promise.all([loadNoticeTaxonomy(), loadNoticeOptions(), loadNotices(), loadSchedules()]);
  } catch (error) {
    ui.error(getErrorText(error, "赛事公告提交失败"));
  } finally {
    savingNotice.value = false;
  }
}
async function removeNotice(item) {
  if (!canManageCompetition.value || !window.confirm(`确认删除赛事公告「${item.title}」？`)) return;
  try {
    await api.delete(`/competition-notices/${item.id}/`);
    ui.success("赛事公告已删除");
    if (editingNoticeId.value === item.id) resetNoticeForm();
    await Promise.all([loadNoticeTaxonomy(), loadNoticeOptions(), loadNotices(), loadSchedules()]);
  } catch (error) {
    ui.error(getErrorText(error, "赛事公告删除失败"));
  }
}

watch(() => route.query.tab, (value) => { activeTab.value = normalizeZoneTab(value); }, { immediate: true });
watch(() => resolvedZoneSections.value, () => { const normalized = normalizeZoneTab(route.query.tab); activeTab.value = normalized; syncZoneTabToRoute(normalized); }, { deep: true });
watch(() => activeScheduleYear.value, () => { if (activeBuiltinView.value === "schedule") loadSchedules(); });
watch(() => activeSeries.value, () => { normalizeNoticeFilter(); if (activeBuiltinView.value === "notice") loadNotices(); });
watch(() => [activeNoticeYear.value, activeStage.value, activeBuiltinView.value], () => { if (activeBuiltinView.value === "notice") loadNotices(); });
watch(
  () => activeBuiltinView.value,
  async (value) => {
    if (value === "notice" && pendingNoticeId.value) {
      await applyRouteNoticeQuery(pendingNoticeId.value);
    }
  }
);
watch(
  () => route.query.notice,
  async (value) => {
    if (activeBuiltinView.value !== "notice" && String(route.query.tab || "").trim() !== findSectionKeyByBuiltinView("notice", "notice")) {
      pendingNoticeId.value = normalizePositiveId(value);
      return;
    }
    await applyRouteNoticeQuery(value);
  },
  { immediate: true }
);

onMounted(async () => {
  await loadCompetitionZoneNav();
  const normalized = normalizeZoneTab(route.query.tab);
  activeTab.value = normalized;
  syncZoneTabToRoute(normalized);
  try {
    await Promise.all([loadScheduleYears(), loadNoticeTaxonomy(), loadNoticeOptions()]);
    resetNoticeForm();
    await Promise.all([loadSchedules(), loadNotices()]);
    await applyRouteNoticeQuery(route.query.notice);
  } catch (error) {
    ui.error(getErrorText(error, "赛事专区初始化失败"));
  }
});
</script>

<style scoped>
.competition-zone { width: min(1440px, 100%); margin: 0 auto; display: grid; gap: 20px; }
.zone-header { display: grid; gap: 6px; }
.zone-header h1 { font-size: clamp(32px, 3vw, 44px); }
.zone-description { color: var(--muted); }
.zone-description :deep(p) { margin: 0; }
.zone-description :deep(a) { color: var(--link); text-decoration: underline; text-underline-offset: 2px; }
.meta { color: var(--muted); }
.zone-block { display: grid; gap: 16px; }
.zone-contributors {
  border-top: 1px solid color-mix(in srgb, var(--hairline) 84%, transparent);
  padding-top: 18px;
}
.toolbar, .action-row, .table-actions, .year-tabs, .chips { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.toolbar { justify-content: space-between; }
.editor-card, .list-card, .detail-card, .notice-filter, .schedule-table-wrap { border-top: 1px solid color-mix(in srgb, var(--hairline) 84%, transparent); padding-top: 18px; }
.form-grid { display: grid; gap: 10px; }
.form-grid--schedule { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.form-grid--notice { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.form-span { grid-column: 1 / -1; }
.notice-layout { display: grid; grid-template-columns: 260px minmax(0, 1fr); gap: 24px; align-items: start; }
.notice-main { min-width: 0; display: grid; gap: 16px; }
.notice-filter { position: sticky; top: 88px; display: grid; gap: 12px; }
.filter-label { font-size: 13px; color: var(--text-quiet); }
.notice-row { grid-template-columns: minmax(0, 1fr) auto; }
.notice-main-btn { border: 0; background: transparent; text-align: left; padding: 0; display: grid; gap: 4px; }
.notice-row--active { box-shadow: inset 3px 0 0 color-mix(in srgb, var(--accent) 24%, transparent); padding-left: 12px; }
.notice-textarea { min-height: 180px; }
.schedule-table-wrap { overflow-x: auto; }
.schedule-table {
  width: 100%;
  min-width: 980px;
  border-collapse: separate;
  border-spacing: 0;
}
.schedule-table th,
.schedule-table td {
  padding: 14px 12px;
  border-bottom: 1px solid color-mix(in srgb, var(--hairline) 84%, transparent);
  text-align: left;
  vertical-align: middle;
}
.schedule-table th {
  font-size: 13px;
  font-weight: 800;
  color: var(--text-quiet);
  white-space: nowrap;
}
.schedule-table td {
  font-size: 15px;
}
.schedule-table__title {
  font-weight: 700;
  color: var(--text);
  min-width: 220px;
}

.schedule-row--muted {
  opacity: 0.72;
}
@media (max-width: 960px) { .notice-layout { grid-template-columns: 1fr; } .notice-filter { position: static; } }
@media (max-width: 720px) { .form-grid--schedule, .form-grid--notice, .notice-row { grid-template-columns: 1fr; } }
</style>

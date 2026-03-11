<template>
  <section class="competition-zone">
    <header class="zone-header">
      <h1>赛事专区</h1>
      <p>赛事时刻表与赛事公告统一管理。学校用户与管理员可直接发布与编辑，无需审核。</p>
    </header>

    <nav class="zone-tabs" aria-label="赛事专区子页面">
      <button
        type="button"
        class="tab-btn"
        :class="{ 'tab-btn--active': activeTab === 'schedule' }"
        @click="activeTab = 'schedule'"
      >
        赛事时刻表
      </button>
      <button
        type="button"
        class="tab-btn"
        :class="{ 'tab-btn--active': activeTab === 'notice' }"
        @click="activeTab = 'notice'"
      >
        赛事公告
      </button>
    </nav>

    <section v-if="activeTab === 'schedule'" class="schedule-page">
      <section class="card schedule-toolbar">
        <div class="year-tabs">
          <button
            v-for="year in scheduleYears"
            :key="`year-${year}`"
            type="button"
            class="btn year-btn"
            :class="{ 'btn-accent': Number(year) === Number(activeScheduleYear) }"
            @click="activeScheduleYear = Number(year)"
          >
            {{ year }} 年
          </button>
        </div>
        <button type="button" class="btn" :disabled="loadingSchedules" @click="loadSchedules">
          {{ loadingSchedules ? "刷新中..." : "刷新" }}
        </button>
      </section>

      <section v-if="canManageCompetition" class="card schedule-editor">
        <h2>{{ editingScheduleId ? "修改时刻表记录" : "添加时刻表记录" }}</h2>
        <div class="editor-grid">
          <input v-model="scheduleForm.event_date" class="input" type="date" />
          <input v-model.trim="scheduleForm.competition_time_range" class="input" placeholder="比赛时间（如 09:00-14:00）" />
          <input v-model.trim="scheduleForm.competition_type" class="input" placeholder="比赛类型（例如 ICPC 区域赛）" />
          <input v-model.trim="scheduleForm.location" class="input" placeholder="地点" />
          <input v-model.trim="scheduleForm.qq_group" class="input" placeholder="QQ群聊（群号/链接均可）" />
          <select v-model="scheduleForm.announcement" class="select">
            <option value="">无公告关联</option>
            <option v-for="item in noticeOptions" :key="`notice-opt-${item.id}`" :value="String(item.id)">
              {{ item.title }}
            </option>
          </select>
        </div>
        <div class="editor-actions">
          <button type="button" class="btn btn-accent" :disabled="savingSchedule" @click="submitSchedule">
            {{ savingSchedule ? "提交中..." : editingScheduleId ? "保存修改" : "添加记录" }}
          </button>
          <button v-if="editingScheduleId" type="button" class="btn" :disabled="savingSchedule" @click="resetScheduleForm">
            取消修改
          </button>
        </div>
      </section>

      <section class="card schedule-table-wrap">
        <p v-if="loadingSchedules" class="meta state-line">时刻表加载中...</p>
        <p v-else-if="scheduleRows.length === 0" class="meta state-line">当前年份暂无记录。</p>
        <table v-else class="schedule-table">
          <thead>
            <tr>
              <th>时间（年月日）</th>
              <th>比赛时间</th>
              <th>比赛类型</th>
              <th>地点</th>
              <th>QQ群聊</th>
              <th>公告</th>
              <th v-if="canManageCompetition">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in scheduleRows"
              :key="`schedule-${row.id}`"
              :class="{ 'row-past': isPast(row) }"
            >
              <td>{{ formatDate(row.event_date) }}</td>
              <td>{{ row.competition_time_range || "-" }}</td>
              <td>{{ row.competition_type || "-" }}</td>
              <td>{{ row.location || "-" }}</td>
              <td>
                <a
                  v-if="isHttpUrl(row.qq_group)"
                  :href="row.qq_group"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="table-link"
                >
                  {{ row.qq_group }}
                </a>
                <span v-else>{{ row.qq_group || "-" }}</span>
              </td>
              <td>
                <button
                  v-if="row.announcement"
                  type="button"
                  class="btn btn-mini"
                  @click="openNoticeFromSchedule(row)"
                >
                  {{ row.announcement_title || "查看公告" }}
                </button>
                <span v-else>-</span>
              </td>
              <td v-if="canManageCompetition">
                <div class="table-actions">
                  <button type="button" class="btn btn-mini" @click="startEditSchedule(row)">编辑</button>
                  <button type="button" class="btn btn-mini" @click="removeSchedule(row)">删除</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </section>
    </section>

    <section v-else class="notice-page">
      <aside class="card notice-filter">
        <h3>赛事分类</h3>
        <div class="series-tabs">
          <button
            v-for="item in seriesFilterOptions"
            :key="`series-${item.key}`"
            type="button"
            class="btn series-btn"
            :class="{ 'btn-accent': item.key === activeSeries }"
            @click="selectSeries(item.key)"
          >
            {{ item.name }}
          </button>
        </div>

        <template v-if="needsYearStage">
          <div class="filter-block">
            <label>年份</label>
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
          </div>
          <div class="filter-block">
            <label>二级分类</label>
            <div class="chips">
              <button
                v-for="stage in stageOptions"
                :key="`notice-stage-${stage.key}`"
                type="button"
                class="btn btn-mini"
                :class="{ 'btn-accent': stage.key === activeStage }"
                @click="activeStage = stage.key"
              >
                {{ stage.name }}
              </button>
            </div>
          </div>
        </template>
      </aside>

      <div class="notice-main">
        <section v-if="canManageCompetition" class="card notice-editor">
          <h2>{{ editingNoticeId ? "修改赛事公告" : "发布赛事公告" }}</h2>
          <div class="editor-grid notice-grid">
            <select v-model="noticeForm.series" class="select" @change="normalizeNoticeForm">
              <option v-for="item in seriesOptions" :key="`form-series-${item.key}`" :value="item.key">
                {{ item.name }}
              </option>
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
              <option v-for="item in nestedStageOptions" :key="`form-stage-${item.key}`" :value="item.key">
                {{ item.name }}
              </option>
            </select>
            <input v-model.trim="noticeForm.title" class="input notice-title-input" placeholder="公告标题" />
          </div>
          <textarea
            v-model="noticeForm.content_md"
            class="textarea notice-textarea"
            placeholder="Markdown 公告内容"
          ></textarea>
          <ImageUploadHelper label="上传图片并插入 Markdown" @uploaded="onNoticeImageUploaded" />
          <label class="switch-line">
            <input type="checkbox" v-model="noticeForm.is_visible" />
            <span>公开显示</span>
          </label>
          <div class="editor-actions">
            <button type="button" class="btn btn-accent" :disabled="savingNotice" @click="submitNotice">
              {{ savingNotice ? "提交中..." : editingNoticeId ? "保存修改" : "发布公告" }}
            </button>
            <button v-if="editingNoticeId" type="button" class="btn" :disabled="savingNotice" @click="resetNoticeForm">
              取消修改
            </button>
          </div>
        </section>

        <section class="card notice-list-wrap">
          <header class="notice-list-head">
            <h2>公告条目</h2>
            <button type="button" class="btn" :disabled="loadingNotices" @click="loadNotices">
              {{ loadingNotices ? "刷新中..." : "刷新" }}
            </button>
          </header>

          <p v-if="loadingNotices" class="meta state-line">赛事公告加载中...</p>
          <p v-else-if="noticeRows.length === 0" class="meta state-line">当前筛选下暂无赛事公告。</p>

          <div v-else class="notice-list">
            <article
              v-for="item in noticeRows"
              :key="`notice-${item.id}`"
              class="notice-row"
              :class="{ 'notice-row--active': item.id === activeNoticeId }"
            >
              <button type="button" class="notice-main-btn" @click="openNoticeDetail(item.id)">
                <strong>{{ item.title }}</strong>
                <span class="meta">
                  {{ formatDateTime(item.published_at || item.created_at) }}
                  ·
                  {{ stageText(item.stage) }}
                </span>
              </button>
              <div v-if="canManageCompetition" class="notice-row-tools">
                <button type="button" class="btn btn-mini" @click="startEditNotice(item)">编辑</button>
                <button type="button" class="btn btn-mini" @click="removeNotice(item)">删除</button>
              </div>
            </article>
          </div>
        </section>

        <article v-if="activeNotice" class="card notice-detail">
          <header class="notice-detail-head">
            <h2>{{ activeNotice.title }}</h2>
            <div class="meta">
              {{ seriesText(activeNotice.series) }}
              <template v-if="isSeriesWithYear(activeNotice.series)"> · {{ activeNotice.year }} · {{ stageText(activeNotice.stage) }}</template>
              · {{ formatDateTime(activeNotice.published_at || activeNotice.created_at) }}
            </div>
          </header>
          <section class="markdown notice-markdown" v-html="renderMarkdown(activeNotice.content_md || '')"></section>
        </article>
      </div>
    </section>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";

import { renderMarkdown } from "../services/markdown";
import api from "../services/api";
import ImageUploadHelper from "../components/ImageUploadHelper.vue";
import { useAuthStore } from "../stores/auth";
import { useUiStore } from "../stores/ui";

const auth = useAuthStore();
const ui = useUiStore();

const activeTab = ref("schedule");
const canManageCompetition = computed(() => auth.isSchoolOrHigher);
const FILTER_ALL = "all";

const SERIES_LABELS = {
  icpc: "ICPC",
  ccpc: "CCPC",
  lanqiao: "蓝桥杯",
  tianti: "天梯赛",
};

const STAGE_LABELS = {
  all: "全部",
  general: "通用",
  regional: "区域赛",
  invitational: "邀请赛",
  provincial: "省赛",
  network: "网络赛",
};

const nestedStageOptions = [
  { key: "regional", name: STAGE_LABELS.regional },
  { key: "invitational", name: STAGE_LABELS.invitational },
  { key: "provincial", name: STAGE_LABELS.provincial },
  { key: "network", name: STAGE_LABELS.network },
];

const scheduleYears = ref([2026]);
const activeScheduleYear = ref(2026);
const scheduleRows = ref([]);
const noticeOptions = ref([]);

const loadingSchedules = ref(false);
const savingSchedule = ref(false);
const editingScheduleId = ref(null);
const scheduleForm = reactive({
  event_date: "",
  competition_time_range: "",
  competition_type: "",
  location: "",
  qq_group: "",
  announcement: "",
});

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
const noticeForm = reactive({
  title: "",
  content_md: "",
  series: "icpc",
  year: 2026,
  stage: "regional",
  is_visible: true,
});

function appendMarkdown(target, snippet) {
  const next = String(snippet || "").trim();
  if (!next) return String(target || "");
  const base = String(target || "");
  return base ? `${base}\n\n${next}\n` : `${next}\n`;
}

function onNoticeImageUploaded(payload) {
  noticeForm.content_md = appendMarkdown(noticeForm.content_md, payload?.markdown);
}

const activeNotice = computed(() => noticeRows.value.find((item) => item.id === activeNoticeId.value) || null);
const seriesFilterOptions = computed(() => [
  { key: FILTER_ALL, name: STAGE_LABELS.all },
  ...seriesOptions.value,
]);
const needsYearStage = computed(() => activeSeries.value === FILTER_ALL || isSeriesWithYear(activeSeries.value));

const seriesYears = computed(() => {
  const pullYears = (list) =>
    list
      .flatMap((item) => item?.years || [])
      .map((value) => Number(value))
      .filter((value) => Number.isFinite(value));

  if (activeSeries.value === FILTER_ALL) {
    const years = pullYears(seriesOptions.value.filter((item) => isSeriesWithYear(item.key)));
    const sorted = years.length ? [...new Set(years)].sort((a, b) => b - a) : [2026];
    return [FILTER_ALL, ...sorted];
  }

  const found = seriesOptions.value.find((item) => item.key === activeSeries.value);
  const years = pullYears(found ? [found] : []);
  if (years.length > 0) return [FILTER_ALL, ...[...new Set(years)].sort((a, b) => b - a)];
  if (isSeriesWithYear(activeSeries.value)) return [FILTER_ALL, 2026];
  return [FILTER_ALL];
});

const stageOptions = computed(() => {
  if (activeSeries.value === FILTER_ALL || isSeriesWithYear(activeSeries.value)) {
    return [{ key: FILTER_ALL, name: STAGE_LABELS.all }, ...nestedStageOptions];
  }
  return [{ key: FILTER_ALL, name: STAGE_LABELS.all }, { key: "general", name: STAGE_LABELS.general }];
});

function extractRows(payload) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.results)) return payload.results;
  return [];
}

function nextPageFromUrl(value) {
  if (!value) return null;
  try {
    const parsed = new URL(value, window.location.origin);
    const page = Number(parsed.searchParams.get("page"));
    return Number.isFinite(page) && page > 0 ? page : null;
  } catch {
    return null;
  }
}

async function fetchAll(path, params = {}) {
  const rows = [];
  let page = 1;
  while (page) {
    const { data } = await api.get(path, { params: { ...params, page } });
    if (Array.isArray(data)) {
      rows.push(...data);
      break;
    }
    rows.push(...extractRows(data));
    page = nextPageFromUrl(data?.next);
  }
  return rows;
}

function getErrorText(error, fallback = "Operation failed") {
  const status = error?.response?.status;
  const payload = error?.response?.data;
  if (!payload) {
    return status ? `${fallback} (HTTP ${status})` : fallback;
  }
  if (typeof payload === "string") return payload;
  if (typeof payload?.detail === "string") return payload.detail;
  if (typeof payload?.message === "string") return payload.message;
  if (typeof payload === "object") {
    const rows = [];
    for (const [key, value] of Object.entries(payload)) {
      if (Array.isArray(value)) rows.push(`${key}: ${value.join("; ")}`);
      else if (typeof value === "string") rows.push(`${key}: ${value}`);
      else if (value && typeof value === "object" && typeof value.detail === "string") rows.push(`${key}: ${value.detail}`);
    }
    if (rows.length) return rows.join("; ");
  }
  return status ? `${fallback} (HTTP ${status})` : fallback;
}

function isSeriesWithYear(series) {
  return series === "icpc" || series === "ccpc";
}

function seriesText(series) {
  return SERIES_LABELS[series] || series || "-";
}

function stageText(stage) {
  return STAGE_LABELS[normalizeStageValue(stage)] || stage || "-";
}

function normalizeStageValue(stage) {
  if (stage === "regional_invitation") return "regional";
  if (stage === "provincial_network") return "provincial";
  return stage || "general";
}

function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("zh-CN");
}

function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function isHttpUrl(value) {
  return /^https?:\/\//i.test(String(value || "").trim());
}

function isPast(row) {
  if (typeof row?.is_past === "boolean") return row.is_past;
  const target = new Date(row?.event_date || "");
  if (Number.isNaN(target.getTime())) return false;
  target.setHours(23, 59, 59, 999);
  return Date.now() > target.getTime();
}

async function loadScheduleYears() {
  try {
    const { data } = await api.get("/competition-schedules/years/");
    const years = (Array.isArray(data?.years) ? data.years : [])
      .map((value) => Number(value))
      .filter((value) => Number.isFinite(value));
    const normalized = years.length ? [...new Set(years)].sort((a, b) => b - a) : [2026];
    scheduleYears.value = normalized;
    if (!normalized.includes(Number(activeScheduleYear.value))) {
      activeScheduleYear.value = normalized.includes(2026) ? 2026 : normalized[0];
    }
  } catch (error) {
    scheduleYears.value = [2026];
    activeScheduleYear.value = 2026;
    ui.error(getErrorText(error, "读取年份失败"));
  }
}

async function loadSchedules() {
  loadingSchedules.value = true;
  try {
    const rows = await fetchAll("/competition-schedules/", {
      year: Number(activeScheduleYear.value),
      order: "asc",
    });
    scheduleRows.value = rows.sort((a, b) => String(a.event_date).localeCompare(String(b.event_date)));
  } catch (error) {
    scheduleRows.value = [];
    ui.error(getErrorText(error, "时刻表加载失败"));
  } finally {
    loadingSchedules.value = false;
  }
}

function resetScheduleForm() {
  editingScheduleId.value = null;
  scheduleForm.event_date = "";
  scheduleForm.competition_time_range = "";
  scheduleForm.competition_type = "";
  scheduleForm.location = "";
  scheduleForm.qq_group = "";
  scheduleForm.announcement = "";
}

function startEditSchedule(row) {
  editingScheduleId.value = row.id;
  scheduleForm.event_date = row.event_date || "";
  scheduleForm.competition_time_range = row.competition_time_range || "";
  scheduleForm.competition_type = row.competition_type || "";
  scheduleForm.location = row.location || "";
  scheduleForm.qq_group = row.qq_group || "";
  scheduleForm.announcement = row.announcement ? String(row.announcement) : "";
}

async function submitSchedule() {
  if (!canManageCompetition.value) return;
  if (!scheduleForm.event_date || !scheduleForm.competition_type || !scheduleForm.location) {
    ui.info("请完整填写时间、比赛类型、地点。");
    return;
  }

  const payload = {
    event_date: scheduleForm.event_date,
    competition_time_range: scheduleForm.competition_time_range || "",
    competition_type: scheduleForm.competition_type,
    location: scheduleForm.location,
    qq_group: scheduleForm.qq_group || "",
    announcement: scheduleForm.announcement ? Number(scheduleForm.announcement) : null,
  };

  savingSchedule.value = true;
  try {
    if (editingScheduleId.value) {
      await api.patch(`/competition-schedules/${editingScheduleId.value}/`, payload);
      ui.success("时刻表记录已更新");
    } else {
      await api.post("/competition-schedules/", payload);
      ui.success("时刻表记录已添加");
    }
    resetScheduleForm();
    await Promise.all([loadScheduleYears(), loadSchedules()]);
  } catch (error) {
    ui.error(getErrorText(error, "提交时刻表失败"));
  } finally {
    savingSchedule.value = false;
  }
}

async function removeSchedule(row) {
  if (!canManageCompetition.value) return;
  if (!window.confirm(`确认删除记录：${row.competition_type}（${row.event_date}）？`)) return;
  try {
    await api.delete(`/competition-schedules/${row.id}/`);
    ui.success("记录已删除");
    if (editingScheduleId.value === row.id) resetScheduleForm();
    await Promise.all([loadScheduleYears(), loadSchedules()]);
  } catch (error) {
    ui.error(getErrorText(error, "删除失败"));
  }
}

async function loadNoticeTaxonomy() {
  try {
    const { data } = await api.get("/competition-notices/taxonomy/");
    const incoming = Array.isArray(data?.series) ? data.series : [];
    if (incoming.length) {
      seriesOptions.value = incoming.map((item) => ({
        ...item,
        name: SERIES_LABELS[item.key] || item.name || item.key,
      }));
    } else {
      seriesOptions.value = [
        { key: "icpc", name: SERIES_LABELS.icpc, years: [2026] },
        { key: "ccpc", name: SERIES_LABELS.ccpc, years: [2026] },
        { key: "lanqiao", name: SERIES_LABELS.lanqiao, years: [] },
        { key: "tianti", name: SERIES_LABELS.tianti, years: [] },
      ];
    }
  } catch (error) {
    seriesOptions.value = [
      { key: "icpc", name: SERIES_LABELS.icpc, years: [2026] },
      { key: "ccpc", name: SERIES_LABELS.ccpc, years: [2026] },
      { key: "lanqiao", name: SERIES_LABELS.lanqiao, years: [] },
      { key: "tianti", name: SERIES_LABELS.tianti, years: [] },
    ];
    ui.error(getErrorText(error, "赛事公告分类加载失败"));
  }
}

function selectSeries(series) {
  activeSeries.value = series;
}

function normalizeNoticeFilter() {
  if (needsYearStage.value) {
    const yearKeys = seriesYears.value.map((item) => String(item));
    if (!yearKeys.includes(String(activeNoticeYear.value))) {
      activeNoticeYear.value = seriesYears.value[0] ?? FILTER_ALL;
    }
    if (!stageOptions.value.some((item) => item.key === activeStage.value)) {
      activeStage.value = FILTER_ALL;
    }
    return;
  }

  activeNoticeYear.value = FILTER_ALL;
  activeStage.value = stageOptions.value.some((item) => item.key === "general") ? "general" : FILTER_ALL;
}

async function loadNoticeOptions() {
  if (!canManageCompetition.value) {
    noticeOptions.value = [];
    return;
  }
  try {
    const rows = await fetchAll("/competition-notices/", { include_hidden: 1, order: "oldest" });
    noticeOptions.value = rows;
  } catch (error) {
    noticeOptions.value = [];
    ui.error(getErrorText(error, "公告下拉选项加载失败"));
  }
}

async function loadNotices() {
  loadingNotices.value = true;
  try {
    const params = {
      include_hidden: canManageCompetition.value ? 1 : 0,
    };
    if (activeSeries.value !== FILTER_ALL) {
      params.series = activeSeries.value;
    }
    if (needsYearStage.value) {
      if (activeNoticeYear.value !== FILTER_ALL) {
        params.year = Number(activeNoticeYear.value);
      }
      if (activeStage.value && activeStage.value !== FILTER_ALL) {
        params.stage = activeStage.value;
      }
    } else if (activeSeries.value !== FILTER_ALL) {
      params.stage = "general";
    }
    const rows = await fetchAll("/competition-notices/", params);
    noticeRows.value = rows;
    if (pendingNoticeId.value && rows.some((item) => item.id === pendingNoticeId.value)) {
      activeNoticeId.value = pendingNoticeId.value;
      pendingNoticeId.value = null;
    } else if (!rows.some((item) => item.id === activeNoticeId.value)) {
      activeNoticeId.value = rows[0]?.id || null;
    }
  } catch (error) {
    noticeRows.value = [];
    activeNoticeId.value = null;
    ui.error(getErrorText(error, "赛事公告加载失败"));
  } finally {
    loadingNotices.value = false;
  }
}

function openNoticeDetail(id) {
  activeNoticeId.value = id;
}

function openNoticeFromSchedule(row) {
  if (!row?.announcement) return;
  activeTab.value = "notice";
  if (row.announcement_series) activeSeries.value = row.announcement_series;
  normalizeNoticeFilter();
  if (needsYearStage.value) {
    if (row.announcement_year) activeNoticeYear.value = Number(row.announcement_year);
    if (row.announcement_stage) activeStage.value = normalizeStageValue(row.announcement_stage);
  }
  pendingNoticeId.value = Number(row.announcement);
  loadNotices();
}

function normalizeNoticeForm() {
  if (!isSeriesWithYear(noticeForm.series)) {
    noticeForm.year = null;
    noticeForm.stage = "general";
    return;
  }
  if (!Number.isFinite(Number(noticeForm.year))) {
    noticeForm.year = 2026;
  }
  if (!nestedStageOptions.some((item) => item.key === noticeForm.stage)) {
    noticeForm.stage = nestedStageOptions[0].key;
  }
}

function resetNoticeForm() {
  editingNoticeId.value = null;
  noticeForm.title = "";
  noticeForm.content_md = "";
  const fallbackSeries = seriesOptions.value[0]?.key || "icpc";
  noticeForm.series = activeSeries.value === FILTER_ALL ? fallbackSeries : activeSeries.value;
  noticeForm.year = activeNoticeYear.value === FILTER_ALL ? 2026 : Number(activeNoticeYear.value || 2026);
  noticeForm.stage = isSeriesWithYear(noticeForm.series)
    ? (nestedStageOptions.some((item) => item.key === activeStage.value) ? activeStage.value : nestedStageOptions[0].key)
    : "general";
  noticeForm.is_visible = true;
  normalizeNoticeForm();
}

function startEditNotice(item) {
  editingNoticeId.value = item.id;
  noticeForm.title = item.title || "";
  noticeForm.content_md = item.content_md || "";
  noticeForm.series = item.series || "icpc";
  noticeForm.year = item.year ?? 2026;
  noticeForm.stage = normalizeStageValue(item.stage);
  noticeForm.is_visible = Boolean(item.is_visible);
  normalizeNoticeForm();
}

async function submitNotice() {
  if (!canManageCompetition.value) return;
  if (!String(noticeForm.title || "").trim() || !String(noticeForm.content_md || "").trim()) {
    ui.info("请填写公告标题和内容。");
    return;
  }
  const payload = {
    title: String(noticeForm.title || "").trim(),
    content_md: noticeForm.content_md || "",
    series: noticeForm.series,
    is_visible: Boolean(noticeForm.is_visible),
  };
  if (isSeriesWithYear(noticeForm.series)) {
    const year = Number(noticeForm.year);
    if (!Number.isFinite(year) || year < 2000 || year > 2099) {
      ui.info("请填写有效年份。");
      return;
    }
    payload.year = year;
    payload.stage = noticeForm.stage;
  } else {
    payload.year = null;
    payload.stage = "general";
  }

  savingNotice.value = true;
  try {
    let noticeId = null;
    if (editingNoticeId.value) {
      const { data } = await api.patch(`/competition-notices/${editingNoticeId.value}/`, payload);
      noticeId = data?.id || editingNoticeId.value;
      ui.success("赛事公告已更新");
    } else {
      const { data } = await api.post("/competition-notices/", payload);
      noticeId = data?.id || null;
      ui.success("赛事公告已发布");
    }
    activeSeries.value = payload.series;
    normalizeNoticeFilter();
    if (payload.year) activeNoticeYear.value = payload.year;
    if (isSeriesWithYear(payload.series)) activeStage.value = FILTER_ALL;
    pendingNoticeId.value = noticeId;
    resetNoticeForm();
    await Promise.all([loadNoticeTaxonomy(), loadNotices(), loadNoticeOptions(), loadSchedules()]);
  } catch (error) {
    ui.error(getErrorText(error, "提交公告失败"));
  } finally {
    savingNotice.value = false;
  }
}

async function removeNotice(item) {
  if (!canManageCompetition.value) return;
  if (!window.confirm(`确认删除公告：${item.title}？`)) return;
  try {
    await api.delete(`/competition-notices/${item.id}/`);
    ui.success("赛事公告已删除");
    if (editingNoticeId.value === item.id) resetNoticeForm();
    if (activeNoticeId.value === item.id) activeNoticeId.value = null;
    await Promise.all([loadNoticeTaxonomy(), loadNotices(), loadNoticeOptions(), loadSchedules()]);
  } catch (error) {
    ui.error(getErrorText(error, "删除公告失败"));
  }
}

watch(
  () => activeScheduleYear.value,
  () => {
    loadSchedules();
  }
);

watch(
  () => activeSeries.value,
  () => {
    normalizeNoticeFilter();
    loadNotices();
    if (!editingNoticeId.value) {
      noticeForm.series = activeSeries.value === FILTER_ALL ? (seriesOptions.value[0]?.key || "icpc") : activeSeries.value;
      normalizeNoticeForm();
    }
  }
);

watch(
  () => [activeNoticeYear.value, activeStage.value],
  () => {
    if (needsYearStage.value) {
      loadNotices();
    }
  }
);

onMounted(async () => {
  await loadScheduleYears();
  await Promise.all([loadSchedules(), loadNoticeTaxonomy(), loadNoticeOptions()]);
  normalizeNoticeFilter();
  resetNoticeForm();
  await loadNotices();
});
</script>

<style scoped>
.competition-zone {
  width: min(1440px, 100%);
  margin: 0 auto;
  display: grid;
  gap: 14px;
}

.zone-header h1 {
  font-size: clamp(32px, 3vw, 44px);
}

.zone-header p {
  margin: 6px 0 0;
  color: var(--muted);
}

.zone-tabs {
  display: flex;
  gap: 10px;
}

.tab-btn {
  border: 0;
  border-radius: 999px;
  padding: 8px 16px;
  background: rgba(255, 255, 255, 0.9);
  color: #38445a;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}

.tab-btn--active {
  background: linear-gradient(135deg, #6a5cff, #4b8cff);
  color: #fff;
}

.schedule-page,
.notice-page {
  display: grid;
  gap: 12px;
}

.schedule-toolbar {
  padding: 12px;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.year-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.year-btn {
  box-shadow: none;
}

.schedule-editor,
.notice-editor {
  padding: 14px;
  display: grid;
  gap: 10px;
}

.schedule-editor h2,
.notice-editor h2 {
  font-size: 22px;
}

.editor-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
}

.editor-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.schedule-table-wrap {
  padding: 8px 12px 12px;
}

.state-line {
  padding: 6px 2px;
}

.schedule-table {
  width: 100%;
  border-collapse: collapse;
}

.schedule-table th,
.schedule-table td {
  border: 1px solid rgba(17, 24, 39, 0.12);
  padding: 8px 10px;
  vertical-align: top;
}

.schedule-table thead th {
  text-align: left;
  background: rgba(244, 247, 255, 0.92);
}

.table-actions {
  display: flex;
  gap: 6px;
}

.btn-mini {
  min-height: 30px;
  padding: 5px 10px;
  font-size: 13px;
  box-shadow: none;
}

.table-link {
  color: #2f66ff;
  text-decoration: underline;
}

.table-link:visited {
  color: #6a45c7;
}

.row-past td {
  color: #95a0b3;
}

.notice-page {
  display: grid;
  grid-template-columns: minmax(220px, 0.28fr) minmax(0, 1fr);
  gap: 12px;
}

.notice-filter {
  align-self: start;
  position: sticky;
  top: 88px;
  padding: 12px;
  display: grid;
  gap: 10px;
}

.notice-filter h3 {
  font-size: 20px;
}

.series-tabs,
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.series-btn {
  box-shadow: none;
}

.filter-block {
  display: grid;
  gap: 6px;
}

.filter-block label {
  font-size: 13px;
  color: #6a7486;
}

.notice-main {
  display: grid;
  gap: 12px;
}

.notice-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.notice-title-input {
  grid-column: 1 / -1;
}

.notice-textarea {
  min-height: 180px;
}

.notice-editor :deep(.image-upload-helper) {
  margin: 2px 0 2px;
}

.switch-line {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #546071;
}

.notice-list-wrap {
  padding: 14px;
  display: grid;
  gap: 10px;
}

.notice-list-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.notice-list-head h2 {
  font-size: 22px;
}

.notice-list {
  display: grid;
  gap: 8px;
}

.notice-row {
  border: 1px solid rgba(17, 24, 39, 0.08);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.55);
  padding: 8px 10px;
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
}

.notice-row--active {
  border-color: rgba(78, 120, 255, 0.36);
  background: rgba(236, 243, 255, 0.78);
}

.notice-main-btn {
  border: 0;
  background: transparent;
  text-align: left;
  display: grid;
  gap: 4px;
  cursor: pointer;
  flex: 1;
  min-width: 0;
}

.notice-main-btn strong {
  font-size: 16px;
  color: #1f2735;
}

.notice-row-tools {
  display: flex;
  gap: 6px;
}

.notice-detail {
  padding: 16px;
}

.notice-detail-head {
  display: grid;
  gap: 6px;
  margin-bottom: 10px;
}

.notice-detail-head h2 {
  font-size: clamp(30px, 2.5vw, 42px);
  line-height: 1.15;
}

@media (max-width: 1060px) {
  .editor-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .notice-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .notice-page {
    grid-template-columns: 1fr;
  }

  .notice-filter {
    position: static;
  }

  .schedule-table-wrap {
    overflow-x: auto;
  }

  .schedule-table {
    min-width: 860px;
  }
}

@media (max-width: 640px) {
  .zone-tabs {
    width: 100%;
    display: grid;
    grid-template-columns: 1fr 1fr;
  }

  .editor-grid,
  .notice-grid {
    grid-template-columns: 1fr;
  }

  .schedule-toolbar {
    flex-direction: column;
    align-items: flex-start;
  }

  .notice-row {
    display: grid;
  }
}
</style>

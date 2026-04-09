<template>
  <section class="practice-page">
    <section class="card practice-toolbar">
      <div class="practice-filter-block">
        <label>年份</label>
        <div class="chips">
          <button
            v-for="year in yearOptions"
            :key="`practice-year-${year}`"
            type="button"
            class="btn btn-mini"
            :class="{ 'btn-accent': String(year) === String(filters.year) }"
            @click="filters.year = year"
          >
            {{ year === FILTER_ALL ? "全部" : year }}
          </button>
        </div>
      </div>
      <div class="practice-filter-block">
        <label>赛事体系</label>
        <div class="chips">
          <button
            v-for="item in seriesOptions"
            :key="`practice-series-${item.key}`"
            type="button"
            class="btn btn-mini"
            :class="{ 'btn-accent': item.key === filters.series }"
            @click="filters.series = item.key"
          >
            {{ item.name }}
          </button>
        </div>
      </div>
      <div class="practice-filter-block">
        <label>赛事类型</label>
        <div class="chips">
          <button
            v-for="item in stageOptions"
            :key="`practice-stage-${item.key}`"
            type="button"
            class="btn btn-mini"
            :class="{ 'btn-accent': item.key === filters.stage }"
            @click="filters.stage = item.key"
          >
            {{ item.name }}
          </button>
        </div>
      </div>
      <div class="practice-actions">
        <button type="button" class="btn" :disabled="loadingRows" @click="loadRows">
          {{ loadingRows ? "刷新中..." : "刷新表格" }}
        </button>
        <button v-if="auth.isAuthenticated" type="button" class="btn btn-accent" @click="openNewProposal">
          提交新增条目
        </button>
      </div>
    </section>

    <section class="card practice-meta">
      <div>
        <h2>补题链接总表</h2>
        <p class="meta">共 {{ taxonomy.count || rows.length }} 条记录，任何登录用户均可提交修改申请，管理员审核后更新公开表格。</p>
      </div>
      <div class="practice-source">
        <strong>数据源</strong>
        <a
          class="practice-source-link"
          :href="practiceSourceUrl"
          target="_blank"
          rel="noopener noreferrer"
        >
          hh2048 / 04 - 历年XCPC赛事补题链接整理
        </a>
        <p class="meta">当前页面数据整理与展示参考上述仓库内容。</p>
      </div>
    </section>

    <section v-if="auth.isManager" class="card practice-review">
      <header class="review-head">
        <div>
          <h3>待审核申请</h3>
          <p class="meta">当前还有 {{ proposals.length }} 条补题链接申请等待处理。</p>
        </div>
        <button type="button" class="btn" :disabled="loadingProposals" @click="loadProposals">
          {{ loadingProposals ? "刷新中..." : "刷新" }}
        </button>
      </header>
      <p v-if="loadingProposals" class="meta state-line">审核列表加载中...</p>
      <p v-else-if="proposals.length === 0" class="meta state-line">当前没有待审核的补题链接申请。</p>
      <div v-else class="review-list">
        <article v-for="item in proposals" :key="`proposal-${item.id}`" class="review-row">
          <strong>{{ item.proposed_short_name }}</strong>
          <p class="meta">{{ item.proposer?.username || "-" }} · {{ item.proposed_year }} · {{ labelOf(seriesOptions, item.proposed_series) }} · {{ labelOf(stageOptions, item.proposed_stage) }}</p>
          <p class="meta" v-if="item.target_entry_summary">目标条目：{{ item.target_entry_summary }}</p>
          <pre class="proposal-preview">{{ item.practice_links_text || "-" }}</pre>
          <p class="meta">说明：{{ item.reason || "-" }}</p>
          <textarea v-model="reviewNotes[item.id]" class="textarea" placeholder="审核备注（可选）"></textarea>
          <div class="editor-actions">
            <button type="button" class="btn btn-accent" @click="reviewProposal(item, 'approve')">通过</button>
            <button type="button" class="btn" @click="reviewProposal(item, 'reject')">驳回</button>
          </div>
        </article>
      </div>
    </section>

    <section v-if="auth.isAuthenticated" class="card practice-editor">
      <header class="practice-editor-head">
        <div>
          <h3>{{ proposalForm.target_entry ? "提交修改申请" : "提交新增申请" }}</h3>
          <p class="meta">
            {{ proposalForm.target_entry ? "当前申请将修改指定表格项。" : "当前申请将新增一条补题链接记录。" }}
          </p>
        </div>
        <button type="button" class="btn" @click="resetProposalForm">清空表单</button>
      </header>

      <div class="practice-editor-grid">
        <input v-model.number="proposalForm.proposed_year" class="input" type="number" min="2000" max="2099" placeholder="年份" />
        <select v-model="proposalForm.proposed_series" class="select">
          <option v-for="item in seriesOptions.slice(1)" :key="`proposal-series-${item.key}`" :value="item.key">
            {{ item.name }}
          </option>
        </select>
        <select v-model="proposalForm.proposed_stage" class="select">
          <option v-for="item in stageOptions.slice(1)" :key="`proposal-stage-${item.key}`" :value="item.key">
            {{ item.name }}
          </option>
        </select>
        <input v-model.trim="proposalForm.proposed_short_name" class="input" placeholder="简称" />
        <input v-model.trim="proposalForm.proposed_official_name" class="input proposal-span-2" placeholder="官方名称" />
        <input v-model.trim="proposalForm.proposed_official_url" class="input" placeholder="官方链接（可选）" />
        <input v-model="proposalForm.proposed_event_date" class="input" type="date" />
        <input v-model.trim="proposalForm.proposed_event_date_text" class="input" placeholder="显示日期（可选）" />
        <input v-model.trim="proposalForm.proposed_organizer" class="input proposal-span-2" placeholder="承办/备注（可选）" />
      </div>

      <textarea
        v-model="proposalForm.proposed_practice_links_text"
        class="textarea practice-textarea"
        placeholder="补题链接，每行一条；例如：QOJ https://qoj.ac/contest/1234"
      ></textarea>
      <textarea v-model="proposalForm.reason" class="textarea" placeholder="修改说明（可选）"></textarea>

      <div class="editor-actions">
        <button type="button" class="btn btn-accent" :disabled="savingProposal" @click="submitProposal">
          {{ savingProposal ? "提交中..." : "提交申请" }}
        </button>
        <button v-if="proposalForm.target_entry" type="button" class="btn" :disabled="savingProposal" @click="openNewProposal">
          改为新增条目
        </button>
      </div>
    </section>
    <section v-else class="card practice-login-note">
      <p class="meta">登录后可提交补题链接的新增或修改申请。</p>
    </section>

    <section class="card practice-table-wrap">
      <p v-if="loadingRows" class="meta state-line">补题链接加载中...</p>
      <p v-else-if="rows.length === 0" class="meta state-line">当前筛选条件下暂无补题链接记录。</p>
      <table v-else class="practice-table">
        <thead>
          <tr>
            <th>年份</th>
            <th>赛事体系</th>
            <th>赛事类型</th>
            <th>简称</th>
            <th>官方名称</th>
            <th>举办时间</th>
            <th>承办</th>
            <th>补题链接</th>
            <th>备注</th>
            <th>来源</th>
            <th v-if="auth.isAuthenticated">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="`practice-${row.id}`">
            <td data-label="年份">{{ row.year }}</td>
            <td data-label="赛事体系">{{ labelOf(seriesOptions, row.series) }}</td>
            <td data-label="赛事类型">{{ labelOf(stageOptions, row.stage) }}</td>
            <td data-label="简称">{{ row.short_name || "-" }}</td>
            <td class="practice-official-cell" data-label="官方名称">
              <a v-if="row.official_url" :href="row.official_url" target="_blank" rel="noopener noreferrer" class="table-link">
                {{ row.official_name || row.official_url }}
              </a>
              <span v-else>{{ row.official_name || "-" }}</span>
            </td>
            <td data-label="举办时间">{{ row.event_date_text || formatDate(row.event_date) }}</td>
            <td data-label="承办">{{ row.organizer || "-" }}</td>
            <td data-label="补题链接">
              <div v-if="Array.isArray(row.practice_links) && row.practice_links.length" class="practice-links">
                <a
                  v-for="(link, index) in row.practice_links"
                  :key="`${row.id}-link-${index}`"
                  :href="link.url"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="table-link"
                >
                  {{ link.label || link.url }}
                </a>
              </div>
              <span v-else>-</span>
            </td>
            <td data-label="备注">{{ row.practice_links_note || "-" }}</td>
            <td data-label="来源">{{ formatSource(row) }}</td>
            <td v-if="auth.isAuthenticated" data-label="操作">
              <div class="practice-row-actions">
                <button type="button" class="btn btn-mini" @click="startProposal(row)">提交修改</button>
                <button
                  v-if="auth.isManager"
                  type="button"
                  class="btn btn-mini"
                  :disabled="removingRowId === row.id"
                  @click="removePracticeRow(row)"
                >
                  {{ removingRowId === row.id ? "删除中..." : "删除" }}
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";

import api from "../services/api";
import { useAuthStore } from "../stores/auth";
import { useUiStore } from "../stores/ui";

const auth = useAuthStore();
const ui = useUiStore();
const FILTER_ALL = "all";
const practiceSourceUrl =
  "https://github.com/hh2048/XCPC/tree/main/04%20-%20%E5%8E%86%E5%B9%B4XCPC%E8%B5%9B%E4%BA%8B%E8%A1%A5%E9%A2%98%E9%93%BE%E6%8E%A5%E6%95%B4%E7%90%86";
const seriesOptions = [
  { key: FILTER_ALL, name: "全部" },
  { key: "icpc", name: "ICPC" },
  { key: "ccpc", name: "CCPC" },
];
const stageOptions = [
  { key: FILTER_ALL, name: "全部" },
  { key: "network", name: "网络赛" },
  { key: "regional", name: "区域赛" },
  { key: "invitational", name: "邀请赛" },
  { key: "provincial", name: "省赛" },
];

const taxonomy = reactive({ count: 0, years: [], sources: [] });
const filters = reactive({ year: FILTER_ALL, series: FILTER_ALL, stage: FILTER_ALL });
const rows = ref([]);
const proposals = ref([]);
const loadingRows = ref(false);
const loadingProposals = ref(false);
const savingProposal = ref(false);
const removingRowId = ref(null);
const reviewNotes = reactive({});
const proposalForm = reactive({
  target_entry: "",
  proposed_year: new Date().getFullYear(),
  proposed_series: "icpc",
  proposed_stage: "regional",
  proposed_short_name: "",
  proposed_official_name: "",
  proposed_official_url: "",
  proposed_event_date: "",
  proposed_event_date_text: "",
  proposed_organizer: "",
  proposed_practice_links_text: "",
  reason: "",
});

const yearOptions = computed(() => [FILTER_ALL, ...taxonomy.years]);

function labelOf(options, key) {
  return options.find((item) => item.key === key)?.name || key || "-";
}

function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString("zh-CN");
}

function formatSource(row) {
  return [row.source_file, row.source_section].filter(Boolean).join(" / ") || "-";
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
  const result = [];
  let page = 1;
  while (page) {
    const { data } = await api.get(path, { params: { ...params, page } });
    if (Array.isArray(data)) {
      result.push(...data);
      break;
    }
    result.push(...(Array.isArray(data?.results) ? data.results : []));
    page = nextPageFromUrl(data?.next);
  }
  return result;
}

function getErrorText(error, fallback) {
  const payload = error?.response?.data;
  if (typeof payload?.detail === "string") return payload.detail;
  if (typeof payload === "string") return payload;
  return fallback;
}

function buildParams() {
  const params = {};
  if (filters.year !== FILTER_ALL) params.year = Number(filters.year);
  if (filters.series !== FILTER_ALL) params.series = filters.series;
  if (filters.stage !== FILTER_ALL) params.stage = filters.stage;
  return params;
}

async function loadTaxonomy() {
  const { data } = await api.get("/competition-practice-links/taxonomy/");
  taxonomy.count = Number(data?.count || 0);
  taxonomy.years = (Array.isArray(data?.years) ? data.years : []).map(Number).filter(Number.isFinite);
  taxonomy.sources = Array.isArray(data?.sources) ? data.sources : [];
}

async function loadRows() {
  loadingRows.value = true;
  try {
    rows.value = await fetchAll("/competition-practice-links/", buildParams());
  } catch (error) {
    rows.value = [];
    ui.error(getErrorText(error, "补题链接加载失败"));
  } finally {
    loadingRows.value = false;
  }
}

function resetProposalForm() {
  proposalForm.target_entry = "";
  proposalForm.proposed_year = Number(filters.year) || taxonomy.years[0] || new Date().getFullYear();
  proposalForm.proposed_series = filters.series !== FILTER_ALL ? filters.series : "icpc";
  proposalForm.proposed_stage = filters.stage !== FILTER_ALL ? filters.stage : "regional";
  proposalForm.proposed_short_name = "";
  proposalForm.proposed_official_name = "";
  proposalForm.proposed_official_url = "";
  proposalForm.proposed_event_date = "";
  proposalForm.proposed_event_date_text = "";
  proposalForm.proposed_organizer = "";
  proposalForm.proposed_practice_links_text = "";
  proposalForm.reason = "";
}

function openNewProposal() {
  resetProposalForm();
}

function startProposal(row) {
  proposalForm.target_entry = row.id;
  proposalForm.proposed_year = row.year || taxonomy.years[0] || new Date().getFullYear();
  proposalForm.proposed_series = row.series || "icpc";
  proposalForm.proposed_stage = row.stage || "regional";
  proposalForm.proposed_short_name = row.short_name || "";
  proposalForm.proposed_official_name = row.official_name || "";
  proposalForm.proposed_official_url = row.official_url || "";
  proposalForm.proposed_event_date = row.event_date || "";
  proposalForm.proposed_event_date_text = row.event_date_text || "";
  proposalForm.proposed_organizer = row.organizer || "";
  proposalForm.proposed_practice_links_text = row.practice_links_text || "";
  proposalForm.reason = "";
}

async function submitProposal() {
  if (!proposalForm.proposed_short_name.trim() || !proposalForm.proposed_official_name.trim()) {
    ui.info("请填写简称和官方名称。");
    return;
  }
  savingProposal.value = true;
  try {
    await api.post("/competition-practice-proposals/", {
      ...proposalForm,
      target_entry: proposalForm.target_entry ? Number(proposalForm.target_entry) : null,
      proposed_year: Number(proposalForm.proposed_year),
      proposed_short_name: proposalForm.proposed_short_name.trim(),
      proposed_official_name: proposalForm.proposed_official_name.trim(),
      proposed_official_url: proposalForm.proposed_official_url.trim(),
      proposed_event_date: proposalForm.proposed_event_date || null,
      proposed_event_date_text: proposalForm.proposed_event_date_text.trim(),
      proposed_organizer: proposalForm.proposed_organizer.trim(),
      reason: proposalForm.reason.trim(),
    });
    ui.success("补题链接申请已提交，等待管理员审核。");
    resetProposalForm();
    if (auth.isManager) await loadProposals();
  } catch (error) {
    ui.error(getErrorText(error, "补题链接申请提交失败"));
  } finally {
    savingProposal.value = false;
  }
}

async function loadProposals() {
  if (!auth.isManager) return;
  loadingProposals.value = true;
  try {
    proposals.value = await fetchAll("/competition-practice-proposals/", { status: "pending" });
  } catch (error) {
    proposals.value = [];
    ui.error(getErrorText(error, "审核列表加载失败"));
  } finally {
    loadingProposals.value = false;
  }
}

async function reviewProposal(item, action) {
  try {
    await api.post(`/competition-practice-proposals/${item.id}/${action}/`, {
      review_note: reviewNotes[item.id] || "",
    });
    ui.success(action === "approve" ? "申请已通过" : "申请已驳回");
    delete reviewNotes[item.id];
    await Promise.all([loadTaxonomy(), loadRows(), loadProposals()]);
  } catch (error) {
    ui.error(getErrorText(error, "审核失败"));
  }
}

async function removePracticeRow(row) {
  if (!auth.isManager) return;
  if (!row?.id) return;
  const label = row.short_name || row.official_name || `#${row.id}`;
  if (!window.confirm(`确认删除补题条目「${label}」？`)) return;

  removingRowId.value = row.id;
  try {
    await api.delete(`/competition-practice-links/${row.id}/remove/`);
    rows.value = rows.value.filter((item) => item.id !== row.id);
    if (String(proposalForm.target_entry || "") === String(row.id)) {
      resetProposalForm();
    }
    ui.success("补题条目已删除");
    await Promise.all([loadTaxonomy(), loadRows(), auth.isManager ? loadProposals() : Promise.resolve()]);
  } catch (error) {
    ui.error(getErrorText(error, "删除补题条目失败"));
  } finally {
    removingRowId.value = null;
  }
}

watch(() => [filters.year, filters.series, filters.stage], () => loadRows());

onMounted(async () => {
  try {
    await Promise.all([loadTaxonomy(), loadRows()]);
    resetProposalForm();
    if (auth.isManager) await loadProposals();
  } catch (error) {
    ui.error(getErrorText(error, "补题链接页面加载失败"));
  }
});
</script>

<style scoped>
.practice-page,
.practice-toolbar,
.practice-meta,
.practice-editor,
.practice-review {
  display: grid;
  gap: 12px;
}

.practice-toolbar,
.practice-meta,
.practice-login-note,
.practice-review,
.practice-editor {
  padding: 14px;
}

.practice-filter-block,
.practice-source {
  display: grid;
  gap: 6px;
}

.practice-filter-block label {
  font-size: 13px;
  color: var(--text-quiet);
}

.chips,
.practice-actions,
.editor-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.practice-source-link {
  color: var(--link);
  text-decoration: underline;
  text-underline-offset: 2px;
  word-break: break-word;
}

.practice-source-link:visited,
.table-link:visited {
  color: var(--link-visited);
}

.practice-row-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.table-link {
  color: var(--link);
  text-decoration: underline;
  text-underline-offset: 2px;
  word-break: break-word;
}

.practice-editor-head,
.review-head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: flex-start;
}

.practice-editor-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.proposal-span-2 {
  grid-column: span 2;
}

.practice-textarea {
  min-height: 150px;
}

.practice-table-wrap {
  padding: 8px 12px 12px;
  overflow-x: auto;
}

.practice-table {
  width: 100%;
  min-width: 1180px;
  border-collapse: collapse;
}

.practice-table th,
.practice-table td {
  border: 1px solid var(--hairline-strong);
  padding: 8px 10px;
  vertical-align: top;
}

.practice-table thead th {
  text-align: left;
  background: var(--table-head-bg);
}

.practice-table tbody tr:nth-child(odd) {
  background: var(--content-table-row);
}

.practice-table tbody tr:nth-child(even) {
  background: var(--content-table-row-alt);
}

.practice-table tbody tr:hover {
  background: color-mix(in srgb, var(--accent) 6%, transparent);
}

.practice-official-cell {
  min-width: 240px;
  white-space: pre-wrap;
}

.practice-links,
.review-list {
  display: grid;
  gap: 6px;
}

.review-row {
  border: 1px solid var(--panel-border);
  border-radius: 12px;
  background: var(--surface);
  padding: 12px;
  display: grid;
  gap: 8px;
}

.proposal-preview {
  margin: 0;
  padding: 10px;
  border-radius: 10px;
  border: 1px solid var(--content-code-border);
  background: linear-gradient(180deg, var(--content-code-bg-top), var(--content-code-bg));
  color: var(--content-code-text);
  font-family: var(--font-mono);
  box-shadow: var(--content-code-shadow);
  white-space: pre-wrap;
  line-height: 1.6;
}

@media (max-width: 1100px) {
  .practice-editor-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .practice-toolbar,
  .practice-meta {
    padding: 12px;
  }

  .practice-actions {
    width: 100%;
  }

  .practice-actions .btn {
    flex: 1 1 100%;
  }

  .practice-editor-grid {
    grid-template-columns: 1fr;
  }

  .proposal-span-2 {
    grid-column: auto;
  }

  .practice-editor-head,
  .review-head {
    flex-direction: column;
  }

  .practice-table {
    min-width: 0;
  }

  .practice-table thead {
    display: none;
  }

  .practice-table,
  .practice-table tbody {
    display: grid;
    gap: 10px;
  }

  .practice-table tr {
    display: grid;
    gap: 8px;
    padding: 12px;
    border: 1px solid var(--panel-border);
    border-radius: 14px;
    background: var(--surface-strong);
  }

  .practice-table td {
    display: grid;
    grid-template-columns: minmax(82px, 96px) minmax(0, 1fr);
    gap: 10px;
    border: 0;
    padding: 0;
  }

  .practice-table td::before {
    content: attr(data-label);
    font-size: 12px;
    font-weight: 600;
    color: var(--text-quiet);
  }

  .practice-official-cell {
    min-width: 0;
  }

  .review-row {
    padding: 10px;
  }
}
</style>

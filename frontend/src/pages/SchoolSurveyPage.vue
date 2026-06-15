<template>
  <section class="school-survey-page">
    <header class="survey-hero card">
      <div>
        <p class="kicker">AlgoWiki School Survey</p>
        <h1>高校算法竞赛队伍情况收集表</h1>
        <p class="meta">
          收集各高校算法竞赛队伍建设、训练情况、经费支持、奖励政策、保研影响等核心信息。信息可能随年份变化，请以学校当年官方文件和实际执行情况为准。
        </p>
      </div>
      <div class="hero-stat">
        <strong>{{ schools.length }}</strong>
        <span>已收录参赛院校</span>
      </div>
    </header>

    <section class="survey-toolbar">
      <label class="search-box">
        <span class="search-icon" aria-hidden="true"></span>
        <input
          v-model.trim="schoolQuery"
          class="search-input"
          type="search"
          placeholder="搜索参赛院校名称、省份或城市"
          aria-label="搜索学校"
        />
      </label>
      <button type="button" class="btn" :disabled="loadingSchools" @click="loadSchools">
        {{ loadingSchools ? "刷新中..." : "刷新" }}
      </button>
      <button
        v-if="auth.isManager"
        type="button"
        class="btn btn-ghost"
        @click="openAddSchoolModal"
      >
        添加学校
      </button>
    </section>

    <section v-if="loadingSchools" class="empty-card card">学校列表加载中...</section>
    <section v-else-if="!filteredSchools.length" class="empty-card card">
      没有找到匹配的学校。
    </section>
    <section v-else class="school-grid" aria-label="参赛院校列表">
      <button
        v-for="school in filteredSchools"
        :key="school.id"
        type="button"
        class="school-card card"
        @click="openSchoolActions(school)"
      >
        <img
          v-if="school.logo_url"
          class="school-logo"
          :src="school.logo_url"
          :alt="`${school.name} 校徽`"
          loading="lazy"
          decoding="async"
        />
        <span v-else class="school-logo school-logo--fallback">
          {{ schoolBadgeText(school) }}
        </span>
        <span class="school-card-main">
          <strong>{{ school.name }}</strong>
          <small>{{ schoolLocation(school) || "高校" }}</small>
        </span>
        <span class="school-card-meta">
          {{ school.submissions_count || 0 }} 份
        </span>
      </button>
    </section>

    <Teleport to="body">
      <div v-if="actionModalOpen && selectedSchool" class="modal-backdrop" @click.self="closeActionModal">
        <section class="action-modal card" role="dialog" aria-modal="true" :aria-label="selectedSchool.name">
          <header class="modal-head">
            <div>
              <p class="kicker">选择操作</p>
              <h2>{{ selectedSchool.name }}</h2>
              <p class="meta">{{ schoolLocation(selectedSchool) || "高校" }}</p>
            </div>
            <button type="button" class="icon-close" @click="closeActionModal">×</button>
          </header>
          <div class="action-list">
            <button type="button" class="action-choice" @click="startNewSubmission">
              <span class="choice-mark">+</span>
              <span>
                <strong>提交新问卷</strong>
                <small>打开问卷窗口，关闭时自动保存草稿。</small>
              </span>
            </button>
            <button type="button" class="action-choice" @click="openSubmittedList">
              <span class="choice-mark choice-mark--soft">□</span>
              <span>
                <strong>查看已提交问卷</strong>
                <small>浏览该校已提交的多份问卷记录。</small>
              </span>
            </button>
          </div>
        </section>
      </div>

      <div v-if="listModalOpen && selectedSchool" class="modal-backdrop" @click.self="closeListModal">
        <section class="list-modal card" role="dialog" aria-modal="true" aria-label="已提交问卷">
          <header class="modal-head">
            <div>
              <p class="kicker">已提交问卷</p>
              <h2>{{ selectedSchool.name }}</h2>
              <p class="meta">每次正式提交都会生成一条独立记录。</p>
            </div>
            <button type="button" class="icon-close" @click="closeListModal">×</button>
          </header>
          <div v-if="loadingSubmissions" class="empty-inline">记录加载中...</div>
          <div v-else-if="!submissions.length" class="empty-inline">该校暂时没有已提交问卷。</div>
          <div v-else class="submission-list">
            <button
              v-for="item in submissions"
              :key="item.id"
              type="button"
              class="submission-row"
              @click="openSubmissionDetail(item)"
            >
              <span>
                <strong>#{{ item.id }} 问卷记录</strong>
                <small>{{ formatDateTime(item.submitted_at || item.updated_at) }}</small>
              </span>
              <span class="submission-author">{{ item.author?.username || "已注销用户" }}</span>
            </button>
          </div>
        </section>
      </div>

      <div v-if="formModalOpen" class="modal-backdrop form-backdrop" @click.self="closeFormModal">
        <section class="form-modal card" role="dialog" aria-modal="true" aria-label="提交新问卷">
          <header class="form-modal-head">
            <div>
              <p class="kicker">提交新问卷</p>
              <h2>{{ selectedSchool?.name || "高校问卷" }}</h2>
              <p class="meta">
                {{ saveStatusText }}。所有问题均可选择性填写，关闭窗口会自动保存已填写内容。
              </p>
            </div>
            <div class="form-head-actions">
              <button type="button" class="btn btn-ghost" :disabled="savingDraft" @click="saveDraftNow">
                保存草稿
              </button>
              <button type="button" class="icon-close" @click="closeFormModal">×</button>
            </div>
          </header>
          <div class="form-modal-body">
            <QuestionnaireForm
              v-model="formData"
              :sections="questionnaireSections"
              :readonly="false"
              @change="scheduleAutosave"
            />
          </div>
          <footer class="form-modal-foot">
            <span class="meta">提交后会进入该学校的历史问卷列表，仍可再次提交新版本。</span>
            <button type="button" class="btn" :disabled="savingDraft" @click="closeFormModal">关闭</button>
            <button type="button" class="btn btn-accent" :disabled="submitting" @click="submitQuestionnaire">
              {{ submitting ? "提交中..." : "提交问卷" }}
            </button>
          </footer>
        </section>
      </div>

      <div v-if="detailModalOpen && detailSubmission" class="modal-backdrop form-backdrop" @click.self="closeDetailModal">
        <section class="form-modal card" role="dialog" aria-modal="true" aria-label="查看已提交问卷">
          <header class="form-modal-head">
            <div>
              <p class="kicker">已提交问卷 #{{ detailSubmission.id }}</p>
              <h2>{{ detailSubmission.school_name || selectedSchool?.name || "高校问卷" }}</h2>
              <p class="meta">
                提交时间：{{ formatDateTime(detailSubmission.submitted_at || detailSubmission.updated_at) }}
              </p>
            </div>
            <button type="button" class="icon-close" @click="closeDetailModal">×</button>
          </header>
          <div class="form-modal-body">
            <QuestionnaireForm
              v-if="detailQuestionnaireSections.length"
              v-model="detailFormData"
              :sections="detailQuestionnaireSections"
              :readonly="true"
            />
            <div v-else class="empty-inline">这份问卷暂时没有填写公开问题。</div>
          </div>
          <footer class="form-modal-foot">
            <span class="meta">
              已提交问卷仅展示已填写的问题，未填写项会自动隐藏。
            </span>
            <button type="button" class="btn btn-accent" @click="closeDetailModal">关闭</button>
          </footer>
        </section>
      </div>

      <div v-if="addSchoolModalOpen" class="modal-backdrop" @click.self="closeAddSchoolModal">
        <section class="add-school-modal card" role="dialog" aria-modal="true" aria-label="添加学校">
          <header class="modal-head">
            <div>
              <p class="kicker">管理员工具</p>
              <h2>添加学校收集表</h2>
              <p class="meta">新增学校会立即进入调研列表，可被用户提交问卷。</p>
            </div>
            <button type="button" class="icon-close" @click="closeAddSchoolModal">×</button>
          </header>
          <form class="add-school-form" @submit.prevent="createSchool">
            <label class="admin-field admin-field--wide">
              <span class="field-label">学校名称</span>
              <input v-model.trim="newSchool.name" class="input" type="text" maxlength="120" required placeholder="例如：深圳职业技术大学" />
            </label>
            <label class="admin-field">
              <span class="field-label">简称</span>
              <input v-model.trim="newSchool.abbreviation" class="input" type="text" maxlength="40" placeholder="例如：SZPU" />
            </label>
            <label class="admin-field">
              <span class="field-label">类型</span>
              <select v-model="newSchool.school_type" class="input">
                <option value="university">本科/大学</option>
                <option value="other">高职/专科/其他</option>
              </select>
            </label>
            <label class="admin-field">
              <span class="field-label">省份</span>
              <input v-model.trim="newSchool.province" class="input" type="text" maxlength="80" placeholder="例如：广东省" />
            </label>
            <label class="admin-field">
              <span class="field-label">城市</span>
              <input v-model.trim="newSchool.city" class="input" type="text" maxlength="80" placeholder="例如：深圳市" />
            </label>
            <footer class="add-school-actions">
              <button type="button" class="btn" @click="closeAddSchoolModal">取消</button>
              <button type="submit" class="btn btn-accent" :disabled="creatingSchool">
                {{ creatingSchool ? "添加中..." : "添加学校" }}
              </button>
            </footer>
          </form>
        </section>
      </div>
    </Teleport>
  </section>
</template>

<script setup>
import { computed, defineComponent, h, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";

import { getCaptchaProof, captchaErrorMessage } from "../composables/useCaptcha";
import { questionnaireSections } from "../data/schoolSurveyQuestionnaire";
import api from "../services/api";
import { useAuthStore } from "../stores/auth";
import { useUiStore } from "../stores/ui";

const QuestionnaireForm = defineComponent({
  name: "QuestionnaireForm",
  props: {
    modelValue: {
      type: Object,
      required: true,
    },
    sections: {
      type: Array,
      required: true,
    },
    readonly: {
      type: Boolean,
      default: false,
    },
  },
  emits: ["update:modelValue", "change"],
  setup(props, { emit }) {
    const updateValue = (key, value) => {
      emit("update:modelValue", {
        ...(props.modelValue || {}),
        [key]: value,
      });
      emit("change");
    };
    const ensureArray = (key) => {
      const value = props.modelValue?.[key];
      return Array.isArray(value) ? value : [];
    };
    const ensureMatrix = (key) => {
      const value = props.modelValue?.[key];
      return value && typeof value === "object" && !Array.isArray(value) ? value : {};
    };
    const toggleCheckbox = (key, option, checked) => {
      const current = ensureArray(key);
      const next = checked
        ? Array.from(new Set([...current, option]))
        : current.filter((item) => item !== option);
      updateValue(key, next);
    };
    const matrixCellValue = (field, row, column) => {
      const matrix = ensureMatrix(field.key);
      const rowValue = matrix[row.key];
      if (rowValue && typeof rowValue === "object" && !Array.isArray(rowValue)) {
        return rowValue[column.key] ?? "";
      }
      if ((field.columns || []).length === 1) {
        return rowValue ?? "";
      }
      return "";
    };
    const updateMatrixCell = (field, row, column, value) => {
      const matrix = ensureMatrix(field.key);
      const currentRow =
        matrix[row.key] && typeof matrix[row.key] === "object" && !Array.isArray(matrix[row.key])
          ? matrix[row.key]
          : {};
      updateValue(field.key, {
        ...matrix,
        [row.key]: {
          ...currentRow,
          [column.key]: value,
        },
      });
    };
    const matrixRows = (field) => {
      const rows = field.rows || [];
      if (!props.readonly) return rows;
      return rows.filter((row) =>
        (field.columns || []).some((column) => String(matrixCellValue(field, row, column) ?? "").trim())
      );
    };
    const renderMatrixCell = (field, row, column) => {
      const value = matrixCellValue(field, row, column);
      const options = column.options || row.options;
      if (props.readonly) {
        return h("td", { class: "matrix-value" }, String(value || ""));
      }
      if (options?.length) {
        return h("td", [
          h(
            "select",
            {
              class: "input matrix-input",
              value,
              onChange: (event) => updateMatrixCell(field, row, column, event.target.value),
            },
            [
              h("option", { value: "" }, "未填写"),
              ...options.map((option) => h("option", { key: option, value: option }, option)),
            ]
          ),
        ]);
      }
      return h("td", [
        h("input", {
          class: "input matrix-input",
          type: "text",
          value,
          placeholder: column.placeholder || row.placeholder || "",
          onInput: (event) => updateMatrixCell(field, row, column, event.target.value),
        }),
      ]);
    };
    const renderMatrixField = (field, label) => {
      const rows = matrixRows(field);
      if (props.readonly && !rows.length) return null;
      return h("fieldset", { class: "survey-field survey-field--wide", key: field.key }, [
        label,
        h("div", { class: "matrix-scroll" }, [
          h("table", { class: "survey-matrix" }, [
            h("thead", [
              h("tr", [
                h("th", "项目"),
                ...(field.columns || []).map((column) => h("th", { key: column.key }, column.label)),
              ]),
            ]),
            h(
              "tbody",
              rows.map((row) =>
                h("tr", { key: row.key }, [
                  h("th", { scope: "row" }, row.label),
                  ...(field.columns || []).map((column) => renderMatrixCell(field, row, column)),
                ])
              )
            ),
          ]),
        ]),
      ]);
    };
    const inputValue = (key) => {
      const value = props.modelValue?.[key];
      if (Array.isArray(value)) return value.join("、");
      if (value && typeof value === "object") return "";
      return value ?? "";
    };
    const readonlyFieldClass = (field) =>
      field.type === "text" ? "survey-field" : "survey-field survey-field--wide";

    return () =>
      h(
        "div",
        { class: "questionnaire-form" },
        props.sections.map((section, sectionIndex) =>
          h("section", { class: "questionnaire-section", key: section.key }, [
            h("header", { class: "questionnaire-section-head" }, [
              h("span", { class: "section-index" }, String(sectionIndex + 1).padStart(2, "0")),
              h("div", [
                h("h3", section.title),
                section.description ? h("p", { class: "meta" }, section.description) : null,
              ]),
            ]),
            h(
              "div",
              { class: "questionnaire-fields" },
              section.fields.map((field) => {
                const label = h("span", { class: "field-label" }, field.label);
                if (field.type === "matrix") {
                  return renderMatrixField(field, label);
                }
                if (props.readonly) {
                  return h("label", { class: readonlyFieldClass(field), key: field.key }, [
                    label,
                    h("div", { class: "readonly-value" }, inputValue(field.key)),
                  ]);
                }
                if (field.type === "textarea") {
                  return h("label", { class: "survey-field survey-field--wide", key: field.key }, [
                    label,
                    h("textarea", {
                      class: "textarea",
                      value: inputValue(field.key),
                      placeholder: field.placeholder || "",
                      readonly: props.readonly,
                      rows: 4,
                      onInput: (event) => updateValue(field.key, event.target.value),
                    }),
                  ]);
                }
                if (field.type === "radio") {
                  return h("fieldset", { class: "survey-field survey-field--wide", key: field.key }, [
                    label,
                    h(
                      "div",
                      { class: "choice-grid" },
                      field.options.map((option) =>
                        h("label", { class: "choice-pill", key: option }, [
                          h("input", {
                            type: "radio",
                            name: field.key,
                            value: option,
                            checked: props.modelValue?.[field.key] === option,
                            disabled: props.readonly,
                            onChange: () => updateValue(field.key, option),
                          }),
                          h("span", option),
                        ])
                      )
                    ),
                  ]);
                }
                if (field.type === "checkbox") {
                  return h("fieldset", { class: "survey-field survey-field--wide", key: field.key }, [
                    label,
                    h(
                      "div",
                      { class: "choice-grid" },
                      field.options.map((option) =>
                        h("label", { class: "choice-pill", key: option }, [
                          h("input", {
                            type: "checkbox",
                            value: option,
                            checked: ensureArray(field.key).includes(option),
                            disabled: props.readonly,
                            onChange: (event) => toggleCheckbox(field.key, option, event.target.checked),
                          }),
                          h("span", option),
                        ])
                      )
                    ),
                  ]);
                }
                return h("label", { class: "survey-field", key: field.key }, [
                  label,
                  h("input", {
                    class: "input",
                    type: "text",
                    value: inputValue(field.key),
                    placeholder: field.placeholder || "",
                    readonly: props.readonly,
                    onInput: (event) => updateValue(field.key, event.target.value),
                  }),
                ]);
              })
            ),
          ])
        )
      );
  },
});

const router = useRouter();
const auth = useAuthStore();
const ui = useUiStore();

const schools = ref([]);
const schoolQuery = ref("");
const loadingSchools = ref(false);
const selectedSchool = ref(null);
const actionModalOpen = ref(false);
const listModalOpen = ref(false);
const submissions = ref([]);
const loadingSubmissions = ref(false);
const formModalOpen = ref(false);
const currentDraft = ref(null);
const formData = ref({});
const savingDraft = ref(false);
const submitting = ref(false);
const lastSavedAt = ref("");
const detailModalOpen = ref(false);
const detailSubmission = ref(null);
const detailFormData = ref({});
const addSchoolModalOpen = ref(false);
const creatingSchool = ref(false);
const newSchool = ref(buildEmptySchoolForm());
let autosaveTimer = null;

const defaultFormData = computed(() => {
  const payload = {};
  for (const section of questionnaireSections) {
    for (const field of section.fields) {
      if (field.type === "checkbox") {
        payload[field.key] = [];
      } else if (field.type === "matrix") {
        payload[field.key] = {};
      } else {
        payload[field.key] = "";
      }
    }
  }
  return payload;
});

const filteredSchools = computed(() => {
  const query = schoolQuery.value.trim().toLowerCase();
  if (!query) return schools.value;
  return schools.value.filter((school) => {
    const haystack = [
      school.name,
      school.abbreviation,
      school.province,
      school.city,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.includes(query);
  });
});

const saveStatusText = computed(() => {
  if (savingDraft.value) return "草稿保存中";
  if (lastSavedAt.value) return `草稿已保存于 ${lastSavedAt.value}`;
  return "草稿尚未保存";
});

const detailQuestionnaireSections = computed(() =>
  questionnaireSections
    .map((section) => ({
      ...section,
      fields: section.fields.filter((field) => hasFilledValue(detailFormData.value?.[field.key])),
    }))
    .filter((section) => section.fields.length > 0)
);

watch(
  () => auth.isAuthenticated,
  (isAuthenticated) => {
    if (!isAuthenticated) {
      closeActionModal();
      closeListModal();
      formModalOpen.value = false;
      detailModalOpen.value = false;
      closeAddSchoolModal();
    }
  }
);

function buildEmptySchoolForm() {
  return {
    name: "",
    abbreviation: "",
    school_type: "university",
    province: "",
    city: "",
  };
}

function hasFilledValue(value) {
  if (Array.isArray(value)) return value.some((item) => String(item || "").trim());
  if (value && typeof value === "object") {
    return Object.values(value).some((row) => {
      if (row && typeof row === "object" && !Array.isArray(row)) {
        return Object.values(row).some((cell) => String(cell ?? "").trim());
      }
      return String(row ?? "").trim();
    });
  }
  return String(value ?? "").trim().length > 0;
}

function normalizeListPayload(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.results)) return data.results;
  return [];
}

function ensureAuthenticated() {
  if (auth.isAuthenticated) return true;
  ui.info("请先登录后再提交或查看高校问卷。", "需要登录");
  router.push({ name: "auth" });
  return false;
}

async function loadSchools() {
  loadingSchools.value = true;
  try {
    const { data } = await api.get("/school-survey-schools/");
    schools.value = normalizeListPayload(data);
  } catch (error) {
    ui.error(error?.response?.data?.detail || "学校列表加载失败。");
  } finally {
    loadingSchools.value = false;
  }
}

function openAddSchoolModal() {
  if (!auth.isManager) return;
  newSchool.value = buildEmptySchoolForm();
  addSchoolModalOpen.value = true;
}

function closeAddSchoolModal() {
  addSchoolModalOpen.value = false;
  creatingSchool.value = false;
}

async function createSchool() {
  const name = String(newSchool.value.name || "").trim();
  if (!name) {
    ui.error("请填写学校名称。");
    return;
  }
  creatingSchool.value = true;
  try {
    const { data } = await api.post("/school-survey-schools/", {
      name,
      abbreviation: newSchool.value.abbreviation,
      province: newSchool.value.province,
      city: newSchool.value.city,
      school_type: newSchool.value.school_type,
      is_active: true,
    });
    ui.success(`${data.name} 已加入学校调研列表。`);
    closeAddSchoolModal();
    await loadSchools();
    schoolQuery.value = data.name;
  } catch (error) {
    ui.error(error?.response?.data?.detail || error?.response?.data?.name?.[0] || "学校添加失败。");
  } finally {
    creatingSchool.value = false;
  }
}

function schoolBadgeText(school) {
  const abbreviation = String(school?.abbreviation || "").trim();
  if (abbreviation) return abbreviation.slice(0, 6).toUpperCase();
  return String(school?.name || "高校").slice(0, 2);
}

function schoolLocation(school) {
  return [school?.province, school?.city].filter(Boolean).join(" / ");
}

function openSchoolActions(school) {
  selectedSchool.value = school;
  actionModalOpen.value = true;
}

function closeActionModal() {
  actionModalOpen.value = false;
}

function closeListModal() {
  listModalOpen.value = false;
}

function buildInitialFormData(raw = {}) {
  const payload = {
    ...defaultFormData.value,
    ...(raw && typeof raw === "object" ? raw : {}),
  };
  return payload;
}

async function startNewSubmission() {
  if (!ensureAuthenticated() || !selectedSchool.value) return;
  closeActionModal();
  savingDraft.value = true;
  try {
    const { data } = await api.get("/school-survey-submissions/my-draft/", {
      params: { school: selectedSchool.value.id },
    });
    currentDraft.value = data;
    formData.value = buildInitialFormData(data?.form_data);
    lastSavedAt.value = data?.updated_at ? formatClock(data.updated_at) : "";
    formModalOpen.value = true;
  } catch (error) {
    ui.error(error?.response?.data?.detail || "草稿加载失败。");
  } finally {
    savingDraft.value = false;
  }
}

async function openSubmittedList() {
  if (!ensureAuthenticated() || !selectedSchool.value) return;
  closeActionModal();
  listModalOpen.value = true;
  await loadSubmissions();
}

async function loadSubmissions() {
  if (!selectedSchool.value) return;
  loadingSubmissions.value = true;
  try {
    const { data } = await api.get("/school-survey-submissions/", {
      params: {
        school: selectedSchool.value.id,
        status: "submitted",
      },
    });
    submissions.value = normalizeListPayload(data);
  } catch (error) {
    ui.error(error?.response?.data?.detail || "已提交问卷加载失败。");
  } finally {
    loadingSubmissions.value = false;
  }
}

function scheduleAutosave() {
  if (!formModalOpen.value || !currentDraft.value?.id) return;
  window.clearTimeout(autosaveTimer);
  autosaveTimer = window.setTimeout(() => {
    saveDraftNow({ silent: true });
  }, 1200);
}

async function saveDraftNow(options = {}) {
  if (!currentDraft.value?.id || submitting.value) return true;
  window.clearTimeout(autosaveTimer);
  savingDraft.value = true;
  try {
    const { data } = await api.patch(`/school-survey-submissions/${currentDraft.value.id}/`, {
      form_data: formData.value,
      status: "draft",
    });
    currentDraft.value = data;
    lastSavedAt.value = formatClock(data.updated_at || new Date().toISOString());
    if (!options.silent) {
      ui.success("草稿已保存。");
    }
    return true;
  } catch (error) {
    if (!options.silent || options.reportError) {
      ui.error(error?.response?.data?.detail || "草稿保存失败。");
    }
    return false;
  } finally {
    savingDraft.value = false;
  }
}

async function closeFormModal() {
  const saved = await saveDraftNow({ silent: true, reportError: true });
  if (!saved) return;
  formModalOpen.value = false;
}

async function submitQuestionnaire() {
  if (!currentDraft.value?.id) return;
  window.clearTimeout(autosaveTimer);
  submitting.value = true;
  try {
    const captcha = await getCaptchaProof("school_survey_submit");
    const { data } = await api.post(`/school-survey-submissions/${currentDraft.value.id}/submit/`, {
      form_data: formData.value,
      captcha,
    });
    currentDraft.value = null;
    formModalOpen.value = false;
    ui.success(`问卷 #${data.id} 已提交。`);
    if (listModalOpen.value) {
      await loadSubmissions();
    }
  } catch (error) {
    ui.error(captchaErrorMessage(error, "问卷提交失败。"));
  } finally {
    submitting.value = false;
  }
}

async function openSubmissionDetail(item) {
  try {
    const { data } = await api.get(`/school-survey-submissions/${item.id}/`);
    detailSubmission.value = data;
    detailFormData.value = data?.form_data && typeof data.form_data === "object" ? data.form_data : {};
    detailModalOpen.value = true;
  } catch (error) {
    ui.error(error?.response?.data?.detail || "问卷详情加载失败。");
  }
}

function closeDetailModal() {
  detailModalOpen.value = false;
  detailSubmission.value = null;
  detailFormData.value = {};
}

function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hour = String(date.getHours()).padStart(2, "0");
  const minute = String(date.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day} ${hour}:${minute}`;
}

function formatClock(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

onMounted(() => {
  loadSchools();
});

onBeforeUnmount(() => {
  window.clearTimeout(autosaveTimer);
});
</script>

<style scoped>
.school-survey-page {
  width: min(1180px, 100%);
  margin: 0 auto;
  display: grid;
  gap: 18px;
}

.survey-hero {
  padding: clamp(22px, 3vw, 34px);
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: end;
  gap: 24px;
}

.kicker {
  margin: 0 0 8px;
  color: var(--accent);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.survey-hero h1,
.modal-head h2,
.form-modal-head h2 {
  margin: 0;
  color: var(--text-strong);
  font-family: var(--font-display);
  letter-spacing: 0;
}

.survey-hero h1 {
  font-size: clamp(28px, 4vw, 44px);
  line-height: 1.12;
}

.meta {
  margin: 8px 0 0;
  color: var(--text-soft);
  font-size: 14px;
  line-height: 1.7;
}

.hero-stat {
  min-width: 118px;
  border: 1px solid var(--hairline);
  border-radius: var(--radius-md);
  padding: 16px;
  background: var(--surface-strong);
  text-align: center;
}

.hero-stat strong {
  display: block;
  color: var(--text-strong);
  font-size: 34px;
  line-height: 1;
}

.hero-stat span {
  display: block;
  margin-top: 6px;
  color: var(--text-soft);
  font-size: 13px;
}

.survey-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
}

.search-box {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  border: 1px solid var(--input-border);
  border-radius: 999px;
  padding: 10px 16px;
  background: var(--input-bg);
  box-shadow: var(--shadow-sm);
}

.search-icon {
  position: relative;
  width: 16px;
  height: 16px;
  color: var(--text-quiet);
  flex: 0 0 auto;
}

.search-icon::before {
  content: "";
  position: absolute;
  inset: 1px 4px 4px 1px;
  border: 2px solid currentColor;
  border-radius: 999px;
}

.search-icon::after {
  content: "";
  position: absolute;
  right: 1px;
  bottom: 1px;
  width: 7px;
  height: 2px;
  border-radius: 999px;
  background: currentColor;
  transform: rotate(45deg);
}

.search-input {
  flex: 1 1 auto;
  min-width: 0;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--text-strong);
  font-size: 16px;
}

.school-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 14px;
}

.school-card {
  width: 100%;
  padding: 16px;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 14px;
  text-align: left;
  color: var(--text);
  cursor: pointer;
  transition:
    transform 0.18s ease,
    box-shadow 0.18s ease,
    border-color 0.18s ease;
}

.school-card:hover {
  transform: translateY(-2px);
  border-color: color-mix(in srgb, var(--accent) 30%, var(--panel-border));
  box-shadow: var(--card-shadow-hover);
}

.school-logo {
  width: 56px;
  height: 56px;
  border-radius: 16px;
  object-fit: cover;
  border: 1px solid var(--hairline);
  background: var(--surface-soft);
}

.school-logo--fallback {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--accent);
  font-family: var(--font-display);
  font-size: 15px;
  font-weight: 800;
  letter-spacing: 0;
}

.school-card-main {
  min-width: 0;
  display: grid;
  gap: 4px;
}

.school-card-main strong {
  color: var(--text-strong);
  font-size: 17px;
  line-height: 1.35;
}

.school-card-main small,
.school-card-meta {
  color: var(--text-soft);
  font-size: 12px;
}

.school-card-meta {
  padding: 5px 8px;
  border-radius: 999px;
  background: var(--surface-chip);
  white-space: nowrap;
}

.empty-card {
  padding: 28px;
  color: var(--text-soft);
  text-align: center;
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: grid;
  place-items: center;
  padding: 20px;
  background: color-mix(in srgb, var(--text-strong) 30%, transparent);
}

.action-modal,
.list-modal,
.add-school-modal {
  width: min(520px, calc(100vw - 28px));
  max-height: min(82vh, 680px);
  overflow: auto;
  background: var(--surface-overlay);
}

.modal-head,
.form-modal-head,
.form-modal-foot {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  padding: 18px;
  border-bottom: 1px solid var(--hairline);
}

.modal-head h2,
.form-modal-head h2 {
  font-size: 24px;
}

.icon-close {
  width: 34px;
  height: 34px;
  border: 1px solid var(--button-border);
  border-radius: 999px;
  background: var(--button-bg);
  color: var(--text-strong);
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
}

.action-list {
  display: grid;
  gap: 12px;
  padding: 18px;
}

.action-choice {
  border: 1px solid var(--hairline);
  border-radius: var(--radius-md);
  background: var(--surface-strong);
  padding: 16px;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 14px;
  text-align: left;
  color: var(--text);
  cursor: pointer;
}

.action-choice:hover {
  border-color: color-mix(in srgb, var(--accent) 34%, var(--hairline));
}

.choice-mark {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--accent-gradient);
  color: var(--accent-contrast);
  font-size: 25px;
  font-weight: 700;
}

.choice-mark--soft {
  background: var(--surface-soft);
  color: var(--accent);
}

.action-choice strong,
.submission-row strong {
  color: var(--text-strong);
  font-size: 16px;
}

.action-choice small,
.submission-row small {
  display: block;
  margin-top: 4px;
  color: var(--text-soft);
  font-size: 13px;
  line-height: 1.5;
}

.empty-inline {
  padding: 28px 18px;
  color: var(--text-soft);
  text-align: center;
}

.submission-list {
  padding: 12px;
  display: grid;
  gap: 8px;
}

.submission-row {
  border: 1px solid var(--hairline);
  border-radius: 14px;
  background: var(--surface-strong);
  padding: 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  text-align: left;
  color: var(--text);
  cursor: pointer;
}

.submission-row:hover {
  border-color: color-mix(in srgb, var(--accent) 30%, var(--hairline));
}

.submission-author {
  color: var(--text-soft);
  font-size: 13px;
  white-space: nowrap;
}

.add-school-form {
  padding: 18px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.admin-field {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.admin-field--wide,
.add-school-actions {
  grid-column: 1 / -1;
}

.add-school-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding-top: 4px;
}

.form-backdrop {
  padding: 18px;
}

.form-modal {
  width: min(1080px, calc(100vw - 28px));
  height: min(90vh, 860px);
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  background: var(--surface-overlay);
}

.form-modal-head,
.form-modal-foot {
  background: var(--surface-overlay);
}

.form-head-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 0 0 auto;
}

.form-modal-body {
  overflow: auto;
  padding: 18px;
}

.form-modal-foot {
  align-items: center;
  border-top: 1px solid var(--hairline);
  border-bottom: 0;
}

.form-modal-foot .meta {
  margin: 0;
  margin-right: auto;
}

:deep(.questionnaire-form) {
  display: grid;
  gap: 18px;
}

:deep(.questionnaire-section) {
  border: 1px solid var(--hairline);
  border-radius: var(--radius-md);
  background: var(--surface-strong);
  overflow: hidden;
}

:deep(.questionnaire-section-head) {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 12px;
  align-items: start;
  padding: 16px;
  border-bottom: 1px solid var(--hairline);
  background: var(--surface-soft);
}

:deep(.questionnaire-section-head h3) {
  margin: 0;
  color: var(--text-strong);
  font-size: 18px;
  letter-spacing: 0;
}

:deep(.section-index) {
  width: 34px;
  height: 34px;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--accent-soft);
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 700;
}

:deep(.questionnaire-fields) {
  padding: 16px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

:deep(.survey-field) {
  display: grid;
  gap: 8px;
  min-width: 0;
  border: 0;
  margin: 0;
  padding: 0;
}

:deep(.survey-field--wide) {
  grid-column: 1 / -1;
}

:deep(.field-label) {
  color: var(--text-strong);
  font-size: 13px;
  font-weight: 700;
}

:deep(.choice-grid) {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

:deep(.choice-pill) {
  border: 1px solid var(--hairline);
  border-radius: 999px;
  padding: 8px 11px;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  background: var(--surface);
  color: var(--text);
  font-size: 13px;
}

:deep(.choice-pill input) {
  margin: 0;
  accent-color: var(--accent);
}

:deep(.matrix-scroll) {
  overflow-x: auto;
  border: 1px solid var(--hairline);
  border-radius: 14px;
  background: var(--surface);
}

:deep(.survey-matrix) {
  width: 100%;
  min-width: 640px;
  border-collapse: collapse;
  font-size: 13px;
}

:deep(.survey-matrix th),
:deep(.survey-matrix td) {
  padding: 10px;
  border-bottom: 1px solid var(--hairline);
  border-right: 1px solid var(--hairline);
  text-align: left;
  vertical-align: top;
}

:deep(.survey-matrix tr:last-child th),
:deep(.survey-matrix tr:last-child td) {
  border-bottom: 0;
}

:deep(.survey-matrix th:last-child),
:deep(.survey-matrix td:last-child) {
  border-right: 0;
}

:deep(.survey-matrix thead th) {
  background: var(--surface-soft);
  color: var(--text-strong);
  font-weight: 800;
  white-space: nowrap;
}

:deep(.survey-matrix tbody th) {
  width: 170px;
  color: var(--text-strong);
  font-weight: 700;
  background: color-mix(in srgb, var(--surface-soft) 70%, transparent);
}

:deep(.matrix-input) {
  min-height: 38px;
  width: 100%;
  min-width: 120px;
  padding: 8px 10px;
}

:deep(.matrix-value) {
  min-width: 120px;
  color: var(--text);
  line-height: 1.6;
  white-space: pre-wrap;
}

:deep(.readonly-value) {
  min-height: 42px;
  border: 1px solid var(--hairline);
  border-radius: 12px;
  padding: 10px 12px;
  background: var(--surface-soft);
  color: var(--text);
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
}

:deep(.input[readonly]),
:deep(.textarea[readonly]),
:deep(input:disabled) {
  cursor: default;
  color: var(--text-soft);
}

@media (max-width: 760px) {
  .survey-hero {
    grid-template-columns: 1fr;
  }

  .hero-stat {
    width: 100%;
  }

  .survey-toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .school-grid {
    grid-template-columns: 1fr;
  }

  .form-backdrop,
  .modal-backdrop {
    padding: 8px;
  }

  .form-modal {
    width: calc(100vw - 16px);
    height: calc(100dvh - 16px);
  }

  .form-modal-head,
  .form-modal-foot {
    flex-direction: column;
    align-items: stretch;
  }

  .form-head-actions {
    justify-content: space-between;
  }

  :deep(.questionnaire-fields) {
    grid-template-columns: 1fr;
  }

  .submission-row {
    align-items: flex-start;
    flex-direction: column;
  }

  .add-school-form {
    grid-template-columns: 1fr;
  }
}
</style>

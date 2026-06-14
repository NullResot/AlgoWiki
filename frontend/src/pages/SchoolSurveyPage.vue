<template>
  <section class="school-survey-page">
    <header class="survey-hero card">
      <div>
        <p class="kicker">AlgoWiki School Survey</p>
        <h1>CCPC/ICPC 院校队伍情况收集</h1>
        <p class="meta">
          收集参加过 CCPC/ICPC 区域赛、省赛、邀请赛或网络赛的院校队伍建设、训练制度、赛事支持与激励政策。提交记录会保留多个版本，联系方式仅提交者本人和管理员可见。
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
              填表人联系方式按权限显示，非本人和非管理员会自动隐藏。
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

import api from "../services/api";
import { useAuthStore } from "../stores/auth";
import { useUiStore } from "../stores/ui";

const questionnaireSections = [
  {
    key: "basic",
    title: "一、基础信息",
    description: "用于确认学校与队伍组织形态。",
    fields: [
      { key: "school_name", label: "学校名称", type: "text", placeholder: "例如：清华大学" },
      { key: "province_city", label: "所在省份/城市", type: "text", placeholder: "例如：北京市 / 北京市" },
      {
        key: "school_type_options",
        label: "学校类型",
        type: "checkbox",
        options: ["985", "211", "双一流", "普通本科", "高职高专", "民办本科", "其他"],
      },
      {
        key: "main_unit_options",
        label: "主要负责学院/单位",
        type: "checkbox",
        options: ["计算机学院", "软件学院", "人工智能学院", "信息学院", "数学学院", "创新创业学院", "校团委/学生组织", "不清楚", "其他"],
      },
      {
        key: "organization_status",
        label: "组织情况",
        type: "checkbox",
        options: ["无正式组织", "非正式训练群", "算法协会", "学院级队伍", "校级队伍", "ACM/ICPC 实验室/基地", "不清楚", "其他"],
      },
      { key: "organization_name", label: "组织名称", type: "text", placeholder: "如无正式名称可填“无”" },
      {
        key: "has_coach",
        label: "是否有固定指导老师",
        type: "radio",
        options: ["有", "无", "不清楚"],
      },
      {
        key: "has_student_leader",
        label: "是否有学生负责人",
        type: "radio",
        options: ["有", "无", "不清楚"],
      },
      {
        key: "has_training_room",
        label: "是否有固定训练场地",
        type: "radio",
        options: ["有", "无", "不清楚"],
      },
      { key: "training_room_note", label: "训练场地说明", type: "textarea", placeholder: "说明机房、实验室、开放时间等情况" },
    ],
  },
  {
    key: "selection",
    title: "二、入队与选拔机制",
    description: "记录入队条件、新人训练和选拔方式。",
    fields: [
      {
        key: "has_entry_requirement",
        label: "是否有正式入队条件",
        type: "radio",
        options: ["有", "无", "不清楚"],
      },
      {
        key: "selection_methods",
        label: "入队/选拔方式",
        type: "checkbox",
        options: ["校赛选拔", "院赛选拔", "线上 OJ 考核", "面试", "训练营结业", "老师推荐", "老队员推荐", "自由加入", "其他"],
      },
      { key: "entry_requirement_detail", label: "具体入队条件说明", type: "textarea", placeholder: "例如题量、排名、语言基础、训练出勤等" },
      {
        key: "has_newbie_training",
        label: "是否有新人训练体系",
        type: "radio",
        options: ["有", "无", "不清楚"],
      },
      { key: "newbie_training_content", label: "新人训练内容", type: "textarea", placeholder: "课程、题单、讲课、训练赛、代码规范等" },
      { key: "newbie_training_cycle", label: "新人训练周期", type: "text", placeholder: "例如 4 周 / 一学期 / 长期滚动" },
    ],
  },
  {
    key: "scale",
    title: "三、队伍规模与当前状态",
    description: "描述队伍规模、活跃程度和梯队建设。",
    fields: [
      { key: "team_total_size", label: "校队/训练群总人数", type: "text", placeholder: "例如：约 120 人" },
      { key: "active_training_size", label: "当前活跃训练人数", type: "text", placeholder: "例如：约 30 人" },
      { key: "grade_distribution", label: "年级分布", type: "textarea", placeholder: "例如：大一 15 人，大二 10 人，大三 6 人，研究生 2 人" },
      {
        key: "team_activity",
        label: "队伍活跃度",
        type: "radio",
        options: ["很活跃", "较活跃", "一般", "较低", "几乎停滞", "不清楚"],
      },
      {
        key: "team_pipeline",
        label: "队伍梯队建设",
        type: "radio",
        options: ["成熟", "基本稳定", "不稳定", "缺少新人", "不清楚"],
      },
      {
        key: "cross_team_allowed",
        label: "是否允许跨年级/跨学院组队",
        type: "radio",
        options: ["允许", "不允许", "视比赛而定", "不清楚"],
      },
    ],
  },
  {
    key: "training",
    title: "四、训练制度",
    description: "记录固定训练安排、平台与校内 OJ。",
    fields: [
      { key: "training_frequency", label: "固定训练频率", type: "text", placeholder: "例如：每周 2 次训练赛" },
      { key: "training_time_note", label: "训练时间说明", type: "textarea", placeholder: "说明训练日、时长、寒暑假安排等" },
      {
        key: "training_forms",
        label: "训练形式",
        type: "checkbox",
        options: ["专题讲课", "训练赛", "补题讲解", "组队 VP", "个人刷题", "新人营", "集训", "其他"],
      },
      {
        key: "training_platforms",
        label: "常用训练平台",
        type: "checkbox",
        options: ["Codeforces", "AtCoder", "洛谷", "牛客", "Vjudge", "HDU", "POJ", "LeetCode", "校内 OJ", "其他"],
      },
      { key: "school_oj_url", label: "校内 OJ 地址", type: "text", placeholder: "没有可填“无”" },
    ],
  },
  {
    key: "competition",
    title: "五、比赛参与情况",
    description: "记录主要比赛、成绩和校内选拔机制。",
    fields: [
      {
        key: "main_competitions",
        label: "主要参加比赛",
        type: "checkbox",
        options: ["ICPC", "CCPC", "蓝桥杯", "团体程序设计天梯赛", "GPLT", "高校校赛", "企业赛", "其他"],
      },
      { key: "recent_awards", label: "近三年获奖情况", type: "textarea", placeholder: "可按年份填写：2025 ICPC 区域赛 银牌 1 队..." },
      { key: "best_recent_result", label: "近三年最好成绩说明", type: "textarea", placeholder: "说明最好奖项、队伍、比赛站点等" },
      { key: "school_selection_mechanism", label: "校内选拔机制", type: "textarea", placeholder: "例如校赛排名、集训考核、教练指定等" },
    ],
  },
  {
    key: "funding",
    title: "六、比赛报销与经费支持",
    description: "记录经费来源、报销范围和到账情况。",
    fields: [
      {
        key: "funding_sources",
        label: "经费来源",
        type: "checkbox",
        options: ["学院经费", "学校经费", "竞赛专项", "实验室经费", "老师课题组", "学生自费", "企业赞助", "其他", "不清楚"],
      },
      {
        key: "reimbursement_overall",
        label: "报销总体情况",
        type: "radio",
        options: ["基本全报", "部分报销", "偶尔报销", "基本不报销", "不清楚"],
      },
      {
        key: "need_advance_payment",
        label: "是否需要学生垫付",
        type: "radio",
        options: ["需要", "不需要", "视情况而定", "不清楚"],
      },
      {
        key: "reimbursement_difficulty",
        label: "报销难度",
        type: "radio",
        options: ["简单", "一般", "较难", "很难", "不清楚"],
      },
      { key: "reimbursement_speed", label: "到账速度", type: "text", placeholder: "例如：1 个月内 / 3 个月以上 / 不稳定" },
      { key: "competition_reimbursement_table", label: "各比赛报销情况", type: "textarea", placeholder: "例如：ICPC 报名费/路费/住宿可报，餐费不可报..." },
      { key: "travel_reimbursement_note", label: "路费报销标准/说明", type: "textarea", placeholder: "高铁二等座、机票限制、跨省限制等" },
      { key: "hotel_reimbursement_note", label: "住宿费报销标准/限制", type: "textarea", placeholder: "每人每天标准、是否限定协议酒店等" },
    ],
  },
  {
    key: "reward",
    title: "七、奖励政策与队内激励",
    description: "记录奖金、综测、学分和队内激励。",
    fields: [
      {
        key: "has_award_bonus",
        label: "获奖是否有奖金",
        type: "radio",
        options: ["有", "无", "不清楚"],
      },
      { key: "bonus_source", label: "奖金来源", type: "text", placeholder: "学校 / 学院 / 实验室 / 企业 / 其他" },
      {
        key: "bonus_rule_public",
        label: "奖励标准是否公开",
        type: "radio",
        options: ["公开", "不公开", "部分公开", "不清楚"],
      },
      {
        key: "bonus_actual_paid",
        label: "实际发放情况",
        type: "radio",
        options: ["稳定发放", "偶尔延迟", "不稳定", "基本不发", "不清楚"],
      },
      { key: "typical_bonus_amount", label: "典型奖励金额", type: "textarea", placeholder: "例如：ICPC 金牌 X 元，银牌 X 元，铜牌 X 元" },
      { key: "evaluation_bonus", label: "综测/学分/奖学金/评优", type: "textarea", placeholder: "说明是否加分、上限、适用范围和规则" },
      { key: "internal_incentives", label: "队内激励", type: "textarea", placeholder: "例如训练积分、题单打卡、队内榜单、补贴等" },
    ],
  },
  {
    key: "graduate",
    title: "八、保研与升学影响",
    description: "记录推免认可范围、加分规则和依据。",
    fields: [
      {
        key: "affects_recommendation",
        label: "是否影响推免/保研",
        type: "radio",
        options: ["明确加分", "可能有帮助", "无直接影响", "不清楚"],
      },
      { key: "recommendation_scope", label: "适用范围", type: "textarea", placeholder: "学院、专业、推免类型、竞赛专项等" },
      { key: "recognized_awards", label: "认可比赛/奖项级别", type: "textarea", placeholder: "列出认可比赛与奖项级别" },
      {
        key: "distinguish_authorship",
        label: "是否区分队长/队员/作者身份",
        type: "radio",
        options: ["区分", "不区分", "视规则而定", "不清楚"],
      },
      { key: "recommendation_score_rule", label: "加分规则", type: "textarea", placeholder: "例如金银铜对应加分、上限、折算规则等" },
      { key: "official_policy_link", label: "官方文件依据/链接", type: "textarea", placeholder: "可填写文件名称、链接或规则截图说明" },
    ],
  },
  {
    key: "inheritance",
    title: "九、资料沉淀与队伍传承",
    description: "记录训练资料、题单和退役队员维护情况。",
    fields: [
      {
        key: "has_training_materials",
        label: "是否有训练资料",
        type: "radio",
        options: ["有", "无", "不清楚"],
      },
      {
        key: "material_forms",
        label: "资料形式",
        type: "checkbox",
        options: ["题单", "课件", "录播", "讲义", "代码模板", "校赛题解", "知识库", "其他"],
      },
      {
        key: "materials_public",
        label: "资料是否公开",
        type: "radio",
        options: ["公开", "队内公开", "部分公开", "不公开", "不清楚"],
      },
      { key: "materials_link", label: "资料链接", type: "textarea", placeholder: "公开资料可填写链接，内部资料可说明存放方式" },
      { key: "newbie_route", label: "新人路线/题单", type: "textarea", placeholder: "说明新人从入门到组队训练的路线" },
      { key: "retired_members_support", label: "退役队员维护", type: "textarea", placeholder: "退役队员是否继续讲课、出题、带队、维护资料" },
      { key: "inheritance_problem", label: "传承问题", type: "textarea", placeholder: "例如断层、缺教练、缺资料、管理不稳定等" },
    ],
  },
  {
    key: "subjective",
    title: "十、主观评价",
    description: "主观评价学校支持、队伍氛围和主要困难。",
    fields: [
      {
        key: "support_score",
        label: "学校支持力度评分",
        type: "radio",
        options: ["1", "2", "3", "4", "5"],
      },
      { key: "support_reason", label: "评分理由", type: "textarea", placeholder: "说明打分原因" },
      {
        key: "team_atmosphere",
        label: "队伍氛围",
        type: "radio",
        options: ["很好", "较好", "一般", "较差", "不清楚"],
      },
      {
        key: "willing_to_mentor",
        label: "带新人意愿",
        type: "radio",
        options: ["很强", "较强", "一般", "较弱", "不清楚"],
      },
      { key: "atmosphere_note", label: "氛围说明", type: "textarea", placeholder: "说明队内协作、讲题、补题、社群氛围等" },
      { key: "main_difficulties", label: "主要困难", type: "textarea", placeholder: "经费、场地、老师、新人、传承、比赛机会等" },
    ],
  },
  {
    key: "submitter",
    title: "十一、填表人信息与可信度",
    description: "联系方式不会向普通浏览者公开。",
    fields: [
      {
        key: "submitter_identity",
        label: "填表人身份",
        type: "checkbox",
        options: ["现役队员", "退役队员", "队长/负责人", "指导老师", "协会成员", "普通学生", "其他"],
      },
      {
        key: "information_source",
        label: "信息来源",
        type: "checkbox",
        options: ["亲身经历", "队内通知", "老师说明", "官方文件", "同学转述", "公开网页", "不确定"],
      },
      { key: "information_updated_at", label: "信息更新时间", type: "text", placeholder: "例如：2026 年 6 月" },
      {
        key: "allow_public",
        label: "是否允许公开问卷内容",
        type: "radio",
        options: ["允许公开", "允许匿名公开", "不建议公开", "不确定"],
      },
      {
        key: "willing_contact",
        label: "是否愿意留联系方式",
        type: "radio",
        options: ["愿意", "不愿意"],
      },
      { key: "submitter_contact", label: "联系方式", type: "text", placeholder: "QQ / 邮箱 / 微信，非本人和非管理员不可见" },
    ],
  },
  {
    key: "extra",
    title: "十二、其他补充",
    description: "补充 PDF 中未覆盖但你认为重要的信息。",
    fields: [
      { key: "extra_note", label: "其他补充", type: "textarea", placeholder: "可填写任何需要补充的信息" },
    ],
  },
];

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
    const toggleCheckbox = (key, option, checked) => {
      const current = ensureArray(key);
      const next = checked
        ? Array.from(new Set([...current, option]))
        : current.filter((item) => item !== option);
      updateValue(key, next);
    };
    const inputValue = (key) => {
      const value = props.modelValue?.[key];
      if (Array.isArray(value)) return value.join("、");
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
      payload[field.key] = field.type === "checkbox" ? [] : "";
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
  if (selectedSchool.value) {
    payload.school_name = payload.school_name || selectedSchool.value.name || "";
    payload.province_city =
      payload.province_city || schoolLocation(selectedSchool.value) || "";
  }
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
    const { data } = await api.post(`/school-survey-submissions/${currentDraft.value.id}/submit/`, {
      form_data: formData.value,
    });
    currentDraft.value = null;
    formModalOpen.value = false;
    ui.success(`问卷 #${data.id} 已提交。`);
    if (listModalOpen.value) {
      await loadSubmissions();
    }
  } catch (error) {
    ui.error(error?.response?.data?.detail || "问卷提交失败。");
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

<template>
  <section class="pulse-manager">
    <header class="manager-head">
      <div><p class="manager-kicker">MIDNIGHT PULSE</p><h2>午夜脉冲管理</h2><p class="meta">管理每日内容、Codeforces 绑定、活动发放、兑换码和不可变流水。</p></div>
      <RouterLink class="btn" :to="{ name: 'pulse' }">打开午夜脉冲</RouterLink>
    </header>

    <nav class="manager-tabs">
      <button v-for="item in tabs" :key="item.id" :class="{ active: tab === item.id }" type="button" @click="selectTab(item.id)">{{ item.label }}</button>
    </nav>

    <section v-if="tab === 'bindings'" class="manager-panel">
      <div class="panel-head"><div><h3>Codeforces 绑定</h3><p class="meta">按 AlgoWiki 用户、邮箱或 Handle 搜索。解绑只结束活跃关系，不删除历史。</p></div><div class="search-row"><input v-model.trim="bindingQuery" class="input" placeholder="用户名 / Handle" @keyup.enter="loadBindings" /><button class="btn" @click="loadBindings">搜索</button></div></div>
      <div class="data-list">
        <article v-for="item in bindings" :key="item.id" class="data-row">
          <div><strong>{{ item.handle }}</strong><p class="meta">{{ item.owner.username }} · Rating {{ item.rating || "未定级" }}</p></div>
          <span class="status-pill" :class="{ active: item.is_active }">{{ item.is_active ? "活跃" : "已解绑" }}</span>
          <button v-if="item.is_active" class="btn btn-danger" type="button" @click="prepareUnbind(item)">代为解绑</button>
        </article>
        <p v-if="!bindings.length && !loading" class="meta">没有找到绑定记录。</p>
      </div>
      <form v-if="unbindTarget" class="operation-card" @submit.prevent="submitUnbind">
        <div><span>ADMIN UNBIND</span><strong>解绑 {{ unbindTarget.handle }} / {{ unbindTarget.owner.username }}</strong></div>
        <textarea v-model.trim="unbindForm.reason" class="textarea" rows="3" maxlength="300" placeholder="必填：说明代解绑原因"></textarea>
        <label class="check-row"><input v-model="unbindForm.allow_rebind_now" type="checkbox" />立即允许 Handle 被其他用户重新绑定</label>
        <div class="operation-actions"><button class="btn" type="button" @click="unbindTarget = null">取消</button><button class="btn btn-danger" :disabled="saving || unbindForm.reason.length < 2">确认解绑</button></div>
      </form>
    </section>

    <section v-else-if="tab === 'grants'" class="manager-panel">
      <div class="panel-head"><div><h3>管理员与活动发放</h3><p class="meta">同一幂等键重复提交不会重复发放。</p></div></div>
      <form class="form-grid" @submit.prevent="submitGrant">
        <label><span>用户 ID</span><input v-model.number="grantForm.user_id" class="input" type="number" min="1" required /></label>
        <label><span>换签卷</span><input v-model.number="grantForm.reroll" class="input" type="number" min="0" /></label>
        <label><span>补签卷</span><input v-model.number="grantForm.makeup" class="input" type="number" min="0" /></label>
        <label><span>超级补签卷</span><input v-model.number="grantForm.super_makeup" class="input" type="number" min="0" /></label>
        <label class="span-2"><span>活动说明</span><input v-model.trim="grantForm.note" class="input" maxlength="300" placeholder="例如：2026 夏季训练活动" /></label>
        <button class="btn btn-accent" :disabled="saving">确认发放</button>
      </form>
      <div class="subsection-head"><div><h3>自动领取活动</h3><p class="meta">活动期内，登录用户首次进入午夜脉冲时自动领取一次，流水按用户和活动永久防重。</p></div></div>
      <form class="form-grid" @submit.prevent="submitCampaign">
        <label><span>活动键</span><input v-model.trim="campaignForm.key" class="input" pattern="[a-z0-9-]+" placeholder="summer-2026" required /></label>
        <label class="span-2"><span>活动名称</span><input v-model.trim="campaignForm.name" class="input" maxlength="120" required /></label>
        <label><span>开始时间</span><input v-model="campaignForm.starts_at" class="input" type="datetime-local" required /></label>
        <label><span>结束时间</span><input v-model="campaignForm.ends_at" class="input" type="datetime-local" required /></label>
        <label><span>换签卷</span><input v-model.number="campaignForm.reroll" class="input" type="number" min="0" /></label>
        <label><span>补签卷</span><input v-model.number="campaignForm.makeup" class="input" type="number" min="0" /></label>
        <label><span>超级补签卷</span><input v-model.number="campaignForm.super_makeup" class="input" type="number" min="0" /></label>
        <button class="btn btn-accent" :disabled="saving">创建活动</button>
      </form>
      <div class="data-list">
        <article v-for="item in campaigns" :key="item.id" class="data-row">
          <div><strong>{{ item.name }}</strong><p class="meta">{{ rewardText(item.reward_payload) }} · {{ item.key }}</p></div>
          <span class="status-pill" :class="{ active: item.is_enabled }">{{ item.is_enabled ? "启用" : "停用" }}</span>
          <button class="btn" type="button" @click="toggleCampaign(item)">{{ item.is_enabled ? "停用" : "启用" }}</button>
        </article>
      </div>
    </section>

    <section v-else-if="tab === 'codes'" class="manager-panel">
      <div class="panel-head"><div><h3>兑换码</h3><p class="meta">明文只在创建成功时显示一次，之后只能看到提示片段。</p></div></div>
      <form class="form-grid code-form" @submit.prevent="submitCode">
        <label class="span-2"><span>兑换码明文</span><input v-model.trim="codeForm.code" class="input" minlength="6" maxlength="64" required /></label>
        <label><span>换签卷</span><input v-model.number="codeForm.reroll" class="input" type="number" min="0" /></label>
        <label><span>补签卷</span><input v-model.number="codeForm.makeup" class="input" type="number" min="0" /></label>
        <label><span>超级补签卷</span><input v-model.number="codeForm.super_makeup" class="input" type="number" min="0" /></label>
        <label><span>总次数</span><input v-model.number="codeForm.max_uses" class="input" type="number" min="1" /></label>
        <label><span>单用户次数</span><input v-model.number="codeForm.per_user_limit" class="input" type="number" min="1" /></label>
        <button class="btn btn-accent" :disabled="saving">创建兑换码</button>
      </form>
      <div v-if="createdPlainCode" class="plain-code"><span>仅显示一次</span><strong>{{ createdPlainCode }}</strong><button class="btn" @click="copyCode">复制</button></div>
      <div class="data-list">
        <article v-for="item in codes" :key="item.id" class="data-row code-row">
          <div><strong>{{ item.code_hint }}</strong><p class="meta">{{ rewardText(item.reward_payload) }} · {{ item.used_count }}/{{ item.max_uses }}</p></div>
          <span class="status-pill" :class="{ active: item.is_enabled }">{{ item.is_enabled ? "启用" : "停用" }}</span>
          <button class="btn" @click="toggleCode(item)">{{ item.is_enabled ? "停用" : "启用" }}</button>
        </article>
      </div>
    </section>

    <section v-else-if="tab === 'editions'" class="manager-panel">
      <div class="panel-head"><div><h3>每日话题与争议</h3><p class="meta">管理员预设优先于系统随机题库，同一日期只能有一期。</p></div></div>
      <form class="form-grid edition-form" @submit.prevent="submitEdition">
        <label><span>日期</span><input v-model="editionForm.date" class="input" type="date" required /></label>
        <label class="span-2"><span>问题标题</span><input v-model.trim="editionForm.title" class="input" maxlength="220" required /></label>
        <label class="span-3"><span>问题正文</span><textarea v-model.trim="editionForm.content_md" class="textarea" rows="3" required></textarea></label>
        <label class="span-2"><span>争议投票题目</span><input v-model.trim="editionForm.poll_prompt" class="input" maxlength="300" required /></label>
        <label class="span-3"><span>选项，每行一个</span><textarea v-model="editionForm.options_text" class="textarea" rows="4" required></textarea></label>
        <label class="check-row"><input v-model="editionForm.publish" type="checkbox" />立即发布</label>
        <button class="btn btn-accent" :disabled="saving">保存预设</button>
      </form>
      <div class="data-list">
        <article v-for="item in editions" :key="item.id" class="data-row edition-row"><div><strong>{{ item.date }} · {{ item.question.title }}</strong><p class="meta">{{ item.poll.prompt }}</p></div><span class="status-pill" :class="{ active: item.status === 'published' }">{{ item.status }}</span></article>
      </div>
    </section>

    <section v-else class="manager-panel">
      <div class="panel-head"><div><h3>积分与道具流水</h3><p class="meta">流水不可直接编辑。需要纠正时应追加相反方向的管理员流水。</p></div><button class="btn" @click="loadLedger">刷新</button></div>
      <div class="ledger-table"><div class="ledger-head"><span>用户</span><span>资产</span><span>变化</span><span>余额</span><span>来源</span></div><div v-for="item in ledger" :key="item.id" class="ledger-line"><span>{{ item.username }}</span><span>{{ item.asset }}</span><strong :class="{ negative: item.delta < 0 }">{{ item.delta > 0 ? `+${item.delta}` : item.delta }}</strong><span>{{ item.balance_after }}</span><small>{{ item.note || item.source_type }}</small></div></div>
    </section>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { RouterLink } from "vue-router";

import pulseApi from "../../services/pulse";
import { useUiStore } from "../../stores/ui";

const ui = useUiStore();
const tabs = [
  { id: "bindings", label: "绑定与解绑" },
  { id: "grants", label: "活动发放" },
  { id: "codes", label: "兑换码" },
  { id: "editions", label: "每日内容" },
  { id: "ledger", label: "资产流水" },
];
const tab = ref("bindings");
const loading = ref(false);
const saving = ref(false);
const bindings = ref([]);
const campaigns = ref([]);
const codes = ref([]);
const editions = ref([]);
const ledger = ref([]);
const bindingQuery = ref("");
const unbindTarget = ref(null);
const createdPlainCode = ref("");
const unbindForm = reactive({ reason: "", allow_rebind_now: false });
const grantForm = reactive({ user_id: null, reroll: 0, makeup: 0, super_makeup: 0, note: "" });
const campaignForm = reactive({ key: "", name: "", starts_at: "", ends_at: "", reroll: 0, makeup: 0, super_makeup: 0 });
const codeForm = reactive({ code: "", reroll: 0, makeup: 0, super_makeup: 0, max_uses: 1, per_user_limit: 1 });
const editionForm = reactive({ date: "", title: "", content_md: "", poll_prompt: "", options_text: "", publish: false });

function errorText(error, fallback) {
  return error?.response?.data?.detail || fallback;
}
function eventKey(prefix) {
  return `${prefix}:${Date.now()}:${Math.random().toString(16).slice(2)}`;
}
function rewardsFrom(form) {
  return Object.fromEntries(["reroll", "makeup", "super_makeup"].filter((key) => Number(form[key]) > 0).map((key) => [key, Number(form[key])]));
}
function rewardText(payload) {
  return Object.entries(payload || {}).map(([key, value]) => `${key} +${value}`).join(" · ") || "无奖励";
}

async function selectTab(value) {
  tab.value = value;
  if (value === "bindings") await loadBindings();
  if (value === "grants") await loadCampaigns();
  if (value === "codes") await loadCodes();
  if (value === "editions") await loadEditions();
  if (value === "ledger") await loadLedger();
}
async function loadBindings() {
  loading.value = true;
  try { bindings.value = (await pulseApi.admin.bindings(bindingQuery.value)).results || []; }
  catch (error) { ui.error(errorText(error, "绑定记录加载失败")); }
  finally { loading.value = false; }
}
function prepareUnbind(item) {
  unbindTarget.value = item;
  unbindForm.reason = "";
  unbindForm.allow_rebind_now = false;
}
async function submitUnbind() {
  if (!unbindTarget.value || unbindForm.reason.length < 2) return;
  saving.value = true;
  try {
    await pulseApi.admin.unbind(unbindTarget.value.id, { ...unbindForm });
    ui.success("管理员解绑已完成并写入审计日志。");
    unbindTarget.value = null;
    await loadBindings();
  } catch (error) { ui.error(errorText(error, "管理员解绑失败")); }
  finally { saving.value = false; }
}
async function submitGrant() {
  const rewards = rewardsFrom(grantForm);
  if (!grantForm.user_id || !Object.keys(rewards).length) return ui.error("请选择用户并填写至少一种道具数量。");
  saving.value = true;
  try {
    await pulseApi.admin.grant({ user_id: grantForm.user_id, rewards, idempotency_key: eventKey("pulse-admin"), note: grantForm.note });
    ui.success("道具已发放并通知用户。");
  } catch (error) { ui.error(errorText(error, "道具发放失败")); }
  finally { saving.value = false; }
}
async function loadCampaigns() {
  try { campaigns.value = (await pulseApi.admin.campaigns()).results || []; }
  catch (error) { ui.error(errorText(error, "活动配置加载失败")); }
}
async function submitCampaign() {
  const reward_payload = rewardsFrom(campaignForm);
  if (!Object.keys(reward_payload).length) return ui.error("活动至少需要一种奖励。");
  const startsAt = new Date(campaignForm.starts_at);
  const endsAt = new Date(campaignForm.ends_at);
  if (!Number.isFinite(startsAt.getTime()) || endsAt <= startsAt) return ui.error("请填写有效的活动时间范围。");
  saving.value = true;
  try {
    await pulseApi.admin.createCampaign({
      key: campaignForm.key,
      name: campaignForm.name,
      reward_payload,
      starts_at: startsAt.toISOString(),
      ends_at: endsAt.toISOString(),
    });
    Object.assign(campaignForm, { key: "", name: "", starts_at: "", ends_at: "", reroll: 0, makeup: 0, super_makeup: 0 });
    ui.success("自动领取活动已创建。");
    await loadCampaigns();
  } catch (error) { ui.error(errorText(error, "活动创建失败")); }
  finally { saving.value = false; }
}
async function toggleCampaign(item) {
  try { await pulseApi.admin.updateCampaign(item.id, { is_enabled: !item.is_enabled }); await loadCampaigns(); }
  catch (error) { ui.error(errorText(error, "活动状态更新失败")); }
}
async function loadCodes() {
  try { codes.value = (await pulseApi.admin.codes()).results || []; }
  catch (error) { ui.error(errorText(error, "兑换码加载失败")); }
}
async function submitCode() {
  const reward_payload = rewardsFrom(codeForm);
  if (!Object.keys(reward_payload).length) return ui.error("兑换码至少需要一种奖励。");
  saving.value = true;
  try {
    const result = await pulseApi.admin.createCode({ code: codeForm.code, reward_payload, max_uses: codeForm.max_uses, per_user_limit: codeForm.per_user_limit });
    createdPlainCode.value = result.code;
    codeForm.code = "";
    ui.success("兑换码已创建，请立即保存明文。");
    await loadCodes();
  } catch (error) { ui.error(errorText(error, "兑换码创建失败")); }
  finally { saving.value = false; }
}
async function toggleCode(item) {
  try { await pulseApi.admin.updateCode(item.id, { is_enabled: !item.is_enabled }); await loadCodes(); }
  catch (error) { ui.error(errorText(error, "兑换码状态更新失败")); }
}
async function copyCode() {
  await navigator.clipboard.writeText(createdPlainCode.value);
  ui.success("兑换码已复制。");
}
async function loadEditions() {
  try { editions.value = (await pulseApi.admin.editions()).results || []; }
  catch (error) { ui.error(errorText(error, "每日内容加载失败")); }
}
async function submitEdition() {
  const options = editionForm.options_text.split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
  if (options.length < 2 || options.length > 5) return ui.error("投票选项必须为 2 至 5 个。");
  saving.value = true;
  try {
    await pulseApi.admin.createEdition({ ...editionForm, options, options_text: undefined });
    ui.success("每日内容预设已保存。");
    await loadEditions();
  } catch (error) { ui.error(errorText(error, "每日内容保存失败")); }
  finally { saving.value = false; }
}
async function loadLedger() {
  try { ledger.value = (await pulseApi.admin.ledger()).results || []; }
  catch (error) { ui.error(errorText(error, "资产流水加载失败")); }
}

onMounted(loadBindings);
</script>

<style scoped>
.subsection-head{padding-top:16px;border-top:1px solid var(--hairline)}.subsection-head h3{margin:0 0 5px}
.pulse-manager{display:grid;gap:18px}.manager-head,.panel-head{display:flex;align-items:flex-start;justify-content:space-between;gap:20px}.manager-head h2,.manager-panel h3{margin:3px 0 6px}.manager-kicker{margin:0;color:#b68732;font-size:10px;font-weight:800;letter-spacing:.16em}.manager-tabs{display:flex;flex-wrap:wrap;gap:6px;padding:5px;border:1px solid var(--hairline);border-radius:14px;background:var(--surface-muted)}.manager-tabs button{border:0;border-radius:9px;padding:9px 12px;color:var(--text-soft);background:transparent;font:inherit;cursor:pointer}.manager-tabs button.active{color:#fff;background:#222b3c}.manager-panel{display:grid;gap:16px}.search-row{display:flex;gap:7px}.data-list{display:grid;gap:8px}.data-row{display:grid;grid-template-columns:minmax(0,1fr) auto auto;align-items:center;gap:12px;padding:13px 15px;border:1px solid var(--hairline);border-radius:12px;background:var(--surface-muted)}.data-row p{margin:4px 0 0}.status-pill{padding:5px 8px;border-radius:999px;color:var(--text-soft);background:var(--surface-strong);font-size:10px}.status-pill.active{color:#147754;background:rgba(70,194,141,.12)}.operation-card,.plain-code{display:grid;gap:12px;padding:16px;border:1px solid rgba(205,151,53,.3);border-radius:14px;background:rgba(205,151,53,.05)}.operation-card>div:first-child{display:grid;gap:4px}.operation-card>div:first-child span,.plain-code span{color:#ad7e2b;font-size:9px;letter-spacing:.12em}.operation-actions{display:flex;justify-content:flex-end;gap:8px}.check-row{display:flex!important;align-items:center;gap:8px!important;color:var(--text-soft);font-size:12px}.form-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.form-grid label{display:grid;gap:6px;color:var(--text-soft);font-size:11px}.span-2{grid-column:span 2}.span-3{grid-column:1/-1}.plain-code{grid-template-columns:1fr auto;align-items:center}.plain-code span{grid-column:1/-1}.plain-code strong{font:700 20px ui-monospace,monospace;letter-spacing:.08em}.ledger-table{overflow:hidden;border:1px solid var(--hairline);border-radius:12px}.ledger-head,.ledger-line{display:grid;grid-template-columns:1fr .7fr .5fr .5fr 1.4fr;gap:10px;align-items:center;padding:10px 13px}.ledger-head{color:var(--text-soft);background:var(--surface-muted);font-size:10px}.ledger-line{border-top:1px solid var(--hairline);font-size:11px}.ledger-line strong{color:#19865f}.ledger-line strong.negative{color:#b44e46}.ledger-line small{overflow:hidden;color:var(--text-soft);white-space:nowrap;text-overflow:ellipsis}@media(max-width:760px){.manager-head,.panel-head{display:grid}.search-row{width:100%}.form-grid{grid-template-columns:1fr}.span-2,.span-3{grid-column:1}.data-row{grid-template-columns:1fr auto}.data-row .btn{grid-column:1/-1}.ledger-table{overflow-x:auto}.ledger-head,.ledger-line{min-width:640px}}
</style>

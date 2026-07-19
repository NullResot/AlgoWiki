<template>
  <section class="pulse-page">
    <div class="pulse-noise" aria-hidden="true"></div>
    <header class="pulse-masthead">
      <div class="pulse-brandline">
        <span class="pulse-live-dot"></span>
        <span>MIDNIGHT OBSERVATORY</span>
        <i></i>
        <span>{{ formattedDate }}</span>
        <span class="pulse-demo-badge">LIVE TEST</span>
      </div>
      <div class="pulse-title-row">
        <div>
          <span class="pulse-kicker">ALGO PULSE / 00:00 DAILY REFRESH</span>
          <h1>午夜脉冲剧场</h1>
          <p>每天三束信号，让一次回答、一次训练和一个立场变成你算法星图里的真实光点。</p>
        </div>
        <div class="pulse-summary">
          <div><Transition name="metric-shift" mode="out-in"><strong :key="pulse.progressCount">{{ pulse.progressCount }}/3</strong></Transition><span>今日完成</span></div>
          <div><Transition name="metric-shift" mode="out-in"><strong :key="pulse.state.wallet.point">{{ pulse.state.wallet.point }}</strong></Transition><span>总积分</span></div>
          <div><Transition name="metric-shift" mode="out-in"><strong :key="pulse.state.wallet.reroll">{{ pulse.state.wallet.reroll }}</strong></Transition><span>换签卷</span></div>
        </div>
      </div>
      <nav class="pulse-tabs" aria-label="午夜脉冲视图">
        <button v-for="item in tabs" :key="item.id" :class="{ active: activeTab === item.id }" @click="switchTab(item.id)">
          <span>{{ item.index }}</span>{{ item.label }}
        </button>
        <button class="pulse-reset" type="button" :disabled="pulse.loading" @click="refreshPulse">↻ 同步信号</button>
      </nav>
      <Transition name="signal-result">
        <div v-if="pulse.error" class="pulse-error" role="alert">
          <span>{{ pulse.error.retryable ? "SIGNAL DELAY" : "SIGNAL NOTICE" }}</span>
          <p>{{ pulse.error.message }}</p>
          <button v-if="pulse.error.retryable" type="button" @click="refreshPulse">重新连接</button>
        </div>
      </Transition>
    </header>

    <Transition name="pulse-view" mode="out-in">
      <section v-if="activeTab === 'observatory'" key="observatory" class="observatory" aria-label="今夜观测台">
        <article class="signal-card signal-card--question" :class="{ complete: pulse.state.communityCompleted }" style="--signal-order: 0">
          <div class="signal-index"><span>01</span><i></i><small>{{ pulse.state.communityCompleted ? "SIGNAL LOCKED" : "OPEN SIGNAL" }}</small></div>
          <div class="signal-heading">
            <span>00:00 · 今日讨论</span>
            <h2>{{ dailyQuestion.title }}</h2>
            <p>{{ dailyQuestion.content_md }}</p>
          </div>
          <div class="signal-tags"><span># 算法竞赛</span><span># 今日观点</span><span># 多回答</span></div>
          <div class="question-stats"><span>{{ dailyQuestion.answer_count || dailyQuestion.answers?.length || 0 }} 个回答</span><span>问题长期开放</span></div>

          <div v-if="!pulse.isAuthenticated" class="auth-signal">
            <span>登录后写下你的判断，并获得当天首次回答奖励</span>
            <RouterLink :to="{ name: 'auth' }">登录并回答</RouterLink>
          </div>
          <div v-else class="answer-box">
            <textarea v-model="answerDraft" rows="3" maxlength="1800" placeholder="写下一条判断规则、一个反例，或一次真实的比赛取舍……"></textarea>
            <div>
              <small>{{ answerDraft.length }}/1800 · {{ pulse.state.communityCompleted ? "可以继续补充新的回答" : "首次有效回答获得 1 张换签卷" }}</small>
              <button type="button" :disabled="pulse.activeAction === 'answer'" @click="submitAnswer">{{ pulse.activeAction === "answer" ? "发送中" : "发布观测" }}</button>
            </div>
          </div>
          <div v-if="dailyQuestion.answers?.length" class="answer-preview">
            <article v-for="answer in dailyQuestion.answers.slice(0, 2)" :key="answer.id">
              <strong>{{ answer.author.username }}</strong><p>{{ answer.content_md }}</p>
            </article>
          </div>
        </article>

        <section class="star-stage" style="--signal-order: 1">
          <div class="star-stage__caption star-stage__caption--top"><span>CORE STATUS</span><strong>{{ pulse.isComplete ? "STABLE" : "AWAITING SIGNAL" }}</strong></div>
          <PulseStar
            :progress="pulse.progressCount"
            :question-complete="pulse.state.communityCompleted"
            :challenge-complete="pulse.state.challengeCompleted"
            :poll-complete="pulse.state.pollCompleted"
          />
          <div class="star-stage__legend">
            <span :class="{ active: pulse.state.communityCompleted }"><i class="gold"></i>知识核心</span>
            <span :class="{ active: pulse.state.challengeCompleted }"><i class="cyan"></i>训练轨道</span>
            <span :class="{ active: pulse.state.pollCompleted }"><i class="violet"></i>观点纹理</span>
          </div>
        </section>

        <article class="signal-card signal-card--challenge" :class="{ complete: pulse.state.challengeCompleted }" style="--signal-order: 2">
          <div class="signal-index"><span>02</span><i></i><small>{{ pulse.state.challengeCompleted ? "ORBIT STABLE" : "CHOOSE AN ORBIT" }}</small></div>
          <div class="signal-heading">
            <span>00:00 · 每日挑战</span>
            <h2>今天，你要点亮哪条训练轨道？</h2>
            <p>首次选择后锁定模式；两次换签只能在同一模式中切换。</p>
          </div>

          <Transition name="signal-result" mode="out-in">
            <div v-if="!pulse.isAuthenticated" class="auth-signal auth-signal--challenge">
              <span>登录后绑定 Codeforces，系统才会为你计算真实训练轨道</span>
              <RouterLink :to="{ name: 'auth' }">登录 AlgoWiki</RouterLink>
            </div>

            <div v-else-if="!pulse.state.binding?.is_active" class="binding-panel">
              <div class="binding-panel__head"><span>CODEFORCES IDENTITY</span><strong>先校准你的训练坐标</strong></div>
              <template v-if="pulse.state.pendingVerification && !pulse.bindingCountdown.expired">
                <p>请在 <b>{{ pulse.bindingCountdown.label }}</b> 内重新 AC <a href="https://codeforces.com/problemset/problem/4/A" target="_blank" rel="noopener">CF 4A Watermelon</a>。</p>
                <small>只检查新的公开 AC 提交，不需要密码、API Key 或代码注释。</small>
                <button class="primary-action" type="button" :disabled="pulse.activeAction === 'bind-verify'" @click="verifyBinding">{{ pulse.activeAction === "bind-verify" ? "正在读取提交" : "我已 AC，开始验证" }}</button>
              </template>
              <template v-else>
                <p v-if="pulse.state.isCooling">该 Handle 仍处于转移冷却期，原用户可以直接重新绑定。</p>
                <label><span>Codeforces Handle</span><input v-model.trim="codeforcesHandle" maxlength="24" placeholder="例如 Tourist" /></label>
                <button class="primary-action" type="button" :disabled="pulse.activeAction === 'bind-start'" @click="beginBinding">{{ pulse.activeAction === "bind-start" ? "正在校准" : "生成 10 分钟验证窗口" }}</button>
              </template>
            </div>

            <div v-else-if="!pulse.currentChallenge" class="mode-grid">
              <button class="mode-card mode-card--a" type="button" :disabled="Boolean(pulse.activeAction)" @click="chooseMode('A')">
                <span class="mode-letter">A</span><small>2 TO 5 MIN ENTRY</small><strong>Rating + 300 单题</strong>
                <p>从 {{ pulse.state.binding.handle }} 尚未 AC 的题目中抽取，难度限定 800 至 3500。</p>
                <em>完成 +1 分 <b>选择 A →</b></em>
              </button>
              <button class="mode-card mode-card--b" type="button" :disabled="Boolean(pulse.activeAction)" @click="chooseMode('B')">
                <span class="mode-letter">B</span><small>FULL CONTEST ORBIT</small><strong>按 Rating 抽取整场 VP</strong>
                <p>比赛必须一题未做，完成至少 n-2 题；最晚可延续到次日 04:00。</p>
                <em>完成 +3 分 <b>选择 B →</b></em>
              </button>
            </div>

            <div v-else class="challenge-draw">
              <div class="challenge-draw__top"><span class="challenge-mode">MODE {{ pulse.currentChallenge.mode }}</span><span>已锁定 · 截止 {{ deadlineLabel }}</span></div>
              <div class="challenge-code"><span>{{ challengeView.code }}</span><strong>{{ challengeView.title }}</strong></div>
              <div class="challenge-facts">
                <span v-if="pulse.currentChallenge.mode === 'A'">难度 <strong>{{ challengeView.rating }}</strong></span>
                <span v-else>题目 <strong>{{ challengeView.tasks }}</strong></span>
                <span v-if="pulse.currentChallenge.mode === 'B'">达标 <strong>{{ challengeView.target }}/{{ challengeView.tasks }}</strong></span>
                <span>换签 <strong>{{ pulse.currentChallenge.rerolls_used }}/2</strong></span>
              </div>
              <p>{{ challengeView.note }}</p>
              <div class="signal-tags"><span># {{ pulse.currentChallenge.mode === "A" ? "未 AC" : "整场 VP" }}</span><span># 公开提交验证</span></div>
              <a class="challenge-link" :href="challengeView.url" target="_blank" rel="noopener">在 Codeforces 打开目标 ↗</a>
              <div v-if="pulse.currentChallenge.status !== 'completed'" class="challenge-actions">
                <button class="secondary-action" type="button" :disabled="!pulse.canReroll || Boolean(pulse.activeAction)" @click="rerollChallenge">⌁ 同模式换签</button>
                <button class="primary-action" type="button" :disabled="Boolean(pulse.activeAction)" @click="completeChallenge">{{ pulse.activeAction === "check" ? "读取 Codeforces" : "检测完成状态" }}</button>
              </div>
              <div v-else class="challenge-complete">✓ 训练轨道已稳定 · +{{ pulse.currentChallenge.points_awarded }} 分</div>
            </div>
          </Transition>
        </article>

        <article class="signal-card signal-card--poll" :class="{ complete: pulse.state.pollCompleted }" style="--signal-order: 3">
          <div class="signal-index"><span>03</span><i></i><small>{{ pulse.state.pollCompleted ? "OPINION RECORDED" : "OPEN VOTE" }}</small></div>
          <div class="poll-copy"><span>00:00 · 今日争议</span><h2>{{ dailyPoll.prompt }}</h2><p>选择你更认可的训练方式，投票后查看今天的观点光谱。</p></div>
          <div class="poll-options">
            <button
              v-for="option in pulse.pollResults"
              :key="option.id"
              type="button"
              :class="[`poll-option--${option.tone}`, { selected: dailyPoll.selected_option_id === option.id }]"
              :disabled="pulse.state.pollCompleted || Boolean(pulse.activeAction)"
              @click="vote(option.id)"
            >
              <span><i></i><strong>{{ option.label }}</strong><em v-if="pulse.state.pollCompleted">{{ option.percent }}%</em></span>
              <span v-if="pulse.state.pollCompleted" class="poll-bar"><i :style="{ '--bar-scale': option.percent / 100 }"></i></span>
            </button>
          </div>
        </article>

        <aside class="orbit-log" style="--signal-order: 4">
          <span>PERSONAL ORBIT / TODAY</span>
          <div class="orbit-log__line"><i :style="{ '--bar-scale': pulse.progressCount / 3 }"></i></div>
          <strong>{{ pulse.isComplete ? "今日星图已写入" : `还差 ${3 - pulse.progressCount} 束信号` }}</strong>
          <p>{{ pulse.isComplete ? "明天 00:00 会出现全新的问题、挑战与争议。" : "每完成一项，中心星都会发生一次可见变化。" }}</p>
        </aside>
      </section>

      <PulseAtlasPanel
        v-else-if="activeTab === 'atlas'"
        key="atlas"
        :progress="pulse.progressCount"
        :atlas="pulse.atlas"
        :wallet="pulse.state.wallet"
        :pending-makeup="pulse.state.pendingMakeup"
        class="pulse-view-panel"
        @makeup="createMakeup"
        @redeem="redeemCode"
        @check-makeup="checkMakeup"
      />
      <PulseRankingPanel v-else key="ranking" :entries="pulse.rankings" class="pulse-view-panel" @scope-change="loadRankingScope" />
    </Transition>

    <footer class="pulse-disclaimer"><span>LIVE TEST</span><p>当前页面已经连接本地测试环境的真实账户、积分、道具与 Codeforces 公开接口；所有数据只写入当前隔离测试环境，不会影响正式网站。</p></footer>

    <Transition name="pulse-toast"><div v-if="toastMessage" class="pulse-toast" role="status"><span>✦</span>{{ toastMessage }}</div></Transition>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";

import PulseAtlasPanel from "../components/pulse-demo/PulseAtlasPanel.vue";
import PulseRankingPanel from "../components/pulse-demo/PulseRankingPanel.vue";
import PulseStar from "../components/pulse-demo/PulseStar.vue";
import { useAuthStore } from "../stores/auth";
import { usePulseStore } from "../stores/pulse";

const pulse = usePulseStore();
const auth = useAuthStore();
const activeTab = ref("observatory");
const answerDraft = ref("");
const codeforcesHandle = ref("");
const toastMessage = ref("");
let toastTimer = null;

const tabs = [
  { id: "observatory", index: "01", label: "今夜观测台" },
  { id: "atlas", index: "02", label: "我的星图" },
  { id: "ranking", index: "03", label: "脉冲排行" },
];

const dailyQuestion = computed(() => pulse.state.edition?.question || { title: "正在接收今日话题", content_md: "请稍候。", answers: [] });
const dailyPoll = computed(() => pulse.state.edition?.poll || { prompt: "正在接收今日争议", options: [] });
const formattedDate = computed(() => {
  const value = pulse.state.edition?.date ? new Date(`${pulse.state.edition.date}T00:00:00+08:00`) : new Date();
  return new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit", weekday: "long", timeZone: "Asia/Shanghai" }).format(value);
});
const challengeView = computed(() => {
  const assignment = pulse.currentChallenge;
  const target = assignment?.target || {};
  if (!assignment) return {};
  if (assignment.mode === "A") {
    return {
      code: `CF ${target.contest_id || ""}${target.index || ""}`,
      title: target.name || assignment.target_key,
      rating: target.rating,
      note: `按 Rating ${assignment.rating_snapshot} 抽取，目标档位 ${target.requested_rating || target.rating}。`,
      url: target.url,
    };
  }
  return {
    code: target.name || assignment.target_key,
    title: `${String(target.division || "VP").toUpperCase()} Virtual Participation`,
    tasks: target.problem_count,
    target: target.required_solved,
    note: "该场比赛此前没有任何提交，必须使用 Codeforces Virtual 参赛并完成达标题数。",
    url: target.url,
  };
});
const deadlineLabel = computed(() => {
  const value = pulse.currentChallenge?.deadline_at;
  if (!value) return "次日 04:00";
  return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Asia/Shanghai" }).format(new Date(value));
});

onMounted(async () => {
  await pulse.initialize().catch(() => {});
  codeforcesHandle.value = pulse.state.binding?.handle || "";
});

onBeforeUnmount(() => window.clearTimeout(toastTimer));

function notify(message) {
  toastMessage.value = message;
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => (toastMessage.value = ""), 2600);
}

async function run(action, successMessage) {
  try {
    await action();
    if (successMessage) notify(successMessage);
    return true;
  } catch {
    notify(pulse.error?.message || "信号暂时没有抵达，请稍后重试");
    return false;
  }
}

async function submitAnswer() {
  if (!answerDraft.value.trim()) return notify("先写下一条观察，再发射信号");
  const sent = await run(() => pulse.answerQuestion(answerDraft.value), "回答已发布，知识核心已更新");
  if (sent) answerDraft.value = "";
}

async function beginBinding() {
  if (!codeforcesHandle.value.trim()) return notify("请先输入 Codeforces Handle");
  await run(() => pulse.startBinding(codeforcesHandle.value), "验证窗口已生成，请前往 AC CF 4A");
}

async function verifyBinding() {
  await run(() => pulse.verifyBinding(), "Codeforces 身份校准完成");
}

async function chooseMode(mode) {
  await run(() => pulse.chooseChallenge(mode), `MODE ${mode} 已锁定，今日只能在该模式内换签`);
}

async function rerollChallenge() {
  if (!pulse.canReroll) return notify("今日换签次数或换签卷已用尽");
  await run(() => pulse.rerollChallenge(), `已在 MODE ${pulse.state.challengeMode} 内切换挑战`);
}

async function completeChallenge() {
  await run(() => pulse.checkChallenge(), "Codeforces 完成证据已写入训练轨道");
}

async function createMakeup(targetDate, kind) {
  const message = kind === "super" ? "超级补签已完成，轨迹和 1 积分已写入" : "补签题已生成，请 AC 后回来检测";
  const created = await run(() => pulse.createMakeup(targetDate, kind), message);
  if (created) await pulse.loadAtlas().catch(() => {});
}

async function checkMakeup(assignmentId) {
  const completed = await run(() => pulse.checkAssignment(assignmentId), "补签验证通过，轨迹和 1 积分已写入");
  if (completed) await pulse.loadAtlas().catch(() => {});
}

async function redeemCode(code) {
  const redeemed = await run(() => pulse.redeem(code), "兑换成功，道具已经写入账户");
  if (redeemed) await pulse.loadAtlas().catch(() => {});
}

async function vote(optionId) {
  if (!pulse.isAuthenticated) return notify("登录后才能写入今日立场");
  await run(() => pulse.vote(optionId), "你的立场已写入今日星体纹理");
}

async function refreshPulse() {
  await run(() => pulse.fetchToday(), "信号已与服务器同步");
}

async function switchTab(tab) {
  activeTab.value = tab;
  if (tab === "atlas" && pulse.isAuthenticated) await pulse.loadAtlas().catch(() => {});
  if (tab === "ranking") await pulse.loadRankings().catch(() => {});
}

async function loadRankingScope(scope) {
  if (scope === "rating") {
    const rating = Number(pulse.state.binding?.rating || 0);
    if (!rating) return notify("绑定 Codeforces 后才能查看 Rating 分段榜");
    const lower = Math.floor(rating / 300) * 300;
    await pulse.loadRankings({ rating_min: lower, rating_max: lower + 299 }).catch(() => {});
    return;
  }
  if (scope === "school") {
    const schoolName = auth.user?.school_name;
    if (!schoolName) return notify("个人资料中还没有学校信息");
    await pulse.loadRankings({ school_name: schoolName }).catch(() => {});
    return;
  }
  await pulse.loadRankings().catch(() => {});
}
</script>

<style scoped>
.pulse-page {
  --pulse-gold: #e2b45d;
  --pulse-cyan: #5ccdf4;
  --pulse-violet: #9f86ff;
  position: relative;
  isolation: isolate;
  min-height: calc(100vh - var(--topbar-height, 64px));
  padding: 0 clamp(14px, 3vw, 46px) 40px;
  overflow: hidden;
  color: #d8dce4;
  background:
    radial-gradient(circle at 50% 32%, rgba(54, 75, 110, 0.16), transparent 36%),
    radial-gradient(circle at 8% 55%, rgba(104, 66, 137, 0.08), transparent 28%),
    #090d17;
}

.pulse-noise {
  position: absolute;
  inset: 0;
  z-index: -1;
  pointer-events: none;
  opacity: 0.35;
  background-image:
    radial-gradient(circle at 15% 18%, rgba(255,255,255,.75) 0 1px, transparent 1.4px),
    radial-gradient(circle at 72% 12%, rgba(255,255,255,.5) 0 1px, transparent 1.3px),
    radial-gradient(circle at 88% 44%, rgba(255,255,255,.45) 0 1px, transparent 1.3px),
    radial-gradient(circle at 38% 67%, rgba(255,255,255,.28) 0 1px, transparent 1.3px);
  background-size: 230px 230px, 310px 310px, 270px 270px, 190px 190px;
}

.pulse-masthead { position: relative; max-width: 1480px; margin: 0 auto; padding-top: clamp(24px, 4vw, 54px); }
.pulse-brandline { display: flex; align-items: center; gap: 10px; color: #6f7a8d; font-size: 9px; letter-spacing: .16em; }
.pulse-brandline i { width: 36px; height: 1px; background: #323b4e; }
.pulse-live-dot { width: 6px; height: 6px; border-radius: 50%; background: #e2b45d; box-shadow: 0 0 12px rgba(226,180,93,.8); }
.pulse-demo-badge { margin-left: auto; padding: 5px 8px; border: 1px solid rgba(226,180,93,.25); border-radius: 999px; color: #cda85f; background: rgba(226,180,93,.06); }
.pulse-title-row { display: flex; align-items: flex-end; justify-content: space-between; gap: 30px; padding: clamp(26px, 4vw, 54px) 0 28px; }
.pulse-kicker { color: var(--pulse-gold); font-size: 10px; letter-spacing: .21em; }
.pulse-title-row h1 { margin: 9px 0 12px; color: #f2f0e9; font: 600 clamp(40px, 6vw, 74px)/.98 Georgia, "Songti SC", serif; letter-spacing: -.045em; }
.pulse-title-row p { max-width: 720px; margin: 0; color: #8f9aab; font-size: 13px; line-height: 1.7; }
.pulse-summary { display: flex; min-width: 310px; border: 1px solid rgba(255,255,255,.075); border-radius: 16px; background: rgba(255,255,255,.025); }
.pulse-summary div { flex: 1; display: grid; justify-items: center; gap: 4px; padding: 15px 12px; border-right: 1px solid rgba(255,255,255,.06); }
.pulse-summary div:last-child { border-right: 0; }
.pulse-summary strong { color: #f2c36b; font: 600 23px/1 Georgia,serif; }
.pulse-summary span { color: #667286; font-size: 9px; }
.pulse-tabs { display: flex; align-items: center; gap: 5px; padding: 5px; border-top: 1px solid rgba(255,255,255,.07); border-bottom: 1px solid rgba(255,255,255,.07); }
.pulse-tabs button { display: inline-flex; align-items: center; gap: 10px; border: 0; padding: 11px 16px; border-radius: 9px; color: #778297; background: transparent; font: inherit; font-size: 11px; cursor: pointer; transition: color .18s ease, background-color .18s ease, transform .18s cubic-bezier(.2,.8,.2,1); }
.pulse-tabs button span { color: #465164; font: 700 9px Georgia,serif; }
.pulse-tabs button.active { color: #eee9df; background: rgba(255,255,255,.055); }
.pulse-tabs button.active span { color: var(--pulse-gold); }
.pulse-tabs .pulse-reset { margin-left: auto; color: #6e798b; }
.pulse-tabs button:hover { color:#f0ede6; background:rgba(255,255,255,.045); }
.pulse-tabs button:active { transform:scale(.97); }
.pulse-tabs button:disabled { opacity:.45; cursor:wait; }
.pulse-error { position:absolute; z-index:8; right:0; bottom:-48px; display:flex; align-items:center; gap:10px; max-width:min(560px,90vw); padding:9px 11px; border:1px solid rgba(244,170,92,.28); border-radius:10px; color:#d9dee7; background:rgba(18,23,36,.97); box-shadow:0 14px 34px rgba(0,0,0,.26); }
.pulse-error span { color:#e6b45d; font-size:8px; letter-spacing:.13em; white-space:nowrap; }.pulse-error p { margin:0; color:#9aa5b7; font-size:9px; }.pulse-error button { border:0; border-radius:7px; padding:6px 8px; color:#171b25; background:#e2b45d; font-size:8px; font-weight:800; cursor:pointer; }

.observatory { max-width: 1480px; margin: 0 auto; padding: clamp(24px, 3vw, 42px) 0; display: grid; grid-template-columns: minmax(280px, 1fr) minmax(330px, .92fr) minmax(300px, 1fr); grid-template-areas: "question star challenge" "poll poll orbit"; gap: clamp(14px, 1.5vw, 22px); align-items: stretch; }
.observatory > .signal-card,
.observatory > .star-stage,
.observatory > .orbit-log { animation:signal-arrive .34s cubic-bezier(.2,.8,.2,1) both; animation-delay:calc(var(--signal-order, 0) * 45ms); }
.signal-card, .orbit-log { position: relative; overflow: hidden; border: 1px solid rgba(255,255,255,.075); border-radius: 20px; background: linear-gradient(145deg, rgba(19,24,38,.92), rgba(10,14,25,.92)); box-shadow: 0 24px 70px rgba(0,0,0,.12); }
.signal-card { padding: clamp(20px, 2.2vw, 30px); }
.signal-card::after { content:""; position:absolute; inset:0; pointer-events:none; opacity:0; background:linear-gradient(120deg,rgba(95,216,167,.07),transparent 50%); transition: opacity .3s; }
.signal-card.complete::after { opacity:1; }
.signal-card--question { grid-area: question; }
.signal-card--challenge { grid-area: challenge; }
.signal-card--poll { grid-area: poll; display: grid; grid-template-columns: 130px minmax(230px,.72fr) minmax(360px,1.28fr); gap: 24px; align-items: center; }
.signal-index { display: flex; align-items: center; gap: 9px; margin-bottom: 21px; }
.signal-index > span { color: #4f5a6c; font: 700 12px Georgia,serif; }
.signal-index i { width: 24px; height: 1px; background: #374153; }
.signal-index small { color: #6c788b; font-size: 8px; letter-spacing: .15em; }
.complete .signal-index small { color: #64cda2; }
.signal-heading > span, .poll-copy > span { color: var(--pulse-gold); font-size: 9px; letter-spacing: .15em; }
.signal-heading h2, .poll-copy h2 { margin: 9px 0 12px; color: #efede7; font: 600 clamp(21px,2.1vw,30px)/1.22 Georgia,"Songti SC",serif; }
.signal-heading p, .poll-copy p { margin: 0; color: #8994a6; font-size: 11px; line-height: 1.75; }
.signal-tags { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 16px; }
.signal-tags span { padding: 5px 8px; border-radius: 999px; color: #7b879b; background: rgba(255,255,255,.035); font-size: 9px; }
.question-stats { display: flex; gap: 14px; margin: 19px 0 9px; color: #667286; font-size: 9px; }
.answer-box { overflow: hidden; border: 1px solid rgba(255,255,255,.08); border-radius: 13px; background: rgba(0,0,0,.13); }
.answer-box textarea { width: 100%; resize: none; border: 0; outline: 0; padding: 13px; color: #dce0e6; background: transparent; font: inherit; font-size: 11px; line-height: 1.6; }
.answer-box textarea::placeholder { color: #505b6e; }
.answer-box > div { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 8px 8px 8px 12px; border-top: 1px solid rgba(255,255,255,.06); }
.answer-box small { color: #5f6a7c; font-size: 8px; }
.answer-box button, .primary-action { border: 0; border-radius: 8px; padding: 9px 12px; color: #171b25; background: var(--pulse-gold); font: inherit; font-size: 10px; font-weight: 800; cursor: pointer; }
.answer-box button:disabled,.primary-action:disabled { opacity:.45; cursor:wait; }
.answer-preview { display:grid; gap:6px; margin-top:8px; }
.answer-preview article { min-width:0; padding:8px 10px; border-left:2px solid rgba(226,180,93,.34); border-radius:0 8px 8px 0; background:rgba(255,255,255,.018); }
.answer-preview strong { color:#aeb8c7; font-size:8px; }.answer-preview p { overflow:hidden; margin:3px 0 0; color:#737f92; font-size:8px; line-height:1.45; white-space:nowrap; text-overflow:ellipsis; }
.auth-signal { display:flex; align-items:center; justify-content:space-between; gap:14px; margin-top:18px; padding:14px; border:1px solid rgba(226,180,93,.16); border-radius:12px; color:#8490a2; background:rgba(226,180,93,.035); font-size:9px; line-height:1.5; }
.auth-signal a { flex:0 0 auto; padding:8px 10px; border-radius:8px; color:#181d28; background:#e2b45d; text-decoration:none; font-weight:800; }
.auth-signal--challenge { display:grid; }
.answer-complete { margin-top: 18px; padding: 15px; border: 1px solid rgba(94,206,159,.18); border-radius: 13px; background: rgba(94,206,159,.055); }
.answer-complete span { color: #69d5a9; font-size: 10px; font-weight: 750; }
.answer-complete p { margin: 10px 0; color: #cbd2d8; font-size: 11px; line-height: 1.6; }
.answer-complete small { color: #647185; font-size: 8px; }

.star-stage { grid-area: star; position: relative; min-height: 510px; display: grid; place-items: center; overflow: hidden; border: 1px solid rgba(255,255,255,.06); border-radius: 20px; background: radial-gradient(circle,rgba(65,79,111,.12),transparent 60%); }
.star-stage__caption { position:absolute; top:21px; left:22px; display:grid; gap:4px; z-index:2; }
.star-stage__caption span { color:#566175; font-size:8px; letter-spacing:.16em; }
.star-stage__caption strong { color:#9aa5b5; font-size:9px; }
.star-stage__legend { position:absolute; bottom:18px; left:50%; transform:translateX(-50%); display:flex; gap:12px; white-space:nowrap; }
.star-stage__legend span { display:flex; align-items:center; gap:5px; color:#536074; font-size:8px; }
.star-stage__legend span.active { color:#c9d0d9; }
.star-stage__legend i { width:5px; height:5px; border-radius:50%; background:#455065; }
.star-stage__legend .gold { background:#dfae54; }.star-stage__legend .cyan { background:#50c7f3; }.star-stage__legend .violet { background:#987bf3; }

.mode-grid { display: grid; gap: 9px; margin-top: 20px; }
.mode-card { position: relative; display: grid; grid-template-columns: auto 1fr; gap: 4px 12px; width: 100%; padding: 15px; border: 1px solid rgba(255,255,255,.075); border-radius: 13px; color: #cfd4dc; background: rgba(255,255,255,.018); text-align: left; cursor: pointer; }
.mode-card:hover { border-color: rgba(226,180,93,.36); background: rgba(226,180,93,.04); }
.mode-letter { grid-row: 1 / 5; width: 36px; height: 36px; display:grid; place-items:center; border-radius:50%; color:#171b24; background:#dcb05b; font:700 15px Georgia,serif; }
.mode-card small { color:#5d687b; font-size:7px; letter-spacing:.12em; }
.mode-card strong { color:#e8e6df; font-size:12px; }
.mode-card p { margin:3px 0; color:#7c8799; font-size:9px; line-height:1.55; }
.mode-card em { display:flex; justify-content:space-between; color:#b9c0ca; font-size:9px; font-style:normal; }.mode-card b { color:#dcb05b; }
.mode-card--b .mode-letter { background:#63c9ed; }
.mode-card--b b { color:#63c9ed; }
.binding-panel { display:grid; gap:11px; margin-top:17px; padding:15px; border:1px solid rgba(92,205,244,.16); border-radius:14px; background:linear-gradient(145deg,rgba(92,205,244,.045),rgba(255,255,255,.012)); }
.binding-panel__head { display:grid; gap:4px; }.binding-panel__head span { color:#57c8ef; font-size:7px; letter-spacing:.15em; }.binding-panel__head strong { color:#e8e9e6; font:600 17px Georgia,"Songti SC",serif; }
.binding-panel p { margin:0; color:#8b96a8; font-size:9px; line-height:1.65; }.binding-panel p b { color:#f0c46b; font:600 14px Georgia,serif; }.binding-panel p a { color:#69d4f6; }.binding-panel > small { color:#606d81; font-size:8px; line-height:1.5; }
.binding-panel label { display:grid; gap:6px; color:#697589; font-size:8px; }.binding-panel input { width:100%; border:1px solid rgba(255,255,255,.1); border-radius:9px; outline:0; padding:10px 11px; color:#edf0f3; background:rgba(0,0,0,.18); font:inherit; font-size:11px; }.binding-panel input:focus { border-color:rgba(92,205,244,.5); box-shadow:0 0 0 3px rgba(92,205,244,.07); }
.challenge-draw { margin-top: 20px; }
.challenge-draw__top { display:flex; justify-content:space-between; gap:10px; color:#657085; font-size:8px; }
.challenge-mode { color:#60ccec; letter-spacing:.12em; }
.challenge-code { display:grid; gap:6px; padding:20px 0 15px; border-bottom:1px solid rgba(255,255,255,.06); }
.challenge-code span { color:#d9ae5d; font-size:10px; }.challenge-code strong { color:#eff0eb; font:600 21px/1.15 Georgia,serif; }
.challenge-facts { display:flex; gap:9px; margin:13px 0; }.challenge-facts span { padding:7px 9px; border-radius:8px; color:#6f7b8e; background:rgba(255,255,255,.035); font-size:8px; }.challenge-facts strong { color:#cfd5dd; }
.challenge-draw > p { margin:0; color:#7f8a9c; font-size:9px; line-height:1.6; }
.challenge-link { display:inline-flex; margin-top:10px; color:#62cdef; font-size:9px; text-decoration:none; }.challenge-link:hover { color:#9ae4ff; }
.challenge-actions { display:grid; grid-template-columns:1fr 1.25fr; gap:8px; margin-top:17px; }
.secondary-action { border:1px solid rgba(255,255,255,.1); border-radius:8px; color:#9ca6b5; background:transparent; font:inherit; font-size:9px; cursor:pointer; }.secondary-action:disabled { opacity:.35; cursor:not-allowed; }
.challenge-complete { margin-top:17px; padding:12px; border-radius:10px; color:#6bd5aa; background:rgba(92,205,159,.08); font-size:10px; text-align:center; }

.signal-card--poll .signal-index { margin:0; }
.poll-copy h2 { font-size:25px; }
.poll-options { display:grid; gap:8px; }
.poll-options button { display:grid; gap:7px; width:100%; padding:11px 13px; border:1px solid rgba(255,255,255,.075); border-radius:10px; color:#c8ced7; background:rgba(255,255,255,.02); font:inherit; font-size:10px; text-align:left; cursor:pointer; }
.poll-options button:disabled { cursor:default; }
.poll-options button > span:first-child { display:flex; align-items:center; gap:9px; }
.poll-options button > span:first-child i { width:8px; height:8px; border:1px solid #596577; border-radius:50%; }
.poll-options button strong { flex:1; font-weight:600; }
.poll-options button em { color:#d7dce3; font-style:normal; font:600 13px Georgia,serif; }
.poll-options button.selected { border-color:rgba(159,134,255,.4); background:rgba(159,134,255,.07); }
.poll-options button.selected > span:first-child i { border-color:#a68eff; background:#a68eff; box-shadow:0 0 9px rgba(166,142,255,.65); }
.poll-bar { height:2px; overflow:hidden; border-radius:2px; background:rgba(255,255,255,.05); }.poll-bar i { display:block; width:100%; height:100%; background:#9c82f5; transform:scaleX(var(--bar-scale, 0)); transform-origin:left; transition:transform .5s cubic-bezier(.2,.8,.2,1); }
.poll-option--cyan .poll-bar i { background:#59c8ef; }.poll-option--gold .poll-bar i { background:#dcb05b; }

.orbit-log { grid-area: orbit; display:grid; align-content:center; gap:9px; padding:24px; }
.orbit-log > span { color:#5f6a7c; font-size:8px; letter-spacing:.15em; }
.orbit-log__line { height:2px; overflow:hidden; background:rgba(255,255,255,.06); }.orbit-log__line i { display:block; width:100%; height:100%; background:linear-gradient(90deg,#e2b45d,#62ceef,#9f86ff); box-shadow:0 0 9px rgba(98,206,239,.5); transform:scaleX(var(--bar-scale, 0)); transform-origin:left; transition:transform .45s cubic-bezier(.2,.8,.2,1); }
.orbit-log strong { color:#e8e7e2; font:600 20px Georgia,serif; }.orbit-log p { margin:0; color:#6f7a8c; font-size:9px; }

.pulse-view-panel { max-width: 1480px; margin: clamp(24px,3vw,42px) auto; }
.pulse-view-enter-active { transition:opacity .28s ease, transform .32s cubic-bezier(.2,.8,.2,1); }
.pulse-view-leave-active { transition:opacity .14s ease, transform .14s ease; }
.pulse-view-enter-from { opacity:0; transform:translateY(8px) scale(.992); }
.pulse-view-leave-to { opacity:0; transform:translateY(-4px) scale(.996); }
.metric-shift-enter-active,.metric-shift-leave-active { transition:opacity .16s ease, transform .2s cubic-bezier(.2,.8,.2,1); }
.metric-shift-enter-from { opacity:0; transform:translateY(5px) scale(.96); }
.metric-shift-leave-to { opacity:0; transform:translateY(-4px) scale(.98); }
.signal-result-enter-active { transition:opacity .2s ease, transform .26s cubic-bezier(.2,.8,.2,1); }
.signal-result-leave-active { transition:opacity .13s ease, transform .13s ease; }
.signal-result-enter-from { opacity:0; transform:translateY(7px) scale(.99); }
.signal-result-leave-to { opacity:0; transform:translateY(-3px); }
.pulse-disclaimer { max-width:1480px; margin:0 auto; display:flex; align-items:flex-start; gap:16px; padding:17px 0 0; border-top:1px solid rgba(255,255,255,.06); color:#5f6a7d; font-size:9px; }
.pulse-disclaimer span { color:#c69f56; letter-spacing:.16em; white-space:nowrap; }.pulse-disclaimer p { margin:0; line-height:1.6; }
.pulse-toast { position:fixed; z-index:40; right:24px; bottom:24px; display:flex; align-items:center; gap:9px; padding:13px 16px; border:1px solid rgba(226,180,93,.3); border-radius:12px; color:#ebe7dc; background:rgba(18,23,35,.96); box-shadow:0 18px 45px rgba(0,0,0,.35); font-size:11px; }.pulse-toast span { color:#e2b45d; }
.pulse-toast-enter-active { transition:opacity .22s ease, transform .26s cubic-bezier(.2,.8,.2,1); }.pulse-toast-leave-active { transition:opacity .14s ease, transform .14s ease; }.pulse-toast-enter-from,.pulse-toast-leave-to { opacity:0; transform:translateY(10px) scale(.98); }

.mode-card,
.poll-options button,
.answer-box button,
.primary-action,
.secondary-action { transition:border-color .18s ease, background-color .18s ease, color .18s ease, opacity .18s ease, transform .18s cubic-bezier(.2,.8,.2,1); }
.mode-card:hover,
.poll-options button:not(:disabled):hover,
.secondary-action:not(:disabled):hover { transform:translateY(-1px); }
.mode-card:active,
.poll-options button:not(:disabled):active,
.answer-box button:active,
.primary-action:active,
.secondary-action:not(:disabled):active { transform:scale(.97); }

@keyframes signal-arrive {
  from { opacity:0; transform:translateY(8px) scale(.992); }
  to { opacity:1; transform:translateY(0) scale(1); }
}

@media (max-width: 1120px) {
  .observatory { grid-template-columns: 1fr 1fr; grid-template-areas:"star star" "question challenge" "poll poll" "orbit orbit"; }
  .star-stage { min-height:430px; }.signal-card--poll { grid-template-columns:100px minmax(220px,.8fr) 1.2fr; }
}

@media (min-width: 1121px) {
  .pulse-page {
    width: 100%;
    height: 100%;
    min-height: 0;
    display: grid;
    grid-template-rows: auto minmax(0, 1fr) auto;
    padding: 0 clamp(16px, 2.2vw, 32px) 8px;
    overflow: hidden;
  }

  .pulse-masthead {
    width: 100%;
    padding-top: 12px;
  }

  .pulse-title-row {
    gap: 24px;
    padding: 12px 0;
  }

  .pulse-title-row h1 {
    margin: 5px 0 7px;
    font-size: clamp(40px, 3.3vw, 58px);
  }

  .pulse-title-row p {
    font-size: 11px;
    line-height: 1.5;
  }

  .pulse-summary {
    min-width: 270px;
  }

  .pulse-summary div {
    padding: 9px 10px;
  }

  .pulse-summary strong {
    font-size: 20px;
  }

  .pulse-tabs button {
    padding: 7px 13px;
  }

  .observatory {
    width: 100%;
    height: 100%;
    min-height: 0;
    grid-template-rows: minmax(0, 1fr) 112px;
    padding: 10px 0 8px;
    gap: 12px;
  }

  .signal-card {
    min-height: 0;
    padding: clamp(16px, 1.35vw, 22px);
  }

  .signal-index {
    margin-bottom: 12px;
  }

  .signal-heading h2,
  .poll-copy h2 {
    margin: 6px 0 8px;
    font-size: clamp(19px, 1.6vw, 26px);
  }

  .signal-heading p,
  .poll-copy p {
    font-size: 10px;
    line-height: 1.55;
  }

  .signal-tags {
    margin-top: 10px;
  }

  .question-stats {
    margin: 11px 0 7px;
  }

  .answer-box textarea {
    min-height: 64px;
    padding: 10px 12px;
  }

  .star-stage {
    height: auto;
    min-height: 0;
  }

  .star-stage :deep(.pulse-star) {
    --star-size: min(36vh, 360px);
  }

  .star-stage__caption {
    top: 16px;
    left: 18px;
  }

  .star-stage__legend {
    bottom: 12px;
  }

  .mode-grid,
  .challenge-draw {
    margin-top: 12px;
  }

  .mode-card {
    padding: 11px 12px;
  }

  .challenge-code {
    padding: 12px 0 10px;
  }

  .challenge-facts {
    margin: 9px 0;
  }

  .signal-card--poll {
    grid-template-columns: 88px minmax(210px, .72fr) minmax(0, 1.5fr);
    gap: 16px;
    padding-block: 14px;
  }

  .poll-copy h2 {
    font-size: 19px;
  }

  .poll-copy p {
    display: none;
  }

  .poll-options {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 7px;
  }

  .poll-options button {
    align-content: center;
    min-height: 52px;
    padding: 8px 10px;
  }

  .orbit-log {
    gap: 6px;
    padding: 15px 18px;
  }

  .orbit-log strong {
    font-size: 17px;
  }

  .pulse-view-panel {
    width: 100%;
    height: calc(100% - 16px);
    min-height: 0;
    margin: 8px auto;
  }

  .pulse-disclaimer {
    width: 100%;
    min-height: 22px;
    padding-top: 6px;
  }
}

@media (min-width: 1121px) and (max-height: 800px) {
  .pulse-brandline,
  .pulse-title-row p {
    display: none;
  }

  .pulse-masthead {
    padding-top: 6px;
  }

  .pulse-title-row {
    padding: 6px 0;
  }

  .pulse-title-row h1 {
    margin-block: 3px;
    font-size: 38px;
  }

  .pulse-tabs button {
    padding-block: 6px;
  }

  .observatory {
    grid-template-rows: minmax(0, 1fr) 96px;
    padding-top: 8px;
  }

  .signal-card {
    padding: 14px;
  }

  .signal-index {
    margin-bottom: 8px;
  }

  .signal-heading h2 {
    font-size: 19px;
  }

  .signal-heading p {
    display: none;
  }

  .signal-tags {
    margin-top: 7px;
  }

  .question-stats {
    margin-block: 7px;
  }

  .mode-grid {
    gap: 6px;
    margin-top: 8px;
  }

  .mode-card p {
    display: none;
  }

  .pulse-disclaimer p {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: clip;
  }
}

@media (max-width: 760px) {
  .pulse-page { padding-inline:10px; }.pulse-title-row { display:grid; }.pulse-summary { min-width:0; width:100%; }.pulse-tabs { overflow-x:auto; }.pulse-tabs button { flex:0 0 auto; }.pulse-tabs .pulse-reset { margin-left:0; }
  .observatory { grid-template-columns:1fr; grid-template-areas:"star" "question" "challenge" "poll" "orbit"; }
  .signal-card--poll { grid-template-columns:1fr; }.signal-card--poll .signal-index { margin-bottom:0; }.star-stage { min-height:370px; }.star-stage__legend { bottom:10px; }
}

@media (max-width: 480px) {
  .pulse-brandline > span:nth-of-type(2), .pulse-brandline i { display:none; }.pulse-title-row h1 { font-size:42px; }.pulse-title-row p { font-size:11px; }.pulse-summary div { padding:12px 8px; }
  .pulse-tabs button { padding:10px; }.pulse-tabs button span { display:none; }.pulse-reset { font-size:0 !important; }.pulse-reset::after { content:"↺"; font-size:13px; }
  .signal-card { padding:20px 17px; border-radius:17px; }.star-stage { min-height:330px; }.star-stage__legend { gap:7px; }.challenge-actions { grid-template-columns:1fr; }.poll-copy h2 { font-size:22px; }
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    scroll-behavior:auto !important;
    animation-duration:.01ms !important;
    animation-iteration-count:1 !important;
    transition-duration:.01ms !important;
  }

  .pulse-view-enter-active,
  .pulse-view-leave-active,
  .metric-shift-enter-active,
  .metric-shift-leave-active,
  .signal-result-enter-active,
  .signal-result-leave-active,
  .pulse-toast-enter-active,
  .pulse-toast-leave-active {
    transition:opacity .12s linear !important;
  }

  .pulse-view-enter-from,
  .pulse-view-leave-to,
  .metric-shift-enter-from,
  .metric-shift-leave-to,
  .signal-result-enter-from,
  .signal-result-leave-to,
  .pulse-toast-enter-from,
  .pulse-toast-leave-to {
    transform:none;
  }
}
</style>

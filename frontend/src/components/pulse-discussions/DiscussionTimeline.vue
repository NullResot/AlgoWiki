<template>
  <div class="discussion-timeline" lang="zh-CN">
    <RouterLink
      v-for="item in items"
      :key="item.id"
      :to="{ name: 'pulse-discussion-detail', params: { date: item.date } }"
      class="discussion-row"
    >
      <div class="date-rail" aria-hidden="true">
        <span>{{ monthDay(item.date) }}</span>
        <i></i>
      </div>
      <article>
        <div class="row-meta">
          <span>{{ sourceLabel(item.source_type) }}</span>
          <time :datetime="item.date">{{ item.date }}</time>
        </div>
        <h2>{{ item.title }}</h2>
        <p>{{ item.content_md }}</p>
        <footer>
          <span>{{ item.answer_count }} 个回答</span>
          <span v-if="item.last_answer_at">最近回应 {{ formatTime(item.last_answer_at) }}</span>
          <strong>进入讨论</strong>
        </footer>
      </article>
    </RouterLink>
    <div v-if="!items.length" class="empty-state">
      <span>NO SIGNAL</span>
      <h2>还没有匹配的讨论</h2>
      <p>换一个关键词，或提交一个值得在午夜点亮的话题。</p>
    </div>
  </div>
</template>

<script setup>
defineProps({ items: { type: Array, default: () => [] } });

function monthDay(value) {
  const [, month = "", day = ""] = String(value || "").split("-");
  return `${month}.${day}`;
}

function sourceLabel(value) {
  return { hot: "社区热议", admin: "编辑精选", random: "午夜抽题" }[value] || "每日讨论";
}

function formatTime(value) {
  if (!value) return "";
  return new Intl.DateTimeFormat("zh-CN", { month: "short", day: "numeric" }).format(new Date(value));
}
</script>

<style scoped>
.discussion-timeline { display: grid; }
.discussion-row { display: grid; grid-template-columns: 92px minmax(0, 1fr); color: inherit; text-decoration: none; }
.date-rail { position: relative; display: grid; justify-items: center; align-content: start; padding-top: 32px; color: var(--text-muted, #778398); font: 600 12px/1.2 ui-monospace, monospace; letter-spacing: .08em; }
.date-rail::after { content: ""; position: absolute; top: 58px; bottom: 0; width: 1px; background: linear-gradient(rgba(204,168,95,.5), rgba(75,198,220,.12)); }
.date-rail i { z-index: 1; width: 11px; height: 11px; margin-top: 15px; border: 2px solid #d5b36d; border-radius: 50%; background: #071117; box-shadow: 0 0 22px rgba(213,179,109,.48); }
.discussion-row article { margin-bottom: 16px; padding: 28px 30px 25px; border: 1px solid rgba(157,194,193,.15); border-radius: 22px; background: linear-gradient(135deg, rgba(18,39,42,.78), rgba(11,17,29,.9) 55%, rgba(37,25,48,.72)); box-shadow: inset 0 1px rgba(255,255,255,.035), 0 18px 50px rgba(0,0,0,.16); transition: transform 200ms ease, border-color 200ms ease, box-shadow 200ms ease; }
.discussion-row:hover article { transform: translateY(-2px); border-color: rgba(213,179,109,.34); box-shadow: inset 0 1px rgba(255,255,255,.05), 0 24px 60px rgba(0,0,0,.24); }
.row-meta, footer { display: flex; align-items: center; gap: 16px; color: var(--text-muted, #82909e); font-size: 12px; }
.row-meta span { color: #d5b36d; letter-spacing: .12em; }
h2 { margin: 13px 0 10px; color: var(--text-primary, #f3f0e7); font: 600 clamp(22px, 2vw, 30px)/1.35 Georgia, "Songti SC", serif; }
p { margin: 0; color: var(--text-secondary, #a8b1bc); font-size: 15px; line-height: 1.8; display: -webkit-box; overflow: hidden; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
footer { margin-top: 22px; padding-top: 17px; border-top: 1px solid rgba(255,255,255,.06); }
footer strong { margin-left: auto; color: #d8bd83; font-weight: 600; }
.empty-state { margin-left: 92px; padding: 64px 30px; border: 1px dashed rgba(157,194,193,.2); border-radius: 22px; text-align: center; color: var(--text-muted, #81909a); }
.empty-state span { color: #d5b36d; font: 600 11px ui-monospace, monospace; letter-spacing: .18em; }
.empty-state h2 { margin-bottom: 8px; }
@media (max-width: 700px) { .discussion-row { grid-template-columns: 58px minmax(0,1fr); } .discussion-row article { padding: 22px 19px; } .date-rail { font-size: 10px; } .empty-state { margin-left: 58px; } footer span:nth-child(2) { display: none; } }
</style>

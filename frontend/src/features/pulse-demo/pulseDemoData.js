export const pulseQuestion = {
  eyebrow: "00:00 · 今日讨论",
  title: "竞赛代码，到底应不应该为可读性牺牲一点速度？",
  prompt:
    "当常数优化和表达清晰发生冲突时，你会把界线画在哪里？可以讲一次比赛中的真实取舍，也可以给出一条自己的判断规则。",
  tags: ["代码风格", "性能边界", "竞赛经验"],
  answerCount: 47,
  watchers: 128,
};

export const challengePools = {
  A: [
    {
      id: "cf-1914-f",
      code: "CF 1914F",
      title: "Programming Competition",
      rating: 1900,
      tags: ["树形 DP", "贪心"],
      note: "基于绑定账号 Rating 1600，抽取 Rating + 300 且尚未 AC 的题目。",
    },
    {
      id: "cf-1798-c",
      code: "CF 1798C",
      title: "Candy Store",
      rating: 1900,
      tags: ["数论", "贪心"],
      note: "同一 A 模式内换签，难度规则保持不变。",
    },
    {
      id: "cf-1942-d",
      code: "CF 1942D",
      title: "Learning to Paint",
      rating: 1900,
      tags: ["优先队列", "DP"],
      note: "第二次换签仍只会出现未 AC 的同档题目。",
    },
  ],
  B: [
    {
      id: "cf-round-918-div4",
      code: "Codeforces Round 918",
      title: "Div. 4 Virtual Participation",
      rating: "≤ 1400",
      tasks: 7,
      target: 5,
      tags: ["整场 VP", "未参赛"],
      note: "该场比赛没有历史提交；完成至少 n-2，即 5/7 题后计为完成。",
    },
    {
      id: "cf-round-927-div3",
      code: "Codeforces Round 927",
      title: "Div. 3 Virtual Participation",
      rating: "≤ 1400",
      tasks: 7,
      target: 5,
      tags: ["整场 VP", "未参赛"],
      note: "同一 B 模式内换签；任务可跨午夜，最晚延续到次日 04:00。",
    },
    {
      id: "cf-round-923-div3",
      code: "Codeforces Round 923",
      title: "Div. 3 Virtual Participation",
      rating: "≤ 1400",
      tasks: 7,
      target: 5,
      tags: ["整场 VP", "未参赛"],
      note: "第二次换签仍遵守 Rating 段与整场未做过的约束。",
    },
  ],
};

export const pulsePoll = {
  eyebrow: "00:00 · 今日争议",
  title: "赛后补题，应该先看官方题解吗？",
  description: "选择你更认可的训练方式，投票后查看今天的观点光谱。",
  totalVotes: 684,
  options: [
    { id: "readability", label: "先独立想够 60 分钟", votes: 287, tone: "violet" },
    { id: "editorial", label: "卡住 20 分钟就看题解", votes: 214, tone: "cyan" },
    { id: "speed", label: "按题目难度动态决定", votes: 183, tone: "gold" },
  ],
};

export const atlasDays = [
  { day: 1, level: 3 },
  { day: 2, level: 2 },
  { day: 3, level: 3 },
  { day: 4, level: 1 },
  { day: 5, level: 0 },
  { day: 6, level: 2, repaired: true },
  { day: 7, level: 3 },
  { day: 8, level: 2 },
  { day: 9, level: 3 },
  { day: 10, level: 3 },
  { day: 11, level: 1 },
  { day: 12, level: 0 },
  { day: 13, level: 3, superRepaired: true },
  { day: 14, level: 2 },
  { day: 15, level: 3 },
  { day: 16, level: 1 },
  { day: 17, level: 3 },
  { day: 18, level: 2 },
  { day: 19, level: 0, today: true },
  ...Array.from({ length: 12 }, (_, index) => ({ day: index + 20, level: 0, future: true })),
];

export const rankingData = {
  monthly: {
    global: [
      { rank: 1, name: "tourist_neo", meta: "连续训练 19 天", score: 43, trend: "+2" },
      { rank: 2, name: "Aurora", meta: "社区连续 16 天", score: 41, trend: "—" },
      { rank: 2, name: "Null_Resot", meta: "完成 8 次 VP", score: 41, trend: "+4" },
      { rank: 4, name: "bitmask_cat", meta: "本月 17 颗星", score: 38, trend: "-1" },
      { rank: 12, name: "你", meta: "Rating 1600 · Demo", score: 26, trend: "+7", self: true },
    ],
    rating: [
      { rank: 1, name: "dp_on_tree", meta: "Rating 1598", score: 34, trend: "+1" },
      { rank: 2, name: "你", meta: "Rating 1600 · Demo", score: 26, trend: "+3", self: true },
      { rank: 3, name: "greedy_moon", meta: "Rating 1512", score: 25, trend: "—" },
      { rank: 4, name: "matrix404", meta: "Rating 1681", score: 23, trend: "+2" },
    ],
    school: [
      { rank: 1, name: "星海大学", meta: "143 位活跃成员", score: 428, trend: "+1" },
      { rank: 2, name: "北辰理工", meta: "118 位活跃成员", score: 401, trend: "—" },
      { rank: 3, name: "云川学院", meta: "96 位活跃成员", score: 376, trend: "+2" },
      { rank: 8, name: "你的学校", meta: "52 位活跃成员", score: 214, trend: "+3", self: true },
    ],
  },
  lifetime: {
    global: [
      { rank: 1, name: "tourist_neo", meta: "总完成 486 天", score: 1218, trend: "—" },
      { rank: 2, name: "Null_Resot", meta: "总完成 402 天", score: 1094, trend: "+1" },
      { rank: 3, name: "Aurora", meta: "总完成 391 天", score: 1067, trend: "-1" },
      { rank: 87, name: "你", meta: "总完成 48 天 · Demo", score: 126, trend: "+8", self: true },
    ],
    rating: [
      { rank: 1, name: "dp_on_tree", meta: "Rating 1598", score: 612, trend: "—" },
      { rank: 18, name: "你", meta: "Rating 1600 · Demo", score: 126, trend: "+2", self: true },
      { rank: 19, name: "greedy_moon", meta: "Rating 1512", score: 119, trend: "-1" },
    ],
    school: [
      { rank: 1, name: "北辰理工", meta: "累计 12,840 分", score: 12840, trend: "—" },
      { rank: 2, name: "星海大学", meta: "累计 12,306 分", score: 12306, trend: "+1" },
      { rank: 12, name: "你的学校", meta: "累计 3,614 分", score: 3614, trend: "+2", self: true },
    ],
  },
};

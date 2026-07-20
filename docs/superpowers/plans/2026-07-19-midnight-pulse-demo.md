# 午夜脉冲剧场 Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan.

**Goal:** 在 AlgoWiki 的 test 基线中实现可独立预览的“午夜脉冲剧场”前端 Demo，同时保留现有首页主体。

**Architecture:** 将每日规则实现为无浏览器依赖的纯状态模块，用 Node 内置测试锁定行为；Pinia store 负责本地日期与 `localStorage`；Vue 组件分别承担首页日签、顶栏入口、中心星、星图、排行和独立页面。真实后端能力不在本次范围内。

**Tech Stack:** Vue 3、Pinia、Vue Router、Vite、CSS、Node `node:test`

---

### Task 1: 锁定每日脉冲状态规则

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/tests/pulse-demo-state.test.mjs`
- Create: `frontend/src/features/pulse-demo/pulseDemoData.js`
- Create: `frontend/src/features/pulse-demo/pulseDemoState.js`

**Steps:**

1. 在 `package.json` 增加 `test:pulse-demo`，使用 `node --test tests/pulse-demo-state.test.mjs`。
2. 先写测试，覆盖初始 0/3、首次访问、回答一次发券、A/B 模式锁定、同模式两次换签、A/B 积分、单次投票、3/3 完成和重置。
3. 运行 `npm run test:pulse-demo`，确认因状态模块或导出缺失而失败。
4. 实现模拟数据与纯函数：`createPulseDemoState`、`normalizePulseDemoState`、`getPulseProgress`、`reducePulseDemoState`。
5. 再次运行测试，确认全部通过。

### Task 2: 增加持久化 Pinia store

**Files:**
- Create: `frontend/src/stores/pulseDemo.js`

**Steps:**

1. 使用 `defineStore` 包装纯状态模块，提供 `initialize`、`answerQuestion`、`chooseChallenge`、`rerollChallenge`、`completeChallenge`、`vote`、`dismissFirstVisit` 和 `resetDemo`。
2. 每次动作后写入 `algowiki-pulse-demo-v1`；读写浏览器 API 时增加环境保护。
3. 暴露 `progressCount`、`isComplete`、`showFirstVisit`、当前题目/VP和当前投票结果。
4. 运行 `npm run test:pulse-demo`，防止规则回归。

### Task 3: 实现核心视觉组件

**Files:**
- Create: `frontend/src/components/pulse-demo/PulseStar.vue`
- Create: `frontend/src/components/pulse-demo/PulseHeaderEntry.vue`
- Create: `frontend/src/components/pulse-demo/PulseFirstVisitSheet.vue`
- Create: `frontend/src/components/pulse-demo/PulseAtlasPanel.vue`
- Create: `frontend/src/components/pulse-demo/PulseRankingPanel.vue`

**Steps:**

1. 实现可按 0/3–3/3 改变光晕、核心、轨道和纹理的 `PulseStar`。
2. 实现紧凑顶栏入口与完成态。
3. 实现首页首次访问日签，提供关闭与进入剧场操作。
4. 实现个人星图：月历星点、社区/训练双连续记录、普通补签虚线轨道与超级补签蓝白耀斑图例。
5. 实现排行：月榜/总榜、全站/Rating/高校切换以及并列名次展示。

### Task 4: 实现独立交互页面

**Files:**
- Create: `frontend/src/pages/PulseDemoPage.vue`

**Steps:**

1. 构建 `今夜观测台 / 我的星图 / 脉冲排行` 三视图。
2. 在观测台中按桌面星体中心、问答左、挑战右、投票下的构图组织内容；移动端按星、问答、挑战、投票排列。
3. 接通回答输入、模式选择、换签、模拟完成检测、投票与重置动作。
4. 所有模拟能力标记为 Demo，不暗示已连接真实 Codeforces 或正式积分。

### Task 5: 接入现有应用

**Files:**
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/components/TopNav.vue`
- Modify: `frontend/src/pages/HomePage.vue`

**Steps:**

1. 在路由中懒加载 `PulseDemoPage` 并新增公开路由 `/pulse-demo`，名称 `pulse-demo`。
2. 在顶栏 actions 区导入并挂载 `PulseHeaderEntry`，移动端保留紧凑星标与进度。
3. 在首页 `.home-inner` 内、原 `.home-above-fold` 之前挂载 `PulseFirstVisitSheet`；不改动原首页主体结构。
4. 首页和顶栏初始化同一 store，确保首次访问和常驻入口状态同步。

### Task 6: 验证与本地预览

**Files:**
- Verify all files above

**Steps:**

1. 运行 `npm run test:pulse-demo`，确认测试零失败。
2. 运行 `npm run build`，确认生产构建退出码为 0。
3. 启动隔离工作树的 Vite 本地服务，访问首页和 `/pulse-demo`。
4. 在桌面和移动视口分别检查：首次日签、顶栏入口、三个交互、三视图、完成态、重置和无横向溢出。
5. 检查 `git diff --check` 和 `git status --short`，仅保留本 Demo 的文件。

## 自检

- 规格中的首次展开、顶栏入口、每日三项、两次同模式换签、A/B 积分、VP 04:00 文案、双连续、星图和排行均有明确落点。
- 状态模块不依赖 Vue 或浏览器，可由 Node 直接测试。
- 页面明确区分 Demo 与真实服务，不引入后端或生产路由冲突。
- 文件路径、函数名、路由名和测试命令在全计划中保持一致，无占位符。

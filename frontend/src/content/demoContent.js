const DEMO_AUTHOR = {
  id: "demo-author-resot",
  username: "NullResot",
  role: "admin",
  school_name: "AlgoWiki Lab",
  avatar_url: "",
  bio: "Demo author for local theme verification.",
  date_joined: "2026-03-01T08:00:00+08:00",
};

export const DEMO_WIKI_CATEGORY = {
  id: "demo-theme-preview",
  name: "主题验收示例",
  slug: "theme-preview",
  description: "开发环境下用于验收 Markdown、表格、代码块与多主题表现的演示分类。",
  parent: null,
  parent_name: "",
  order: 10,
  moderation_scope: "public",
  is_visible: true,
  created_at: "2026-03-25T09:00:00+08:00",
  updated_at: "2026-03-25T09:00:00+08:00",
};

const DEMO_ARTICLE_MARKDOWN = `
# AlgoWiki 主题验收示例

这是一篇仅在本地开发环境中兜底展示的示例正文，用来帮助你直接验收 **排版、代码块、表格、引用、按钮区和侧栏目录** 是否符合预期。

> 如果你现在数据库里没有正式文章，也可以先拿这篇内容看主题切换是否完整。

## 阅读目标

- 验收三套主题在长文场景下的可读性
- 检查代码块、表格、引用、列表、行内代码是否一起切换风格
- 观察移动端宽度下正文、目录、评论侧栏是否仍然顺畅

## 示例表格

| 维度 | Modern Glass | Clean Academic | Neo-Geek |
| --- | --- | --- | --- |
| 视觉关键词 | 玻璃、渐变、轻盈 | 纸面、学术、秩序 | 边框、强对比、终端感 |
| 推荐场景 | 首页、公告、探索页 | 长文阅读、知识库 | 练习区、工具页 |
| 正文关注点 | 色彩层次与高亮 | 行高、段距、页感 | 代码感与信息块边界 |

## 示例代码

下面这段代码专门用来观察不同主题下的语法高亮、语言标签和阴影是否合理：

\`\`\`cpp
#include <bits/stdc++.h>
using namespace std;

int longest_increasing_subsequence(const vector<int>& nums) {
    vector<int> tails;
    for (int value : nums) {
        auto it = lower_bound(tails.begin(), tails.end(), value);
        if (it == tails.end()) {
            tails.push_back(value);
        } else {
            *it = value;
        }
    }
    return static_cast<int>(tails.size());
}
\`\`\`

行内代码例如 \`vector<int>\`、\`lower_bound\`、\`O(n log n)\` 也应该跟随主题一起变化。

## 示例段落

算法竞赛资料站最容易出问题的地方，不在于“有没有内容”，而在于“内容多起来之后还能不能看”。真正的主题设计，必须同时照顾到标题层级、段落密度、代码阅读、表格横向滚动，以及移动端的交互节奏。

### 一条操作建议

如果你想快速验收：

1. 打开这篇演示文章。
2. 在顶部切三次主题。
3. 依次看表格、代码块、引用、评论区、移动端折叠区。

### 键盘标记

你也可以观察 \`Ctrl\` + \`K\` 或者 <kbd>Ctrl</kbd> + <kbd>K</kbd> 这类提示是否仍然清晰。

## 小结

当前这篇内容不会写入生产数据库，只作为本地验收的可视样本。等正式文章补齐后，它就应该自然退出主流程。
`.trim();

export function buildDemoWikiArticle(category = DEMO_WIKI_CATEGORY) {
  const normalizedCategory = category || DEMO_WIKI_CATEGORY;
  return {
    id: "demo-theme-article",
    slug: "demo-theme-article",
    title: "AlgoWiki 主题验收示例正文",
    summary: "用于本地验收 Markdown、表格、代码块与三套主题细节的演示正文。",
    content_md: DEMO_ARTICLE_MARKDOWN,
    category: normalizedCategory.id,
    category_name: normalizedCategory.name,
    author: DEMO_AUTHOR,
    status: "published",
    is_featured: false,
    is_locked: false,
    allow_comments: true,
    view_count: 0,
    published_at: "2026-03-25T09:30:00+08:00",
    star_count: 12,
    comment_count: 2,
    is_starred: false,
    can_edit: false,
    created_at: "2026-03-25T09:30:00+08:00",
    updated_at: "2026-03-25T09:30:00+08:00",
    __demo: true,
    demo_comments: [
      {
        id: "demo-comment-1",
        article: "demo-theme-article",
        article_title: "AlgoWiki 主题验收示例正文",
        author: {
          id: "demo-reader-1",
          username: "FreshmanCoder",
          role: "normal",
          school_name: "",
          avatar_url: "",
          bio: "",
          date_joined: "2026-03-10T08:00:00+08:00",
        },
        parent: null,
        content: "这一版很好，三套主题下的表格边界都能一眼看清。",
        status: "visible",
        created_at: "2026-03-25T10:00:00+08:00",
        updated_at: "2026-03-25T10:00:00+08:00",
      },
      {
        id: "demo-comment-2",
        article: "demo-theme-article",
        article_title: "AlgoWiki 主题验收示例正文",
        author: {
          id: "demo-reader-2",
          username: "GraphTheory",
          role: "school",
          school_name: "Local Test University",
          avatar_url: "",
          bio: "",
          date_joined: "2026-03-12T08:00:00+08:00",
        },
        parent: null,
        content: "移动端下代码块的横向滚动也正常，能继续往这个方向打磨。",
        status: "visible",
        created_at: "2026-03-25T10:12:00+08:00",
        updated_at: "2026-03-25T10:12:00+08:00",
      },
    ],
  };
}

export const DEMO_QA_QUESTIONS = [
  {
    id: "demo-question-1",
    title: "如何为 AlgoWiki 制定一套适合新生阅读的 Markdown 规范？",
    content_md: `
我在整理一篇面向新生的入门文章，希望同一套内容能够同时兼顾：

- 长文阅读体验
- 表格和代码块的一致性
- 移动端的可读性

目前想采用如下规则：

| 模块 | 建议写法 | 目的 |
| --- | --- | --- |
| 标题 | 从 \`##\` 开始组织章节 | 方便目录结构稳定 |
| 代码 | 明确写语言名 | 提升高亮准确率 |
| 图片 | 用 Markdown 外链 | 保持内容可迁移 |

你们会怎么补充这套规范？
    `.trim(),
    author: {
      id: "demo-user-1",
      username: "CampusEditor",
      role: "school",
      school_name: "AlgoWiki Lab",
      avatar_url: "",
      bio: "",
      date_joined: "2026-03-11T09:00:00+08:00",
    },
    category: "demo-category-editorial",
    category_name: "编辑规范",
    status: "open",
    answers_count: 2,
    created_at: "2026-03-25T11:00:00+08:00",
    updated_at: "2026-03-25T11:35:00+08:00",
    __demo: true,
    demo_answers: [
      {
        id: "demo-answer-1",
        question: "demo-question-1",
        question_title: "如何为 AlgoWiki 制定一套适合新生阅读的 Markdown 规范？",
        question_status: "open",
        author: DEMO_AUTHOR,
        content_md: `
先把规则写得**少而硬**，不要一上来就做成写作教科书。第一版建议只固定四条：

1. 每段只表达一个核心意思。
2. 代码块必须显式写语言名。
3. 表格只保留真正需要横向对比的信息。
4. 图片外链必须可公开访问。

如果文章里经常出现公式、代码和表格混排，再慢慢补“示例模板”。
        `.trim(),
        is_accepted: true,
        status: "visible",
        created_at: "2026-03-25T11:18:00+08:00",
        updated_at: "2026-03-25T11:18:00+08:00",
        __demo: true,
      },
      {
        id: "demo-answer-2",
        question: "demo-question-1",
        question_title: "如何为 AlgoWiki 制定一套适合新生阅读的 Markdown 规范？",
        question_status: "open",
        author: {
          id: "demo-user-2",
          username: "TemplateMaker",
          role: "normal",
          school_name: "",
          avatar_url: "",
          bio: "",
          date_joined: "2026-03-07T09:00:00+08:00",
        },
        content_md: "还可以给投稿者提供一份模板，让大家默认就带上摘要、目录和参考链接。",
        is_accepted: false,
        status: "visible",
        created_at: "2026-03-25T11:26:00+08:00",
        updated_at: "2026-03-25T11:26:00+08:00",
        __demo: true,
      },
    ],
  },
  {
    id: "demo-question-2",
    title: "问答区的卡片式布局，应该优先展示标题还是回答摘要？",
    content_md: `
我准备把问答页改成更接近论坛流的结构，希望首页列表里就能看出：

- 这条问题属于什么主题
- 有没有被采纳的回答
- 最新讨论大概在说什么

你更倾向于卡片里优先显示**标题信息密度**，还是优先显示**回答摘要**？
    `.trim(),
    author: {
      id: "demo-user-3",
      username: "LayoutPilot",
      role: "normal",
      school_name: "",
      avatar_url: "",
      bio: "",
      date_joined: "2026-03-09T09:00:00+08:00",
    },
    category: "demo-category-product",
    category_name: "界面设计",
    status: "open",
    answers_count: 1,
    created_at: "2026-03-25T10:32:00+08:00",
    updated_at: "2026-03-25T11:10:00+08:00",
    __demo: true,
    demo_answers: [
      {
        id: "demo-answer-3",
        question: "demo-question-2",
        question_title: "问答区的卡片式布局，应该优先展示标题还是回答摘要？",
        question_status: "open",
        author: {
          id: "demo-user-4",
          username: "UIObserver",
          role: "normal",
          school_name: "",
          avatar_url: "",
          bio: "",
          date_joined: "2026-03-08T09:00:00+08:00",
        },
        content_md: "先把标题、标签、回答数和是否采纳做清楚，再给一段一到两行的摘要，信息层次会更稳定。",
        is_accepted: false,
        status: "visible",
        created_at: "2026-03-25T11:10:00+08:00",
        updated_at: "2026-03-25T11:10:00+08:00",
        __demo: true,
      },
    ],
  },
  {
    id: "demo-question-3",
    title: "普通用户提交的问题进入审核后，前台列表应该如何提示状态更稳妥？",
    content_md: `
为了避免未审核内容直接公开，我已经把普通用户提交的问题改成先进入审核。

现在还在考虑前端提示方式：

- 是直接显示“审核中”
- 还是在自己的视图里单独分组
- 又或者默认隐藏，只在个人中心查看

想听听大家对可理解性和安全性的取舍建议。
    `.trim(),
    author: {
      id: "demo-user-5",
      username: "ReviewGuard",
      role: "admin",
      school_name: "AlgoWiki Lab",
      avatar_url: "",
      bio: "",
      date_joined: "2026-03-06T09:00:00+08:00",
    },
    category: "demo-category-security",
    category_name: "审核流程",
    status: "closed",
    answers_count: 1,
    created_at: "2026-03-25T09:28:00+08:00",
    updated_at: "2026-03-25T10:08:00+08:00",
    __demo: true,
    demo_answers: [
      {
        id: "demo-answer-4",
        question: "demo-question-3",
        question_title: "普通用户提交的问题进入审核后，前台列表应该如何提示状态更稳妥？",
        question_status: "closed",
        author: {
          id: "demo-user-6",
          username: "ModerationOps",
          role: "admin",
          school_name: "AlgoWiki Lab",
          avatar_url: "",
          bio: "",
          date_joined: "2026-03-05T09:00:00+08:00",
        },
        content_md: "前台公开列表不要出现未审核内容，但作者自己的视图里可以明确显示“审核中”和最近更新时间。",
        is_accepted: true,
        status: "visible",
        created_at: "2026-03-25T10:08:00+08:00",
        updated_at: "2026-03-25T10:08:00+08:00",
        __demo: true,
      },
    ],
  },
];

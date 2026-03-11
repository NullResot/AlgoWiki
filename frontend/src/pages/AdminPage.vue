<template>
  <section class="admin-layout">
    <article class="admin-card full">
      <h2>管理概览</h2>
      <div class="overview-grid" v-if="adminOverview">
        <div class="overview-item">
          <strong>{{ adminOverview.users?.active ?? 0 }}</strong>
          <span>活跃用户</span>
        </div>
        <div class="overview-item">
          <strong>{{ adminOverview.users?.banned ?? 0 }}</strong>
          <span>封禁用户</span>
        </div>
        <div class="overview-item">
          <strong>{{ adminOverview.content?.articles_total ?? 0 }}</strong>
          <span>文章总数</span>
        </div>
        <div class="overview-item">
          <strong>{{ adminOverview.content?.articles_published ?? 0 }}</strong>
          <span>已发布文章</span>
        </div>
        <div class="overview-item">
          <strong>{{ adminOverview.workflow?.tickets_open ?? 0 }}</strong>
          <span>待处理工单</span>
        </div>
        <div class="overview-item">
          <strong>{{ adminOverview.workflow?.revisions_pending ?? 0 }}</strong>
          <span>待审核修订</span>
        </div>
      </div>
      <div class="overview-actions">
        <button class="btn" @click="loadAdminOverview" :disabled="overviewLoading">
          {{ overviewLoading ? "刷新中..." : "刷新概览" }}
        </button>
      </div>
      <div class="overview-analytics" v-if="adminOverview">
        <section class="overview-panel">
          <h3>事件类型分布</h3>
          <div class="overview-bar-list">
            <div class="overview-bar-row" v-for="item in eventTypeSeries" :key="`type-${item.event_type}`">
              <span>{{ formatEventType(item.event_type) }}</span>
              <div class="overview-bar-track">
                <div class="overview-bar-fill" :style="{ width: `${eventTypeBarPercent(item.count)}%` }"></div>
              </div>
              <strong>{{ item.count }}</strong>
            </div>
          </div>
        </section>
        <section class="overview-panel">
          <h3>近7天活跃事件</h3>
          <div class="overview-day-list">
            <div class="overview-day-row" v-for="item in dailyEventSeries" :key="`day-${item.date}`">
              <span>{{ item.date.slice(5) }}</span>
              <div class="overview-bar-track">
                <div class="overview-bar-fill" :style="{ width: `${dailyEventBarPercent(item.count)}%` }"></div>
              </div>
              <strong>{{ item.count }}</strong>
            </div>
          </div>
        </section>
      </div>
      <p class="meta" v-if="!adminOverview">概览数据加载中...</p>
    </article>
    <article class="admin-card">
      <h2>公告发布</h2>

      <div class="announce-form">
        <input class="input" v-model="announceForm.title" placeholder="公告标题" />
        <textarea class="textarea" v-model="announceForm.content_md" placeholder="Markdown 公告正文"></textarea>
        <div class="announce-actions">
          <input class="input" type="number" v-model.number="announceForm.priority" placeholder="优先级" />
          <label class="bulk-check">
            <input type="checkbox" v-model="announceForm.is_published" />
            立即发布
          </label>
          <button class="btn btn-accent" @click="saveAnnouncement">
            {{ editingAnnouncementId ? "保存公告" : "发布公告" }}
          </button>
          <button class="btn" v-if="editingAnnouncementId" @click="resetAnnouncementForm">取消编辑</button>
        </div>
      </div>

      <article class="notice" v-for="item in announcements" :key="item.id">
        <div class="notice-head">
          <strong>{{ item.title }}</strong>
          <span class="meta">priority {{ item.priority }} · {{ item.is_published ? "已发布" : "已下线" }}</span>
        </div>
        <p class="meta">{{ item.content_md }}</p>
        <div class="notice-tools">
          <button class="btn" @click="startEditAnnouncement(item)">编辑</button>
          <button class="btn" @click="toggleAnnouncementPublished(item)">
            {{ item.is_published ? "下线" : "发布" }}
          </button>
          <button class="btn" @click="deleteAnnouncement(item)">删除</button>
        </div>
      </article>
    </article>

    <article class="admin-card">
      <h2>用户管理</h2>
      <div class="bulk-tools">
        <select class="select bulk-select" v-model="userFilters.role">
          <option value="">全部角色</option>
          <option value="normal">normal</option>
          <option value="school">school</option>
          <option value="admin">admin</option>
          <option value="superadmin">superadmin</option>
        </select>
        <select class="select bulk-select" v-model="userFilters.is_active">
          <option value="">全部状态</option>
          <option value="1">active</option>
          <option value="0">inactive</option>
        </select>
        <select class="select bulk-select" v-model="userFilters.is_banned">
          <option value="">全部封禁状态</option>
          <option value="1">banned</option>
          <option value="0">not banned</option>
        </select>
        <input class="input bulk-input" v-model="userFilters.search" placeholder="搜索用户名/邮箱/学校" @keyup.enter="loadUsers()" />
        <button class="btn" @click="loadUsers">筛选</button>
        <button class="btn" @click="resetUserFilters">重置</button>
      </div>
      <p class="meta">共 {{ usersMeta.count }} 个用户</p>
      <div class="bulk-tools">
        <label class="bulk-check">
          <input type="checkbox" :checked="allUsersChecked" @change="toggleSelectAllUsers($event.target.checked)" />
          全选用户
        </label>
        <button class="btn" @click="bulkBanUsers">批量封禁</button>
        <button class="btn" @click="bulkUnbanUsers">批量解封</button>
        <button class="btn" @click="bulkReactivateUsers">批量恢复</button>
        <button class="btn" @click="bulkSoftDeleteUsers">批量删除</button>
        <template v-if="auth.isSuperAdmin">
          <select class="select bulk-select" v-model="bulkRole">
            <option value="normal">normal</option>
            <option value="school">school</option>
            <option value="admin">admin</option>
          </select>
          <button class="btn" @click="bulkSetRole">批量设角色</button>
        </template>
      </div>
      <article class="user-row" v-for="item in users" :key="item.id">
        <div>
          <label class="bulk-check">
            <input type="checkbox" :value="item.id" v-model="selectedUserIds" />
            选择
          </label>
          <strong>{{ item.username }}</strong>
          <div class="meta">
            {{ item.role }} · {{ item.is_active ? "活跃" : "已删除" }} · {{ item.is_banned ? "已封禁" : "正常" }}
          </div>
        </div>

        <div class="user-actions">
          <button v-if="!item.is_banned" class="btn" @click="banUser(item.id)">封禁</button>
          <button v-else class="btn" @click="unbanUser(item.id)">解封</button>
          <button v-if="!item.is_active" class="btn" @click="reactivateUser(item.id)">恢复用户</button>
          <button class="btn" @click="softDeleteUser(item)">删除用户</button>

          <button v-if="auth.isSuperAdmin && item.role !== 'admin'" class="btn" @click="setRole(item.id, 'admin')">
            设为管理员
          </button>
          <button v-if="auth.isSuperAdmin && item.role !== 'school'" class="btn" @click="setRole(item.id, 'school')">
            设为学校用户
          </button>
          <button v-if="auth.isSuperAdmin && item.role !== 'normal'" class="btn" @click="setRole(item.id, 'normal')">
            设为普通用户
          </button>
        </div>
      </article>
      <button v-if="usersMeta.hasMore" class="btn" @click="loadMoreUsers">加载更多用户</button>
    </article>

    <article class="admin-card full">
      <h2>Issue / Request 处理</h2>
      <p class="meta">共 {{ ticketsMeta.count }} 条工单</p>
      <div class="bulk-tools">
        <select class="select bulk-select" v-model="ticketFilters.status" @change="loadTickets()">
          <option value="">全部状态</option>
          <option value="pending">pending</option>
          <option value="open">open</option>
          <option value="in_progress">in_progress</option>
          <option value="resolved">resolved</option>
          <option value="rejected">rejected</option>
        </select>
        <select class="select bulk-select" v-model="ticketFilters.kind" @change="loadTickets()">
          <option value="">全部类型</option>
          <option value="issue">issue</option>
          <option value="request">request</option>
        </select>
        <input class="input bulk-input" v-model="ticketFilters.author" placeholder="提交者用户名" />
        <select class="select bulk-select" v-model="ticketFilters.assignee">
          <option value="">全部处理人</option>
          <option value="none">未分派</option>
          <option v-for="user in assigneeOptions" :key="`ticket-filter-assignee-${user.id}`" :value="String(user.id)">
            {{ user.username }} ({{ user.role }})
          </option>
        </select>
        <select class="select bulk-select" v-model="ticketFilters.order">
          <option value="updated_newest">按最近更新</option>
          <option value="updated_oldest">按最早更新</option>
          <option value="created_newest">按创建时间（新）</option>
          <option value="created_oldest">按创建时间（旧）</option>
        </select>
        <input class="input bulk-input" v-model="ticketFilters.search" placeholder="搜索标题或内容" @keyup.enter="loadTickets()" />
        <button class="btn" @click="loadTickets">筛选</button>
        <button class="btn" @click="resetTicketFilters">重置</button>
      </div>
      <div class="bulk-tools">
        <label class="bulk-check">
          <input type="checkbox" :checked="allTicketsChecked" @change="toggleSelectAllTickets($event.target.checked)" />
          全选工单
        </label>
        <select class="select bulk-select" v-model="bulkTicketForm.status">
          <option value="pending">pending</option>
          <option value="open">open</option>
          <option value="in_progress">in_progress</option>
          <option value="resolved">resolved</option>
          <option value="rejected">rejected</option>
        </select>
        <select class="select bulk-select" v-model="bulkTicketForm.assign_to">
          <option value="__keep__">保持处理人不变</option>
          <option value="__none__">清空处理人</option>
          <option v-for="user in assigneeOptions" :key="`ticket-bulk-assignee-${user.id}`" :value="String(user.id)">
            指派给 {{ user.username }} ({{ user.role }})
          </option>
        </select>
        <input class="input bulk-input" v-model="bulkTicketForm.note" placeholder="批量处理备注" />
        <button class="btn" @click="bulkUpdateTicketStatus">批量提交</button>
      </div>
      <article class="ticket-row" v-for="item in tickets" :key="item.id">
        <div class="ticket-main">
          <label class="bulk-check">
            <input type="checkbox" :value="item.id" v-model="selectedTicketIds" />
            选择
          </label>
          <strong>{{ item.title }}</strong>
          <p class="meta">{{ item.kind }} · {{ item.status }} · {{ item.author.username }}</p>
          <p class="meta">
            处理人：{{ item.assignee?.username ? `${item.assignee.username} (${item.assignee.role})` : "未分派" }}
          </p>
          <p class="meta" v-if="item.related_article_title">关联条目：{{ item.related_article_title }}</p>
          <p class="ticket-content">{{ item.content }}</p>
        </div>

        <div class="ticket-actions">
          <select class="select" v-model="item._nextStatus">
            <option value="pending">pending</option>
            <option value="open">open</option>
            <option value="in_progress">in_progress</option>
            <option value="resolved">resolved</option>
            <option value="rejected">rejected</option>
          </select>
          <select class="select" v-model="item._assignTo">
            <option value="">未分派</option>
            <option v-for="user in assigneeOptions" :key="`ticket-assignee-${item.id}-${user.id}`" :value="String(user.id)">
              {{ user.username }} ({{ user.role }})
            </option>
          </select>
          <input class="input" v-model="item._note" placeholder="处理备注" />
          <button class="btn" @click="updateTicketStatus(item)">提交处理</button>
        </div>
      </article>
      <button v-if="ticketsMeta.hasMore" class="btn" @click="loadMoreTickets">加载更多工单</button>
    </article>

    <article class="admin-card full">
      <h2>扩展页面管理</h2>
      <div class="page-panel">
        <div class="page-form-grid">
          <input class="input" v-model="pageForm.title" placeholder="页面标题" />
          <input class="input" v-model="pageForm.slug" placeholder="slug（例如 about-team）" />
        </div>
        <input class="input" v-model="pageForm.description" placeholder="页面简介" />
        <textarea class="textarea" v-model="pageForm.content_md" placeholder="Markdown 页面正文"></textarea>
        <div class="page-actions">
          <select class="select" v-model="pageForm.access_level">
            <option value="public">public</option>
            <option value="auth">auth</option>
            <option value="admin">admin</option>
          </select>
          <label class="meta">
            <input type="checkbox" v-model="pageForm.is_enabled" />
            启用
          </label>
          <button class="btn btn-accent" @click="savePage">{{ editingPageSlug ? "保存页面" : "创建页面" }}</button>
          <button class="btn" v-if="editingPageSlug" @click="resetPageForm">取消编辑</button>
        </div>
      </div>

      <article class="page-row" v-for="item in extensionPages" :key="item.id">
        <div class="ticket-main">
          <strong>{{ item.title }}</strong>
          <p class="meta">
            /extra/{{ item.slug }} · {{ item.access_level }} · {{ item.is_enabled ? "已启用" : "已停用" }}
          </p>
          <p class="ticket-content">{{ item.description || "无简介" }}</p>
        </div>
        <div class="page-tools">
          <button class="btn" @click="startEditPage(item)">编辑</button>
          <button class="btn" @click="togglePageEnabled(item)">{{ item.is_enabled ? "停用" : "启用" }}</button>
          <button class="btn" @click="deletePage(item)">删除</button>
        </div>
      </article>
    </article>

    <article class="admin-card full">
      <h2>分类管理</h2>
      <div class="page-panel">
        <div class="category-form-grid">
          <input class="input" v-model="categoryForm.name" placeholder="分类名称" />
          <input class="input" v-model="categoryForm.slug" placeholder="slug（可选）" />
          <select class="select" v-model="categoryForm.parent">
            <option value="">无父级分类</option>
            <option v-for="item in parentCategoryOptions" :key="item.id" :value="String(item.id)">
              {{ item.name }}
            </option>
          </select>
          <select class="select" v-model="categoryForm.moderation_scope">
            <option value="public">public</option>
            <option value="school">school</option>
          </select>
          <input class="input" type="number" v-model.number="categoryForm.order" placeholder="排序（order）" />
          <label class="meta category-visible">
            <input type="checkbox" v-model="categoryForm.is_visible" />
            显示
          </label>
        </div>
        <textarea class="textarea" v-model="categoryForm.description" placeholder="分类简介"></textarea>
        <div class="page-actions">
          <button class="btn btn-accent" @click="saveCategory">{{ editingCategoryId ? "保存分类" : "创建分类" }}</button>
          <button class="btn" @click="normalizeCategoryOrder">标准化排序</button>
          <button class="btn" v-if="editingCategoryId" @click="resetCategoryForm">取消编辑</button>
        </div>
      </div>

      <article class="category-row" v-for="item in categories" :key="item.id">
        <div class="ticket-main">
          <strong>{{ item.name }}</strong>
          <p class="meta">
            {{ item.slug || "-" }} · {{ item.moderation_scope }} · order {{ item.order }} ·
            {{ item.is_visible ? "显示" : "隐藏" }}
          </p>
          <p class="ticket-content">{{ item.description || "无分类描述" }}</p>
          <p class="meta" v-if="item.parent_name">父级：{{ item.parent_name }}</p>
        </div>

        <div class="page-tools">
          <button class="btn" @click="startEditCategory(item)">编辑</button>
          <button class="btn" :disabled="isCategoryAtTop(item)" @click="moveCategory(item, -1)">上移</button>
          <button class="btn" :disabled="isCategoryAtBottom(item)" @click="moveCategory(item, 1)">下移</button>
          <button class="btn" @click="toggleCategoryVisibility(item)">{{ item.is_visible ? "隐藏" : "显示" }}</button>
          <button class="btn" @click="toggleCategoryScope(item)">
            切换为{{ item.moderation_scope === "public" ? "school" : "public" }}
          </button>
          <button class="btn" @click="deleteCategory(item)">删除</button>
        </div>
      </article>
    </article>

    <article class="admin-card full">
      <h2>内容治理</h2>

      <h3 class="sub-title">文章管理</h3>
      <p class="meta">共 {{ moderationArticlesMeta.count }} 篇文章</p>
      <div class="bulk-tools">
        <label class="bulk-check">
          <input
            type="checkbox"
            :checked="allModerationArticlesChecked"
            @change="toggleSelectAllModerationArticles($event.target.checked)"
          />
          全选文章
        </label>
        <input class="input bulk-input" v-model="moderationArticleFilters.search" placeholder="按标题/摘要搜索" />
        <select class="select bulk-select" v-model="moderationArticleFilters.status">
          <option value="">全部状态</option>
          <option value="published">published</option>
          <option value="draft">draft</option>
        </select>
        <select class="select bulk-select" v-model="moderationArticleFilters.category">
          <option value="">全部分类</option>
          <option v-for="item in categories" :key="item.id" :value="String(item.id)">{{ item.name }}</option>
        </select>
        <input class="input bulk-input" v-model="moderationArticleFilters.author" placeholder="作者用户名" />
        <button class="btn" @click="loadModerationArticles">筛选文章</button>
        <button class="btn" @click="resetModerationArticleFilters">重置</button>
        <button class="btn" @click="bulkPublishArticles">批量发布</button>
        <button class="btn" @click="bulkDeleteArticles">批量删除</button>
      </div>
      <article class="ticket-row" v-for="item in moderationArticles" :key="`article-${item.id}`">
        <div class="ticket-main">
          <label class="bulk-check">
            <input type="checkbox" :value="item.id" v-model="selectedModerationArticleIds" />
            选择
          </label>
          <strong>{{ item.title }}</strong>
          <p class="meta">{{ item.status }} · {{ item.author.username }} · 分类 {{ item.category_name }}</p>
          <p class="ticket-content">{{ item.summary || "无摘要" }}</p>
        </div>
        <div class="ticket-actions">
          <button v-if="item.status !== 'published'" class="btn" @click="publishArticle(item)">发布</button>
          <button class="btn" @click="deleteArticle(item)">删除</button>
        </div>
      </article>
      <button v-if="moderationArticlesMeta.hasMore" class="btn" @click="loadMoreModerationArticles">
        加载更多文章
      </button>
      <p v-if="!moderationArticles.length" class="meta">暂无可管理文章。</p>

      <h3 class="sub-title">评论管理</h3>
      <p class="meta">共 {{ moderationCommentsMeta.count }} 条评论</p>
      <div class="bulk-tools">
        <label class="bulk-check">
          <input
            type="checkbox"
            :checked="allModerationCommentsChecked"
            @change="toggleSelectAllModerationComments($event.target.checked)"
          />
          全选评论
        </label>
        <input class="input bulk-input" v-model="moderationCommentFilters.search" placeholder="按内容搜索评论" />
        <input class="input bulk-input" v-model="moderationCommentFilters.author" placeholder="评论用户名" />
        <select class="select bulk-select" v-model="moderationCommentFilters.status">
          <option value="">全部状态</option>
          <option value="pending">pending</option>
          <option value="visible">visible</option>
          <option value="hidden">hidden</option>
        </select>
        <input class="input bulk-input" v-model="moderationCommentFilters.article" placeholder="条目ID" />
        <button class="btn" @click="loadModerationComments">筛选评论</button>
        <button class="btn" @click="resetModerationCommentFilters">重置</button>
        <button class="btn" @click="bulkHideComments">批量隐藏</button>
      </div>
      <article class="ticket-row" v-for="item in moderationComments" :key="`comment-${item.id}`">
        <div class="ticket-main">
          <label class="bulk-check">
            <input type="checkbox" :value="item.id" v-model="selectedModerationCommentIds" />
            选择
          </label>
          <strong>评论 #{{ item.id }}</strong>
          <p class="meta">条目 #{{ item.article }} · {{ item.author.username }} · {{ item.status }}</p>
          <p class="ticket-content">{{ item.content }}</p>
        </div>
        <div class="ticket-actions">
          <button class="btn" @click="hideComment(item)" :disabled="item.status === 'hidden'">
            {{ item.status === "hidden" ? "已隐藏" : "隐藏评论" }}
          </button>
        </div>
      </article>
      <button v-if="moderationCommentsMeta.hasMore" class="btn" @click="loadMoreModerationComments">
        加载更多评论
      </button>
      <p v-if="!moderationComments.length" class="meta">暂无评论记录。</p>

      <h3 class="sub-title">问题管理</h3>
      <p class="meta">共 {{ moderationQuestionsMeta.count }} 条问题</p>
      <div class="bulk-tools">
        <label class="bulk-check">
          <input
            type="checkbox"
            :checked="allModerationQuestionsChecked"
            @change="toggleSelectAllModerationQuestions($event.target.checked)"
          />
          全选问题
        </label>
        <input class="input bulk-input" v-model="moderationQuestionFilters.search" placeholder="按标题/内容搜索问题" />
        <input class="input bulk-input" v-model="moderationQuestionFilters.author" placeholder="提问用户名" />
        <select class="select bulk-select" v-model="moderationQuestionFilters.status">
          <option value="">全部状态</option>
          <option value="open">open</option>
          <option value="closed">closed</option>
          <option value="hidden">hidden</option>
        </select>
        <select class="select bulk-select" v-model="moderationQuestionFilters.category">
          <option value="">全部分类</option>
          <option v-for="item in categories" :key="`question-category-${item.id}`" :value="String(item.id)">
            {{ item.name }}
          </option>
        </select>
        <button class="btn" @click="loadModerationQuestions">筛选问题</button>
        <button class="btn" @click="resetModerationQuestionFilters">重置</button>
        <button class="btn" @click="bulkCloseQuestions">批量关闭</button>
        <button class="btn" @click="bulkReopenQuestions">批量重开</button>
        <button class="btn" @click="bulkHideQuestions">批量隐藏</button>
      </div>
      <article class="ticket-row" v-for="item in moderationQuestions" :key="`question-${item.id}`">
        <div class="ticket-main">
          <label class="bulk-check">
            <input type="checkbox" :value="item.id" v-model="selectedModerationQuestionIds" />
            选择
          </label>
          <strong>{{ item.title }}</strong>
          <p class="meta">
            提问者 {{ item.author.username }} · {{ item.status }} · 回答 {{ item.answers_count }}
            <span v-if="item.category_name"> · 分类 {{ item.category_name }}</span>
          </p>
          <p class="ticket-content">{{ item.content_md }}</p>
        </div>
        <div class="ticket-actions">
          <button class="btn" v-if="item.status !== 'closed'" @click="closeQuestionItem(item)">关闭</button>
          <button class="btn" v-if="item.status !== 'open'" @click="reopenQuestionItem(item)">重开</button>
          <button class="btn" v-if="item.status !== 'hidden'" @click="hideQuestionItem(item)">隐藏</button>
        </div>
      </article>
      <button v-if="moderationQuestionsMeta.hasMore" class="btn" @click="loadMoreModerationQuestions">
        加载更多问题
      </button>
      <p v-if="!moderationQuestions.length" class="meta">暂无问题记录。</p>
    </article>

    <article class="admin-card full">
      <h2>安全审计日志</h2>
      <div class="bulk-tools">
        <select class="select bulk-select" v-model="securityWindowHours">
          <option :value="6">最近 6 小时</option>
          <option :value="24">最近 24 小时</option>
          <option :value="72">最近 72 小时</option>
          <option :value="168">最近 7 天</option>
        </select>
        <button class="btn" :disabled="securitySummaryLoading" @click="loadSecuritySummary">
          {{ securitySummaryLoading ? "刷新中..." : "刷新安全概览" }}
        </button>
      </div>
      <div class="overview-grid" v-if="securitySummary">
        <div class="overview-item">
          <strong>{{ securitySummary.totals?.failed_events ?? 0 }}</strong>
          <span>失败事件</span>
        </div>
        <div class="overview-item">
          <strong>{{ securitySummary.totals?.login_failed ?? 0 }}</strong>
          <span>登录失败</span>
        </div>
        <div class="overview-item">
          <strong>{{ securitySummary.totals?.login_locked ?? 0 }}</strong>
          <span>锁定次数</span>
        </div>
        <div class="overview-item">
          <strong>{{ securitySummary.unique?.ips ?? 0 }}</strong>
          <span>异常IP数</span>
        </div>
        <div class="overview-item">
          <strong>{{ securitySummary.unique?.usernames ?? 0 }}</strong>
          <span>异常用户名数</span>
        </div>
        <div class="overview-item">
          <strong>{{ securitySummary.totals?.all_events ?? 0 }}</strong>
          <span>总安全事件</span>
        </div>
      </div>
      <p v-if="securitySummary?.since" class="meta">统计起点：{{ formatDateTime(securitySummary.since) }}</p>
      <div class="overview-bar-list" v-if="securitySummary?.top_failed_ips?.length">
        <div class="overview-bar-row" v-for="item in securitySummary.top_failed_ips" :key="`security-ip-${item.ip_address}`">
          <span>{{ item.ip_address }}</span>
          <div class="overview-bar-track">
            <div class="overview-bar-fill" :style="{ width: `${securityTopIpBarPercent(item.count)}%` }"></div>
          </div>
          <strong>{{ item.count }}</strong>
        </div>
      </div>
      <p class="meta">共 {{ securityLogsMeta.count }} 条安全事件</p>
      <div class="bulk-tools">
        <select class="select bulk-select" v-model="securityFilters.event_type">
          <option value="">全部事件</option>
          <option value="login_success">login_success</option>
          <option value="login_failed">login_failed</option>
          <option value="login_locked">login_locked</option>
          <option value="login_denied">login_denied</option>
          <option value="register_success">register_success</option>
          <option value="logout">logout</option>
          <option value="password_changed">password_changed</option>
          <option value="user_banned">user_banned</option>
          <option value="user_unbanned">user_unbanned</option>
          <option value="user_soft_deleted">user_soft_deleted</option>
          <option value="user_reactivated">user_reactivated</option>
          <option value="user_role_changed">user_role_changed</option>
        </select>
        <select class="select bulk-select" v-model="securityFilters.success">
          <option value="">全部结果</option>
          <option value="1">success</option>
          <option value="0">failed</option>
        </select>
        <input class="input bulk-input" v-model="securityFilters.username" placeholder="用户名" />
        <input class="input bulk-input" v-model="securityFilters.ip" placeholder="IP 地址" />
        <input class="input bulk-input" v-model="securityFilters.detail" placeholder="关键词（detail）" />
        <input class="input bulk-input" type="datetime-local" v-model="securityFilters.start_at" />
        <input class="input bulk-input" type="datetime-local" v-model="securityFilters.end_at" />
        <button class="btn" @click="loadSecurityLogs">筛选</button>
        <button class="btn" @click="exportSecurityLogs">导出CSV</button>
        <button class="btn" @click="resetSecurityFilters">重置</button>
      </div>
      <article class="ticket-row" v-for="item in securityLogs" :key="`security-${item.id}`">
        <div class="ticket-main">
          <strong>{{ formatSecurityEventType(item.event_type) }}</strong>
          <p class="meta">
            用户 {{ item.username || item.user?.username || "unknown" }} ·
            {{ item.ip_address || "-" }} ·
            {{ item.success ? "success" : "failed" }} ·
            {{ formatDateTime(item.created_at) }}
          </p>
          <p class="ticket-content">{{ item.detail || "-" }}</p>
        </div>
      </article>
      <button v-if="securityLogsMeta.hasMore" class="btn" @click="loadMoreSecurityLogs">加载更多安全日志</button>
      <p v-if="!securityLogs.length" class="meta">暂无安全日志。</p>
    </article>

    <article class="admin-card full">
      <h2>操作日志</h2>
      <p class="meta">共 {{ eventsMeta.count }} 条日志</p>
      <div class="bulk-tools">
        <select class="select bulk-select" v-model="eventFilters.event_type">
          <option value="">全部类型</option>
          <option value="star">star</option>
          <option value="comment">comment</option>
          <option value="issue">issue</option>
          <option value="revision">revision</option>
          <option value="question">question</option>
          <option value="answer">answer</option>
          <option value="announcement">announcement</option>
          <option value="admin">admin</option>
        </select>
        <input class="input bulk-input" v-model="eventFilters.user" placeholder="用户ID或用户名" />
        <input class="input bulk-input" v-model="eventFilters.target_type" placeholder="目标类型（如 Article）" />
        <input class="input bulk-input" v-model="eventFilters.search" placeholder="检索 payload 关键词" />
        <input class="input bulk-input" type="datetime-local" v-model="eventFilters.start_at" />
        <input class="input bulk-input" type="datetime-local" v-model="eventFilters.end_at" />
        <button class="btn" @click="loadEvents">筛选日志</button>
        <button class="btn" @click="exportEvents">导出CSV</button>
        <button class="btn" @click="resetEventFilters">重置</button>
      </div>
      <article class="ticket-row" v-for="item in events" :key="`event-${item.id}`">
        <div class="ticket-main">
          <strong>{{ formatEventType(item.event_type) }} · {{ item.target_type }} #{{ item.target_id }}</strong>
          <p class="meta">{{ item.user?.username || "unknown" }} · {{ formatDateTime(item.created_at) }}</p>
          <p class="ticket-content">{{ renderPayload(item.payload) }}</p>
        </div>
      </article>
      <button v-if="eventsMeta.hasMore" class="btn" @click="loadMoreEvents">加载更多日志</button>
      <p v-if="!events.length" class="meta">暂无日志记录。</p>
    </article>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import api from "../services/api";
import { useAuthStore } from "../stores/auth";
import { useUiStore } from "../stores/ui";

const auth = useAuthStore();
const ui = useUiStore();

const announcements = ref([]);
const users = ref([]);
const tickets = ref([]);
const assigneeOptions = ref([]);
const extensionPages = ref([]);
const categories = ref([]);
const moderationArticles = ref([]);
const moderationComments = ref([]);
const moderationQuestions = ref([]);
const securityLogs = ref([]);
const events = ref([]);
const adminOverview = ref(null);
const securitySummary = ref(null);
const overviewLoading = ref(false);
const securitySummaryLoading = ref(false);
const editingAnnouncementId = ref(null);
const editingPageSlug = ref("");
const editingCategoryId = ref(null);
const selectedUserIds = ref([]);
const selectedTicketIds = ref([]);
const selectedModerationArticleIds = ref([]);
const selectedModerationCommentIds = ref([]);
const selectedModerationQuestionIds = ref([]);
const bulkRole = ref("normal");
const securityWindowHours = ref(24);

const usersMeta = reactive({ count: 0, page: 1, hasMore: false });
const ticketsMeta = reactive({ count: 0, page: 1, hasMore: false });
const moderationArticlesMeta = reactive({ count: 0, page: 1, hasMore: false });
const moderationCommentsMeta = reactive({ count: 0, page: 1, hasMore: false });
const moderationQuestionsMeta = reactive({ count: 0, page: 1, hasMore: false });
const securityLogsMeta = reactive({ count: 0, page: 1, hasMore: false });
const eventsMeta = reactive({ count: 0, page: 1, hasMore: false });

const announceForm = reactive({
  title: "",
  content_md: "",
  priority: 0,
  is_published: true,
});

const pageForm = reactive({
  title: "",
  slug: "",
  description: "",
  content_md: "",
  access_level: "public",
  is_enabled: true,
});

const categoryForm = reactive({
  name: "",
  slug: "",
  description: "",
  parent: "",
  moderation_scope: "public",
  order: 0,
  is_visible: true,
});

const bulkTicketForm = reactive({
  status: "in_progress",
  assign_to: "__keep__",
  note: "",
});

const ticketFilters = reactive({
  status: "",
  kind: "",
  author: "",
  assignee: "",
  order: "updated_newest",
  search: "",
});

const userFilters = reactive({
  role: "",
  is_active: "",
  is_banned: "",
  search: "",
});

const moderationArticleFilters = reactive({
  search: "",
  status: "",
  category: "",
  author: "",
});

const moderationCommentFilters = reactive({
  search: "",
  status: "",
  author: "",
  article: "",
});

const moderationQuestionFilters = reactive({
  search: "",
  status: "",
  category: "",
  author: "",
});

const eventFilters = reactive({
  event_type: "",
  user: "",
  target_type: "",
  search: "",
  start_at: "",
  end_at: "",
});

const securityFilters = reactive({
  event_type: "",
  success: "",
  username: "",
  ip: "",
  detail: "",
  start_at: "",
  end_at: "",
});

const parentCategoryOptions = computed(() =>
  categories.value.filter((item) => item.id !== editingCategoryId.value)
);

const allUsersChecked = computed(
  () => users.value.length > 0 && selectedUserIds.value.length === users.value.length
);
const allTicketsChecked = computed(
  () => tickets.value.length > 0 && selectedTicketIds.value.length === tickets.value.length
);
const allModerationArticlesChecked = computed(
  () =>
    moderationArticles.value.length > 0 &&
    selectedModerationArticleIds.value.length === moderationArticles.value.length
);
const allModerationCommentsChecked = computed(
  () =>
    moderationComments.value.length > 0 &&
    selectedModerationCommentIds.value.length === moderationComments.value.length
);
const allModerationQuestionsChecked = computed(
  () =>
    moderationQuestions.value.length > 0 &&
    selectedModerationQuestionIds.value.length === moderationQuestions.value.length
);
const eventTypeSeries = computed(() => adminOverview.value?.analytics?.event_type_counts || []);
const dailyEventSeries = computed(() => adminOverview.value?.analytics?.daily_events || []);
const eventTypeMaxCount = computed(() => {
  const max = Math.max(...eventTypeSeries.value.map((item) => Number(item.count) || 0), 0);
  return max || 1;
});
const dailyEventMaxCount = computed(() => {
  const max = Math.max(...dailyEventSeries.value.map((item) => Number(item.count) || 0), 0);
  return max || 1;
});
const securityTopIpMaxCount = computed(() => {
  const rows = Array.isArray(securitySummary.value?.top_failed_ips) ? securitySummary.value.top_failed_ips : [];
  const max = Math.max(...rows.map((item) => Number(item.count) || 0), 0);
  return max || 1;
});

function getErrorText(error, fallback = "操作失败") {
  const payload = error?.response?.data;
  if (!payload) return fallback;
  if (typeof payload === "string") return payload;
  if (typeof payload.detail === "string") return payload.detail;
  if (Array.isArray(payload)) return payload.join("；");
  if (typeof payload === "object") {
    const parts = [];
    for (const [field, value] of Object.entries(payload)) {
      if (Array.isArray(value)) {
        parts.push(`${field}: ${value.join("，")}`);
      } else if (typeof value === "string") {
        parts.push(`${field}: ${value}`);
      }
    }
    if (parts.length) return parts.join("；");
  }
  return fallback;
}

function unpackListPayload(data) {
  if (Array.isArray(data)) {
    return { results: data, count: data.length };
  }
  const results = Array.isArray(data?.results) ? data.results : [];
  const count = Number.isFinite(data?.count) ? data.count : results.length;
  return { results, count };
}

function appendUniqueById(baseList, extraList) {
  const existed = new Set(baseList.map((item) => item.id));
  const merged = [...baseList];
  for (const item of extraList) {
    if (!existed.has(item.id)) {
      existed.add(item.id);
      merged.push(item);
    }
  }
  return merged;
}

function updatePageMeta(meta, totalCount, loadedCount, page) {
  meta.count = totalCount;
  meta.page = page;
  meta.hasMore = loadedCount < totalCount;
}

function eventTypeBarPercent(value) {
  return Math.round(((Number(value) || 0) / eventTypeMaxCount.value) * 100);
}

function dailyEventBarPercent(value) {
  return Math.round(((Number(value) || 0) / dailyEventMaxCount.value) * 100);
}

function securityTopIpBarPercent(value) {
  return Math.round(((Number(value) || 0) / securityTopIpMaxCount.value) * 100);
}

function orderedCategories() {
  return [...categories.value].sort((a, b) => {
    const orderA = Number(a.order) || 0;
    const orderB = Number(b.order) || 0;
    if (orderA !== orderB) return orderA - orderB;
    return a.id - b.id;
  });
}

function syncSelectedIds(target, list) {
  const valid = new Set(list.map((item) => item.id));
  target.value = target.value.filter((id) => valid.has(id));
}

function toggleSelectAllUsers(checked) {
  selectedUserIds.value = checked ? users.value.map((item) => item.id) : [];
}

function toggleSelectAllTickets(checked) {
  selectedTicketIds.value = checked ? tickets.value.map((item) => item.id) : [];
}

function toggleSelectAllModerationArticles(checked) {
  selectedModerationArticleIds.value = checked ? moderationArticles.value.map((item) => item.id) : [];
}

function toggleSelectAllModerationComments(checked) {
  selectedModerationCommentIds.value = checked ? moderationComments.value.map((item) => item.id) : [];
}

function toggleSelectAllModerationQuestions(checked) {
  selectedModerationQuestionIds.value = checked ? moderationQuestions.value.map((item) => item.id) : [];
}

async function runBulk(requests, successText) {
  const results = await Promise.allSettled(requests);
  const successCount = results.filter((item) => item.status === "fulfilled").length;
  const failCount = results.length - successCount;
  if (successCount) {
    ui.success(`${successText}：成功 ${successCount} 条`);
  }
  if (failCount) {
    ui.error(`${successText}：失败 ${failCount} 条`);
  }
}

function notifyBulkSummary(summary, successText) {
  const successCount = Number(summary?.success || 0);
  const failCount = Number(summary?.failed || 0);
  if (successCount) {
    ui.success(`${successText}：成功 ${successCount} 条`);
  }
  if (failCount) {
    const sample = Array.isArray(summary?.results)
      ? summary.results.find((item) => item && item.success === false && item.detail)
      : null;
    ui.error(`${successText}：失败 ${failCount} 条${sample ? `（示例：${sample.detail}）` : ""}`);
  }
}

async function loadAnnouncements() {
  try {
    const { data } = await api.get("/announcements/", { params: { all: 1 } });
    announcements.value = data.results || data;
  } catch (error) {
    ui.error(getErrorText(error, "公告加载失败"));
  }
}

async function loadUsers(page = 1, append = false) {
  try {
    const params = { page };
    if (userFilters.role) params.role = userFilters.role;
    if (userFilters.is_active) params.is_active = userFilters.is_active;
    if (userFilters.is_banned) params.is_banned = userFilters.is_banned;
    if (userFilters.search.trim()) params.search = userFilters.search.trim();
    const { data } = await api.get("/users/", { params });
    const { results, count } = unpackListPayload(data);
    users.value = append ? appendUniqueById(users.value, results) : results;
    updatePageMeta(usersMeta, count, users.value.length, page);
    syncSelectedIds(selectedUserIds, users.value);
  } catch (error) {
    ui.error(getErrorText(error, "用户列表加载失败"));
  }
}

async function loadTickets(page = 1, append = false) {
  try {
    const params = { page };
    if (ticketFilters.status) params.status = ticketFilters.status;
    if (ticketFilters.kind) params.kind = ticketFilters.kind;
    if (ticketFilters.author.trim()) params.author = ticketFilters.author.trim();
    if (ticketFilters.assignee) params.assignee = ticketFilters.assignee;
    if (ticketFilters.order && ticketFilters.order !== "updated_newest") params.order = ticketFilters.order;
    if (ticketFilters.search.trim()) params.search = ticketFilters.search.trim();

    const { data } = await api.get("/issues/", { params });
    const { results, count } = unpackListPayload(data);
    const mapped = results.map((item) => ({
      ...item,
      _nextStatus: item.status,
      _assignTo: item.assignee?.id ? String(item.assignee.id) : "",
      _note: item.resolution_note || "",
    }));
    tickets.value = append ? appendUniqueById(tickets.value, mapped) : mapped;
    updatePageMeta(ticketsMeta, count, tickets.value.length, page);
    syncSelectedIds(selectedTicketIds, tickets.value);
  } catch (error) {
    ui.error(getErrorText(error, "工单加载失败"));
  }
}

async function loadAssigneeOptions() {
  try {
    const { data } = await api.get("/users/assignees/");
    assigneeOptions.value = Array.isArray(data) ? data : data.results || [];
  } catch (error) {
    ui.error(getErrorText(error, "处理人列表加载失败"));
  }
}

async function loadExtensionPages() {
  try {
    const { data } = await api.get("/pages/", { params: { include_disabled: 1 } });
    extensionPages.value = data.results || data;
  } catch (error) {
    ui.error(getErrorText(error, "扩展页面加载失败"));
  }
}

async function loadCategories() {
  try {
    const { data } = await api.get("/categories/", { params: { include_hidden: 1 } });
    categories.value = data.results || data;
  } catch (error) {
    ui.error(getErrorText(error, "分类加载失败"));
  }
}

async function loadModerationArticles(page = 1, append = false) {
  try {
    const params = { order: "created_newest", page };
    if (moderationArticleFilters.search.trim()) params.search = moderationArticleFilters.search.trim();
    if (moderationArticleFilters.status) params.status = moderationArticleFilters.status;
    if (moderationArticleFilters.category) params.category = moderationArticleFilters.category;
    if (moderationArticleFilters.author.trim()) params.author = moderationArticleFilters.author.trim();
    const { data } = await api.get("/articles/", { params });
    const { results, count } = unpackListPayload(data);
    moderationArticles.value = append ? appendUniqueById(moderationArticles.value, results) : results;
    updatePageMeta(moderationArticlesMeta, count, moderationArticles.value.length, page);
    syncSelectedIds(selectedModerationArticleIds, moderationArticles.value);
  } catch (error) {
    ui.error(getErrorText(error, "文章列表加载失败"));
  }
}

async function loadModerationComments(page = 1, append = false) {
  try {
    const params = { page };
    if (moderationCommentFilters.search.trim()) params.search = moderationCommentFilters.search.trim();
    if (moderationCommentFilters.status) params.status = moderationCommentFilters.status;
    if (moderationCommentFilters.author.trim()) params.author = moderationCommentFilters.author.trim();
    if (moderationCommentFilters.article.trim()) params.article = moderationCommentFilters.article.trim();
    const { data } = await api.get("/comments/", { params });
    const { results, count } = unpackListPayload(data);
    moderationComments.value = append ? appendUniqueById(moderationComments.value, results) : results;
    updatePageMeta(moderationCommentsMeta, count, moderationComments.value.length, page);
    syncSelectedIds(selectedModerationCommentIds, moderationComments.value);
  } catch (error) {
    ui.error(getErrorText(error, "评论列表加载失败"));
  }
}

async function loadModerationQuestions(page = 1, append = false) {
  try {
    const params = { page, order: "created_newest" };
    if (moderationQuestionFilters.search.trim()) params.search = moderationQuestionFilters.search.trim();
    if (moderationQuestionFilters.status) params.status = moderationQuestionFilters.status;
    if (moderationQuestionFilters.category) params.category = moderationQuestionFilters.category;
    if (moderationQuestionFilters.author.trim()) params.author = moderationQuestionFilters.author.trim();
    const { data } = await api.get("/questions/", { params });
    const { results, count } = unpackListPayload(data);
    moderationQuestions.value = append ? appendUniqueById(moderationQuestions.value, results) : results;
    updatePageMeta(moderationQuestionsMeta, count, moderationQuestions.value.length, page);
    syncSelectedIds(selectedModerationQuestionIds, moderationQuestions.value);
  } catch (error) {
    ui.error(getErrorText(error, "问题列表加载失败"));
  }
}

async function loadEvents(page = 1, append = false) {
  try {
    const { data } = await api.get("/events/", { params: buildEventParams(page) });
    const { results, count } = unpackListPayload(data);
    events.value = append ? appendUniqueById(events.value, results) : results;
    updatePageMeta(eventsMeta, count, events.value.length, page);
  } catch (error) {
    ui.error(getErrorText(error, "日志加载失败"));
  }
}

async function loadSecurityLogs(page = 1, append = false) {
  try {
    const { data } = await api.get("/security-logs/", { params: buildSecurityParams(page) });
    const { results, count } = unpackListPayload(data);
    securityLogs.value = append ? appendUniqueById(securityLogs.value, results) : results;
    updatePageMeta(securityLogsMeta, count, securityLogs.value.length, page);
  } catch (error) {
    ui.error(getErrorText(error, "安全日志加载失败"));
  }
}

async function loadSecuritySummary() {
  securitySummaryLoading.value = true;
  try {
    const { data } = await api.get("/security-logs/summary/", {
      params: { window_hours: securityWindowHours.value },
    });
    securitySummary.value = data;
  } catch (error) {
    ui.error(getErrorText(error, "安全概览加载失败"));
  } finally {
    securitySummaryLoading.value = false;
  }
}

function buildEventParams(page = 1) {
  const params = { page };
  if (eventFilters.event_type) params.event_type = eventFilters.event_type;
  if (eventFilters.user.trim()) params.user = eventFilters.user.trim();
  if (eventFilters.target_type.trim()) params.target_type = eventFilters.target_type.trim();
  if (eventFilters.search.trim()) params.search = eventFilters.search.trim();
  if (eventFilters.start_at) params.start_at = eventFilters.start_at;
  if (eventFilters.end_at) params.end_at = eventFilters.end_at;
  return params;
}

function buildSecurityParams(page = 1) {
  const params = { page };
  if (securityFilters.event_type) params.event_type = securityFilters.event_type;
  if (securityFilters.success) params.success = securityFilters.success;
  if (securityFilters.username.trim()) params.username = securityFilters.username.trim();
  if (securityFilters.ip.trim()) params.ip = securityFilters.ip.trim();
  if (securityFilters.detail.trim()) params.detail = securityFilters.detail.trim();
  if (securityFilters.start_at) params.start_at = securityFilters.start_at;
  if (securityFilters.end_at) params.end_at = securityFilters.end_at;
  return params;
}

async function loadAdminOverview() {
  overviewLoading.value = true;
  try {
    const { data } = await api.get("/admin/overview/");
    adminOverview.value = data;
  } catch (error) {
    ui.error(getErrorText(error, "概览加载失败"));
  } finally {
    overviewLoading.value = false;
  }
}

async function loadMoreUsers() {
  if (!usersMeta.hasMore) return;
  await loadUsers(usersMeta.page + 1, true);
}

async function loadMoreTickets() {
  if (!ticketsMeta.hasMore) return;
  await loadTickets(ticketsMeta.page + 1, true);
}

async function loadMoreModerationArticles() {
  if (!moderationArticlesMeta.hasMore) return;
  await loadModerationArticles(moderationArticlesMeta.page + 1, true);
}

async function loadMoreModerationComments() {
  if (!moderationCommentsMeta.hasMore) return;
  await loadModerationComments(moderationCommentsMeta.page + 1, true);
}

async function loadMoreModerationQuestions() {
  if (!moderationQuestionsMeta.hasMore) return;
  await loadModerationQuestions(moderationQuestionsMeta.page + 1, true);
}

async function loadMoreEvents() {
  if (!eventsMeta.hasMore) return;
  await loadEvents(eventsMeta.page + 1, true);
}

async function loadMoreSecurityLogs() {
  if (!securityLogsMeta.hasMore) return;
  await loadSecurityLogs(securityLogsMeta.page + 1, true);
}

function resetAnnouncementForm() {
  editingAnnouncementId.value = null;
  announceForm.title = "";
  announceForm.content_md = "";
  announceForm.priority = 0;
  announceForm.is_published = true;
}

function resetUserFilters() {
  userFilters.role = "";
  userFilters.is_active = "";
  userFilters.is_banned = "";
  userFilters.search = "";
  loadUsers();
}

function startEditAnnouncement(item) {
  editingAnnouncementId.value = item.id;
  announceForm.title = item.title;
  announceForm.content_md = item.content_md || "";
  announceForm.priority = item.priority || 0;
  announceForm.is_published = !!item.is_published;
}

async function saveAnnouncement() {
  if (!announceForm.title || !announceForm.content_md) return;
  try {
    const payload = {
      title: announceForm.title,
      content_md: announceForm.content_md,
      priority: announceForm.priority,
      is_published: announceForm.is_published,
    };

    if (editingAnnouncementId.value) {
      await api.patch(`/announcements/${editingAnnouncementId.value}/`, payload);
      ui.success("公告已更新");
    } else {
      await api.post("/announcements/", payload);
      ui.success("公告发布成功");
    }

    resetAnnouncementForm();
    await loadAnnouncements();
  } catch (error) {
    ui.error(getErrorText(error, "公告保存失败"));
  }
}

async function toggleAnnouncementPublished(item) {
  try {
    await api.patch(`/announcements/${item.id}/`, { is_published: !item.is_published });
    ui.success(item.is_published ? "公告已下线" : "公告已发布");
    await loadAnnouncements();
  } catch (error) {
    ui.error(getErrorText(error, "公告状态更新失败"));
  }
}

async function deleteAnnouncement(item) {
  if (!window.confirm(`确认删除公告「${item.title}」？`)) return;
  try {
    await api.delete(`/announcements/${item.id}/`);
    if (editingAnnouncementId.value === item.id) {
      resetAnnouncementForm();
    }
    ui.success("公告已删除");
    await loadAnnouncements();
  } catch (error) {
    ui.error(getErrorText(error, "删除公告失败"));
  }
}

async function banUser(userId) {
  try {
    await api.post(`/users/${userId}/ban/`, { reason: "violated rules" });
    ui.success("用户已封禁");
    await loadUsers();
  } catch (error) {
    ui.error(getErrorText(error, "封禁失败"));
  }
}

async function unbanUser(userId) {
  try {
    await api.post(`/users/${userId}/unban/`);
    ui.success("用户已解封");
    await loadUsers();
  } catch (error) {
    ui.error(getErrorText(error, "解封失败"));
  }
}

async function softDeleteUser(user) {
  if (!window.confirm(`确认删除用户「${user.username}」？`)) return;
  try {
    await api.post(`/users/${user.id}/soft_delete/`);
    ui.success("用户已删除");
    await loadUsers();
  } catch (error) {
    ui.error(getErrorText(error, "删除用户失败"));
  }
}

async function reactivateUser(userId) {
  try {
    await api.post(`/users/${userId}/reactivate/`);
    ui.success("用户已恢复");
    await loadUsers();
  } catch (error) {
    ui.error(getErrorText(error, "恢复用户失败"));
  }
}

async function setRole(userId, role) {
  try {
    await api.post(`/users/${userId}/set_role/`, { role });
    ui.success("角色更新成功");
    await loadUsers();
  } catch (error) {
    ui.error(getErrorText(error, "角色更新失败"));
  }
}

async function bulkBanUsers() {
  if (!selectedUserIds.value.length) {
    ui.info("请先选择要封禁的用户");
    return;
  }
  if (!window.confirm(`确认封禁选中的 ${selectedUserIds.value.length} 个用户？`)) return;
  await runUserBulkAction({
    action: "ban",
    extraPayload: { reason: "bulk moderation" },
    successText: "批量封禁",
  });
}

async function bulkUnbanUsers() {
  if (!selectedUserIds.value.length) {
    ui.info("请先选择要解封的用户");
    return;
  }
  await runUserBulkAction({
    action: "unban",
    successText: "批量解封",
  });
}

async function bulkReactivateUsers() {
  if (!selectedUserIds.value.length) {
    ui.info("请先选择要恢复的用户");
    return;
  }
  await runUserBulkAction({
    action: "reactivate",
    successText: "批量恢复用户",
  });
}

async function bulkSoftDeleteUsers() {
  if (!selectedUserIds.value.length) {
    ui.info("请先选择要删除的用户");
    return;
  }
  if (!window.confirm(`确认删除选中的 ${selectedUserIds.value.length} 个用户？`)) return;
  await runUserBulkAction({
    action: "soft_delete",
    successText: "批量删除用户",
  });
}

async function bulkSetRole() {
  if (!selectedUserIds.value.length) {
    ui.info("请先选择要调整角色的用户");
    return;
  }
  await runUserBulkAction({
    action: "set_role",
    extraPayload: { role: bulkRole.value },
    successText: "批量角色调整",
  });
}

async function runUserBulkAction({ action, extraPayload = {}, successText }) {
  try {
    const { data } = await api.post("/users/bulk-action/", {
      ids: selectedUserIds.value,
      action,
      ...extraPayload,
    });
    notifyBulkSummary(data, successText);
    await loadUsers();
  } catch (error) {
    ui.error(getErrorText(error, `${successText}失败`));
  }
}

async function updateTicketStatus(ticket) {
  try {
    const payload = {
      status: ticket._nextStatus,
      resolution_note: ticket._note,
      assign_to: ticket._assignTo ? Number(ticket._assignTo) : null,
    };
    await api.post(`/issues/${ticket.id}/set_status/`, payload);
    ui.success("工单状态已更新");
    await Promise.all([loadTickets(), loadEvents(), loadAdminOverview()]);
  } catch (error) {
    ui.error(getErrorText(error, "工单更新失败"));
  }
}

async function bulkUpdateTicketStatus() {
  if (!selectedTicketIds.value.length) {
    ui.info("请先选择要处理的工单");
    return;
  }
  try {
    const payload = {
      ids: selectedTicketIds.value,
      status: bulkTicketForm.status,
      resolution_note: bulkTicketForm.note,
    };
    if (bulkTicketForm.assign_to !== "__keep__") {
      payload.assign_to = bulkTicketForm.assign_to === "__none__" ? null : Number(bulkTicketForm.assign_to);
    }

    const { data } = await api.post("/issues/bulk-set-status/", payload);
    notifyBulkSummary(data, "批量工单更新");
    await Promise.all([loadTickets(), loadEvents(), loadAdminOverview()]);
  } catch (error) {
    ui.error(getErrorText(error, "批量工单更新失败"));
  }
}

function resetTicketFilters() {
  ticketFilters.status = "";
  ticketFilters.kind = "";
  ticketFilters.author = "";
  ticketFilters.assignee = "";
  ticketFilters.order = "updated_newest";
  ticketFilters.search = "";
  loadTickets();
}

function resetModerationArticleFilters() {
  moderationArticleFilters.search = "";
  moderationArticleFilters.status = "";
  moderationArticleFilters.category = "";
  moderationArticleFilters.author = "";
  loadModerationArticles();
}

function resetModerationCommentFilters() {
  moderationCommentFilters.search = "";
  moderationCommentFilters.status = "";
  moderationCommentFilters.author = "";
  moderationCommentFilters.article = "";
  loadModerationComments();
}

function resetModerationQuestionFilters() {
  moderationQuestionFilters.search = "";
  moderationQuestionFilters.status = "";
  moderationQuestionFilters.category = "";
  moderationQuestionFilters.author = "";
  loadModerationQuestions();
}

function resetEventFilters() {
  eventFilters.event_type = "";
  eventFilters.user = "";
  eventFilters.target_type = "";
  eventFilters.search = "";
  eventFilters.start_at = "";
  eventFilters.end_at = "";
  loadEvents();
}

function resetSecurityFilters() {
  securityFilters.event_type = "";
  securityFilters.success = "";
  securityFilters.username = "";
  securityFilters.ip = "";
  securityFilters.detail = "";
  securityFilters.start_at = "";
  securityFilters.end_at = "";
  loadSecurityLogs();
}

async function exportEvents() {
  try {
    const response = await api.get("/events/export/", {
      params: buildEventParams(1),
      responseType: "blob",
    });
    const blob = new Blob([response.data], { type: "text/csv;charset=utf-8;" });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `algowiki-events-${Date.now()}.csv`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
    ui.success("日志已导出");
  } catch (error) {
    ui.error(getErrorText(error, "导出日志失败"));
  }
}

async function exportSecurityLogs() {
  try {
    const response = await api.get("/security-logs/export/", {
      params: buildSecurityParams(1),
      responseType: "blob",
    });
    const blob = new Blob([response.data], { type: "text/csv;charset=utf-8;" });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `algowiki-security-${Date.now()}.csv`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
    ui.success("安全日志已导出");
  } catch (error) {
    ui.error(getErrorText(error, "导出安全日志失败"));
  }
}

function resetPageForm() {
  editingPageSlug.value = "";
  pageForm.title = "";
  pageForm.slug = "";
  pageForm.description = "";
  pageForm.content_md = "";
  pageForm.access_level = "public";
  pageForm.is_enabled = true;
}

function startEditPage(item) {
  editingPageSlug.value = item.slug;
  pageForm.title = item.title;
  pageForm.slug = item.slug;
  pageForm.description = item.description || "";
  pageForm.content_md = item.content_md || "";
  pageForm.access_level = item.access_level;
  pageForm.is_enabled = item.is_enabled;
}

async function savePage() {
  if (!pageForm.title.trim() || !pageForm.slug.trim()) return;

  const payload = {
    title: pageForm.title.trim(),
    slug: pageForm.slug.trim(),
    description: pageForm.description,
    content_md: pageForm.content_md,
    access_level: pageForm.access_level,
    is_enabled: pageForm.is_enabled,
  };

  try {
    if (editingPageSlug.value) {
      await api.put(`/pages/${editingPageSlug.value}/`, payload);
      ui.success("扩展页面已保存");
    } else {
      await api.post("/pages/", payload);
      ui.success("扩展页面已创建");
    }

    resetPageForm();
    await loadExtensionPages();
  } catch (error) {
    ui.error(getErrorText(error, "扩展页面保存失败"));
  }
}

async function togglePageEnabled(item) {
  try {
    await api.patch(`/pages/${item.slug}/`, { is_enabled: !item.is_enabled });
    ui.success(item.is_enabled ? "页面已停用" : "页面已启用");
    await loadExtensionPages();
  } catch (error) {
    ui.error(getErrorText(error, "页面状态更新失败"));
  }
}

async function deletePage(item) {
  if (!window.confirm(`确认删除扩展页「${item.title}」？`)) return;
  try {
    await api.delete(`/pages/${item.slug}/`);
    if (editingPageSlug.value === item.slug) {
      resetPageForm();
    }
    ui.success("扩展页面已删除");
    await loadExtensionPages();
  } catch (error) {
    ui.error(getErrorText(error, "删除页面失败"));
  }
}

function resetCategoryForm() {
  editingCategoryId.value = null;
  categoryForm.name = "";
  categoryForm.slug = "";
  categoryForm.description = "";
  categoryForm.parent = "";
  categoryForm.moderation_scope = "public";
  categoryForm.order = 0;
  categoryForm.is_visible = true;
}

function startEditCategory(item) {
  editingCategoryId.value = item.id;
  categoryForm.name = item.name;
  categoryForm.slug = item.slug || "";
  categoryForm.description = item.description || "";
  categoryForm.parent = item.parent ? String(item.parent) : "";
  categoryForm.moderation_scope = item.moderation_scope || "public";
  categoryForm.order = item.order || 0;
  categoryForm.is_visible = !!item.is_visible;
}

function getCategoryPayload() {
  const payload = {
    name: categoryForm.name.trim(),
    slug: categoryForm.slug.trim(),
    description: categoryForm.description,
    parent: categoryForm.parent ? Number(categoryForm.parent) : null,
    moderation_scope: categoryForm.moderation_scope,
    order: Number(categoryForm.order) || 0,
    is_visible: categoryForm.is_visible,
  };
  if (!payload.slug) delete payload.slug;
  return payload;
}

async function saveCategory() {
  if (!categoryForm.name.trim()) return;
  const payload = getCategoryPayload();
  try {
    if (editingCategoryId.value) {
      await api.patch(`/categories/${editingCategoryId.value}/`, payload);
      ui.success("分类已保存");
    } else {
      await api.post("/categories/", payload);
      ui.success("分类已创建");
    }

    resetCategoryForm();
    await loadCategories();
  } catch (error) {
    ui.error(getErrorText(error, "分类保存失败"));
  }
}

async function toggleCategoryVisibility(item) {
  try {
    await api.patch(`/categories/${item.id}/`, { is_visible: !item.is_visible });
    ui.success(item.is_visible ? "分类已隐藏" : "分类已显示");
    await loadCategories();
  } catch (error) {
    ui.error(getErrorText(error, "分类显示状态更新失败"));
  }
}

async function toggleCategoryScope(item) {
  const nextScope = item.moderation_scope === "public" ? "school" : "public";
  try {
    await api.patch(`/categories/${item.id}/`, { moderation_scope: nextScope });
    ui.success(`分类作用域已切换为 ${nextScope}`);
    await loadCategories();
  } catch (error) {
    ui.error(getErrorText(error, "分类作用域切换失败"));
  }
}

function isCategoryAtTop(item) {
  const ordered = orderedCategories();
  return ordered[0]?.id === item.id;
}

function isCategoryAtBottom(item) {
  const ordered = orderedCategories();
  return ordered[ordered.length - 1]?.id === item.id;
}

async function moveCategory(item, direction) {
  const ordered = orderedCategories();
  const index = ordered.findIndex((entry) => entry.id === item.id);
  const targetIndex = index + direction;
  if (index < 0 || targetIndex < 0 || targetIndex >= ordered.length) return;

  const swapped = [...ordered];
  [swapped[index], swapped[targetIndex]] = [swapped[targetIndex], swapped[index]];
  const orderMap = new Map(swapped.map((entry, idx) => [entry.id, idx * 10]));
  const target = ordered[targetIndex];

  try {
    await Promise.all([
      api.patch(`/categories/${item.id}/`, { order: orderMap.get(item.id) }),
      api.patch(`/categories/${target.id}/`, { order: orderMap.get(target.id) }),
    ]);
    await loadCategories();
    ui.success("分类顺序已更新");
  } catch (error) {
    ui.error(getErrorText(error, "分类顺序调整失败"));
  }
}

async function normalizeCategoryOrder() {
  const ordered = orderedCategories();
  if (ordered.length < 2) return;
  try {
    await Promise.all(
      ordered.map((item, index) => api.patch(`/categories/${item.id}/`, { order: index * 10 }))
    );
    await loadCategories();
    ui.success("分类排序已标准化");
  } catch (error) {
    ui.error(getErrorText(error, "分类排序标准化失败"));
  }
}

async function deleteCategory(item) {
  if (!window.confirm(`确认删除分类「${item.name}」？`)) return;
  try {
    await api.delete(`/categories/${item.id}/`);
    if (editingCategoryId.value === item.id) {
      resetCategoryForm();
    }
    ui.success("分类已删除");
    await loadCategories();
  } catch (error) {
    ui.error(getErrorText(error, "删除分类失败（可能存在关联文章）"));
  }
}

async function reloadModerationContent() {
  await Promise.all([loadModerationArticles(), loadModerationComments(), loadModerationQuestions()]);
}

async function publishArticle(item) {
  try {
    await api.post(`/articles/${item.id}/publish/`);
    ui.success("文章已发布");
    await Promise.all([loadModerationArticles(), loadEvents(), loadAdminOverview()]);
  } catch (error) {
    ui.error(getErrorText(error, "发布文章失败"));
  }
}

async function deleteArticle(item) {
  if (!window.confirm(`确认删除文章「${item.title}」？`)) return;
  try {
    await api.delete(`/articles/${item.id}/`);
    ui.success("文章已删除");
    await Promise.all([loadModerationArticles(), loadEvents(), loadAdminOverview()]);
  } catch (error) {
    ui.error(getErrorText(error, "删除文章失败"));
  }
}

async function hideComment(item) {
  if (item.status === "hidden") return;
  try {
    await api.delete(`/comments/${item.id}/`);
    ui.success("评论已隐藏");
    await Promise.all([loadModerationComments(), loadEvents(), loadAdminOverview()]);
  } catch (error) {
    ui.error(getErrorText(error, "隐藏评论失败"));
  }
}

async function closeQuestionItem(item) {
  if (item.status === "closed") return;
  try {
    await api.post(`/questions/${item.id}/close/`);
    ui.success("问题已关闭");
    await Promise.all([loadModerationQuestions(), loadEvents(), loadAdminOverview()]);
  } catch (error) {
    ui.error(getErrorText(error, "关闭问题失败"));
  }
}

async function reopenQuestionItem(item) {
  if (item.status === "open") return;
  try {
    await api.post(`/questions/${item.id}/reopen/`);
    ui.success("问题已重开");
    await Promise.all([loadModerationQuestions(), loadEvents(), loadAdminOverview()]);
  } catch (error) {
    ui.error(getErrorText(error, "重开问题失败"));
  }
}

async function hideQuestionItem(item) {
  if (item.status === "hidden") return;
  try {
    await api.delete(`/questions/${item.id}/`);
    ui.success("问题已隐藏");
    await Promise.all([loadModerationQuestions(), loadEvents(), loadAdminOverview()]);
  } catch (error) {
    ui.error(getErrorText(error, "隐藏问题失败"));
  }
}

async function bulkPublishArticles() {
  if (!selectedModerationArticleIds.value.length) {
    ui.info("请先选择要发布的文章");
    return;
  }
  await runArticleBulkModeration("publish", "批量发布文章");
}

async function bulkDeleteArticles() {
  if (!selectedModerationArticleIds.value.length) {
    ui.info("请先选择要删除的文章");
    return;
  }
  if (!window.confirm(`确认删除选中的 ${selectedModerationArticleIds.value.length} 篇文章？`)) return;
  await runArticleBulkModeration("delete", "批量删除文章");
}

async function bulkHideComments() {
  if (!selectedModerationCommentIds.value.length) {
    ui.info("请先选择要隐藏的评论");
    return;
  }
  try {
    const { data } = await api.post("/comments/bulk-hide/", {
      ids: selectedModerationCommentIds.value,
    });
    notifyBulkSummary(data, "批量隐藏评论");
    await Promise.all([loadModerationComments(), loadEvents(), loadAdminOverview()]);
  } catch (error) {
    ui.error(getErrorText(error, "批量隐藏评论失败"));
  }
}

async function bulkCloseQuestions() {
  if (!selectedModerationQuestionIds.value.length) {
    ui.info("请先选择要关闭的问题");
    return;
  }
  await runQuestionBulkModeration("close", "批量关闭问题");
}

async function bulkReopenQuestions() {
  if (!selectedModerationQuestionIds.value.length) {
    ui.info("请先选择要重开的问题");
    return;
  }
  await runQuestionBulkModeration("reopen", "批量重开问题");
}

async function bulkHideQuestions() {
  if (!selectedModerationQuestionIds.value.length) {
    ui.info("请先选择要隐藏的问题");
    return;
  }
  await runQuestionBulkModeration("hide", "批量隐藏问题");
}

async function runArticleBulkModeration(action, successText) {
  try {
    const { data } = await api.post("/articles/bulk-moderate/", {
      ids: selectedModerationArticleIds.value,
      action,
    });
    notifyBulkSummary(data, successText);
    await Promise.all([loadModerationArticles(), loadEvents(), loadAdminOverview()]);
  } catch (error) {
    ui.error(getErrorText(error, `${successText}失败`));
  }
}

async function runQuestionBulkModeration(action, successText) {
  try {
    const { data } = await api.post("/questions/bulk-moderate/", {
      ids: selectedModerationQuestionIds.value,
      action,
    });
    notifyBulkSummary(data, successText);
    await Promise.all([loadModerationQuestions(), loadEvents(), loadAdminOverview()]);
  } catch (error) {
    ui.error(getErrorText(error, `${successText}失败`));
  }
}

function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function formatEventType(value) {
  const labels = {
    star: "收藏",
    comment: "评论",
    issue: "Issue/Request",
    revision: "修订",
    question: "提问",
    answer: "回答",
    announcement: "公告",
    admin: "管理操作",
  };
  return labels[value] || value || "未知事件";
}

function formatSecurityEventType(value) {
  const labels = {
    login_success: "登录成功",
    login_failed: "登录失败",
    login_locked: "登录锁定",
    login_denied: "登录拒绝",
    register_success: "注册成功",
    logout: "退出登录",
    password_changed: "密码修改",
    user_banned: "账号封禁",
    user_unbanned: "账号解封",
    user_soft_deleted: "账号软删除",
    user_reactivated: "账号恢复",
    user_role_changed: "角色变更",
  };
  return labels[value] || value || "未知事件";
}

function renderPayload(payload) {
  if (!payload || typeof payload !== "object") {
    return "{}";
  }
  const pairs = Object.entries(payload)
    .map(([key, value]) => `${key}=${typeof value === "string" ? value : JSON.stringify(value)}`)
    .join(" | ");
  return pairs || "{}";
}

onMounted(async () => {
  await Promise.all([
    loadAdminOverview(),
    loadAnnouncements(),
    loadUsers(),
    loadAssigneeOptions(),
    loadTickets(),
    loadExtensionPages(),
    loadCategories(),
    reloadModerationContent(),
    loadSecuritySummary(),
    loadSecurityLogs(),
    loadEvents(),
  ]);
});
</script>

<style scoped>
.admin-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.admin-card {
  border: 1px solid var(--hairline);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.58);
  padding: 14px;
  box-shadow: var(--shadow-sm);
}

.admin-card.full {
  grid-column: 1 / -1;
}

.admin-card h2 {
  font-size: 32px;
  margin-bottom: 10px;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.overview-item {
  border-radius: 12px;
  background: rgba(245, 250, 255, 0.82);
  padding: 10px 12px;
  display: grid;
  gap: 3px;
}

.overview-item strong {
  font-size: 26px;
}

.overview-item span {
  font-size: 14px;
  color: #5d6673;
}

.overview-actions {
  margin-top: 10px;
}

.overview-analytics {
  margin-top: 12px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.overview-panel {
  border-radius: 12px;
  padding: 10px 12px;
  background: rgba(245, 250, 255, 0.82);
}

.overview-panel h3 {
  font-size: 18px;
  margin-bottom: 8px;
}

.overview-bar-list,
.overview-day-list {
  display: grid;
  gap: 6px;
}

.overview-bar-row,
.overview-day-row {
  display: grid;
  grid-template-columns: 90px minmax(0, 1fr) 42px;
  align-items: center;
  gap: 8px;
}

.overview-day-row {
  grid-template-columns: 52px minmax(0, 1fr) 42px;
}

.overview-bar-row span,
.overview-day-row span {
  color: #586270;
  font-size: 13px;
}

.overview-bar-row strong,
.overview-day-row strong {
  font-size: 13px;
  color: #2f3742;
  text-align: right;
}

.overview-bar-track {
  height: 8px;
  border-radius: 999px;
  background: rgba(30, 41, 59, 0.1);
  overflow: hidden;
}

.overview-bar-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #4f8fff, #6d6bff);
}

.sub-title {
  margin: 12px 0 8px;
  font-size: 22px;
}

.announce-form {
  display: grid;
  gap: 8px;
  margin-bottom: 12px;
}

.announce-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.bulk-tools {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}

.bulk-check {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  color: #2f3742;
}

.bulk-select {
  width: 140px;
}

.bulk-input {
  width: min(320px, 100%);
}

.notice {
  padding: 10px 12px;
  margin-top: 10px;
  border-radius: 10px;
  background: rgba(245, 250, 255, 0.82);
}

.notice-head {
  display: flex;
  justify-content: space-between;
  gap: 8px;
}

.notice-tools {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.user-row,
.ticket-row {
  padding: 11px 12px;
  margin-top: 10px;
  border-radius: 10px;
  background: rgba(245, 250, 255, 0.82);
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.user-row:first-of-type,
.ticket-row:first-of-type {
  margin-top: 0;
}

.user-actions,
.ticket-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: flex-end;
}

.ticket-main {
  min-width: 0;
}

.ticket-content {
  margin: 6px 0 0;
  font-size: 16px;
  color: #2f3742;
  line-height: 1.56;
}

.ticket-actions {
  width: 280px;
  align-content: flex-start;
}

.page-panel {
  display: grid;
  gap: 8px;
  margin-bottom: 12px;
}

.page-form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.category-form-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.category-visible {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.page-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.page-row {
  padding: 11px 12px;
  margin-top: 10px;
  border-radius: 10px;
  background: rgba(245, 250, 255, 0.82);
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.category-row {
  padding: 11px 12px;
  margin-top: 10px;
  border-radius: 10px;
  background: rgba(245, 250, 255, 0.82);
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.page-tools {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}

@media (max-width: 1100px) {
  .admin-layout {
    grid-template-columns: 1fr;
  }

  .ticket-row {
    flex-direction: column;
  }

  .ticket-actions {
    width: 100%;
  }

  .page-row {
    flex-direction: column;
  }

  .category-row {
    flex-direction: column;
  }

  .page-tools {
    justify-content: flex-start;
  }
}

@media (max-width: 640px) {
  .announce-actions {
    align-items: stretch;
  }

  .page-form-grid {
    grid-template-columns: 1fr;
  }

  .category-form-grid {
    grid-template-columns: 1fr;
  }

  .overview-grid {
    grid-template-columns: 1fr 1fr;
  }

  .overview-analytics {
    grid-template-columns: 1fr;
  }

  .user-actions,
  .ticket-actions,
  .page-tools {
    width: 100%;
  }

  .bulk-tools {
    align-items: stretch;
  }

  .bulk-select,
  .bulk-input {
    width: 100%;
  }
}
</style>

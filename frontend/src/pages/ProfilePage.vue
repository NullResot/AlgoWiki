<template>
  <section v-if="profile" class="profile-layout">
    <article class="profile-main">
      <div class="profile-shell">
        <aside class="profile-sidebar" aria-label="Profile sections">
          <section class="sidebar-card sidebar-summary">
            <div class="sidebar-profile">
              <img v-if="profile.user.avatar_url" class="sidebar-avatar" :src="profile.user.avatar_url" alt="avatar" />
              <div v-else class="sidebar-avatar sidebar-avatar--fallback">{{ initials(profile.user.username) }}</div>
              <div class="sidebar-profile__body">
                <h2>{{ profile.user.username }}</h2>
                <p class="meta">{{ profile.user.role }}</p>
                <p class="meta">{{ profile.user.school_name || "暂无学校信息" }}</p>
                <p class="meta">
                  手机号：
                  <span class="pill" :class="{ 'pill-success': phoneVerification.status === 'verified' }">
                    {{ formatPhoneVerificationStatus(phoneVerification.status) }}
                  </span>
                </p>
                <button
                  v-if="phoneVerification.status !== 'verified'"
                  class="btn btn-mini btn-accent sidebar-action"
                  type="button"
                  @click="openPhoneVerificationModal"
                >
                  手机号验证
                </button>
              </div>
            </div>
          </section>

          <nav class="profile-nav">
            <div v-for="group in profileNavGroups" :key="group.title" class="profile-nav-group">
              <p class="profile-nav-title">{{ group.title }}</p>
              <button
                v-for="item in group.items"
                :key="item.key"
                class="profile-nav-item"
                :class="{ 'is-active': activeTab === item.key }"
                type="button"
                @click="activateTab(item.key)"
              >
                <span class="profile-nav-icon" aria-hidden="true">{{ item.icon }}</span>
                <span>{{ item.label }}</span>
              </button>
            </div>
          </nav>
        </aside>

        <div class="profile-content">
      <header class="profile-headline">
        <div>
          <p class="kicker">个人中心</p>
          <h1>{{ activeProfileSection.title }}</h1>
          <p class="meta">{{ activeProfileSection.description }}</p>
        </div>
      </header>

      <section v-show="profileUtilityTabs.includes(activeTab)" class="tab-panel">
        <div v-show="activeTab === 'profile'" class="profile-head profile-overview" id="profile-summary">
          <div class="profile-identity">
            <div class="profile-avatar-edit">
              <img v-if="currentAvatarPreview" class="avatar" :src="currentAvatarPreview" alt="avatar" />
              <div v-else class="avatar avatar--fallback">{{ initials(profile.user.username) }}</div>
              <template v-if="profileEditVisible">
                <input
                  ref="avatarInputRef"
                  class="visually-hidden"
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  @change="onAvatarSelected"
                />
                <div class="profile-avatar-actions">
                  <button class="btn btn-mini" type="button" @click="pickAvatar">
                    {{ avatarFile ? "重新选择头像" : "上传头像" }}
                  </button>
                  <button v-if="avatarFile" class="btn btn-mini" type="button" @click="clearSelectedAvatar">
                    取消选择
                  </button>
                </div>
              </template>
            </div>
            <div class="profile-identity__body">
              <input
                v-if="profileEditVisible"
                class="input profile-inline-name"
                v-model="profileForm.username"
                placeholder="昵称"
              />
              <h2 v-else>{{ profile.user.username }}</h2>
              <p class="meta">{{ formatRole(profile.user.role) }}</p>
              <p v-if="profileEditVisible" class="meta">支持 JPG、PNG、WebP 头像，单张最大 2MB。</p>
            </div>
          </div>

          <section class="section-block profile-overview-card">
            <div class="profile-overview-card__head">
              <div>
                <h3>资料概览</h3>
                <p class="meta">展示账号身份、联系方式与学习资料。</p>
              </div>
              <div class="profile-edit-actions">
                <button
                  v-if="!profileEditVisible"
                  class="btn btn-mini"
                  type="button"
                  @click="toggleProfileEditor"
                >
                  编辑资料
                </button>
                <template v-else>
                  <button class="btn btn-mini btn-accent" type="button" :disabled="savingProfile" @click="saveProfile">
                    {{ savingProfile ? "保存中..." : "保存" }}
                  </button>
                  <button class="btn btn-mini" type="button" :disabled="savingProfile" @click="cancelProfileEditor">
                    取消
                  </button>
                </template>
              </div>
            </div>
            <div class="profile-info-grid">
              <article class="profile-info-item">
                <span>ID</span>
                <strong>#{{ profile.user.id }}</strong>
              </article>
              <article class="profile-info-item">
                <span>用户权限</span>
                <strong>{{ formatRole(profile.user.role) }}</strong>
              </article>
              <article class="profile-info-item">
                <span>注册时间</span>
                <strong>{{ formatTime(profile.user.date_joined) }}</strong>
              </article>
              <article class="profile-info-item">
                <span>性别</span>
                <div v-if="profileEditVisible" class="inline-radio-group" role="radiogroup" aria-label="性别">
                  <label v-for="item in genderOptions" :key="item.value" class="inline-radio">
                    <input type="radio" v-model="profileForm.gender" :value="item.value" />
                    <span>{{ item.label }}</span>
                  </label>
                </div>
                <strong v-else>{{ formatGender(profile.user.gender || profile.profile_settings?.gender) }}</strong>
              </article>
              <article class="profile-info-item">
                <span>手机号</span>
                <strong>{{ formatPrivatePhoneLabel() }}</strong>
              </article>
              <article class="profile-info-item">
                <span>邮箱</span>
                <strong>{{ formatPrivateEmailLabel() }}</strong>
                <small>{{ profile.profile_settings?.email_verified ? "已验证" : "未验证" }}</small>
              </article>
              <article class="profile-info-item">
                <span>学习 / 学校</span>
                <input
                  v-if="profileEditVisible"
                  class="input profile-inline-input"
                  v-model="profileForm.school_name"
                  placeholder="学校"
                />
                <strong v-else>{{ profile.profile_settings?.school_name || profile.user.school_name || "未填写" }}</strong>
              </article>
              <article class="profile-info-item">
                <span>个人简介</span>
                <textarea
                  v-if="profileEditVisible"
                  class="textarea profile-inline-textarea"
                  v-model="profileForm.bio"
                  placeholder="个人简介"
                  rows="3"
                ></textarea>
                <strong v-else>{{ profile.profile_settings?.bio || profile.user.bio || "暂无个人简介" }}</strong>
              </article>
            </div>
          </section>

          <section class="section-block profile-overview-card">
            <div class="profile-overview-card__head">
              <div>
                <h3>我的待办</h3>
                <p class="meta">优先处理会影响发布、审核或账号可用性的事项。</p>
              </div>
              <strong class="summary-total">{{ profile.todo_summary?.total || 0 }}</strong>
            </div>
            <div v-if="visibleTodoSummaryItems.length" class="summary-card-grid">
              <RouterLink
                v-for="item in visibleTodoSummaryItems"
                :key="item.key"
                class="summary-stat-card"
                :class="`summary-stat-card--${item.severity || 'normal'}`"
                :to="item.url || { name: 'profile' }"
              >
                <span>{{ item.label }}</span>
                <strong>{{ item.count }}</strong>
              </RouterLink>
            </div>
            <p v-else class="meta">当前没有需要立即处理的事项。</p>
          </section>

          <section class="section-block profile-overview-card">
            <div class="profile-overview-card__head">
              <div>
                <h3>内容摘要</h3>
                <p class="meta">按动态、知识贡献、赛事协作和收藏反馈归档你的站内数据。</p>
              </div>
            </div>
            <div class="creation-summary-list">
              <article v-for="group in creationSummaryGroups" :key="group.key" class="creation-summary-group">
                <h4>{{ group.label }}</h4>
                <div class="summary-mini-grid">
                  <RouterLink
                    v-for="item in group.items"
                    :key="`${group.key}-${item.key}`"
                    class="summary-mini-item"
                    :to="item.url || { name: 'profile' }"
                  >
                    <span>{{ item.label }}</span>
                    <strong>{{ item.count }}</strong>
                  </RouterLink>
                </div>
              </article>
            </div>
          </section>
        </div>

        <section v-show="activeTab === 'security'" class="section-block" id="profile-security">
          <h3>手机号验证</h3>
          <p class="meta">
            当前状态：
            <span class="pill" :class="{ 'pill-success': phoneVerification.status === 'verified' }">
              {{ formatPhoneVerificationStatus(phoneVerification.status) }}
            </span>
          </p>
          <p v-if="phoneVerification.phone_masked" class="meta">
            已验证手机号：{{ maskPrivateContact(phoneVerification.phone_masked, 11) }}
            <span v-if="phoneVerification.verified_at"> · {{ formatTime(phoneVerification.verified_at) }}</span>
          </p>
          <div class="settings-actions">
            <button
              v-if="phoneVerification.status !== 'verified'"
              class="btn btn-accent"
              type="button"
              @click="openPhoneVerificationModal"
            >
              手机号验证
            </button>
            <button v-else class="btn" type="button" disabled>
              已完成验证
            </button>
          </div>
        </section>

        <section v-show="activeTab === 'stars'" class="section-block" id="profile-stars">
          <h3>&#x6536;&#x85CF;&#x6761;&#x76EE;</h3>
          <div class="event-filters">
            <input
              class="input"
              v-model="starFilters.search"
              placeholder="搜索收藏内容"
              @keyup.enter="loadStarredArticles()"
            />
            <button class="btn btn-mini" @click="loadStarredArticles">筛选</button>
          </div>
          <p class="meta">Total {{ starredMeta.count }}</p>
          <article class="star-row" v-for="item in starredArticles" :key="item.id">
            <RouterLink class="star-link" :to="{ name: 'article', params: { id: item.id } }">
              {{ item.title }}
            </RouterLink>
            <button
              class="btn btn-mini"
              :disabled="unstarLoadingId === item.id"
              @click="unstarFromProfile(item)"
            >
              {{ unstarLoadingId === item.id ? "处理中..." : "取消收藏" }}
            </button>
          </article>
          <button v-if="starredMeta.next" class="btn" @click="loadMoreStarredArticles">
            {{ starredMeta.loadingMore ? "加载中..." : "加载更多" }}
          </button>
          <p v-if="!starredArticles.length" class="meta">暂无收藏条目。</p>
        </section>

        <section v-show="activeTab === 'security'" class="section-block">
          <h3>&#x90AE;&#x7BB1;&#x9A8C;&#x8BC1; / &#x4FEE;&#x6539;</h3>
          <p class="meta">
            当前邮箱：{{ maskPrivateContact(profile.profile_settings?.email, 8) }}
            <span class="pill" :class="{ 'pill-success': profile.profile_settings?.email_verified }">
              {{ profile.profile_settings?.email_verified ? "已验证" : "未验证" }}
            </span>
          </p>
          <p v-if="profile.profile_settings?.pending_email" class="meta">
            待确认邮箱：{{ maskPrivateContact(profile.profile_settings.pending_email, 8) }}
            <span v-if="profile.profile_settings?.pending_email_expires_at">
              （有效至 {{ formatTime(profile.profile_settings.pending_email_expires_at) }}）
            </span>
          </p>
          <div class="settings-grid">
            <input
              class="input"
              v-model="emailChangeForm.email"
              placeholder="新邮箱，或输入当前邮箱重新验证"
              @input="clearEmailChangeSession"
            />
            <input
              class="input"
              type="password"
              v-model="emailChangeForm.current_password"
              placeholder="当前密码"
              @input="clearEmailChangeSession"
            />
          </div>
          <div v-if="emailChangeTicket.token" class="email-verify-card">
            <p class="meta">验证码已发送至 {{ emailChangeTicket.masked_email }}。</p>
            <input class="input" v-model="emailChangeForm.code" placeholder="邮箱验证码" inputmode="numeric" />
          </div>
          <div class="settings-actions">
            <button class="btn" :disabled="sendingEmailCode" @click="sendEmailChangeCode">
              {{ sendingEmailCode ? "发送中..." : emailChangeTicket.token ? "重新发送验证码" : "发送验证码" }}
            </button>
            <button class="btn btn-accent" :disabled="changingEmail || !emailChangeTicket.token" @click="confirmEmailChange">
              {{ changingEmail ? "更新中..." : "确认邮箱" }}
            </button>
          </div>
        </section>

        <section v-show="activeTab === 'security'" class="section-block">
          <h3>&#x5BC6;&#x7801;&#x4FEE;&#x6539;</h3>
          <div class="settings-grid">
            <div class="password-field">
              <input
                class="input password-input"
                :type="passwordVisibility.old ? 'text' : 'password'"
                v-model="passwordForm.old_password"
                placeholder="当前密码"
                @input="clearPasswordChangeSession"
              />
              <button
                class="password-toggle"
                type="button"
                :aria-label="passwordVisibility.old ? '隐藏密码' : '显示密码'"
                :title="passwordVisibility.old ? '隐藏密码' : '显示密码'"
                @click="togglePasswordVisibility('old')"
              >
                {{ passwordVisibility.old ? "隐藏" : "显示" }}
              </button>
            </div>
            <div class="password-field">
              <input
                class="input password-input"
                :type="passwordVisibility.new ? 'text' : 'password'"
                v-model="passwordForm.new_password"
                placeholder="新密码（至少 8 位）"
                @input="clearPasswordChangeSession"
              />
              <button
                class="password-toggle"
                type="button"
                :aria-label="passwordVisibility.new ? '隐藏密码' : '显示密码'"
                :title="passwordVisibility.new ? '隐藏密码' : '显示密码'"
                @click="togglePasswordVisibility('new')"
              >
                {{ passwordVisibility.new ? "隐藏" : "显示" }}
              </button>
            </div>
          </div>
          <div class="password-field">
            <input
              class="input password-input"
              :type="passwordVisibility.confirm ? 'text' : 'password'"
              v-model="passwordForm.confirm_password"
              placeholder="确认新密码"
              @input="clearPasswordChangeSession"
            />
            <button
              class="password-toggle"
              type="button"
              :aria-label="passwordVisibility.confirm ? '隐藏密码' : '显示密码'"
              :title="passwordVisibility.confirm ? '隐藏密码' : '显示密码'"
              @click="togglePasswordVisibility('confirm')"
            >
              {{ passwordVisibility.confirm ? "隐藏" : "显示" }}
            </button>
          </div>
          <div v-if="passwordChangeTicket.token" class="email-verify-card">
            <p class="meta">验证码已发送至 {{ passwordChangeTicket.masked_email }}。</p>
            <input class="input" v-model="passwordForm.code" placeholder="邮箱验证码" inputmode="numeric" />
          </div>
          <div class="settings-actions">
            <button class="btn" :disabled="sendingPasswordCode" @click="sendPasswordChangeCode">
              {{ sendingPasswordCode ? "发送中..." : passwordChangeTicket.token ? "重新发送验证码" : "发送验证码" }}
            </button>
            <button class="btn btn-accent" :disabled="changingPassword || !passwordChangeTicket.token" @click="changePassword">
              {{ changingPassword ? "更新中..." : "确认修改密码" }}
            </button>
          </div>
        </section>

        <section v-show="activeTab === 'interaction'" class="section-block">
          <h3>社区互动记录</h3>
          <p class="meta">这里记录你在站内的收藏、评论、修订和管理类操作轨迹。</p>
          <div class="event-filters">
            <select class="select" v-model="eventFilters.event_type" @change="loadMyEvents()">
              <option value="">全部事件</option>
              <option value="star">收藏</option>
              <option value="comment">评论</option>
              <option value="issue">Issue/Request</option>
              <option value="revision">修订</option>
              <option value="announcement">公告</option>
              <option value="admin">管理操作</option>
            </select>
            <button class="btn btn-mini" @click="loadMyEvents">筛选</button>
          </div>
          <div class="event" v-for="item in myEvents" :key="item.id">
            <span class="pill">{{ formatEventType(item.event_type) }}</span>
            <span class="event-target">{{ item.target_type }} #{{ item.target_id }}</span>
            <span class="meta">{{ formatTime(item.created_at) }}</span>
          </div>
          <button v-if="myEventsMeta.next" class="btn" @click="loadMoreMyEvents">
            {{ myEventsMeta.loadingMore ? "加载中..." : "加载更多" }}
          </button>
          <p v-if="!myEvents.length" class="meta">暂无记录。</p>
        </section>

        <section v-show="activeTab === 'security-log'" class="section-block" id="profile-security-log">
          <h3>&#x8D26;&#x53F7;&#x5B89;&#x5168;&#x8BB0;&#x5F55;</h3>
          <p v-if="securitySchemaOutdated" class="meta">安全表结构较旧，请先执行数据库迁移。</p>
          <div class="event-filters">
            <select class="select" v-model="securitySummaryWindow">
              <option :value="24">最近 24 小时</option>
              <option :value="72">最近 72 小时</option>
              <option :value="168">最近 7 天</option>
            </select>
            <button class="btn btn-mini" :disabled="securitySummaryLoading" @click="loadMySecuritySummary">
              {{ securitySummaryLoading ? "刷新中..." : "刷新" }}
            </button>
          </div>
          <div class="security-summary-grid" v-if="mySecuritySummary">
            <div class="security-summary-item">
              <strong>{{ mySecuritySummary.totals?.events ?? 0 }}</strong>
              <span>事件数</span>
            </div>
            <div class="security-summary-item">
              <strong>{{ mySecuritySummary.totals?.login_failed ?? 0 }}</strong>
              <span>登录失败</span>
            </div>
            <div class="security-summary-item">
              <strong>{{ mySecuritySummary.totals?.login_locked ?? 0 }}</strong>
              <span>登录锁定</span>
            </div>
            <div class="security-summary-item">
              <strong>{{ mySecuritySummary.totals?.password_changed ?? 0 }}</strong>
              <span>密码修改</span>
            </div>
          </div>
          <p class="meta" v-if="mySecuritySummary?.since">统计起点：{{ formatTime(mySecuritySummary.since) }}</p>
          <div class="event-filters">
            <select class="select" v-model="securityEventFilters.event_type" @change="loadMySecurityEvents()">
              <option value="">全部事件类型</option>
              <option value="login_success">登录成功</option>
              <option value="login_failed">登录失败</option>
              <option value="login_locked">登录锁定</option>
              <option value="login_denied">登录拒绝</option>
              <option value="register_code_sent">注册验证码发送</option>
              <option value="register_success">注册成功</option>
              <option value="logout">退出登录</option>
              <option value="password_change_requested">密码修改验证码</option>
              <option value="password_changed">密码修改</option>
              <option value="password_reset_requested">找回密码验证码</option>
              <option value="password_reset_completed">找回密码完成</option>
              <option value="email_change_requested">邮箱验证码发送</option>
              <option value="email_changed">邮箱变更</option>
            </select>
            <select class="select" v-model="securityEventFilters.success" @change="loadMySecurityEvents()">
              <option value="">全部结果</option>
              <option value="1">成功</option>
              <option value="0">失败</option>
            </select>
          </div>
          <p class="meta">Total {{ mySecurityEventsMeta.count }}</p>
          <div class="event" v-for="item in mySecurityEvents" :key="item.id">
            <span class="pill">{{ formatSecurityEventType(item.event_type) }}</span>
            <span class="event-target">{{ item.ip_address || "-" }} | {{ item.success ? "成功" : "失败" }}</span>
            <span class="meta">{{ formatTime(item.created_at) }}</span>
            <span class="meta" v-if="item.detail">{{ item.detail }}</span>
          </div>
          <button v-if="mySecurityEventsMeta.next" class="btn" @click="loadMoreMySecurityEvents">
            {{ mySecurityEventsMeta.loadingMore ? "加载中..." : "加载更多" }}
          </button>
          <p v-if="!mySecurityEvents.length" class="meta">暂无安全记录。</p>
        </section>

        <section v-show="activeTab === 'privacy'" class="section-block" id="profile-privacy">
          <h3>数据与隐私</h3>
          <p class="meta">这里说明当前站点对手机号、内容审核、删除内容和账号数据的处理方式。</p>
          <div class="privacy-grid">
            <article class="privacy-item">
              <strong>手机号</strong>
              <p>仅用于账号验证、防滥用与安全通知，不向普通用户公开。管理员可在合规范围内查看验证通过的手机号。</p>
            </article>
            <article class="privacy-item">
              <strong>内容审核</strong>
              <p>动态、评论、Trick 和部分工单会先经过 AI 审核，少量异常内容会进入人工复核队列。</p>
            </article>
            <article class="privacy-item">
              <strong>删除归档</strong>
              <p>被删除的帖子和评论会从前台消失，并进入删除内容归档，仅管理员可查看与恢复。</p>
            </article>
            <article class="privacy-item">
              <strong>账号数据</strong>
              <p>账号注销后，帖子、评论和修改记录仍会保留在站内链路中，但作者会统一显示为“已注销用户”。</p>
            </article>
          </div>
          <div class="settings-actions">
            <button
              class="btn btn-mini btn-danger"
              type="button"
              :disabled="auth.isManager || cancellingAccount"
              @click="openAccountCancellationModal"
            >
              账号注销
            </button>
          </div>
          <p v-if="auth.isManager" class="meta danger-note">管理员账号请先完成权限移交，再执行注销。</p>
        </section>

        <section v-show="activeTab === 'admin' && auth.isManager" class="section-block" id="profile-admin">
          <h3>管理员入口</h3>
          <p class="meta">用于快速跳转到审核、举报、删除归档和系统管理页面。</p>
          <div class="admin-link-grid">
            <RouterLink class="admin-link-card" :to="{ name: 'manage-moments' }">
              <strong>动态审核</strong>
              <span>审核动态、评论和举报后的内容处理。</span>
            </RouterLink>
            <RouterLink class="admin-link-card" :to="{ name: 'review-tricks' }">
              <strong>Trick 审核</strong>
              <span>处理 Trick 的通过、驳回和删除审核。</span>
            </RouterLink>
            <RouterLink class="admin-link-card" :to="{ name: 'manage-deleted-content' }">
              <strong>删除内容归档</strong>
              <span>查看、恢复和追踪被删除的帖子与评论。</span>
            </RouterLink>
            <RouterLink class="admin-link-card" :to="{ name: 'manage-security' }">
              <strong>安全日志</strong>
              <span>查看登录、验证码和账号操作记录。</span>
            </RouterLink>
            <RouterLink class="admin-link-card" :to="{ name: 'manage-ai-moderation' }">
              <strong>AI 审核配置</strong>
              <span>维护 AI 审核规则与人工复核策略。</span>
            </RouterLink>
            <RouterLink class="admin-link-card" :to="{ name: 'manage-events' }">
              <strong>操作日志</strong>
              <span>查看站内重要操作和管理动作。</span>
            </RouterLink>
          </div>
        </section>
      </section>

      <section v-show="activeTab === 'published'" class="tab-panel">
        <section class="section-block">
          <h3>我发布的帖子</h3>
          <p class="meta">已删除的帖子不会再跳转回动态页，仅管理员可以在删除内容管理中查看。</p>
          <div class="event-filters">
            <select class="select" v-model="momentPostFilters.status" @change="loadMyMomentPosts()">
              <option value="">全部状态</option>
              <option value="pending">待审核</option>
              <option value="published">已发布</option>
              <option value="rejected">已驳回</option>
              <option value="hidden">已隐藏</option>
              <option value="deleted">已删除</option>
            </select>
            <input class="input" v-model="momentPostFilters.search" placeholder="搜索帖子 ID / 内容" @keyup.enter="loadMyMomentPosts()" />
            <button class="btn btn-mini" @click="loadMyMomentPosts">筛选</button>
            <button class="btn btn-mini" @click="resetMomentPostFilters">重置</button>
          </div>
          <p class="meta">Total {{ myMomentPostsMeta.count }}</p>
          <article class="history-row" v-for="item in myMomentPosts" :key="item.id">
            <strong>动态 #{{ item.id }}</strong>
            <div class="meta">
              {{ formatMomentStatus(item.status) }} | {{ formatTime(item.published_at || item.created_at) }}
              <span v-if="item.review_note"> | 批注：{{ item.review_note }}</span>
            </div>
            <p class="content-preview">{{ summarizeText(item.content, 180) }}</p>
            <div class="settings-actions">
              <RouterLink v-if="canOpenMomentPost(item)" class="btn btn-mini" :to="{ name: 'moments', query: { moment: item.id } }">
                查看
              </RouterLink>
              <span v-else class="meta deleted-note">{{ formatMomentOpenBlockedReason(item) }}</span>
              <button
                v-if="item.status !== 'deleted'"
                class="btn btn-mini"
                :disabled="deletingMyMomentId === item.id"
                @click="deleteMyMoment(item)"
              >
                {{ deletingMyMomentId === item.id ? "删除中..." : "删除" }}
              </button>
            </div>
          </article>
          <button v-if="myMomentPostsMeta.next" class="btn" @click="loadMoreMyMomentPosts">
            {{ myMomentPostsMeta.loadingMore ? "加载中..." : "加载更多" }}
          </button>
          <p v-if="!myMomentPosts.length" class="meta">暂无动态帖子记录。</p>
        </section>

        <section class="section-block">
          <h3>我发布的动态评论</h3>
          <p class="meta">已删除的评论不会再跳转回动态页，仅管理员可以在删除内容管理中查看。</p>
          <div class="event-filters">
            <select class="select" v-model="momentCommentFilters.status" @change="loadMyMomentComments()">
              <option value="">全部状态</option>
              <option value="pending">待审核</option>
              <option value="visible">可见</option>
              <option value="rejected">已驳回</option>
              <option value="hidden">已隐藏</option>
              <option value="deleted">已删除</option>
            </select>
            <input class="input" v-model="momentCommentFilters.search" placeholder="搜索评论 / 动态 ID" @keyup.enter="loadMyMomentComments()" />
            <button class="btn btn-mini" @click="loadMyMomentComments">筛选</button>
            <button class="btn btn-mini" @click="resetMomentCommentFilters">重置</button>
          </div>
          <p class="meta">Total {{ myMomentCommentsMeta.count }}</p>
          <article class="history-row" v-for="item in myMomentComments" :key="item.id">
            <strong>评论 #{{ item.id }}</strong>
            <div class="meta">
              {{ formatMomentCommentStatus(item.status) }} | 动态 #{{ item.moment }} | {{ formatTime(item.created_at) }}
              <span v-if="item.review_note"> | 批注：{{ item.review_note }}</span>
            </div>
            <p class="content-preview">{{ summarizeText(item.content, 180) }}</p>
            <p class="meta">所属动态：{{ item.moment_summary || "-" }}</p>
            <div class="settings-actions">
              <RouterLink v-if="canOpenMomentComment(item)" class="btn btn-mini" :to="{ name: 'moments', query: { moment: item.moment } }">
                查看动态
              </RouterLink>
              <span v-else class="meta deleted-note">{{ formatMomentCommentOpenBlockedReason(item) }}</span>
              <button
                v-if="item.status !== 'deleted'"
                class="btn btn-mini"
                :disabled="deletingMyMomentCommentId === item.id"
                @click="deleteMyMomentComment(item)"
              >
                {{ deletingMyMomentCommentId === item.id ? "删除中..." : "删除" }}
              </button>
            </div>
          </article>
          <button v-if="myMomentCommentsMeta.next" class="btn" @click="loadMoreMyMomentComments">
            {{ myMomentCommentsMeta.loadingMore ? "加载中..." : "加载更多" }}
          </button>
          <p v-if="!myMomentComments.length" class="meta">暂无动态评论记录。</p>
        </section>
      </section>

      <section v-show="activeTab === 'published'" class="tab-panel">
        <section class="section-block">
          <h3>我的 Trick</h3>
          <p class="meta">Total {{ myTricksMeta.count }}</p>
          <article class="history-row my-trick-row" v-for="item in myTricks" :key="item.record_id">
            <div class="history-row-head">
              <div class="history-row-main">
                <strong>{{ item.title || "未命名 Trick" }}</strong>
                <div class="meta">
                  {{ formatTrickRecordStatus(item) }} | {{ formatTime(item.deleted_at || item.updated_at || item.created_at) }}
                </div>
                <div class="meta" v-if="item.deleted_at && item.previous_status">
                  删除前状态：{{ formatModerationStatus(item.previous_status) }}
                </div>
                <div class="meta" v-if="item.review_note">批注：{{ item.review_note }}</div>
                <div class="trick-chip-list" v-if="(item.terms && item.terms.length) || (item.keywords && item.keywords.length)">
                  <span class="trick-chip" v-for="term in item.terms || []" :key="`${item.record_id}-term-${term.id || term.name}`">
                    {{ term.name }}
                  </span>
                  <span class="trick-chip trick-chip-keyword" v-for="keyword in item.keywords || []" :key="`${item.record_id}-keyword-${keyword}`">
                    {{ keyword }}
                  </span>
                </div>
              </div>
              <div class="history-row-actions">
                <button class="btn btn-mini" @click="startEditMyTrick(item)">
                  {{ item.source === "deleted_archive" ? "编辑并重新提交" : "编辑并提交审核" }}
                </button>
              </div>
            </div>

            <pre class="content-preview my-trick-preview">{{ summarizeText(item.content_md, 260) }}</pre>

            <div v-if="editingMyTrickRecordId === item.record_id" class="my-trick-editor">
              <input class="input" v-model="myTrickEditForm.title" placeholder="标题" />
              <input
                class="input"
                v-model="myTrickEditForm.keywords_text"
                placeholder="关键词，使用空格分隔"
              />
              <div class="my-trick-term-grid">
                <button
                  v-for="term in myTrickTerms"
                  :key="term.id"
                  type="button"
                  class="my-trick-term-option"
                  :class="{ 'is-active': myTrickEditForm.term_ids.includes(term.id) }"
                  @click="toggleMyTrickTerm(term.id)"
                >
                  {{ term.name }}
                </button>
              </div>
              <textarea
                class="textarea my-trick-content-editor"
                v-model="myTrickEditForm.content_md"
                placeholder="Markdown 内容"
              ></textarea>
              <div class="my-trick-editor-actions">
                <button
                  class="btn btn-accent"
                  :disabled="savingMyTrickRecordId === item.record_id"
                  @click="submitMyTrickEdit"
                >
                  {{
                    savingMyTrickRecordId === item.record_id
                      ? "提交中..."
                      : item.source === "deleted_archive"
                        ? "重新提交审核"
                        : "保存并提交审核"
                  }}
                </button>
                <button class="btn btn-mini" :disabled="savingMyTrickRecordId === item.record_id" @click="cancelEditMyTrick">
                  取消
                </button>
              </div>
            </div>
          </article>
          <p v-if="!myTricks.length" class="meta">暂无 Trick 记录。</p>
        </section>
      </section>

      <section v-show="activeTab === 'learning'" class="tab-panel">
        <section class="section-block">
          <h3>我的补题链接</h3>
          <p class="meta">Total {{ myPracticeMeta.count }}</p>
          <article class="history-row" v-for="item in myPracticeProposals" :key="item.id">
            <strong>{{ item.proposed_short_name || item.proposed_official_name }}</strong>
            <div class="meta">
              {{ formatModerationStatus(item.status) }} | {{ item.proposed_year || "-" }} |
              {{ item.proposed_series_label || item.proposed_series || "-" }} ·
              {{ item.proposed_stage_label || item.proposed_stage || "-" }}
            </div>
            <p class="meta" v-if="item.review_note">审核批注：{{ item.review_note }}</p>
            <p class="meta" v-else-if="item.reason">提交说明：{{ item.reason }}</p>
          </article>
          <p v-if="!myPracticeProposals.length" class="meta">暂无补题链接提交记录。</p>
        </section>
      </section>

      <section v-show="activeTab === 'learning'" class="tab-panel">
        <section class="section-block">
          <h3>我的赛事公告</h3>
          <p class="meta">Total {{ myNoticeMeta.count }}</p>
          <article class="history-row" v-for="item in myCompetitionNotices" :key="item.id">
            <strong>{{ item.title }}</strong>
            <div class="meta">
              {{ formatModerationStatus(item.status) }} | {{ item.year || "-" }} |
              {{ item.series_label || item.series || "-" }} · {{ item.stage_label || item.stage || "-" }}
            </div>
            <p class="meta" v-if="item.revision_of_title">修订目标：{{ item.revision_of_title }}</p>
            <p class="meta" v-if="item.review_note">审核批注：{{ item.review_note }}</p>
          </article>
          <p v-if="!myCompetitionNotices.length" class="meta">暂无赛事公告记录。</p>
        </section>
      </section>

      <section v-show="activeTab === 'published'" class="tab-panel">
        <section class="section-block">
          <h3>&#x6211;&#x7684;&#x8BC4;&#x8BBA;</h3>
          <p class="meta">Total {{ myCommentsMeta.count }}</p>
          <article class="history-row" v-for="item in myComments" :key="item.id">
            <strong>{{ item.article_title || `文章 #${item.article}` }}</strong>
            <div class="meta">{{ formatModerationStatus(item.status) }} | {{ formatTime(item.created_at) }}</div>
            <p class="meta">{{ item.content }}</p>
            <button
              v-if="item.status !== 'hidden'"
              class="btn btn-mini"
              :disabled="deletingMyCommentId === item.id"
              @click="deleteMyComment(item)"
            >
              {{ deletingMyCommentId === item.id ? "删除中..." : "删除" }}
            </button>
          </article>
          <button v-if="myCommentsMeta.next" class="btn" @click="loadMoreMyComments">
            {{ myCommentsMeta.loadingMore ? "加载中..." : "加载更多" }}
          </button>
          <p v-if="!myComments.length" class="meta">暂无评论记录。</p>
        </section>
      </section>

      <section v-show="activeTab === 'learning'" class="tab-panel">
        <section class="section-block">
          <h3>&#x6211;&#x7684;&#x4FEE;&#x8BA2;&#x610F;&#x89C1;</h3>
          <p class="meta">Total {{ myRevisionsMeta.count }} | Pending {{ pendingRevisionCount }}/5</p>
          <div class="revision-filters">
            <select class="select" v-model="revisionFilters.status" @change="loadMyRevisions()">
              <option value="">全部状态</option>
              <option value="pending">审核中</option>
              <option value="approved">通过</option>
              <option value="rejected">驳回</option>
            </select>
            <input
              class="input"
              v-model="revisionFilters.search"
              placeholder="搜索标题或批注"
              @keyup.enter="loadMyRevisions()"
            />
            <button class="btn" @click="loadMyRevisions">筛选</button>
            <button class="btn" @click="resetRevisionFilters">重置</button>
          </div>
          <article
            class="history-row revision-row"
            :class="{ 'is-expanded': expandedRevisionId === item.id }"
            v-for="item in myRevisions"
            :key="item.id"
          >
            <button class="revision-card-trigger" @click="toggleRevisionDetails(item.id)">
              <strong>{{ item.article_title || item.proposed_title || `Article #${item.article}` }}</strong>
              <div class="meta">{{ formatModerationStatus(item.status) }} | {{ formatTime(item.created_at) }}</div>
              <p class="meta">
                {{ (item.reason || item.proposed_summary || item.proposed_content_md || "").slice(0, 120) || "No description." }}
              </p>
            </button>

            <div v-if="expandedRevisionId === item.id" class="revision-detail" @click.stop>
              <template v-if="editingRevisionId === item.id">
                <input class="input" v-model="revisionEditForm.proposed_title" placeholder="Proposed title" />
                <textarea class="textarea" v-model="revisionEditForm.proposed_summary" placeholder="Proposed summary"></textarea>
                <textarea
                  class="textarea revision-editor-content"
                  v-model="revisionEditForm.proposed_content_md"
                  placeholder="Markdown content"
                ></textarea>
                <textarea class="textarea" v-model="revisionEditForm.reason" placeholder="Reason"></textarea>
                <div class="revision-actions">
                  <button
                    class="btn btn-mini"
                    :disabled="savingRevisionEditId === item.id"
                    @click="saveRevisionEdit(item)"
                  >
                    {{ savingRevisionEditId === item.id ? "保存中..." : "保存修改" }}
                  </button>
                  <button class="btn btn-mini" :disabled="savingRevisionEditId === item.id" @click="cancelRevisionEdit">
                    取消
                  </button>
                </div>
              </template>
              <template v-else>
                <p class="meta"><strong>建议标题：</strong> {{ item.proposed_title || "-" }}</p>
                <p class="meta"><strong>建议摘要：</strong> {{ item.proposed_summary || "-" }}</p>
                <p class="meta" v-if="item.reason"><strong>提交说明：</strong> {{ item.reason }}</p>
                <p class="meta" v-if="item.review_note"><strong>审核批注：</strong> {{ item.review_note }}</p>
                <p class="meta"><strong>提交的 Markdown：</strong></p>
                <pre class="revision-content-preview">{{ item.proposed_content_md }}</pre>
                <div class="revision-actions" v-if="item.status === 'pending'">
                  <button class="btn btn-mini" @click="startEditRevision(item)">编辑</button>
                  <button
                    class="btn btn-mini"
                    :disabled="cancellingRevisionId === item.id"
                    @click="cancelRevision(item)"
                  >
                    {{ cancellingRevisionId === item.id ? "取消中..." : "撤销提案" }}
                  </button>
                </div>
              </template>
            </div>
          </article>
          <button v-if="myRevisionsMeta.next" class="btn" @click="loadMoreMyRevisions">
            {{ myRevisionsMeta.loadingMore ? "加载中..." : "加载更多" }}
          </button>
          <p v-if="!myRevisions.length" class="meta">暂无修订记录。</p>
        </section>
      </section>

      <section v-show="activeTab === 'learning'" class="tab-panel">
        <section class="section-block my-issues">
          <h3>&#x6211;&#x7684; Issue / Request</h3>
          <p class="meta">Total {{ issuesMeta.count }}</p>
          <div class="issue-form">
            <select class="select" v-model="issueForm.kind">
              <option value="issue">问题</option>
              <option value="request">需求</option>
            </select>
            <select class="select" v-model="issueForm.visibility">
              <option value="public">公开</option>
              <option value="private">个人</option>
            </select>
            <input class="input" v-model="issueForm.title" placeholder="标题" />
            <textarea class="textarea" v-model="issueForm.content" placeholder="描述"></textarea>
            <button class="btn" @click="submitIssue">提交</button>
          </div>

          <div class="issue-filters">
            <select class="select" v-model="issueFilters.scope" @change="loadIssues()">
              <option value="mine">我的</option>
              <option value="all">全部</option>
            </select>
            <select class="select" v-model="issueFilters.kind" @change="loadIssues()">
              <option value="">全部类型</option>
              <option value="issue">问题</option>
              <option value="request">需求</option>
            </select>
            <select class="select" v-model="issueFilters.visibility" @change="loadIssues()">
              <option value="">全部可见性</option>
              <option value="private">个人</option>
              <option value="public">公开</option>
            </select>
            <select class="select" v-model="issueFilters.status" @change="loadIssues()">
              <option value="">全部状态</option>
              <option value="pending">审核中</option>
              <option value="open">开放</option>
              <option value="in_progress">处理中</option>
              <option value="resolved">已解决</option>
              <option value="rejected">驳回</option>
            </select>
            <input class="input" v-model="issueFilters.search" placeholder="搜索标题或描述" @keyup.enter="loadIssues()" />
            <button class="btn" @click="loadIssues">筛选</button>
            <button class="btn" @click="resetIssueFilters">重置</button>
          </div>

          <article class="issue-row" v-for="item in issues" :key="item.id">
            <strong>{{ item.title }}</strong>
            <div class="meta">
              {{ formatIssueKind(item.kind) }} | {{ formatIssueVisibility(item.visibility) }} | {{ formatModerationStatus(item.status) }} | {{ formatTime(item.created_at) }}
            </div>
            <p class="meta" v-if="issueFilters.scope === 'all' && item.author">
              作者：{{ item.author.username }}
            </p>
            <p class="meta" v-if="item.related_article_title">关联文章：{{ item.related_article_title }}</p>
            <p class="issue-note" v-if="item.resolution_note">说明：{{ item.resolution_note }}</p>
          </article>
          <button v-if="issuesMeta.next" class="btn" @click="loadMoreIssues">
            {{ issuesMeta.loadingMore ? "加载中..." : "加载更多" }}
          </button>
          <p v-if="!issues.length" class="meta">暂无 Issue / Request 记录。</p>
        </section>
      </section>
        </div>
      </div>
    </article>
    <teleport to="body">
      <div v-if="phoneVerificationModalOpen" class="modal-backdrop" @click.self="closePhoneVerificationModal">
        <section class="verification-modal" role="dialog" aria-modal="true" aria-label="手机号验证">
          <header class="verification-modal__head">
            <div>
              <p class="meta">手机号验证</p>
              <h2>验证手机号</h2>
            </div>
            <button type="button" class="icon-close" @click="closePhoneVerificationModal">×</button>
          </header>
          <p class="meta">完成手机号验证后，你可以使用动态发布、评论、点赞和收藏功能。</p>
          <form class="verification-form" @submit.prevent="checkPhoneVerificationCode">
            <input v-model.trim="phoneVerificationForm.phone_number" class="input" placeholder="手机号" autocomplete="tel" />
            <div class="settings-actions">
              <button class="btn" type="button" :disabled="sendingPhoneCode" @click="sendPhoneVerificationCode">
                {{ sendingPhoneCode ? "发送中..." : "发送验证码" }}
              </button>
              <button
                v-if="phoneVerificationTicket.token"
                class="btn btn-accent"
                type="submit"
                :disabled="checkingPhoneCode"
              >
                {{ checkingPhoneCode ? "验证中..." : "完成验证" }}
              </button>
            </div>
            <input
              v-if="phoneVerificationTicket.token"
              v-model.trim="phoneVerificationForm.code"
              class="input"
              placeholder="短信验证码"
              inputmode="numeric"
              autocomplete="one-time-code"
            />
          </form>
          <p v-if="phoneVerificationTicket.masked_phone" class="meta">
            验证码已发送至 {{ phoneVerificationTicket.masked_phone }}，5 分钟内有效。
          </p>
        </section>
      </div>
    </teleport>
    <teleport to="body">
      <div v-if="accountCancellationModalOpen" class="modal-backdrop" @click.self="closeAccountCancellationModal">
        <section class="verification-modal" role="dialog" aria-modal="true" aria-label="账号注销确认">
          <header class="verification-modal__head">
            <div>
              <p class="meta">账号注销</p>
              <h2>确认注销账号</h2>
            </div>
            <button type="button" class="icon-close" :disabled="cancellingAccount" @click="closeAccountCancellationModal">×</button>
          </header>
          <p class="meta danger-copy">
            注销后当前账号将无法登录。已发布的帖子、评论和修改记录不会回到个人身份名下，相关作者统一显示为“已注销用户”。
          </p>
          <form class="verification-form" @submit.prevent="submitAccountCancellation">
            <input
              v-model="accountCancellationForm.current_password"
              class="input"
              type="password"
              placeholder="当前密码"
              autocomplete="current-password"
            />
            <input
              v-model.trim="accountCancellationForm.confirmation"
              class="input"
              :placeholder="`输入：${ACCOUNT_CANCELLATION_CONFIRM_TEXT}`"
              autocomplete="off"
            />
            <div class="settings-actions">
              <button class="btn" type="button" :disabled="cancellingAccount" @click="closeAccountCancellationModal">
                取消
              </button>
              <button class="btn btn-danger" type="submit" :disabled="cancellingAccount">
                {{ cancellingAccount ? "注销中..." : "确认注销" }}
              </button>
            </div>
          </form>
        </section>
      </div>
    </teleport>
  </section>
</template>



<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";

import { getCaptchaProof, captchaErrorMessage } from "../composables/useCaptcha";
import api from "../services/api";
import { useAuthStore } from "../stores/auth";
import { useUiStore } from "../stores/ui";

const auth = useAuthStore();
const ui = useUiStore();
const route = useRoute();
const router = useRouter();

const baseProfileNavGroups = [
  {
    title: "账户管理",
    items: [
      { key: "profile", label: "个人资料", icon: "○", title: "个人资料", description: "管理昵称、学校、简介、头像和个人贡献概览。" },
      { key: "security", label: "账号安全", icon: "◇", title: "账号安全", description: "管理手机号验证、邮箱验证和登录密码。" },
      { key: "security-log", label: "安全记录", icon: "□", title: "安全记录", description: "查看登录、验证码、改密等账号安全事件。" },
      { key: "privacy", label: "数据与隐私", icon: "◇", title: "数据与隐私", description: "了解手机号用途、内容审核、删除归档和账号数据处理规则。" },
    ],
  },
  {
    title: "社区内容",
    items: [
      { key: "published", label: "我的发布", icon: "✎", title: "我的发布", description: "管理动态、评论、Trick 和 Wiki 修订记录。" },
      { key: "interaction", label: "我的互动", icon: "◎", title: "我的互动", description: "查看收藏、评论、修订、管理等社区行为记录。" },
      { key: "stars", label: "我的收藏", icon: "☆", title: "我的收藏", description: "查看并管理你收藏的 Wiki 条目。" },
    ],
  },
  {
    title: "学习与协作",
    items: [
      { key: "learning", label: "竞赛与学习", icon: "△", title: "竞赛与学习", description: "查看补题链接、赛事公告、协作工单和学习贡献概览。" },
    ],
  },
];

const adminProfileGroup = {
  title: "管理员",
  items: [
    { key: "admin", label: "管理员入口", icon: "□", title: "管理员入口", description: "快速进入审核、举报、删除归档和站点管理页面。" },
  ],
};

const profileNavGroups = computed(() =>
  auth.isManager ? [...baseProfileNavGroups, adminProfileGroup] : baseProfileNavGroups,
);
const profileSections = computed(() => profileNavGroups.value.flatMap((group) => group.items));
const profileSectionKeys = computed(() => new Set(profileSections.value.map((item) => item.key)));
const profileUtilityTabs = ["profile", "security", "stars", "security-log", "interaction", "privacy", "admin"];

function normalizeProfileSection(value) {
  const rawKey = String(value || "profile");
  const aliases = {
    creation: "published",
    competition: "learning",
  };
  const key = aliases[rawKey] || rawKey;
  return profileSectionKeys.value.has(key) ? key : "profile";
}
const profile = ref(null);
const issues = ref([]);
const myComments = ref([]);
const myMomentPosts = ref([]);
const myMomentComments = ref([]);
const myRevisions = ref([]);
const myEvents = ref([]);
const mySecurityEvents = ref([]);
const mySecuritySummary = ref(null);
const starredArticles = ref([]);
const myTricks = ref([]);
const myTrickTerms = ref([]);
const myPracticeProposals = ref([]);
const myCompetitionNotices = ref([]);
const expandedRevisionId = ref(null);
const editingRevisionId = ref(null);
const editingMyTrickRecordId = ref("");
const savingProfile = ref(false);
const changingPassword = ref(false);
const sendingPasswordCode = ref(false);
const sendingEmailCode = ref(false);
const changingEmail = ref(false);
const securitySummaryLoading = ref(false);
const unstarLoadingId = ref(null);
const deletingMyCommentId = ref(null);
const deletingMyMomentId = ref(null);
const deletingMyMomentCommentId = ref(null);
const savingRevisionEditId = ref(null);
const cancellingRevisionId = ref(null);
const savingMyTrickRecordId = ref("");
const securitySummaryWindow = ref(24);
const securitySchemaOutdated = ref(false);
const pendingRevisionTotal = ref(0);
const phoneVerificationModalOpen = ref(false);
const accountCancellationModalOpen = ref(false);
const sendingPhoneCode = ref(false);
const checkingPhoneCode = ref(false);
const cancellingAccount = ref(false);
const phoneVerificationPromptKey = "algowiki_phone_verification_prompted";
const ACCOUNT_CANCELLATION_CONFIRM_TEXT = "注销账户";
const profileEditVisible = ref(false);
const genderOptions = [
  { value: "male", label: "男" },
  { value: "female", label: "女" },
  { value: "private", label: "保密" },
];

const phoneVerification = reactive({
  status: "unverified",
  phone_masked: "",
  phone_last4: "",
  verified_at: null,
  review_note: "",
});

const phoneVerificationForm = reactive({
  phone_number: sessionStorage.getItem("algowiki_phone_verification_number") || "",
  code: "",
});

const phoneVerificationTicket = reactive({
  token: sessionStorage.getItem("algowiki_phone_verification_ticket") || "",
  masked_phone: sessionStorage.getItem("algowiki_phone_verification_masked") || "",
  expires_in_seconds: Number(sessionStorage.getItem("algowiki_phone_verification_expires") || 0),
});

const issuesMeta = reactive({
  count: 0,
  next: "",
  loadingMore: false,
});

const myCommentsMeta = reactive({
  count: 0,
  next: "",
  loadingMore: false,
});

const myMomentPostsMeta = reactive({
  count: 0,
  next: "",
  loadingMore: false,
});

const myMomentCommentsMeta = reactive({
  count: 0,
  next: "",
  loadingMore: false,
});

const myRevisionsMeta = reactive({
  count: 0,
  next: "",
  loadingMore: false,
});

const myEventsMeta = reactive({
  count: 0,
  next: "",
  loadingMore: false,
});

const mySecurityEventsMeta = reactive({
  count: 0,
  next: "",
  loadingMore: false,
});

const starredMeta = reactive({
  count: 0,
  next: "",
  loadingMore: false,
});

const myTricksMeta = reactive({
  count: 0,
});

const myPracticeMeta = reactive({
  count: 0,
});

const myNoticeMeta = reactive({
  count: 0,
});

const issueForm = reactive({
  kind: "issue",
  visibility: "public",
  title: "",
  content: "",
});

const issueFilters = reactive({
  scope: "mine",
  kind: "",
  visibility: "",
  status: "",
  search: "",
});

const eventFilters = reactive({
  event_type: "",
});

const securityEventFilters = reactive({
  event_type: "",
  success: "",
});

const revisionFilters = reactive({
  status: "",
  search: "",
});

const revisionEditForm = reactive({
  base_title: "",
  base_summary: "",
  base_content_md: "",
  base_updated_at: "",
  proposed_title: "",
  proposed_summary: "",
  proposed_content_md: "",
  reason: "",
});

const myTrickEditForm = reactive({
  record_id: "",
  source: "entry",
  entry_id: null,
  archive_id: null,
  title: "",
  keywords_text: "",
  content_md: "",
  term_ids: [],
});

const starFilters = reactive({
  search: "",
});

const momentPostFilters = reactive({
  status: "",
  search: "",
});

const momentCommentFilters = reactive({
  status: "",
  search: "",
});

const profileForm = reactive({
  username: "",
  gender: "private",
  school_name: "",
  bio: "",
  avatar_url: "",
});
const avatarInputRef = ref(null);
const avatarFile = ref(null);
const avatarPreviewUrl = ref("");
const avatarMaxUploadBytes = 2 * 1024 * 1024;
const allowedAvatarMimeTypes = new Set(["image/jpeg", "image/png", "image/webp"]);
const currentAvatarPreview = computed(() => avatarPreviewUrl.value || profile.value?.user?.avatar_url || "");

const emailChangeForm = reactive({
  email: "",
  current_password: "",
  code: "",
});

const emailChangeTicket = reactive({
  token: "",
  masked_email: "",
  expires_in_seconds: 0,
});

const passwordChangeTicket = reactive({
  token: "",
  masked_email: "",
  expires_in_seconds: 0,
});

const passwordForm = reactive({
  old_password: "",
  new_password: "",
  confirm_password: "",
  code: "",
});

const passwordVisibility = reactive({
  old: false,
  new: false,
  confirm: false,
});

const accountCancellationForm = reactive({
  current_password: "",
  confirmation: "",
});

const pendingRevisionCount = computed(() => pendingRevisionTotal.value);
const activeTab = ref(normalizeProfileSection(route.params.section));
const activeProfileSection = computed(
  () => profileSections.value.find((item) => item.key === activeTab.value) || profileSections.value[0],
);
const visibleTodoSummaryItems = computed(() =>
  (profile.value?.todo_summary?.items || []).filter((item) => Number(item?.count || 0) > 0),
);
const creationSummaryGroups = computed(() =>
  (profile.value?.creation_summary?.groups || []).map((group) => ({
    ...group,
    items: Array.isArray(group?.items) ? group.items : [],
  })),
);

watch(
  () => route.params.section,
  (section) => {
    activeTab.value = normalizeProfileSection(section);
  },
);

async function activateTab(key) {
  const nextKey = normalizeProfileSection(key);
  activeTab.value = nextKey;
  await nextTick();
  if (route.name !== "profile-section" || route.params.section !== nextKey) {
    await router.push(nextKey === "profile" ? { name: "profile" } : { name: "profile-section", params: { section: nextKey } });
  }
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function canOpenMomentPost(item) {
  return item?.status === "published";
}

function canOpenMomentComment(item) {
  return item?.status === "visible" && item?.moment_status === "published";
}

function formatMomentOpenBlockedReason(item) {
  if (!item) return "当前不可查看";
  const map = {
    pending: "待审核，不在动态流展示",
    rejected: "已驳回，不在动态流展示",
    hidden: "已隐藏，仅管理员可查看",
    deleted: "已删除，仅管理员可查看",
  };
  return map[item.status] || "当前不可查看";
}

function formatMomentCommentOpenBlockedReason(item) {
  if (!item) return "当前不可查看";
  if (item.moment_status && item.moment_status !== "published") {
    return `所属动态${formatMomentStatus(item.moment_status)}，不在动态流展示`;
  }
  const map = {
    pending: "评论待审核，不在动态流展示",
    rejected: "评论已驳回，不在动态流展示",
    hidden: "评论已隐藏，仅管理员可查看",
    deleted: "评论已删除，仅管理员可查看",
  };
  return map[item.status] || "当前不可查看";
}

function formatTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function initials(value) {
  const text = String(value || "U").trim();
  return text.slice(0, 2).toUpperCase();
}

function formatModerationStatus(value) {
  const map = {
    pending: "审核中",
    approved: "通过",
    rejected: "驳回",
    deleted: "已删除",
    visible: "已展示",
    hidden: "已隐藏",
    open: "开放",
    in_progress: "处理中",
    resolved: "已解决",
  };
  return map[value] || value || "-";
}

function formatMomentStatus(value) {
  const map = {
    pending: "待审核",
    published: "已发布",
    rejected: "已驳回",
    hidden: "已隐藏",
    deleted: "已删除",
  };
  return map[value] || value || "-";
}

function formatMomentCommentStatus(value) {
  const map = {
    pending: "待审核",
    visible: "可见",
    rejected: "已驳回",
    hidden: "已隐藏",
    deleted: "已删除",
  };
  return map[value] || value || "-";
}

function formatPhoneVerificationStatus(value) {
  const map = {
    verified: "已验证",
    pending: "验证中",
    rejected: "未通过",
    revoked: "已撤销",
    unverified: "未验证",
  };
  return map[value] || "未验证";
}

function formatRole(value) {
  const map = {
    normal: "普通用户",
    school: "学校用户",
    admin: "管理员",
    superadmin: "超级管理员",
  };
  return map[value] || value || "-";
}

function formatGender(value) {
  const map = {
    male: "男",
    female: "女",
    private: "保密",
    other: "保密",
    unknown: "保密",
  };
  return map[value] || "保密";
}

function maskPrivateContact(value, fallbackLength = 8) {
  if (!String(value || "").trim()) return "未绑定";
  return "*".repeat(Math.max(4, fallbackLength));
}

function formatPrivatePhoneLabel() {
  if (phoneVerification.status === "verified") {
    return maskPrivateContact(phoneVerification.phone_masked, 11);
  }
  return formatPhoneVerificationStatus(phoneVerification.status);
}

function formatPrivateEmailLabel() {
  return maskPrivateContact(profile.value?.profile_settings?.email, 8);
}

function formatTrickRecordStatus(item) {
  if (!item) return "-";
  if (item.status === "deleted") {
    const previous = item.previous_status ? `，原状态：${formatModerationStatus(item.previous_status)}` : "";
    return `已删除${previous}`;
  }
  return formatModerationStatus(item.status);
}

function formatIssueVisibility(value) {
  const map = {
    private: "个人",
    public: "公开",
  };
  return map[value] || value || "-";
}

function formatIssueKind(value) {
  const map = {
    issue: "问题",
    request: "需求",
  };
  return map[value] || value || "-";
}

function nextPageFromUrl(url, fallback = 2) {
  if (!url) return fallback;
  try {
    return Number(new URL(url, window.location.origin).searchParams.get("page") || String(fallback));
  } catch {
    return fallback;
  }
}

function unpackListPayload(data, currentLength = 0) {
  if (Array.isArray(data)) {
    return { results: data, count: currentLength + data.length, next: "" };
  }
  return {
    results: Array.isArray(data?.results) ? data.results : [],
    count: Number.isFinite(data?.count) ? data.count : currentLength,
    next: typeof data?.next === "string" ? data.next : "",
  };
}

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

function summarizeText(value, maxLength = 160) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  if (!text) return "暂无内容。";
  return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text;
}

function isSchemaOutdatedError(error) {
  return error?.response?.data?.code === "schema_outdated";
}

function applyProfileForm(data) {
  const user = data?.user || data || {};
  const settings = data?.profile_settings || data || {};
  profileForm.username = user?.username || "";
  profileForm.gender = settings?.gender || user?.gender || "private";
  profileForm.school_name = settings?.school_name || "";
  profileForm.bio = settings?.bio || "";
  profileForm.avatar_url = settings?.avatar_url || "";
  Object.assign(phoneVerification, data?.phone_verification || {});
}

function revokeAvatarPreview() {
  if (avatarPreviewUrl.value) {
    URL.revokeObjectURL(avatarPreviewUrl.value);
  }
  avatarPreviewUrl.value = "";
}

function pickAvatar() {
  avatarInputRef.value?.click();
}

function clearSelectedAvatar() {
  avatarFile.value = null;
  revokeAvatarPreview();
  if (avatarInputRef.value) {
    avatarInputRef.value.value = "";
  }
}

function onAvatarSelected(event) {
  const file = event.target.files?.[0] || null;
  if (!file) return;
  const fileName = String(file.name || "").toLowerCase();
  const hasAllowedExtension = [".jpg", ".jpeg", ".png", ".webp"].some((ext) => fileName.endsWith(ext));
  if (!allowedAvatarMimeTypes.has(file.type) && !hasAllowedExtension) {
    ui.info("仅支持 JPG、PNG、WebP 头像");
    clearSelectedAvatar();
    return;
  }
  if (file.size > avatarMaxUploadBytes) {
    ui.info("头像图片不能超过 2MB");
    clearSelectedAvatar();
    return;
  }
  revokeAvatarPreview();
  avatarFile.value = file;
  avatarPreviewUrl.value = URL.createObjectURL(file);
}

function clearPhoneVerificationSession() {
  phoneVerificationTicket.token = "";
  phoneVerificationTicket.masked_phone = "";
  phoneVerificationTicket.expires_in_seconds = 0;
  phoneVerificationForm.code = "";
  sessionStorage.removeItem("algowiki_phone_verification_ticket");
  sessionStorage.removeItem("algowiki_phone_verification_masked");
  sessionStorage.removeItem("algowiki_phone_verification_expires");
}

function savePhoneVerificationSession(payload) {
  phoneVerificationTicket.token = payload?.ticket_token || "";
  phoneVerificationTicket.masked_phone = payload?.masked_phone || "";
  phoneVerificationTicket.expires_in_seconds = Number(payload?.expires_in_seconds || 0);
  if (phoneVerificationTicket.token) {
    sessionStorage.setItem("algowiki_phone_verification_ticket", phoneVerificationTicket.token);
    sessionStorage.setItem("algowiki_phone_verification_masked", phoneVerificationTicket.masked_phone);
    sessionStorage.setItem("algowiki_phone_verification_expires", String(phoneVerificationTicket.expires_in_seconds));
    sessionStorage.setItem("algowiki_phone_verification_number", phoneVerificationForm.phone_number);
  }
}

function openPhoneVerificationModal() {
  sessionStorage.setItem(phoneVerificationPromptKey, "1");
  phoneVerificationModalOpen.value = true;
}

function closePhoneVerificationModal() {
  phoneVerificationModalOpen.value = false;
}

function resetAccountCancellationForm() {
  accountCancellationForm.current_password = "";
  accountCancellationForm.confirmation = "";
}

function openAccountCancellationModal() {
  accountCancellationModalOpen.value = true;
  resetAccountCancellationForm();
}

function closeAccountCancellationModal() {
  if (cancellingAccount.value) return;
  accountCancellationModalOpen.value = false;
  resetAccountCancellationForm();
}

async function submitAccountCancellation() {
  if (cancellingAccount.value) return;
  if (!accountCancellationForm.current_password) {
    ui.info("请输入当前密码");
    return;
  }
  if (accountCancellationForm.confirmation !== ACCOUNT_CANCELLATION_CONFIRM_TEXT) {
    ui.info(`请输入“${ACCOUNT_CANCELLATION_CONFIRM_TEXT}”确认操作`);
    return;
  }

  cancellingAccount.value = true;
  try {
    await api.post("/me/cancel-account/", {
      current_password: accountCancellationForm.current_password,
      confirmation: accountCancellationForm.confirmation,
    });
    accountCancellationModalOpen.value = false;
    resetAccountCancellationForm();
    clearPhoneVerificationSession();
    sessionStorage.removeItem(phoneVerificationPromptKey);
    auth.clearAuth();
    ui.success("账号已注销");
    await router.replace({ name: "home" });
  } catch (error) {
    ui.error(getErrorText(error, "账号注销失败"));
  } finally {
    cancellingAccount.value = false;
  }
}

function toggleProfileEditor() {
  if (!profileEditVisible.value && profile.value) {
    applyProfileForm(profile.value);
    clearSelectedAvatar();
  }
  profileEditVisible.value = !profileEditVisible.value;
}

function cancelProfileEditor() {
  if (profile.value) {
    applyProfileForm(profile.value);
  }
  clearSelectedAvatar();
  profileEditVisible.value = false;
}

function clearEmailChangeSession() {
  emailChangeTicket.token = "";
  emailChangeTicket.masked_email = "";
  emailChangeTicket.expires_in_seconds = 0;
  emailChangeForm.code = "";
}

function applyEmailChangeDefaults(data) {
  const pendingEmail = data?.pending_email || "";
  emailChangeForm.email = pendingEmail || data?.email || "";
  emailChangeForm.current_password = "";
  clearEmailChangeSession();
}

function clearPasswordChangeSession() {
  passwordChangeTicket.token = "";
  passwordChangeTicket.masked_email = "";
  passwordChangeTicket.expires_in_seconds = 0;
  passwordForm.code = "";
}

function resetPasswordVisibility() {
  passwordVisibility.old = false;
  passwordVisibility.new = false;
  passwordVisibility.confirm = false;
}

function togglePasswordVisibility(key) {
  if (!(key in passwordVisibility)) return;
  passwordVisibility[key] = !passwordVisibility[key];
}

function normalizeNumericIdList(values) {
  const result = [];
  for (const value of values || []) {
    const numeric = Number(value);
    if (Number.isInteger(numeric) && numeric > 0 && !result.includes(numeric)) {
      result.push(numeric);
    }
  }
  return result;
}

function clearMyTrickEditForm() {
  myTrickEditForm.record_id = "";
  myTrickEditForm.source = "entry";
  myTrickEditForm.entry_id = null;
  myTrickEditForm.archive_id = null;
  myTrickEditForm.title = "";
  myTrickEditForm.keywords_text = "";
  myTrickEditForm.content_md = "";
  myTrickEditForm.term_ids = [];
}

function startEditMyTrick(item) {
  if (!item?.record_id) return;
  editingMyTrickRecordId.value = item.record_id;
  myTrickEditForm.record_id = item.record_id;
  myTrickEditForm.source = item.source || "entry";
  myTrickEditForm.entry_id = item.entry_id || item.id || null;
  myTrickEditForm.archive_id = item.archive_id || null;
  myTrickEditForm.title = item.title || "";
  myTrickEditForm.keywords_text = item.keywords_text || "";
  myTrickEditForm.content_md = item.content_md || "";
  myTrickEditForm.term_ids = normalizeNumericIdList(item.term_ids || (item.terms || []).map((term) => term.id));
}

function cancelEditMyTrick() {
  editingMyTrickRecordId.value = "";
  clearMyTrickEditForm();
}

function toggleMyTrickTerm(termId) {
  const numeric = Number(termId);
  if (!Number.isInteger(numeric) || numeric <= 0) return;
  if (myTrickEditForm.term_ids.includes(numeric)) {
    myTrickEditForm.term_ids = myTrickEditForm.term_ids.filter((item) => item !== numeric);
  } else {
    myTrickEditForm.term_ids = [...myTrickEditForm.term_ids, numeric];
  }
}

function clearRevisionEditForm() {
  revisionEditForm.base_title = "";
  revisionEditForm.base_summary = "";
  revisionEditForm.base_content_md = "";
  revisionEditForm.base_updated_at = "";
  revisionEditForm.proposed_title = "";
  revisionEditForm.proposed_summary = "";
  revisionEditForm.proposed_content_md = "";
  revisionEditForm.reason = "";
}

function toggleRevisionDetails(revisionId) {
  if (expandedRevisionId.value === revisionId) {
    expandedRevisionId.value = null;
    editingRevisionId.value = null;
    clearRevisionEditForm();
    return;
  }
  expandedRevisionId.value = revisionId;
  editingRevisionId.value = null;
  clearRevisionEditForm();
}

function startEditRevision(item) {
  if (!item || item.status !== "pending") return;
  expandedRevisionId.value = item.id;
  editingRevisionId.value = item.id;
  revisionEditForm.base_title = item.base_title || item.article_title || "";
  revisionEditForm.base_summary = Object.prototype.hasOwnProperty.call(item, "base_summary")
    ? (item.base_summary ?? "")
    : (item.article_summary || "");
  revisionEditForm.base_content_md = Object.prototype.hasOwnProperty.call(item, "base_content_md")
    ? (item.base_content_md ?? "")
    : (item.article_content_md || "");
  revisionEditForm.base_updated_at = item.base_updated_at || item.article_updated_at || "";
  revisionEditForm.proposed_title = item.proposed_title || item.article_title || "";
  revisionEditForm.proposed_summary = item.proposed_summary || "";
  revisionEditForm.proposed_content_md = item.proposed_content_md || "";
  revisionEditForm.reason = item.reason || "";
}

function cancelRevisionEdit() {
  editingRevisionId.value = null;
  clearRevisionEditForm();
}

async function loadProfile() {
  const { data } = await api.get("/me/");
  profile.value = data;
  const settings = data.profile_settings || data.user || {};
  applyProfileForm(data);
  applyEmailChangeDefaults(settings);
  if (phoneVerification.status === "verified") {
    clearPhoneVerificationSession();
    sessionStorage.removeItem(phoneVerificationPromptKey);
    closePhoneVerificationModal();
  } else if (!sessionStorage.getItem(phoneVerificationPromptKey)) {
    openPhoneVerificationModal();
  }
}

async function sendPhoneVerificationCode() {
  if (!phoneVerificationForm.phone_number) {
    ui.info("请输入手机号");
    return;
  }
  sendingPhoneCode.value = true;
  try {
    const captcha = await getCaptchaProof("send_sms_code");
    const { data } = await api.post("/phone-verifications/me/", {
      phone_number: phoneVerificationForm.phone_number,
      country_code: "86",
      captcha,
    });
    Object.assign(phoneVerification, data?.verification || data || {});
    savePhoneVerificationSession(data || {});
    phoneVerificationForm.code = "";
    ui.success("短信验证码已发送");
  } catch (error) {
    ui.error(getErrorText(error, "短信验证码发送失败"));
  } finally {
    sendingPhoneCode.value = false;
  }
}

async function checkPhoneVerificationCode() {
  if (!phoneVerificationTicket.token) {
    ui.info("请先发送验证码");
    return;
  }
  if (!phoneVerificationForm.code) {
    ui.info("请输入短信验证码");
    return;
  }
  checkingPhoneCode.value = true;
  try {
    const { data } = await api.post("/phone-verifications/check/", {
      ticket_token: phoneVerificationTicket.token,
      phone_number: phoneVerificationForm.phone_number,
      verify_code: phoneVerificationForm.code,
    });
    Object.assign(phoneVerification, data || {});
    if (data?.status === "verified") {
      clearPhoneVerificationSession();
      sessionStorage.removeItem(phoneVerificationPromptKey);
      phoneVerificationForm.phone_number = "";
      sessionStorage.removeItem("algowiki_phone_verification_number");
      closePhoneVerificationModal();
      ui.success("手机号验证已通过");
      await loadProfile();
    } else if (data?.status === "rejected") {
      clearPhoneVerificationSession();
      ui.error("手机号验证未通过，请核对后重新发送验证码。");
    } else {
      ui.info("手机号验证暂未完成，请输入正确验证码。");
    }
  } catch (error) {
    ui.error(getErrorText(error, "手机号验证失败"));
  } finally {
    checkingPhoneCode.value = false;
  }
}

async function loadIssues(page = 1, append = false) {
  const params = { page };
  if (issueFilters.scope !== "all") params.mine = 1;
  if (issueFilters.kind) params.kind = issueFilters.kind;
  if (issueFilters.visibility) params.visibility = issueFilters.visibility;
  if (issueFilters.status) params.status = issueFilters.status;
  if (issueFilters.search.trim()) params.search = issueFilters.search.trim();
  const { data } = await api.get("/issues/", { params });
  const parsed = unpackListPayload(data, issues.value.length);
  issues.value = append ? [...issues.value, ...parsed.results] : parsed.results;
  issuesMeta.count = parsed.count;
  issuesMeta.next = parsed.next;
}

async function loadMyComments(page = 1, append = false) {
  const { data } = await api.get("/comments/mine/", { params: { page } });
  const parsed = unpackListPayload(data, myComments.value.length);
  myComments.value = append ? [...myComments.value, ...parsed.results] : parsed.results;
  myCommentsMeta.count = parsed.count;
  myCommentsMeta.next = parsed.next;
}

async function loadMyMomentPosts(page = 1, append = false) {
  const params = { page, mine: 1 };
  if (momentPostFilters.status) params.status = momentPostFilters.status;
  if (momentPostFilters.search.trim()) params.search = momentPostFilters.search.trim();
  const { data } = await api.get("/moments/", { params });
  const parsed = unpackListPayload(data, myMomentPosts.value.length);
  myMomentPosts.value = append ? [...myMomentPosts.value, ...parsed.results] : parsed.results;
  myMomentPostsMeta.count = parsed.count;
  myMomentPostsMeta.next = parsed.next;
}

async function loadMyMomentComments(page = 1, append = false) {
  const params = { page, mine: 1 };
  if (momentCommentFilters.status) params.status = momentCommentFilters.status;
  if (momentCommentFilters.search.trim()) params.search = momentCommentFilters.search.trim();
  const { data } = await api.get("/moment-comments/", { params });
  const parsed = unpackListPayload(data, myMomentComments.value.length);
  myMomentComments.value = append ? [...myMomentComments.value, ...parsed.results] : parsed.results;
  myMomentCommentsMeta.count = parsed.count;
  myMomentCommentsMeta.next = parsed.next;
}

async function loadMyRevisions(page = 1, append = false) {
  const params = { page };
  if (auth.user?.id) params.proposer = auth.user.id;
  if (revisionFilters.status) params.status = revisionFilters.status;
  if (revisionFilters.search.trim()) params.search = revisionFilters.search.trim();
  const { data } = await api.get("/revisions/", { params });
  const parsed = unpackListPayload(data, myRevisions.value.length);
  myRevisions.value = append ? [...myRevisions.value, ...parsed.results] : parsed.results;
  myRevisionsMeta.count = parsed.count;
  myRevisionsMeta.next = parsed.next;
  if (!append) {
    await loadMyRevisionPendingCount();
    if (expandedRevisionId.value && !myRevisions.value.some((item) => item.id === expandedRevisionId.value)) {
      expandedRevisionId.value = null;
      cancelRevisionEdit();
    }
  }
}

async function loadMyRevisionPendingCount() {
  const params = { page: 1, status: "pending" };
  if (auth.user?.id) params.proposer = auth.user.id;
  const { data } = await api.get("/revisions/", { params });
  const parsed = unpackListPayload(data, 0);
  pendingRevisionTotal.value = parsed.count;
}

async function loadMyEvents(page = 1, append = false) {
  const params = { page };
  if (eventFilters.event_type) params.event_type = eventFilters.event_type;
  const { data } = await api.get("/me/events/", { params });
  const parsed = unpackListPayload(data, myEvents.value.length);
  myEvents.value = append ? [...myEvents.value, ...parsed.results] : parsed.results;
  myEventsMeta.count = parsed.count;
  myEventsMeta.next = parsed.next;
}

async function loadMySecurityEvents(page = 1, append = false) {
  try {
    const params = { page };
    if (securityEventFilters.event_type) params.event_type = securityEventFilters.event_type;
    if (securityEventFilters.success) params.success = securityEventFilters.success;
    const { data } = await api.get("/me/security-events/", { params });
    const parsed = unpackListPayload(data, mySecurityEvents.value.length);
    mySecurityEvents.value = append ? [...mySecurityEvents.value, ...parsed.results] : parsed.results;
    mySecurityEventsMeta.count = parsed.count;
    mySecurityEventsMeta.next = parsed.next;
  } catch (error) {
    if (isSchemaOutdatedError(error)) {
      securitySchemaOutdated.value = true;
      mySecurityEvents.value = [];
      mySecurityEventsMeta.count = 0;
      mySecurityEventsMeta.next = "";
      return;
    }
    throw error;
  }
}

async function loadMySecuritySummary() {
  securitySummaryLoading.value = true;
  try {
    const { data } = await api.get("/me/security-summary/", {
      params: { window_hours: securitySummaryWindow.value },
    });
    mySecuritySummary.value = data;
  } catch (error) {
    if (isSchemaOutdatedError(error)) {
      securitySchemaOutdated.value = true;
      mySecuritySummary.value = null;
      return;
    }
    ui.error(getErrorText(error, "安全概览加载失败"));
  } finally {
    securitySummaryLoading.value = false;
  }
}

async function loadStarredArticles(page = 1, append = false) {
  const params = { page };
  if (starFilters.search.trim()) params.search = starFilters.search.trim();
  const { data } = await api.get("/articles/starred/", { params });
  const parsed = unpackListPayload(data, starredArticles.value.length);
  starredArticles.value = append ? [...starredArticles.value, ...parsed.results] : parsed.results;
  starredMeta.count = parsed.count;
  starredMeta.next = parsed.next;
}

async function loadMyTricks() {
  const { data } = await api.get("/me/tricks/");
  const parsed = unpackListPayload(data, 0);
  myTricks.value = parsed.results;
  myTricksMeta.count = parsed.count;
  if (editingMyTrickRecordId.value && !myTricks.value.some((item) => item.record_id === editingMyTrickRecordId.value)) {
    cancelEditMyTrick();
  }
}

async function loadMyTrickTerms() {
  const { data } = await api.get("/trick-terms/");
  const parsed = unpackListPayload(data, 0);
  myTrickTerms.value = parsed.results;
}

async function loadMyPracticeProposals() {
  const { data } = await api.get("/me/competition-practice-proposals/");
  const parsed = unpackListPayload(data, 0);
  myPracticeProposals.value = parsed.results;
  myPracticeMeta.count = parsed.count;
}

async function loadMyCompetitionNotices() {
  const { data } = await api.get("/me/competition-notices/");
  const parsed = unpackListPayload(data, 0);
  myCompetitionNotices.value = parsed.results;
  myNoticeMeta.count = parsed.count;
}

async function loadMoreIssues() {
  if (!issuesMeta.next || issuesMeta.loadingMore) return;
  issuesMeta.loadingMore = true;
  try {
    await loadIssues(nextPageFromUrl(issuesMeta.next), true);
  } finally {
    issuesMeta.loadingMore = false;
  }
}

async function loadMoreMyComments() {
  if (!myCommentsMeta.next || myCommentsMeta.loadingMore) return;
  myCommentsMeta.loadingMore = true;
  try {
    await loadMyComments(nextPageFromUrl(myCommentsMeta.next), true);
  } finally {
    myCommentsMeta.loadingMore = false;
  }
}

async function loadMoreMyMomentPosts() {
  if (!myMomentPostsMeta.next || myMomentPostsMeta.loadingMore) return;
  myMomentPostsMeta.loadingMore = true;
  try {
    await loadMyMomentPosts(nextPageFromUrl(myMomentPostsMeta.next), true);
  } finally {
    myMomentPostsMeta.loadingMore = false;
  }
}

async function loadMoreMyMomentComments() {
  if (!myMomentCommentsMeta.next || myMomentCommentsMeta.loadingMore) return;
  myMomentCommentsMeta.loadingMore = true;
  try {
    await loadMyMomentComments(nextPageFromUrl(myMomentCommentsMeta.next), true);
  } finally {
    myMomentCommentsMeta.loadingMore = false;
  }
}

async function loadMoreMyEvents() {
  if (!myEventsMeta.next || myEventsMeta.loadingMore) return;
  myEventsMeta.loadingMore = true;
  try {
    await loadMyEvents(nextPageFromUrl(myEventsMeta.next), true);
  } finally {
    myEventsMeta.loadingMore = false;
  }
}

async function loadMoreMySecurityEvents() {
  if (!mySecurityEventsMeta.next || mySecurityEventsMeta.loadingMore) return;
  mySecurityEventsMeta.loadingMore = true;
  try {
    await loadMySecurityEvents(nextPageFromUrl(mySecurityEventsMeta.next), true);
  } finally {
    mySecurityEventsMeta.loadingMore = false;
  }
}

async function loadMoreMyRevisions() {
  if (!myRevisionsMeta.next || myRevisionsMeta.loadingMore) return;
  myRevisionsMeta.loadingMore = true;
  try {
    await loadMyRevisions(nextPageFromUrl(myRevisionsMeta.next), true);
  } finally {
    myRevisionsMeta.loadingMore = false;
  }
}

async function loadMoreStarredArticles() {
  if (!starredMeta.next || starredMeta.loadingMore) return;
  starredMeta.loadingMore = true;
  try {
    await loadStarredArticles(nextPageFromUrl(starredMeta.next), true);
  } finally {
    starredMeta.loadingMore = false;
  }
}

function resetIssueFilters() {
  issueFilters.scope = "mine";
  issueFilters.kind = "";
  issueFilters.visibility = "";
  issueFilters.status = "";
  issueFilters.search = "";
  loadIssues(1, false);
}

function resetRevisionFilters() {
  revisionFilters.status = "";
  revisionFilters.search = "";
  expandedRevisionId.value = null;
  cancelRevisionEdit();
  loadMyRevisions(1, false);
}

function resetMomentPostFilters() {
  momentPostFilters.status = "";
  momentPostFilters.search = "";
  loadMyMomentPosts(1, false);
}

function resetMomentCommentFilters() {
  momentCommentFilters.status = "";
  momentCommentFilters.search = "";
  loadMyMomentComments(1, false);
}

async function submitMyTrickEdit() {
  if (!editingMyTrickRecordId.value || savingMyTrickRecordId.value) return;
  const title = myTrickEditForm.title.trim();
  const keywordsText = myTrickEditForm.keywords_text.trim();
  const contentMd = myTrickEditForm.content_md.trim();
  const termIds = normalizeNumericIdList(myTrickEditForm.term_ids);

  if (!title) {
    ui.info("请填写 trick 标题");
    return;
  }
  if (!keywordsText) {
    ui.info("请填写至少 1 个关键词");
    return;
  }
  if (!termIds.length) {
    ui.info("请至少选择一个词条");
    return;
  }
  if (!contentMd) {
    ui.info("请填写 trick 内容");
    return;
  }

  const recordId = editingMyTrickRecordId.value;
  savingMyTrickRecordId.value = recordId;
  try {
    const payload = {
      title,
      keywords_text: keywordsText,
      content_md: myTrickEditForm.content_md,
      term_ids: termIds,
    };
    if (myTrickEditForm.source === "deleted_archive") {
      await api.post("/me/tricks/resubmit-deleted/", {
        ...payload,
        archive_id: myTrickEditForm.archive_id,
      });
      ui.success("已从删除记录重新提交，等待审核");
    } else {
      await api.patch(`/tricks/${myTrickEditForm.entry_id}/`, payload);
      ui.success("已保存修改，等待审核");
    }
    cancelEditMyTrick();
    await loadMyTricks();
  } catch (error) {
    ui.error(getErrorText(error, "trick 提交失败"));
  } finally {
    savingMyTrickRecordId.value = "";
  }
}

async function saveRevisionEdit(item) {
  if (!item?.id || savingRevisionEditId.value) return;
  if (!revisionEditForm.proposed_title.trim() || !revisionEditForm.proposed_content_md.trim()) {
    ui.info("Title and markdown content are required.");
    return;
  }

  savingRevisionEditId.value = item.id;
  try {
    const payload = {
      base_title: revisionEditForm.base_title,
      base_summary: revisionEditForm.base_summary,
      base_content_md: revisionEditForm.base_content_md,
      base_updated_at: revisionEditForm.base_updated_at || null,
      proposed_title: revisionEditForm.proposed_title.trim(),
      proposed_summary: revisionEditForm.proposed_summary.trim(),
      proposed_content_md: revisionEditForm.proposed_content_md,
      reason: revisionEditForm.reason.trim(),
    };
    await api.patch(`/revisions/${item.id}/`, payload);
    ui.success("Revision proposal updated.");
    cancelRevisionEdit();
    await loadMyRevisions(1, false);
    expandedRevisionId.value = item.id;
  } catch (error) {
    const merge = error?.response?.data?.merge;
    if (error?.response?.status === 409 && error?.response?.data?.code === "revision_merge_conflict" && merge) {
      revisionEditForm.base_title = merge?.current?.title ?? revisionEditForm.base_title;
      revisionEditForm.base_summary = merge?.current?.summary ?? revisionEditForm.base_summary;
      revisionEditForm.base_content_md = merge?.current?.content_md ?? revisionEditForm.base_content_md;
      revisionEditForm.base_updated_at = merge?.current?.updated_at ?? revisionEditForm.base_updated_at;
      revisionEditForm.proposed_title = merge?.merged?.title ?? revisionEditForm.proposed_title;
      revisionEditForm.proposed_summary = merge?.merged?.summary ?? revisionEditForm.proposed_summary;
      revisionEditForm.proposed_content_md = merge?.merged?.content_md ?? revisionEditForm.proposed_content_md;
      ui.error(error?.response?.data?.detail || "条目已有新版本，已把合并结果放回编辑器，请处理冲突后再保存。");
      return;
    }
    ui.error(getErrorText(error, "Failed to update revision proposal"));
  } finally {
    savingRevisionEditId.value = null;
  }
}

async function cancelRevision(item) {
  if (!item?.id || item.status !== "pending" || cancellingRevisionId.value) return;
  if (!window.confirm("Cancel this pending revision proposal?")) return;

  cancellingRevisionId.value = item.id;
  try {
    await api.delete(`/revisions/${item.id}/`);
    ui.success("Revision proposal cancelled.");
    if (expandedRevisionId.value === item.id) {
      expandedRevisionId.value = null;
      cancelRevisionEdit();
    }
    await loadMyRevisions(1, false);
  } catch (error) {
    ui.error(getErrorText(error, "Failed to cancel revision proposal"));
  } finally {
    cancellingRevisionId.value = null;
  }
}

async function saveProfile() {
  if (savingProfile.value) return;
  savingProfile.value = true;
  try {
    const payload = {
      username: profileForm.username.trim(),
      gender: profileForm.gender || "private",
      school_name: profileForm.school_name.trim(),
      bio: profileForm.bio.trim(),
    };
    if (!payload.username) {
      ui.info("请填写昵称");
      return;
    }
    let requestBody = payload;
    if (avatarFile.value) {
      const captcha = await getCaptchaProof("upload_image");
      const formData = new FormData();
      Object.entries(payload).forEach(([key, value]) => formData.append(key, value));
      formData.append("avatar_image", avatarFile.value);
      formData.append("captcha", JSON.stringify(captcha));
      requestBody = formData;
    }
    const { data } = await api.patch("/me/", requestBody);
    if (profile.value) {
      profile.value.user = data.user || profile.value.user;
      profile.value.profile_settings = data.profile_settings || payload;
    }
    applyProfileForm(data);
    clearSelectedAvatar();
    if (auth.user && data.user) {
      auth.applyAuth(auth.token, data.user);
    }
    profileEditVisible.value = false;
    ui.success("个人资料已更新");
  } catch (error) {
    ui.error(captchaErrorMessage(error, getErrorText(error, "保存资料失败")));
  } finally {
    savingProfile.value = false;
  }
}

async function sendEmailChangeCode() {
  if (sendingEmailCode.value) return;
  if (!emailChangeForm.email.trim() || !emailChangeForm.current_password) {
    ui.info("请填写目标邮箱和当前密码");
    return;
  }

  sendingEmailCode.value = true;
  try {
    const captcha = await getCaptchaProof("bind_email");
    const { data } = await api.post("/me/email-code/", {
      email: emailChangeForm.email.trim(),
      current_password: emailChangeForm.current_password,
      captcha,
    });
    emailChangeTicket.token = data.ticket_token || "";
    emailChangeTicket.masked_email = data.masked_email || "";
    emailChangeTicket.expires_in_seconds = Number(data.expires_in_seconds || 0);
    emailChangeForm.code = "";
    if (profile.value?.profile_settings) {
      profile.value.profile_settings.pending_email = emailChangeForm.email.trim();
    }
    ui.success(`验证码已发送至 ${emailChangeTicket.masked_email}`);
  } catch (error) {
    ui.error(getErrorText(error, "邮箱验证码发送失败"));
  } finally {
    sendingEmailCode.value = false;
  }
}

async function confirmEmailChange() {
  if (changingEmail.value) return;
  if (!emailChangeTicket.token || !emailChangeForm.code.trim()) {
    ui.info("请先发送验证码并填写收到的验证码");
    return;
  }

  changingEmail.value = true;
  try {
    const { data } = await api.post("/me/change-email/", {
      ticket_token: emailChangeTicket.token,
      code: emailChangeForm.code.trim(),
    });
    if (profile.value) {
      profile.value.user = data.user || profile.value.user;
      profile.value.profile_settings = data.profile_settings || profile.value.profile_settings;
    }
    applyEmailChangeDefaults(data.profile_settings || {});
    if (auth.user && data.user) {
      auth.applyAuth(auth.token, data.user);
    }
    ui.success("邮箱已更新并验证");
  } catch (error) {
    ui.error(getErrorText(error, "邮箱确认失败"));
  } finally {
    changingEmail.value = false;
  }
}

async function sendPasswordChangeCode() {
  if (sendingPasswordCode.value) return;
  if (!passwordForm.old_password || !passwordForm.new_password || !passwordForm.confirm_password) {
    ui.info("请完整填写密码信息");
    return;
  }

  sendingPasswordCode.value = true;
  try {
    const captcha = await getCaptchaProof("change_password_code");
    const { data } = await api.post("/me/change-password-code/", {
      old_password: passwordForm.old_password,
      new_password: passwordForm.new_password,
      confirm_password: passwordForm.confirm_password,
      captcha,
    });
    passwordChangeTicket.token = data.ticket_token || "";
    passwordChangeTicket.masked_email = data.masked_email || "";
    passwordChangeTicket.expires_in_seconds = Number(data.expires_in_seconds || 0);
    passwordForm.code = "";
    ui.success(`验证码已发送至 ${passwordChangeTicket.masked_email}`);
  } catch (error) {
    ui.error(getErrorText(error, "密码验证码发送失败"));
  } finally {
    sendingPasswordCode.value = false;
  }
}

async function submitIssue() {
  if (!issueForm.title.trim() || !issueForm.content.trim()) {
    ui.info("请填写标题和问题描述");
    return;
  }
  try {
    const { data } = await api.post("/issues/", {
      kind: issueForm.kind,
      visibility: issueForm.visibility,
      title: issueForm.title.trim(),
      content: issueForm.content.trim(),
    });
    issueForm.title = "";
    issueForm.content = "";
    if (data?.status === "pending") {
      ui.success("Issue/Request 已提交（审核中）");
    } else {
      ui.success("Issue/Request 已提交");
    }
    await loadIssues(1, false);
  } catch (error) {
    ui.error(getErrorText(error, "提交失败"));
  }
}

async function deleteMyComment(item) {
  if (!item?.id || deletingMyCommentId.value) return;
  deletingMyCommentId.value = item.id;
  try {
    await api.delete(`/comments/${item.id}/`);
    ui.success("评论已删除");
    await Promise.all([loadProfile(), loadMyComments()]);
  } catch (error) {
    ui.error(getErrorText(error, "删除评论失败"));
  } finally {
    deletingMyCommentId.value = null;
  }
}

async function deleteMyMoment(item) {
  if (!item?.id || deletingMyMomentId.value) return;
  if (!window.confirm("确认删除这条动态？其下评论也会同步删除。")) return;
  deletingMyMomentId.value = item.id;
  try {
    await api.delete(`/moments/${item.id}/`);
    ui.success("动态已删除");
    await Promise.all([loadProfile(), loadMyMomentPosts(), loadMyMomentComments()]);
  } catch (error) {
    ui.error(getErrorText(error, "删除动态失败"));
  } finally {
    deletingMyMomentId.value = null;
  }
}

async function deleteMyMomentComment(item) {
  if (!item?.id || deletingMyMomentCommentId.value) return;
  if (!window.confirm("确认删除这条动态评论？")) return;
  deletingMyMomentCommentId.value = item.id;
  try {
    await api.delete(`/moment-comments/${item.id}/`);
    ui.success("动态评论已删除");
    await Promise.all([loadProfile(), loadMyMomentComments(), loadMyMomentPosts()]);
  } catch (error) {
    ui.error(getErrorText(error, "删除动态评论失败"));
  } finally {
    deletingMyMomentCommentId.value = null;
  }
}

async function unstarFromProfile(item) {
  if (!item?.id || unstarLoadingId.value) return;
  unstarLoadingId.value = item.id;
  try {
    await api.post(`/articles/${item.id}/unstar/`);
    ui.success("已取消收藏");
    await Promise.all([loadProfile(), loadStarredArticles()]);
  } catch (error) {
    ui.error(getErrorText(error, "取消收藏失败"));
  } finally {
    unstarLoadingId.value = null;
  }
}

async function changePassword() {
  if (changingPassword.value) return;
  if (!passwordChangeTicket.token || !passwordForm.code.trim()) {
    ui.info("请先发送验证码并填写收到的验证码");
    return;
  }

  changingPassword.value = true;
  try {
    const { data } = await api.post("/me/change-password/", {
      ticket_token: passwordChangeTicket.token,
      code: passwordForm.code.trim(),
    });
    const nextUser = auth.user || profile.value?.user || null;
    if (data?.token && nextUser) {
      auth.applyAuth(data.token, nextUser);
    }
    passwordForm.old_password = "";
    passwordForm.new_password = "";
    passwordForm.confirm_password = "";
    clearPasswordChangeSession();
    resetPasswordVisibility();
    ui.success("密码修改成功");
    await Promise.all([loadMySecurityEvents(), loadMySecuritySummary()]);
  } catch (error) {
    ui.error(getErrorText(error, "密码修改失败"));
  } finally {
    changingPassword.value = false;
  }
}

function formatEventType(value) {
  const labels = {
    star: "收藏",
    comment: "评论",
    issue: "Issue/Request",
    revision: "修订",
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
    register_code_sent: "注册验证码发送",
    register_success: "注册成功",
    logout: "退出登录",
    password_change_requested: "密码修改验证码",
    password_changed: "密码修改",
    password_reset_requested: "找回密码验证码",
    password_reset_completed: "找回密码完成",
    email_change_requested: "邮箱验证码发送",
    email_changed: "邮箱变更",
    user_banned: "账号封禁",
    user_unbanned: "账号解封",
    user_soft_deleted: "账号软删除",
    user_reactivated: "账号恢复",
    user_role_changed: "角色变更",
  };
  return labels[value] || value || "未知事件";
}

onMounted(async () => {
  try {
    await Promise.all([
      loadProfile(),
      loadIssues(),
      loadMyComments(),
      loadMyMomentPosts(),
      loadMyMomentComments(),
      loadMyRevisions(),
      loadMyEvents(),
      loadMySecurityEvents(),
      loadMySecuritySummary(),
      loadStarredArticles(),
      loadMyTricks(),
      loadMyTrickTerms(),
      loadMyPracticeProposals(),
      loadMyCompetitionNotices(),
    ]);
  } catch (error) {
    ui.error(getErrorText(error, "个人中心加载失败"));
  }
});

onBeforeUnmount(() => {
  revokeAvatarPreview();
});
</script>

<style scoped>
.profile-layout {
  display: block;
  padding: 18px 8px 56px;
}

.profile-shell {
  display: grid;
  grid-template-columns: minmax(190px, 260px) minmax(0, 1fr);
  gap: 44px;
  align-items: start;
  width: min(1180px, 100%);
  margin: 0 auto;
}

.profile-main {
  border: 0;
  border-radius: 0;
  background: transparent;
  padding: 0;
  box-shadow: none;
  min-width: 0;
}

.profile-content {
  min-width: 0;
  display: grid;
  gap: 26px;
  width: 100%;
  max-width: 780px;
  margin: 0 auto;
}

.profile-sidebar {
  position: sticky;
  top: 84px;
  display: grid;
  gap: 14px;
}

.sidebar-card {
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
  padding: 0;
}

.sidebar-summary {
  display: none;
}

.sidebar-profile {
  display: grid;
  gap: 12px;
}

.sidebar-avatar {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  object-fit: cover;
}

.sidebar-avatar--fallback {
  display: grid;
  place-items: center;
  background: color-mix(in srgb, var(--accent) 18%, var(--surface));
  color: var(--accent);
  font-size: 24px;
  font-weight: 800;
}

.profile-sidebar .sidebar-profile__body h2 {
  margin: 0;
  font-size: 22px;
}

.sidebar-action {
  width: fit-content;
}

.profile-nav {
  display: grid;
  gap: 24px;
}

.profile-nav-group {
  display: grid;
  gap: 6px;
}

.profile-nav-title {
  margin: 0;
  font-size: 12px;
  font-weight: 700;
  color: var(--text-quiet);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.profile-nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  border: 0;
  background: transparent;
  color: var(--text-soft);
  border-radius: 10px;
  padding: 10px 12px;
  text-align: left;
  font-size: 14px;
  line-height: 1.2;
  font-family: inherit;
  cursor: pointer;
  transition: all 0.2s ease;
}

.profile-nav-item:hover {
  color: var(--text-strong);
  background: color-mix(in srgb, var(--surface) 70%, transparent);
}

.profile-nav-item.is-active {
  background: color-mix(in srgb, var(--accent) 12%, var(--surface-strong));
  color: var(--accent);
  font-weight: 600;
}

.profile-nav-icon {
  width: 18px;
  display: inline-grid;
  place-items: center;
  color: inherit;
  font-size: 16px;
}

.profile-headline {
  display: grid;
  gap: 6px;
  justify-items: start;
  text-align: left;
  padding: 2px 2px 0;
}

.profile-main h1 {
  font-size: 34px;
  margin: 0;
}

.profile-main h2 {
  font-size: 28px;
}

.profile-tabs {
  display: none;
}

.profile-tab {
  border: 1px solid var(--hairline);
  background: var(--surface-strong);
  color: var(--text-soft);
  border-radius: 999px;
  padding: 7px 14px;
  font-size: 14px;
  line-height: 1;
  cursor: pointer;
  transition: all 0.2s ease;
}

.profile-tab:hover {
  border-color: var(--hairline-strong);
  color: var(--text-strong);
}

.profile-tab.is-active {
  border-color: color-mix(in srgb, var(--accent) 35%, transparent);
  background: color-mix(in srgb, var(--accent) 12%, var(--surface-strong));
  color: var(--accent);
  font-weight: 600;
}

.tab-panel {
  margin-top: 0;
  display: grid;
  gap: 14px;
}

.profile-head {
  display: grid;
  justify-items: center;
  gap: 12px;
  border: 0;
  border-radius: 0;
  background: transparent;
  padding: 0 0 4px;
  text-align: center;
}

.avatar {
  width: 112px;
  height: 112px;
  border-radius: 50%;
  object-fit: cover;
  border: 1px solid var(--hairline);
  box-shadow: var(--shadow-sm);
}

.avatar--fallback {
  display: grid;
  place-items: center;
  background: color-mix(in srgb, var(--accent) 16%, var(--surface));
  color: var(--accent);
  font-size: 24px;
  font-weight: 800;
}

.bio {
  margin: 8px 0 0;
  color: var(--text);
  font-size: 17px;
}

.profile-overview {
  justify-items: stretch;
  text-align: left;
}

.profile-identity {
  display: grid;
  justify-items: center;
  gap: 12px;
  text-align: center;
}

.profile-avatar-edit,
.profile-identity__body {
  display: grid;
  justify-items: center;
  gap: 8px;
}

.profile-avatar-actions,
.profile-edit-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
}

.profile-inline-name {
  width: min(280px, 100%);
  text-align: center;
  font-size: 18px;
  font-weight: 800;
}

.profile-identity h2 {
  margin: 0 0 4px;
}

.profile-overview-card {
  width: 100%;
}

.profile-overview-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.profile-overview-card__head h3 {
  margin-bottom: 4px;
}

.profile-info-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.profile-info-item {
  display: grid;
  gap: 4px;
  min-width: 0;
  padding: 12px 14px;
  border: 1px solid var(--hairline);
  border-radius: 12px;
  background: var(--surface-strong);
}

.profile-info-item span {
  color: var(--text-quiet);
  font-size: 12px;
  font-weight: 700;
}

.profile-info-item strong {
  color: var(--text-strong);
  font-size: 15px;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.profile-info-item small {
  color: var(--text-soft);
  font-size: 12px;
}

.profile-inline-input,
.profile-inline-textarea {
  width: 100%;
  margin: 0;
}

.profile-inline-textarea {
  min-height: 72px;
  resize: vertical;
}

.inline-radio-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.inline-radio {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 34px;
  padding: 7px 10px;
  border: 1px solid var(--hairline);
  border-radius: 999px;
  background: var(--surface);
  color: var(--text-soft);
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.inline-radio input {
  accent-color: var(--accent);
}

.summary-total {
  min-width: 42px;
  height: 42px;
  border-radius: 999px;
  display: inline-grid;
  place-items: center;
  background: color-mix(in srgb, var(--accent) 12%, var(--surface-strong));
  color: var(--accent);
  font-size: 18px;
}

.summary-card-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.summary-stat-card,
.summary-mini-item {
  min-width: 0;
  display: grid;
  gap: 6px;
  border: 1px solid var(--hairline);
  border-radius: 12px;
  background: var(--surface-strong);
  color: inherit;
  text-decoration: none;
  transition:
    border-color 0.18s ease,
    transform 0.18s ease,
    background 0.18s ease;
}

.summary-stat-card {
  padding: 13px 14px;
}

.summary-stat-card:hover,
.summary-mini-item:hover {
  transform: translateY(-1px);
  border-color: color-mix(in srgb, var(--accent) 28%, var(--hairline));
  background: color-mix(in srgb, var(--accent) 7%, var(--surface-strong));
}

.summary-stat-card span,
.summary-mini-item span {
  color: var(--text-soft);
  font-size: 13px;
}

.summary-stat-card strong {
  color: var(--text-strong);
  font-size: 24px;
}

.summary-stat-card--warning {
  border-color: color-mix(in srgb, #d97706 28%, var(--hairline));
}

.summary-stat-card--danger {
  border-color: color-mix(in srgb, #dc2626 30%, var(--hairline));
}

.creation-summary-list {
  display: grid;
  gap: 12px;
}

.creation-summary-group {
  display: grid;
  gap: 8px;
}

.creation-summary-group h4 {
  margin: 0;
  color: var(--text-strong);
  font-size: 15px;
}

.summary-mini-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.summary-mini-item {
  padding: 10px 11px;
}

.summary-mini-item strong {
  color: var(--text-strong);
  font-size: 18px;
}

.section-block {
  margin-top: 0;
  padding: 18px 20px;
  border: 1px solid var(--hairline);
  border-radius: 16px;
  background: var(--surface);
  box-shadow: var(--shadow-sm);
}

.section-block h3 {
  margin-bottom: 10px;
  font-size: 20px;
}

.settings-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 8px;
}

.section-block .input,
.section-block .textarea {
  margin-bottom: 8px;
}

.section-block .profile-inline-input,
.section-block .profile-inline-textarea,
.section-block .profile-inline-name {
  margin-bottom: 0;
}

.settings-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}

.avatar-upload-card {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 14px;
  align-items: center;
  margin: 0 0 8px;
  padding: 12px;
  border: 1px solid var(--hairline);
  border-radius: 14px;
  background: var(--surface-strong);
}

.avatar-upload-preview,
.avatar-upload-preview img,
.avatar-upload-fallback {
  width: 64px;
  height: 64px;
  border-radius: 50%;
}

.avatar-upload-preview img {
  display: block;
  object-fit: cover;
}

.avatar-upload-fallback {
  display: grid;
  place-items: center;
  background: color-mix(in srgb, var(--accent) 16%, var(--surface));
  color: var(--accent);
  font-weight: 800;
}

.avatar-upload-body {
  display: grid;
  gap: 6px;
}

.email-verify-card {
  margin-bottom: 8px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--hairline);
  background: var(--surface-strong);
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1200;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgba(15, 23, 42, 0.42);
  backdrop-filter: blur(8px);
}

.verification-modal {
  display: grid;
  gap: 14px;
  width: min(520px, 100%);
  border: 1px solid var(--hairline);
  border-radius: 16px;
  background: var(--surface);
  box-shadow: var(--shadow-lg);
  padding: 18px;
}

.verification-modal__head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.verification-modal h2 {
  margin: 0;
}

.icon-close {
  border: 0;
  border-radius: 999px;
  width: 32px;
  height: 32px;
  background: var(--surface-strong);
  color: var(--text);
  font-size: 20px;
  cursor: pointer;
}

.verification-form {
  display: grid;
  gap: 10px;
}

.password-field {
  position: relative;
}

.password-input {
  padding-right: 64px;
}

.password-toggle {
  position: absolute;
  top: 50%;
  right: 14px;
  transform: translateY(-50%);
  border: 0;
  background: transparent;
  padding: 0;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-soft);
  cursor: pointer;
}

.password-toggle:hover {
  color: var(--accent);
}

.pill {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 12px;
  margin-left: 8px;
  background: var(--surface-strong);
  color: var(--text-soft);
}

.pill-success {
  background: color-mix(in srgb, var(--accent) 16%, var(--surface-strong));
  color: var(--accent);
}

.kicker {
  margin: 0 0 6px;
  color: var(--accent);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.deleted-note {
  display: inline-flex;
  align-items: center;
  padding: 4px 8px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--accent) 10%, var(--surface-strong));
  color: var(--text-soft);
  font-size: 12px;
}

.history-row {
  margin-top: 10px;
  padding: 11px 12px;
  border-radius: 10px;
  background: var(--surface-strong);
  border: 1px solid var(--hairline);
}

.history-row-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.history-row-main {
  min-width: 0;
  display: grid;
  gap: 4px;
}

.history-row-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.my-trick-row {
  display: grid;
  gap: 10px;
}

.trick-chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 2px;
}

.trick-chip {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 12px;
  font-weight: 600;
  background: color-mix(in srgb, var(--accent) 12%, var(--surface));
  color: var(--accent);
}

.trick-chip-keyword {
  background: var(--surface-soft);
  color: var(--text-soft);
  border: 1px solid var(--hairline);
}

.content-preview {
  margin: 0;
  border: 1px solid var(--content-code-border);
  border-radius: 10px;
  background: linear-gradient(180deg, var(--content-code-bg-top), var(--content-code-bg));
  color: var(--content-code-text);
  padding: 10px;
  white-space: pre-wrap;
  font-family: var(--font-mono);
  line-height: 1.45;
  overflow: auto;
  box-shadow: var(--content-code-shadow);
}

.my-trick-preview {
  max-height: 120px;
  font-size: 13px;
}

.my-trick-editor {
  display: grid;
  gap: 8px;
  padding-top: 10px;
  border-top: 1px solid var(--hairline);
}

.my-trick-term-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.my-trick-term-option {
  border: 1px solid var(--hairline);
  border-radius: 999px;
  background: var(--surface-soft);
  color: var(--text-soft);
  padding: 6px 11px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.my-trick-term-option:hover {
  border-color: color-mix(in srgb, var(--accent) 40%, var(--hairline));
  color: var(--text-strong);
}

.my-trick-term-option.is-active {
  border-color: color-mix(in srgb, var(--accent) 45%, transparent);
  background: color-mix(in srgb, var(--accent) 14%, var(--surface-strong));
  color: var(--accent);
  font-weight: 700;
}

.my-trick-content-editor {
  min-height: 260px;
  font-family: var(--font-mono);
}

.my-trick-editor-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.revision-row {
  padding: 0;
  overflow: hidden;
}

.revision-card-trigger {
  border: 0;
  width: 100%;
  margin: 0;
  padding: 11px 12px;
  text-align: left;
  background: transparent;
  display: grid;
  gap: 4px;
  cursor: pointer;
}

.revision-row.is-expanded .revision-card-trigger {
  border-bottom: 1px solid var(--hairline);
}

.revision-detail {
  padding: 10px 12px 12px;
  display: grid;
  gap: 8px;
}

.revision-editor-content {
  min-height: 220px;
}

.revision-content-preview {
  margin: 0;
  border: 1px solid var(--content-code-border);
  border-radius: 10px;
  background: linear-gradient(180deg, var(--content-code-bg-top), var(--content-code-bg));
  color: var(--content-code-text);
  padding: 10px;
  white-space: pre-wrap;
  font-family: var(--font-mono);
  line-height: 1.45;
  max-height: 260px;
  overflow: auto;
  box-shadow: var(--content-code-shadow);
}

.revision-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.my-issues {
  margin-top: 0;
}

.my-issues h3 {
  margin-bottom: 10px;
  font-size: 24px;
}

.issue-form {
  display: grid;
  gap: 8px;
}

.issue-filters {
  margin-top: 10px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.issue-filters .select {
  width: 160px;
}

.issue-filters .input {
  width: min(320px, 100%);
}

.revision-filters {
  margin-top: 10px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.revision-filters .select {
  width: 180px;
}

.revision-filters .input {
  width: min(320px, 100%);
}

.issue-row {
  margin-top: 10px;
  padding: 11px 12px;
  border-radius: 10px;
  background: var(--surface-strong);
  border: 1px solid var(--hairline);
}

.issue-note {
  margin-top: 6px;
  color: var(--text);
}

.event {
  padding: 9px 0;
  display: grid;
  gap: 2px;
}

.event:first-of-type {
  border-top: 0;
}

.event-filters {
  margin-bottom: 8px;
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.event-filters .select {
  flex: 1;
  min-width: 0;
}

.event-filters .input {
  flex: 1;
  min-width: 0;
  margin: 0;
}

.security-summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 8px;
}

.security-summary-item {
  border: 1px solid var(--hairline);
  border-radius: 10px;
  padding: 8px;
  background: var(--surface-strong);
  display: grid;
  gap: 2px;
}

.security-summary-item strong {
  font-size: 18px;
}

.security-summary-item span {
  color: var(--muted);
  font-size: 12px;
}

.event-target {
  font-size: 13px;
  color: var(--text-quiet);
}

.star-link {
  display: block;
  color: var(--accent);
  font-size: 14px;
  line-height: 1.4;
}

.star-row {
  margin-top: 8px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
}

.privacy-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 10px;
}

.privacy-item,
.admin-link-card {
  display: grid;
  gap: 6px;
  padding: 12px 14px;
  border: 1px solid var(--hairline);
  border-radius: 12px;
  background: var(--surface-strong);
  transition:
    border-color 0.2s ease,
    background 0.2s ease,
    transform 0.2s ease;
}

.privacy-item strong,
.admin-link-card strong {
  font-size: 15px;
  color: var(--text-strong);
}

.privacy-item p,
.admin-link-card span {
  margin: 0;
  color: var(--text-soft);
  font-size: 13px;
  line-height: 1.55;
}

.danger-copy {
  color: var(--danger, #cf3f53);
}

.danger-note {
  margin-top: 10px;
  color: var(--text-soft);
  font-size: 13px;
}

.admin-link-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 10px;
}

.admin-link-card {
  color: inherit;
  text-decoration: none;
}

.admin-link-card:hover {
  border-color: color-mix(in srgb, var(--accent) 28%, var(--hairline));
  background: color-mix(in srgb, var(--accent) 8%, var(--surface-strong));
  transform: translateY(-1px);
}

@media (max-width: 1080px) {
  .profile-shell {
    grid-template-columns: 1fr;
  }

  .profile-sidebar {
    position: static;
  }
}

@media (max-width: 760px) {
  .profile-main h1 {
    font-size: 30px;
  }

  .settings-grid {
    grid-template-columns: 1fr;
  }

  .issue-filters .select,
  .issue-filters .input,
  .revision-filters .select,
  .revision-filters .input {
    width: 100%;
  }

  .security-summary-grid {
    grid-template-columns: 1fr;
  }

  .profile-info-grid {
    grid-template-columns: 1fr;
  }

  .summary-card-grid,
  .summary-mini-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .profile-overview-card__head {
    flex-direction: column;
  }

  .privacy-grid,
  .admin-link-grid {
    grid-template-columns: 1fr;
  }

  .profile-nav-item {
    width: 100%;
  }

  .history-row-head {
    flex-direction: column;
  }

  .history-row-actions {
    width: 100%;
    justify-content: flex-start;
  }

  .profile-tabs {
    display: none;
  }
}

@media (max-width: 560px) {
  .profile-head {
    flex-direction: column;
  }

  .profile-identity {
    justify-items: start;
    text-align: left;
  }

  .summary-card-grid,
  .summary-mini-grid {
    grid-template-columns: 1fr;
  }
}
</style>


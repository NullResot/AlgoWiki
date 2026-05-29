<template>
  <section class="moments-page">
    <header class="moments-hero">
      <div>
        <p class="kicker">AlgoWiki Moments</p>
        <h1>竞赛社群动态</h1>
        <p class="meta">记录学习日常，交流算法心得，分享每一次 AC 的喜悦。</p>
      </div>
      <div class="hero-status">
        <span :class="['status-pill', settings.is_enabled ? 'status-pill--ok' : '']">
          {{ settings.is_enabled ? "已开放" : "未开放" }}
        </span>
        <span :class="['status-pill', verification.status === 'verified' ? 'status-pill--ok' : '']">
          {{ verificationLabel }}
        </span>
      </div>
    </header>

    <div v-if="!settings.is_enabled" class="notice-card">
      <h2>动态功能暂未开放</h2>
      <p class="meta">管理员可以在“动态社区管理”中开启动态、发布、评论和热门前十。</p>
    </div>

    <template v-else>
      <section v-if="settings.require_real_name && verification.status !== 'verified'" class="notice-card">
        <div>
          <h2>完成实名认证后使用动态</h2>
          <p class="meta">
            动态、评论、点赞和收藏仅面向已实名用户。认证由阿里云金融级实人认证完成，站内只保存脱敏姓名、证件后四位和第三方流水号，完整证件号不会落库。
          </p>
        </div>
        <div class="verify-actions">
          <form class="verify-form" @submit.prevent="submitRealName">
            <input v-model.trim="verifyForm.real_name" class="input" placeholder="真实姓名" autocomplete="name" />
            <input v-model.trim="verifyForm.id_number" class="input" placeholder="居民身份证号" autocomplete="off" />
            <button class="btn btn-accent" type="submit" :disabled="submittingVerify">
              {{ submittingVerify ? "正在打开认证..." : "开始实名认证" }}
            </button>
          </form>
          <button v-if="verification.status === 'pending'" class="btn btn-ghost" type="button" :disabled="checkingVerify" @click="checkRealNameStatus()">
            {{ checkingVerify ? "刷新中..." : "刷新认证状态" }}
          </button>
        </div>
        <p v-if="verification.review_note" class="meta">认证状态：{{ verification.review_note }}</p>
      </section>

      <div class="moments-layout">
        <main class="feed-column">
          <article v-if="canPublish" class="publisher-card">
            <div class="avatar avatar-me">{{ initials(auth.user?.username || "ME") }}</div>
            <form class="publisher-body" @submit.prevent="publishMoment">
              <textarea
                v-model="publishForm.content"
                class="publisher-input"
                :maxlength="settings.max_text_length || 2000"
                rows="4"
                placeholder="写下你的算法心得，或分享竞赛日常..."
              ></textarea>
              <div v-if="imagePreviews.length" class="image-preview-grid">
                <div v-for="(item, index) in imagePreviews" :key="item.url" class="image-preview">
                  <img :src="item.url" alt="" />
                  <button type="button" @click="removeImage(index)">移除</button>
                </div>
              </div>
              <div class="publisher-toolbar">
                <label class="icon-action">
                  <input type="file" accept="image/*" multiple @change="onImagesSelected" />
                  <span>图片</span>
                </label>
                <span class="meta">{{ publishForm.content.length }}/{{ settings.max_text_length || 2000 }}</span>
                <button type="button" class="btn btn-ghost" @click="resetPublisher">清除</button>
                <button class="btn btn-accent" type="submit" :disabled="publishing">
                  {{ publishing ? "提交审核中..." : "发布动态" }}
                </button>
              </div>
            </form>
          </article>

          <article v-else class="notice-card compact">
            <strong>发布入口未开放</strong>
            <span class="meta">{{ publishBlockedReason }}</span>
          </article>

          <nav class="feed-tabs" aria-label="动态列表">
            <button
              v-for="item in tabs"
              :key="item.key"
              type="button"
              :class="{ active: activeTab === item.key }"
              @click="switchTab(item.key)"
            >
              {{ item.label }}
            </button>
          </nav>

          <article v-for="item in moments" :key="item.id" class="moment-card">
            <header class="moment-head">
              <div class="avatar">{{ initials(item.author?.username) }}</div>
              <div class="moment-author">
                <strong>{{ item.author?.username || "-" }}</strong>
                <span class="meta">{{ formatDateTime(item.published_at || item.created_at) }}</span>
              </div>
              <select class="row-menu" @change="handleMomentMenu(item, $event)">
                <option value="">更多</option>
                <option value="report">举报</option>
                <option v-if="item.can_edit" value="delete">删除</option>
              </select>
            </header>

            <p class="moment-content">{{ item.content }}</p>

            <div v-if="item.images?.length" :class="['moment-images', `moment-images--${Math.min(item.images.length, 3)}`]">
              <button v-for="image in item.images" :key="image.id" type="button" class="moment-image">
                <img :src="image.url" :alt="image.original_name || '动态图片'" />
              </button>
            </div>

            <footer class="moment-actions">
              <button v-if="settings.reactions_enabled" type="button" :class="{ active: item.liked }" @click="toggleLike(item)">
                赞 {{ item.like_count || 0 }}
              </button>
              <button type="button" @click="toggleComments(item)">
                评论 {{ item.comment_count || 0 }}
              </button>
              <button v-if="settings.favorites_enabled" type="button" :class="{ active: item.favorited }" @click="toggleFavorite(item)">
                {{ item.favorited ? "已收藏" : "收藏" }}
              </button>
            </footer>

            <section v-if="expandedComments.has(item.id)" class="comments-panel">
              <div v-if="commentsLoading[item.id]" class="meta">评论加载中...</div>
              <div v-for="comment in comments[item.id] || []" :key="comment.id" class="comment-row">
                <div class="avatar avatar-small">{{ initials(comment.author?.username) }}</div>
                <div class="comment-bubble">
                  <strong>{{ comment.author?.username || "-" }}</strong>
                  <p>{{ comment.content }}</p>
                  <span class="meta">{{ formatDateTime(comment.created_at) }}</span>
                </div>
                <select class="comment-menu" @change="handleCommentMenu(comment, $event)">
                  <option value="">更多</option>
                  <option value="report">举报</option>
                  <option v-if="comment.can_delete || comment.can_manage" value="delete">删除</option>
                </select>
              </div>
              <form v-if="canComment(item)" class="comment-form" @submit.prevent="postComment(item)">
                <input v-model.trim="commentDrafts[item.id]" class="input" :maxlength="settings.max_comment_length || 500" placeholder="写一句善意的评论..." />
                <button class="btn btn-accent btn-mini" type="submit">发送</button>
              </form>
              <p v-else class="meta">评论暂不可用。</p>
            </section>
          </article>

          <p v-if="!moments.length && !loading" class="empty">暂无动态。</p>
          <button v-if="nextPage" class="btn load-more" type="button" :disabled="loading" @click="loadMoments(nextPage, true)">
            {{ loading ? "加载中..." : "加载更多" }}
          </button>
        </main>

        <aside class="side-column">
          <section class="side-card">
            <h3>我的状态</h3>
            <p><strong>{{ auth.user?.username || "-" }}</strong></p>
            <p class="meta">{{ verificationLabel }}</p>
          </section>

          <section class="side-card">
            <h3>热门前十</h3>
            <div v-if="hotMoments.length" class="hot-list">
              <button v-for="(item, index) in hotMoments" :key="item.id" type="button" @click="focusMoment(item)">
                <span>{{ index + 1 }}</span>
                <strong>{{ item.content }}</strong>
              </button>
            </div>
            <p v-else class="meta">热门榜暂未开放或暂无内容。</p>
          </section>

          <section class="side-card side-card--rules">
            <h3>动态规范提示</h3>
            <p>{{ settings.rules_summary }}</p>
          </section>
        </aside>
      </div>
    </template>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { useRoute } from "vue-router";

import api, { isRequestCanceled } from "../services/api";
import { useAuthStore } from "../stores/auth";
import { useUiStore } from "../stores/ui";

const auth = useAuthStore();
const ui = useUiStore();
const route = useRoute();

const settings = reactive({
  is_enabled: false,
  publishing_enabled: false,
  commenting_enabled: false,
  reactions_enabled: true,
  favorites_enabled: true,
  hot_list_enabled: false,
  featured_feed_enabled: false,
  require_real_name: true,
  max_text_length: 2000,
  max_comment_length: 500,
  max_images_per_post: 9,
  max_image_size_mb: 5,
  rules_summary: "",
});

const verification = reactive({
  status: "unverified",
  review_note: "",
});

const verifyForm = reactive({ real_name: "", id_number: "" });
const publishForm = reactive({ content: "", images: [] });
const imagePreviews = ref([]);
const moments = ref([]);
const hotMoments = ref([]);
const comments = reactive({});
const commentsLoading = reactive({});
const commentDrafts = reactive({});
const expandedComments = ref(new Set());
const activeTab = ref("latest");
const loading = ref(false);
const publishing = ref(false);
const submittingVerify = ref(false);
const checkingVerify = ref(false);
const nextPage = ref(null);
let objectUrls = [];
let aliyunMetaInfoLoader = null;

const ALIYUN_META_INFO_SCRIPT = "https://o.alicdn.com/yd-cloudauth/cloudauth-cdn/jsvm_all.js";

const tabs = computed(() =>
  [
    { key: "latest", label: "最新动态", enabled: true },
    { key: "featured", label: "站内精选", enabled: settings.featured_feed_enabled },
    { key: "hot", label: "热门前十", enabled: settings.hot_list_enabled },
  ].filter((item) => item.enabled)
);

const verificationLabel = computed(() => {
  const map = {
    verified: "已实名",
    pending: "实名认证中",
    rejected: "实名未通过",
    revoked: "实名已撤销",
    unverified: "未实名",
  };
  return map[verification.status] || "未实名";
});

const canPublish = computed(
  () =>
    settings.is_enabled &&
    settings.publishing_enabled &&
    (!settings.require_real_name || verification.status === "verified")
);

const publishBlockedReason = computed(() => {
  if (!settings.publishing_enabled) return "动态发布当前已由管理员关闭。";
  if (settings.require_real_name && verification.status !== "verified") {
    return "完成实名认证后可以发布动态。";
  }
  return "当前不可发布动态。";
});

function getErrorText(error, fallback = "操作失败") {
  if (isRequestCanceled(error)) return "";
  const payload = error?.response?.data;
  if (!payload) return error?.message || fallback;
  if (typeof payload === "string") return payload;
  if (typeof payload.detail === "string") return payload.detail;
  const firstValue = Object.values(payload)[0];
  if (Array.isArray(firstValue)) return firstValue.join("；");
  return fallback;
}

function initials(value) {
  const text = String(value || "U").trim();
  return text.slice(0, 2).toUpperCase();
}

function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function extractRows(data) {
  return Array.isArray(data?.results) ? data.results : Array.isArray(data) ? data : [];
}

function nextPageFromUrl(value) {
  if (!value) return null;
  try {
    const parsed = new URL(value, window.location.origin);
    const page = Number(parsed.searchParams.get("page"));
    return Number.isFinite(page) && page > 0 ? page : null;
  } catch {
    return null;
  }
}

async function loadSettings() {
  const { data } = await api.get("/moment-settings/current/");
  Object.assign(settings, data || {});
}

async function loadVerification() {
  const { data } = await api.get("/real-name-verifications/me/");
  Object.assign(verification, data || {});
}

async function loadMoments(page = 1, append = false) {
  loading.value = true;
  try {
    const params = { page };
    if (activeTab.value === "hot") params.feed = "hot";
    if (activeTab.value === "featured") params.feed = "featured";
    const { data } = await api.get("/moments/", { params });
    const rows = extractRows(data);
    moments.value = append ? [...moments.value, ...rows] : rows;
    nextPage.value = nextPageFromUrl(data?.next);
  } catch (error) {
    ui.error(getErrorText(error, "动态加载失败"));
  } finally {
    loading.value = false;
  }
}

async function loadHotMoments() {
  if (!settings.hot_list_enabled) {
    hotMoments.value = [];
    return;
  }
  try {
    const { data } = await api.get("/moments/", { params: { feed: "hot" } });
    hotMoments.value = extractRows(data).slice(0, 10);
  } catch {
    hotMoments.value = [];
  }
}

async function loadLinkedMoment() {
  const momentId = Number(route.query.moment || 0);
  if (!Number.isFinite(momentId) || momentId <= 0) return;
  try {
    const { data } = await api.get(`/moments/${momentId}/`);
    if (data?.id) {
      moments.value = [data, ...moments.value.filter((item) => item.id !== data.id)];
    }
  } catch {
    // The target may be hidden, deleted, pending review, or unavailable after shutdown.
  }
}

async function loadAll() {
  await Promise.all([loadSettings(), loadVerification()]);
  if (settings.is_enabled) {
    await Promise.all([loadMoments(), loadHotMoments()]);
    await loadLinkedMoment();
  }
}

function loadAliyunMetaInfoScript() {
  if (typeof window === "undefined") return Promise.reject(new Error("浏览器环境不可用。"));
  if (typeof window.getMetaInfo === "function") return Promise.resolve();
  if (aliyunMetaInfoLoader) return aliyunMetaInfoLoader;

  aliyunMetaInfoLoader = new Promise((resolve, reject) => {
    const existing = document.querySelector(`script[src="${ALIYUN_META_INFO_SCRIPT}"]`);
    if (existing) {
      existing.addEventListener("load", resolve, { once: true });
      existing.addEventListener("error", () => reject(new Error("实名认证环境脚本加载失败。")), { once: true });
      return;
    }
    const script = document.createElement("script");
    script.src = ALIYUN_META_INFO_SCRIPT;
    script.async = true;
    script.onload = resolve;
    script.onerror = () => reject(new Error("实名认证环境脚本加载失败。"));
    document.head.appendChild(script);
  });
  return aliyunMetaInfoLoader;
}

async function getAliyunMetaInfo() {
  await loadAliyunMetaInfoScript();
  if (typeof window.getMetaInfo !== "function") {
    throw new Error("实名认证环境初始化失败，请刷新页面后重试。");
  }
  const metaInfo = window.getMetaInfo();
  if (!metaInfo) {
    throw new Error("未能获取浏览器实名环境信息，请刷新页面后重试。");
  }
  if (typeof metaInfo === "string") {
    try {
      return JSON.parse(metaInfo);
    } catch {
      return metaInfo;
    }
  }
  return metaInfo;
}

function getCertifyUrlType() {
  const ua = navigator.userAgent || "";
  return /Android|iPhone|iPad|iPod|Mobile/i.test(ua) ? "H5" : "WEB";
}

function firstQueryValue(value) {
  return Array.isArray(value) ? value[0] : value;
}

function findCertifyId(payload) {
  if (!payload || typeof payload !== "object") return "";
  const direct =
    payload.certifyId ||
    payload.CertifyId ||
    payload.certify_id ||
    payload.certifyID ||
    payload.resultObject?.certifyId ||
    payload.result_object?.certify_id ||
    "";
  if (direct) return String(direct);
  for (const value of Object.values(payload)) {
    const nested = findCertifyId(value);
    if (nested) return nested;
  }
  return "";
}

function extractReturnedCertifyId() {
  const direct =
    firstQueryValue(route.query.certifyId) ||
    firstQueryValue(route.query.CertifyId) ||
    firstQueryValue(route.query.certify_id) ||
    firstQueryValue(route.query.certifyID);
  if (direct) return String(direct);

  const responseText =
    firstQueryValue(route.query.response) ||
    firstQueryValue(route.query.Response) ||
    firstQueryValue(route.query.certifyResult);
  if (responseText) {
    try {
      const decoded = decodeURIComponent(String(responseText));
      return findCertifyId(JSON.parse(decoded));
    } catch {
      return "";
    }
  }

  return sessionStorage.getItem("algowiki_real_name_certify_id") || "";
}

async function submitRealName() {
  submittingVerify.value = true;
  try {
    const metaInfo = await getAliyunMetaInfo();
    const { data } = await api.post("/real-name-verifications/me/", {
      real_name: verifyForm.real_name,
      id_number: verifyForm.id_number,
      meta_info: metaInfo,
      certify_url_type: getCertifyUrlType(),
    });
    Object.assign(verification, data?.verification || data || {});
    if (data?.certify_id) {
      sessionStorage.setItem("algowiki_real_name_certify_id", data.certify_id);
    }
    verifyForm.real_name = "";
    verifyForm.id_number = "";
    if (data?.certify_url) {
      window.location.href = data.certify_url;
      return;
    }
    ui.info("实名认证已创建，请稍后刷新认证状态。");
  } catch (error) {
    ui.error(getErrorText(error, "实名认证启动失败"));
  } finally {
    submittingVerify.value = false;
  }
}

async function checkRealNameStatus(options = {}) {
  const { quiet = false } = options;
  checkingVerify.value = true;
  try {
    const certifyId = extractReturnedCertifyId();
    const { data } = await api.post("/real-name-verifications/check/", {
      certify_id: certifyId || verification.provider_certify_id || verification.provider_trace_id || "",
    });
    Object.assign(verification, data || {});
    if (data?.status === "verified") {
      sessionStorage.removeItem("algowiki_real_name_certify_id");
      if (!quiet) ui.success("实名认证已通过");
    } else if (data?.status === "rejected") {
      sessionStorage.removeItem("algowiki_real_name_certify_id");
      if (!quiet) ui.error("实名认证未通过，请核对信息后重新发起认证。");
    } else if (!quiet) {
      ui.info("认证结果暂未完成，请完成页面认证后再刷新。");
    }
  } catch (error) {
    if (!quiet) ui.error(getErrorText(error, "认证状态刷新失败"));
  } finally {
    checkingVerify.value = false;
  }
}

function revokeObjectUrls() {
  objectUrls.forEach((url) => URL.revokeObjectURL(url));
  objectUrls = [];
}

function onImagesSelected(event) {
  const files = Array.from(event.target.files || []);
  const maxCount = Number(settings.max_images_per_post || 9);
  const nextFiles = [...publishForm.images, ...files].slice(0, maxCount);
  const maxBytes = Number(settings.max_image_size_mb || 5) * 1024 * 1024;
  const accepted = [];
  for (const file of nextFiles) {
    if (!file.type.startsWith("image/")) {
      ui.info("仅支持图片文件");
      continue;
    }
    if (file.size > maxBytes) {
      ui.info(`单张图片不能超过 ${settings.max_image_size_mb || 5}MB`);
      continue;
    }
    accepted.push(file);
  }
  publishForm.images = accepted;
  revokeObjectUrls();
  imagePreviews.value = accepted.map((file) => {
    const url = URL.createObjectURL(file);
    objectUrls.push(url);
    return { url, name: file.name };
  });
  event.target.value = "";
}

function removeImage(index) {
  publishForm.images.splice(index, 1);
  revokeObjectUrls();
  imagePreviews.value = publishForm.images.map((file) => {
    const url = URL.createObjectURL(file);
    objectUrls.push(url);
    return { url, name: file.name };
  });
}

function resetPublisher() {
  publishForm.content = "";
  publishForm.images = [];
  revokeObjectUrls();
  imagePreviews.value = [];
}

async function publishMoment() {
  if (!publishForm.content.trim()) {
    ui.info("请输入动态内容");
    return;
  }
  publishing.value = true;
  try {
    const form = new FormData();
    form.append("content", publishForm.content.trim());
    publishForm.images.forEach((file) => form.append("images", file));
    await api.post("/moments/", form, { headers: { "Content-Type": "multipart/form-data" } });
    resetPublisher();
    ui.success("动态已提交审核");
    await Promise.all([loadMoments(), loadHotMoments()]);
  } catch (error) {
    ui.error(getErrorText(error, "动态发布失败"));
  } finally {
    publishing.value = false;
  }
}

async function toggleLike(item) {
  try {
    const { data } = await api.post(`/moments/${item.id}/like/`);
    Object.assign(item, data.moment || {});
  } catch (error) {
    ui.error(getErrorText(error, "点赞失败"));
  }
}

async function toggleFavorite(item) {
  try {
    const { data } = await api.post(`/moments/${item.id}/favorite/`);
    Object.assign(item, data.moment || {});
  } catch (error) {
    ui.error(getErrorText(error, "收藏失败"));
  }
}

async function loadComments(item) {
  commentsLoading[item.id] = true;
  try {
    const { data } = await api.get("/moment-comments/", { params: { moment: item.id } });
    comments[item.id] = extractRows(data);
  } catch (error) {
    ui.error(getErrorText(error, "评论加载失败"));
  } finally {
    commentsLoading[item.id] = false;
  }
}

async function toggleComments(item) {
  const next = new Set(expandedComments.value);
  if (next.has(item.id)) {
    next.delete(item.id);
    expandedComments.value = next;
    return;
  }
  next.add(item.id);
  expandedComments.value = next;
  await loadComments(item);
}

function canComment(item) {
  return settings.commenting_enabled && !item.comments_locked && (!settings.require_real_name || verification.status === "verified");
}

async function postComment(item) {
  const content = String(commentDrafts[item.id] || "").trim();
  if (!content) {
    ui.info("请输入评论内容");
    return;
  }
  try {
    await api.post("/moment-comments/", { moment: item.id, content });
    commentDrafts[item.id] = "";
    ui.success("评论已提交审核");
    await loadComments(item);
  } catch (error) {
    ui.error(getErrorText(error, "评论失败"));
  }
}

async function reportTarget({ targetType, id }) {
  const reason = normalizeReportReason(
    window.prompt("举报类型：垃圾信息 / 色情 / 涉政 / 暴力 / 辱骂 / 隐私 / 作弊 / 无关 / 其他", "无关")
  );
  if (!reason) return;
  const description = window.prompt("补充说明（可选）", "") || "";
  try {
    if (targetType === "moment") {
      await api.post(`/moments/${id}/report/`, { reason, description });
    } else {
      await api.post(`/moment-comments/${id}/report/`, { reason, description });
    }
    ui.success("举报已提交");
  } catch (error) {
    ui.error(getErrorText(error, "举报失败"));
  }
}

function normalizeReportReason(value) {
  const raw = String(value || "").trim().toLowerCase();
  if (!raw) return "";
  const map = {
    垃圾信息: "spam",
    垃圾: "spam",
    spam: "spam",
    色情: "porn",
    porn: "porn",
    涉政: "political",
    政治: "political",
    political: "political",
    暴力: "violence",
    violence: "violence",
    辱骂: "abuse",
    攻击: "abuse",
    abuse: "abuse",
    隐私: "privacy",
    privacy: "privacy",
    作弊: "cheating",
    cheating: "cheating",
    无关: "irrelevant",
    irrelevant: "irrelevant",
    其他: "other",
    other: "other",
  };
  return map[raw] || "other";
}

async function handleMomentMenu(item, event) {
  const action = event.target.value;
  event.target.value = "";
  if (action === "report") {
    await reportTarget({ targetType: "moment", id: item.id });
  } else if (action === "delete" && window.confirm("确认删除这条动态？")) {
    try {
      await api.delete(`/moments/${item.id}/`);
      moments.value = moments.value.filter((row) => row.id !== item.id);
      ui.success("动态已删除");
    } catch (error) {
      ui.error(getErrorText(error, "删除失败"));
    }
  }
}

async function handleCommentMenu(comment, event) {
  const action = event.target.value;
  event.target.value = "";
  if (action === "report") {
    await reportTarget({ targetType: "comment", id: comment.id });
  } else if (action === "delete" && window.confirm("确认删除这条评论？")) {
    try {
      await api.delete(`/moment-comments/${comment.id}/`);
      for (const key of Object.keys(comments)) {
        comments[key] = (comments[key] || []).filter((item) => item.id !== comment.id);
      }
      ui.success("评论已删除");
    } catch (error) {
      ui.error(getErrorText(error, "删除失败"));
    }
  }
}

async function switchTab(key) {
  activeTab.value = key;
  nextPage.value = null;
  await loadMoments();
}

function focusMoment(item) {
  activeTab.value = "latest";
  moments.value = [item, ...moments.value.filter((row) => row.id !== item.id)];
  window.scrollTo({ top: 0, behavior: "smooth" });
}

onMounted(async () => {
  await loadAll();
  const returnedFromAliyun = Boolean(
    firstQueryValue(route.query.real_name_return) ||
      firstQueryValue(route.query.response) ||
      firstQueryValue(route.query.certifyId) ||
      sessionStorage.getItem("algowiki_real_name_certify_id")
  );
  if (returnedFromAliyun && verification.status !== "verified") {
    await checkRealNameStatus({ quiet: false });
  }
});

onBeforeUnmount(() => {
  revokeObjectUrls();
});
</script>

<style scoped>
.moments-page {
  display: grid;
  gap: 18px;
  max-width: 1180px;
  margin: 0 auto;
}

.moments-hero,
.notice-card,
.publisher-card,
.moment-card,
.side-card {
  border: 1px solid var(--hairline);
  background: var(--surface);
  box-shadow: var(--shadow-sm);
}

.moments-hero {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: flex-start;
  border-radius: 22px;
  padding: 24px;
}

.kicker {
  margin: 0 0 6px;
  color: var(--accent);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.moments-hero h1 {
  margin: 0;
  font-size: clamp(32px, 4vw, 48px);
}

.meta {
  margin: 0;
  color: var(--text-quiet);
  line-height: 1.65;
}

.hero-status {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.status-pill {
  border-radius: 999px;
  background: var(--surface-muted);
  color: var(--text-soft);
  font-size: 12px;
  font-weight: 800;
  padding: 6px 10px;
}

.status-pill--ok {
  background: color-mix(in srgb, var(--accent) 14%, var(--surface));
  color: var(--accent);
}

.notice-card {
  display: grid;
  gap: 12px;
  border-radius: 22px;
  padding: 18px;
}

.notice-card.compact {
  grid-template-columns: auto 1fr;
  align-items: center;
}

.notice-card h2 {
  margin: 0;
}

.verify-form {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto;
  gap: 10px;
}

.verify-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: stretch;
}

.verify-actions .verify-form {
  flex: 1 1 520px;
}

.moments-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 18px;
  align-items: start;
}

.feed-column,
.side-column {
  display: grid;
  gap: 16px;
}

.publisher-card {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 14px;
  border-radius: 28px;
  padding: 22px;
}

.avatar {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  display: inline-grid;
  place-items: center;
  flex: 0 0 auto;
  background: color-mix(in srgb, var(--accent) 16%, var(--surface-strong));
  color: var(--accent);
  font-weight: 900;
}

.avatar-me {
  background: var(--accent-gradient);
  color: var(--accent-contrast);
}

.avatar-small {
  width: 28px;
  height: 28px;
  font-size: 11px;
}

.publisher-body {
  display: grid;
  gap: 12px;
}

.publisher-input {
  width: 100%;
  border: 0;
  outline: none;
  resize: vertical;
  min-height: 112px;
  background: transparent;
  color: var(--text);
  font: inherit;
}

.publisher-toolbar,
.moment-actions,
.moment-head,
.comment-form {
  display: flex;
  align-items: center;
  gap: 10px;
}

.publisher-toolbar {
  justify-content: flex-end;
  border-top: 1px solid var(--hairline);
  padding-top: 12px;
}

.icon-action {
  margin-right: auto;
  cursor: pointer;
  color: var(--accent);
  font-weight: 800;
}

.icon-action input {
  display: none;
}

.image-preview-grid,
.moment-images {
  display: grid;
  gap: 8px;
}

.image-preview-grid {
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
}

.image-preview,
.moment-image {
  overflow: hidden;
  border: 1px solid var(--hairline);
  border-radius: 14px;
  background: var(--surface-strong);
}

.image-preview {
  position: relative;
  aspect-ratio: 4 / 3;
}

.image-preview img,
.moment-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.image-preview button {
  position: absolute;
  right: 6px;
  top: 6px;
  border: 0;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.58);
  color: #fff;
  padding: 4px 8px;
  font-size: 12px;
}

.feed-tabs {
  display: flex;
  gap: 8px;
}

.feed-tabs button,
.moment-actions button {
  border: 1px solid var(--hairline);
  border-radius: 999px;
  background: var(--surface);
  color: var(--text-soft);
  padding: 8px 14px;
  font-weight: 800;
  cursor: pointer;
}

.feed-tabs button.active,
.moment-actions button.active {
  border-color: color-mix(in srgb, var(--accent) 36%, transparent);
  color: var(--accent);
  background: color-mix(in srgb, var(--accent) 10%, var(--surface));
}

.moment-card {
  display: grid;
  gap: 14px;
  border-radius: 24px;
  padding: 18px;
}

.moment-head {
  justify-content: space-between;
}

.moment-author {
  display: grid;
  gap: 2px;
  margin-right: auto;
}

.row-menu,
.comment-menu {
  border: 1px solid var(--hairline);
  border-radius: 999px;
  background: var(--surface);
  color: var(--text-soft);
  padding: 7px 10px;
}

.moment-content {
  margin: 0;
  color: var(--text);
  font-size: 15px;
  line-height: 1.8;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.moment-images--1 {
  grid-template-columns: minmax(0, 1fr);
}

.moment-images--2 {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.moment-images--3,
.moment-images:not(.moment-images--1):not(.moment-images--2) {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.moment-image {
  aspect-ratio: 4 / 3;
  padding: 0;
  cursor: zoom-in;
}

.comments-panel {
  display: grid;
  gap: 10px;
  border-top: 1px solid var(--hairline);
  padding-top: 12px;
}

.comment-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 8px;
  align-items: start;
}

.comment-bubble {
  display: grid;
  gap: 4px;
  border: 1px solid var(--hairline);
  border-radius: 14px;
  background: var(--surface-strong);
  padding: 9px 11px;
}

.comment-bubble p {
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.comment-form {
  align-items: stretch;
}

.comment-form .input {
  min-width: 0;
}

.side-card {
  display: grid;
  gap: 10px;
  border-radius: 22px;
  padding: 16px;
}

.side-card h3 {
  margin: 0;
}

.side-card--rules p {
  margin: 0;
  color: var(--text-soft);
  line-height: 1.72;
}

.hot-list {
  display: grid;
  gap: 8px;
}

.hot-list button {
  border: 0;
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr);
  gap: 8px;
  text-align: left;
  background: transparent;
  color: var(--text);
  padding: 6px 0;
  cursor: pointer;
}

.hot-list span {
  color: var(--accent);
  font-weight: 900;
}

.hot-list strong {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.empty,
.load-more {
  justify-self: center;
}

@media (max-width: 960px) {
  .moments-layout,
  .verify-form {
    grid-template-columns: 1fr;
  }

  .moments-hero,
  .moment-head,
  .publisher-toolbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .publisher-card {
    grid-template-columns: 1fr;
  }

  .moment-images--3,
  .moment-images:not(.moment-images--1):not(.moment-images--2) {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>

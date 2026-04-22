import { createRouter, createWebHistory } from "vue-router";

import HomePage from "../pages/HomePage.vue";
import { useAuthStore } from "../stores/auth";

const AnnouncementsPage = () => import("../pages/AnnouncementsPage.vue");
const CompetitionZonePage = () => import("../pages/CompetitionZonePage.vue");
const FriendlyLinksPage = () => import("../pages/FriendlyLinksPage.vue");
const WikiPage = () => import("../pages/WikiPage.vue");
const ArticlePage = () => import("../pages/ArticlePage.vue");
const ProfilePage = () => import("../pages/ProfilePage.vue");
const ExtraPage = () => import("../pages/ExtraPage.vue");
const AdminPage = () => import("../pages/AdminPage.vue");
const AuthPage = () => import("../pages/AuthPage.vue");
const QaPage = () => import("../pages/QaPage.vue");
const ReviewPage = () => import("../pages/ReviewPage.vue");
const RevisionReviewPage = () => import("../pages/RevisionReviewPage.vue");

const ROUTE_CHUNK_RELOAD_QUERY = "__route_reload__";
const ROUTE_CHUNK_ERROR_PATTERN =
  /Failed to fetch dynamically imported module|Importing a module script failed|error loading dynamically imported module|Unable to preload CSS/i;

const manageSections = [
  { path: "users", name: "manage-users", section: "users" },
  {
    path: "competition-wiki",
    name: "manage-competition-wiki",
    section: "competition-wiki",
  },
  {
    path: "competition-zone",
    name: "manage-competition-zone",
    section: "competition-zone",
  },
  {
    path: "document-pages",
    name: "manage-document-pages",
    section: "document-pages",
  },
  {
    path: "deleted-content",
    name: "manage-deleted-content",
    section: "deleted-content",
  },
  { path: "assistant", name: "manage-assistant", section: "assistant" },
  { path: "events", name: "manage-events", section: "events" },
  { path: "security", name: "manage-security", section: "security" },
];

const reviewSections = [
  { path: "/review", name: "review", section: "revisions" },
  { path: "/review/practice", name: "review-practice", section: "practice" },
  { path: "/review/notices", name: "review-notices", section: "notices" },
  { path: "/review/schedules", name: "review-schedules", section: "schedules" },
  { path: "/review/tickets", name: "review-tickets", section: "tickets" },
  { path: "/review/comments", name: "review-comments", section: "comments" },
  { path: "/review/tricks", name: "review-tricks", section: "tricks" },
  {
    path: "/review/trick-terms",
    name: "review-trick-terms",
    section: "trick_terms",
  },
  { path: "/review/questions", name: "review-questions", section: "questions" },
  { path: "/review/answers", name: "review-answers", section: "answers" },
].filter((item) => item.section !== "trick_terms");

const routes = [
  { path: "/", name: "home", component: HomePage },
  {
    path: "/announcements",
    name: "announcements",
    component: AnnouncementsPage,
  },
  {
    path: "/competition-calendar",
    name: "competition-calendar",
    redirect: { name: "competitions", query: { tab: "calendar" } },
  },
  {
    path: "/competitions",
    name: "competitions",
    component: CompetitionZonePage,
  },
  {
    path: "/friendly-links",
    name: "friendly-links",
    component: FriendlyLinksPage,
  },
  { path: "/wiki", name: "wiki", component: WikiPage },
  { path: "/wiki/:id", name: "article", component: ArticlePage, props: true },
  { path: "/questions", name: "questions", component: QaPage },
  {
    path: "/profile",
    name: "profile",
    component: ProfilePage,
    meta: { requiresAuth: true },
  },
  {
    path: "/extra/tricks",
    name: "extra-tricks",
    redirect: { name: "competitions", query: { tab: "tricks" } },
  },
  { path: "/extra/:slug", name: "extra", component: ExtraPage, props: true },
  {
    path: "/manage",
    name: "admin",
    component: AdminPage,
    props: { section: "users" },
    meta: { requiresManager: true },
  },
  ...manageSections.map((item) => ({
    path: `/manage/${item.path}`,
    name: item.name,
    component: AdminPage,
    props: { section: item.section },
    meta: { requiresManager: true },
  })),
  {
    path: "/manage/:legacySection",
    redirect: (to) => {
      const match = manageSections.find(
        (item) => item.section === to.params.legacySection,
      );
      return match ? { name: match.name } : { name: "admin" };
    },
    meta: { requiresManager: true },
  },
  ...reviewSections.map((item) => ({
    path: item.path,
    name: item.name,
    component: ReviewPage,
    props: { section: item.section },
    meta: { requiresManager: true },
  })),
  {
    path: "/review/trick-terms",
    redirect: { name: "review-tricks" },
    meta: { requiresManager: true },
  },
  {
    path: "/review/submissions",
    redirect: { name: "review-tickets" },
  },
  {
    path: "/review/revisions/:id",
    name: "review-revision",
    component: RevisionReviewPage,
    props: true,
    meta: { requiresManager: true },
  },
  { path: "/auth", name: "auth", component: AuthPage },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.onError((error) => {
  const message = String(error?.message || "");
  if (typeof window === "undefined" || !ROUTE_CHUNK_ERROR_PATTERN.test(message)) {
    return;
  }

  const currentUrl = new URL(window.location.href);
  if (currentUrl.searchParams.get(ROUTE_CHUNK_RELOAD_QUERY) === "1") {
    return;
  }

  currentUrl.searchParams.set(ROUTE_CHUNK_RELOAD_QUERY, "1");
  window.location.replace(currentUrl.toString());
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();

  if (
    to.name === "competitions" &&
    String(to.query.tab || "").trim() === "qa"
  ) {
    const questionId = String(to.query.question || "").trim();
    return questionId
      ? { name: "questions", query: { question: questionId } }
      : { name: "questions" };
  }

  if (auth.token && !auth.user) {
    try {
      await auth.fetchMe();
    } catch {
      auth.clearAuth();
    }
  }

  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: "auth" };
  }

  if (to.meta.requiresManager && !auth.isManager) {
    return { name: "home" };
  }

  return true;
});

router.isReady().then(() => {
  if (typeof window === "undefined") {
    return;
  }

  const currentUrl = new URL(window.location.href);
  if (currentUrl.searchParams.get(ROUTE_CHUNK_RELOAD_QUERY) !== "1") {
    return;
  }

  currentUrl.searchParams.delete(ROUTE_CHUNK_RELOAD_QUERY);
  window.history.replaceState({}, document.title, `${currentUrl.pathname}${currentUrl.search}${currentUrl.hash}`);
});

export default router;

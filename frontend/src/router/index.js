import { createRouter, createWebHistory } from "vue-router";

import { useAuthStore } from "../stores/auth";

const HomePage = () => import("../pages/HomePage.vue");
const AnnouncementsPage = () => import("../pages/AnnouncementsPage.vue");
const CompetitionCalendarPage = () => import("../pages/CompetitionCalendarPage.vue");
const CompetitionZonePage = () => import("../pages/CompetitionZonePage.vue");
const FriendlyLinksPage = () => import("../pages/FriendlyLinksPage.vue");
const WikiPage = () => import("../pages/WikiPage.vue");
const ArticlePage = () => import("../pages/ArticlePage.vue");
const QaPage = () => import("../pages/QaPage.vue");
const ProfilePage = () => import("../pages/ProfilePage.vue");
const ExtraPage = () => import("../pages/ExtraPage.vue");
const AdminPage = () => import("../pages/AdminPage.vue");
const AuthPage = () => import("../pages/AuthPage.vue");
const ReviewPage = () => import("../pages/ReviewPage.vue");
const RevisionReviewPage = () => import("../pages/RevisionReviewPage.vue");

const manageSections = [
  { path: "announcements", name: "manage-announcements", section: "announcements" },
  { path: "users", name: "manage-users", section: "users" },
  { path: "tickets", name: "manage-tickets", section: "tickets" },
  { path: "pages", name: "manage-pages", section: "pages" },
  { path: "categories", name: "manage-categories", section: "categories" },
  { path: "articles", name: "manage-articles", section: "articles" },
  { path: "comments", name: "manage-comments", section: "comments" },
  { path: "questions", name: "manage-questions", section: "questions" },
  { path: "answers", name: "manage-answers", section: "answers" },
  { path: "security", name: "manage-security", section: "security" },
  { path: "events", name: "manage-events", section: "events" },
];

const routes = [
  { path: "/", name: "home", component: HomePage },
  { path: "/announcements", name: "announcements", component: AnnouncementsPage },
  { path: "/competition-calendar", name: "competition-calendar", component: CompetitionCalendarPage },
  { path: "/competitions", name: "competitions", component: CompetitionZonePage },
  { path: "/friendly-links", name: "friendly-links", component: FriendlyLinksPage },
  { path: "/wiki", name: "wiki", component: WikiPage },
  { path: "/wiki/:id", name: "article", component: ArticlePage, props: true },
  { path: "/questions", name: "questions", component: QaPage },
  { path: "/profile", name: "profile", component: ProfilePage, meta: { requiresAuth: true } },
  { path: "/extra/:slug", name: "extra", component: ExtraPage, props: true },
  {
    path: "/manage",
    name: "admin",
    component: AdminPage,
    props: { section: "overview" },
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
      const match = manageSections.find((item) => item.section === to.params.legacySection);
      return match ? { name: match.name } : { name: "admin" };
    },
    meta: { requiresManager: true },
  },
  { path: "/review", name: "review", component: ReviewPage, props: { section: "revisions" }, meta: { requiresReviewer: true } },
  {
    path: "/review/tickets",
    name: "review-tickets",
    component: ReviewPage,
    props: { section: "tickets" },
    meta: { requiresReviewer: true },
  },
  {
    path: "/review/comments",
    name: "review-comments",
    component: ReviewPage,
    props: { section: "comments" },
    meta: { requiresReviewer: true },
  },
  { path: "/review/revisions/:id", name: "review-revision", component: RevisionReviewPage, props: true, meta: { requiresReviewer: true } },
  { path: "/auth", name: "auth", component: AuthPage },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();

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

  if (to.meta.requiresReviewer && !auth.isReviewer) {
    return { name: "home" };
  }

  return true;
});

export default router;

import { createRouter, createWebHistory } from "vue-router";

import { useAuthStore } from "../stores/auth";

const HomePage = () => import("../pages/HomePage.vue");
const AnnouncementsPage = () => import("../pages/AnnouncementsPage.vue");
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

const routes = [
  { path: "/", name: "home", component: HomePage },
  { path: "/announcements", name: "announcements", component: AnnouncementsPage },
  { path: "/competitions", name: "competitions", component: CompetitionZonePage },
  { path: "/friendly-links", name: "friendly-links", component: FriendlyLinksPage },
  { path: "/wiki", name: "wiki", component: WikiPage },
  { path: "/wiki/:id", name: "article", component: ArticlePage, props: true },
  { path: "/questions", name: "questions", component: QaPage },
  { path: "/profile", name: "profile", component: ProfilePage, meta: { requiresAuth: true } },
  { path: "/extra/:slug", name: "extra", component: ExtraPage, props: true },
  { path: "/admin", name: "admin", component: AdminPage, meta: { requiresManager: true } },
  { path: "/review", name: "review", component: ReviewPage, meta: { requiresReviewer: true } },
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

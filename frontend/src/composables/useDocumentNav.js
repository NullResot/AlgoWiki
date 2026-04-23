import { computed, ref } from "vue";

import api from "../services/api";

const fallbackSections = [
  {
    id: "fallback-doc-about",
    title: "关于AlgoWiki",
    key: "about",
    page_slug: "about",
    page_title: "关于 AlgoWiki",
    display_order: 10,
    is_visible: true,
  },
  {
    id: "fallback-doc-trick-guide",
    title: "trick 规范手册",
    key: "trick-guide",
    page_slug: "trick-guide",
    page_title: "trick 规范手册",
    display_order: 20,
    is_visible: true,
  },
  {
    id: "fallback-doc-trick-regulation",
    title: "Trick 页面贡献值与投票规则",
    key: "trick-regulation",
    page_slug: "trick-regulation",
    page_title: "Trick 页面贡献值与投票规则",
    display_order: 25,
    is_visible: true,
  },
  {
    id: "fallback-doc-announcement-guide",
    title: "公告手册",
    key: "announcement-guide",
    page_slug: "announcement-guide",
    page_title: "赛事公告手册",
    display_order: 30,
    is_visible: true,
  },
  {
    id: "fallback-doc-admin-guide",
    title: "管理员手册",
    key: "admin-guide",
    page_slug: "admin-guide",
    page_title: "管理员手册",
    display_order: 40,
    is_visible: true,
  },
];

const navState = ref([...fallbackSections]);
const loading = ref(false);
let loaded = false;
let pendingPromise = null;

function unpackListPayload(data) {
  if (Array.isArray(data)) {
    return data;
  }
  return Array.isArray(data?.results) ? data.results : [];
}

function mapSections(rows) {
  return rows
    .filter((item) => item && item.key && item.is_visible !== false)
    .sort((left, right) => {
      const orderDelta =
        Number(left.display_order || 0) - Number(right.display_order || 0);
      if (orderDelta !== 0) return orderDelta;
      return Number(left.id || 0) - Number(right.id || 0);
    })
    .map((item) => ({
      ...item,
      title: String(item.title || item.page_title || item.key || "").trim(),
      key: String(item.key || "").trim(),
      page_slug: String(item.page_slug || "").trim(),
      page_title: String(item.page_title || "").trim(),
    }));
}

async function loadDocumentNav(force = false) {
  if (loaded && !force) return navState.value;
  if (pendingPromise && !force) return pendingPromise;

  pendingPromise = (async () => {
    loading.value = true;
    try {
      const { data } = await api.get("/document-page-sections/");
      const mapped = mapSections(unpackListPayload(data));
      navState.value = mapped.length ? mapped : [...fallbackSections];
      loaded = true;
      return navState.value;
    } catch {
      if (force || !loaded) {
        navState.value = [...fallbackSections];
      }
      return navState.value;
    } finally {
      loading.value = false;
      pendingPromise = null;
    }
  })();

  return pendingPromise;
}

export function useDocumentNav() {
  return {
    documentNav: computed(() => navState.value),
    documentNavLoading: computed(() => loading.value),
    loadDocumentNav,
  };
}

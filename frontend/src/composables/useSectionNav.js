import { computed, ref } from "vue";

import api from "../services/api";

const fallbackNav = [
  { id: "fallback-sites", label: "关键网站", slug: "key-sites", order: 10 },
  { id: "fallback-concepts", label: "竞赛概念", slug: "competition-concepts", order: 20 },
  { id: "fallback-intro", label: "比赛介绍", slug: "competition-intro", order: 30 },
  { id: "fallback-terms", label: "常见术语", slug: "common-terms", order: 40 },
  { id: "fallback-tools", label: "代码工具", slug: "code-tools", order: 50 },
  { id: "fallback-tasks", label: "阶段任务", slug: "milestones", order: 60 },
  { id: "fallback-training", label: "关于训练", slug: "training", order: 70 },
];

const navState = ref([...fallbackNav]);
const loading = ref(false);
let loaded = false;
let pendingPromise = null;

function unpackListPayload(data) {
  if (Array.isArray(data)) {
    return data;
  }
  return Array.isArray(data?.results) ? data.results : [];
}

function mapCategoriesToNav(categories) {
  return categories
    .filter((item) => !item.parent && item.slug && item.is_visible !== false)
    .sort((left, right) => {
      const orderDelta = Number(left.order || 0) - Number(right.order || 0);
      if (orderDelta !== 0) return orderDelta;
      return String(left.name || "").localeCompare(String(right.name || ""), "zh-Hans-CN");
    })
    .map((item) => ({
      id: item.id,
      label: item.name,
      slug: item.slug,
      order: Number(item.order || 0),
    }));
}

async function loadSectionNav(force = false) {
  if (loaded && !force) return navState.value;
  if (pendingPromise && !force) return pendingPromise;

  pendingPromise = (async () => {
    loading.value = true;
    try {
      const { data } = await api.get("/categories/", { params: { top_level: 1 } });
      const mapped = mapCategoriesToNav(unpackListPayload(data));
      navState.value = mapped.length ? mapped : [...fallbackNav];
      loaded = true;
      return navState.value;
    } catch {
      if (force || !loaded) {
        navState.value = [...fallbackNav];
      }
      return navState.value;
    } finally {
      loading.value = false;
      pendingPromise = null;
    }
  })();

  return pendingPromise;
}

export function useSectionNav() {
  return {
    sectionNav: computed(() => navState.value),
    sectionNavLoading: computed(() => loading.value),
    loadSectionNav,
  };
}

import { computed, ref } from "vue";

import api from "../services/api";

const fallbackNav = [
  { id: "fallback-0", label: "0. 阅前须知", slug: "xcpc-preface", order: 10 },
  { id: "fallback-1", label: "1. 学术诚信", slug: "xcpc-academic-integrity", order: 20 },
  { id: "fallback-2", label: "2. 常见术语", slug: "xcpc-common-terms", order: 30 },
  { id: "fallback-3", label: "3. 竞赛概念", slug: "xcpc-concepts", order: 40 },
  { id: "fallback-4", label: "4. 比赛介绍", slug: "xcpc-contests", order: 50 },
  { id: "fallback-5", label: "5. 关键网站", slug: "xcpc-sites", order: 60 },
  { id: "fallback-6", label: "6. 代码工具", slug: "xcpc-tools", order: 70 },
  { id: "fallback-7", label: "7. 阶段任务", slug: "xcpc-stages", order: 80 },
  { id: "fallback-8", label: "8. 关于训练", slug: "xcpc-training", order: 90 },
  { id: "fallback-9", label: "9. 结语与致谢", slug: "xcpc-closing", order: 100 },
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
    .filter((item) => !item.parent && item.slug && item.is_visible)
    .sort((a, b) => {
      const orderDelta = Number(a.order || 0) - Number(b.order || 0);
      if (orderDelta !== 0) return orderDelta;
      return String(a.name || "").localeCompare(String(b.name || ""), "zh-Hans-CN");
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
      const { data } = await api.get("/categories/");
      const categories = unpackListPayload(data);
      const mapped = mapCategoriesToNav(categories);
      if (mapped.length) {
        navState.value = mapped;
      } else if (force) {
        navState.value = [...fallbackNav];
      }
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

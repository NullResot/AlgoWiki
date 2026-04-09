import { computed, ref } from "vue";

import api from "../services/api";

const fallbackItems = [
  { id: "fallback-home", key: "home", title: "首页", display_order: 10, is_visible: true },
  { id: "fallback-competition-wiki", key: "competition-wiki", title: "竞赛wiki", display_order: 20, is_visible: true },
  { id: "fallback-competitions", key: "competitions", title: "赛事专区", display_order: 30, is_visible: true },
  { id: "fallback-about", key: "about", title: "关于AlgoWiki", display_order: 40, is_visible: true },
  { id: "fallback-friendly-links", key: "friendly-links", title: "友链", display_order: 50, is_visible: true },
];

const navState = ref([...fallbackItems]);
const loading = ref(false);
let loaded = false;
let pendingPromise = null;

function unpackListPayload(data) {
  if (Array.isArray(data)) {
    return data;
  }
  return Array.isArray(data?.results) ? data.results : [];
}

function mapHeaderNav(rows) {
  return rows
    .filter((item) => item && item.key)
    .sort((left, right) => {
      const orderDelta = Number(left.display_order || 0) - Number(right.display_order || 0);
      if (orderDelta !== 0) return orderDelta;
      return String(left.key || "").localeCompare(String(right.key || ""));
    })
    .map((item) => ({
      ...item,
      key: String(item.key || "").trim(),
      title: String(item.title || "").trim(),
      display_order: Number(item.display_order || 0),
      is_visible: item.is_visible !== false,
    }));
}

async function loadHeaderNav(force = false) {
  if (loaded && !force) return navState.value;
  if (pendingPromise && !force) return pendingPromise;

  pendingPromise = (async () => {
    loading.value = true;
    try {
      const { data } = await api.get("/header-nav/");
      const mapped = mapHeaderNav(unpackListPayload(data));
      navState.value = mapped.length ? mapped : [...fallbackItems];
      loaded = true;
      return navState.value;
    } catch {
      if (force || !loaded) {
        navState.value = [...fallbackItems];
      }
      return navState.value;
    } finally {
      loading.value = false;
      pendingPromise = null;
    }
  })();

  return pendingPromise;
}

export function useHeaderNav() {
  return {
    headerNav: computed(() => navState.value),
    headerNavLoading: computed(() => loading.value),
    loadHeaderNav,
  };
}

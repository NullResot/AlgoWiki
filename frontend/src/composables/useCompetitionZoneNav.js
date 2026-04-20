import { computed, ref } from "vue";

import api from "../services/api";

const BUILTIN_SECTION_TITLES = {
  calendar: "常规赛",
  tricks: "trick技巧",
  schedule: "锦标赛",
  notice: "赛事公告",
  qa: "问答",
};

const fallbackSections = [
  {
    id: "fallback-calendar",
    title: BUILTIN_SECTION_TITLES.calendar,
    key: "calendar",
    target_type: "builtin",
    builtin_view: "calendar",
    page_slug: "",
    page_title: "",
    display_order: 1,
    is_visible: true,
  },
  {
    id: "fallback-tricks",
    title: BUILTIN_SECTION_TITLES.tricks,
    key: "tricks",
    target_type: "builtin",
    builtin_view: "tricks",
    page_slug: "",
    page_title: "",
    display_order: 2,
    is_visible: true,
  },
  {
    id: "fallback-schedule",
    title: BUILTIN_SECTION_TITLES.schedule,
    key: "schedule",
    target_type: "builtin",
    builtin_view: "schedule",
    page_slug: "",
    page_title: "",
    display_order: 3,
    is_visible: true,
  },
  {
    id: "fallback-notice",
    title: BUILTIN_SECTION_TITLES.notice,
    key: "notice",
    target_type: "builtin",
    builtin_view: "notice",
    page_slug: "",
    page_title: "",
    display_order: 4,
    is_visible: true,
  },
  {
    id: "fallback-qa",
    title: BUILTIN_SECTION_TITLES.qa,
    key: "qa",
    target_type: "builtin",
    builtin_view: "qa",
    page_slug: "",
    page_title: "",
    display_order: 5,
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
      const orderDelta = Number(left.display_order || 0) - Number(right.display_order || 0);
      if (orderDelta !== 0) return orderDelta;
      return Number(left.id || 0) - Number(right.id || 0);
    })
    .map((item) => ({
      ...item,
      title:
        item.target_type === "builtin"
          ? BUILTIN_SECTION_TITLES[String(item.builtin_view || "").trim()] ||
            String(item.title || item.page_title || item.key || "").trim()
          : String(item.title || item.page_title || item.key || "").trim(),
      page_slug: String(item.page_slug || "").trim(),
      page_title: String(item.page_title || "").trim(),
      builtin_view: String(item.builtin_view || "").trim(),
    }));
}

async function loadCompetitionZoneNav(force = false) {
  if (loaded && !force) return navState.value;
  if (pendingPromise && !force) return pendingPromise;

  pendingPromise = (async () => {
    loading.value = true;
    try {
      const { data } = await api.get("/competition-zone-sections/");
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

export function useCompetitionZoneNav() {
  return {
    competitionZoneNav: computed(() => navState.value),
    competitionZoneNavLoading: computed(() => loading.value),
    loadCompetitionZoneNav,
  };
}

import { onMounted, ref, watch } from "vue";

import api from "../services/api";

export function useAnnouncementPopup(auth) {
  const showAnnouncement = ref(false);
  const activeAnnouncement = ref(null);
  const loadedForAuthState = ref("");

  function currentModeKey() {
    return auth?.isAuthenticated ? `auth:${auth.user?.id || "unknown"}` : "anon";
  }

  async function fetchCandidateAnnouncement() {
    if (auth?.isAuthenticated) {
      try {
        const { data } = await api.get("/announcements/unread/");
        return Array.isArray(data) && data.length ? data[0] : null;
      } catch {
        const { data } = await api.get("/announcements/");
        const items = data?.results || data || [];
        return Array.isArray(items) && items.length ? items[0] : null;
      }
    }

    const { data } = await api.get("/announcements/");
    const items = data?.results || data || [];
    return Array.isArray(items) && items.length ? items[0] : null;
  }

  async function tryOpenAnnouncement() {
    const mode = currentModeKey();
    if (loadedForAuthState.value === mode) return;
    loadedForAuthState.value = mode;

    const candidate = await fetchCandidateAnnouncement();
    if (!candidate) return;

    if (!auth?.isAuthenticated) {
      const key = `anon_seen_announcement_${candidate.id}`;
      if (localStorage.getItem(key)) return;
    }

    activeAnnouncement.value = candidate;
    showAnnouncement.value = true;
  }

  async function dismissAnnouncement() {
    const current = activeAnnouncement.value;
    showAnnouncement.value = false;
    if (!current) return;

    if (auth?.isAuthenticated) {
      try {
        await api.post(`/announcements/${current.id}/acknowledge/`);
      } catch {
        // Keep UX non-blocking for popup close.
      }
    } else {
      localStorage.setItem(`anon_seen_announcement_${current.id}`, "1");
    }
    activeAnnouncement.value = null;
  }

  onMounted(() => {
    tryOpenAnnouncement();
  });

  watch(
    () => [auth?.isAuthenticated, auth?.user?.id],
    () => {
      loadedForAuthState.value = "";
      tryOpenAnnouncement();
    }
  );

  return {
    showAnnouncement,
    activeAnnouncement,
    dismissAnnouncement,
  };
}

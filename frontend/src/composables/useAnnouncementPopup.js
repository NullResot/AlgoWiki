import { onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";

import api from "../services/api";

export function useAnnouncementPopup(auth) {
  const route = useRoute();
  const showAnnouncement = ref(false);
  const activeAnnouncement = ref(null);
  const loadedForAuthState = ref("");

  function currentModeKey() {
    return auth?.isAuthenticated ? `auth:${auth.user?.id || "unknown"}` : "anon";
  }

  async function fetchCandidateAnnouncement() {
    try {
      const { data } = await api.get("/announcements/popup-candidate/");
      return data?.id ? data : null;
    } catch {
      return null;
    }
  }

  async function tryOpenAnnouncement() {
    if (route?.name === "auth") return;
    const mode = currentModeKey();
    if (loadedForAuthState.value === mode) return;
    loadedForAuthState.value = mode;

    const candidate = await fetchCandidateAnnouncement();
    if (!candidate) return;

    if (!auth?.isAuthenticated) {
      const key = `anon_seen_announcement_${candidate.id}`;
      try {
        if (localStorage.getItem(key)) return;
      } catch {
        // Ignore storage read restrictions.
      }
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
      try {
        localStorage.setItem(`anon_seen_announcement_${current.id}`, "1");
      } catch {
        // Ignore storage write errors.
      }
    }
    activeAnnouncement.value = null;
  }

  onMounted(() => {
    tryOpenAnnouncement();
  });

  watch(
    () => [auth?.isAuthenticated, auth?.user?.id, route?.name],
    () => {
      if (route?.name === "auth") return;
      if (loadedForAuthState.value !== currentModeKey()) {
        tryOpenAnnouncement();
      }
    }
  );

  return {
    showAnnouncement,
    activeAnnouncement,
    dismissAnnouncement,
  };
}

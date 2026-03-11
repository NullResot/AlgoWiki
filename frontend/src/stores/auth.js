import { defineStore } from "pinia";

import api from "../services/api";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    token: localStorage.getItem("algowiki_token") || "",
    user: JSON.parse(localStorage.getItem("algowiki_user") || "null"),
    loading: false,
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.token),
    role: (state) => state.user?.role || "anonymous",
    isManager: (state) => ["admin", "superadmin"].includes(state.user?.role),
    isSuperAdmin: (state) => state.user?.role === "superadmin",
    isSchoolOrHigher: (state) => ["school", "admin", "superadmin"].includes(state.user?.role),
    isReviewer: (state) => ["school", "admin", "superadmin"].includes(state.user?.role),
  },
  actions: {
    applyAuth(token, user) {
      this.token = token;
      this.user = user;
      localStorage.setItem("algowiki_token", token);
      localStorage.setItem("algowiki_user", JSON.stringify(user));
    },
    clearAuth() {
      this.token = "";
      this.user = null;
      localStorage.removeItem("algowiki_token");
      localStorage.removeItem("algowiki_user");
    },
    async register(payload) {
      this.loading = true;
      try {
        const { data } = await api.post("/auth/register/", payload);
        this.applyAuth(data.token, data.user);
        return data;
      } finally {
        this.loading = false;
      }
    },
    async login(payload) {
      this.loading = true;
      try {
        const { data } = await api.post("/auth/login/", payload);
        this.applyAuth(data.token, data.user);
        return data;
      } finally {
        this.loading = false;
      }
    },
    async fetchMe() {
      if (!this.token) return null;
      const { data } = await api.get("/me/");
      this.user = data.user;
      localStorage.setItem("algowiki_user", JSON.stringify(data.user));
      return data;
    },
    async logout() {
      try {
        if (this.token) {
          await api.post("/auth/logout/");
        }
      } finally {
        this.clearAuth();
      }
    },
  },
});

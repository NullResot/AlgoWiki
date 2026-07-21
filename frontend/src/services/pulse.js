import api from "./api";

function dataOf(request) {
  return request.then((response) => response.data);
}

export const pulseApi = {
  today: () => dataOf(api.get("/pulse/today/")),
  answers: (params = {}) => dataOf(api.get("/pulse/answers/", { params })),
  answer: (content_md) => dataOf(api.post("/pulse/answers/", { content_md })),
  vote: (option_id) => dataOf(api.post("/pulse/vote/", { option_id })),
  startBinding: (handle) => dataOf(api.post("/pulse/codeforces/bind/start/", { handle })),
  verifyBinding: (verification_id) =>
    dataOf(api.post("/pulse/codeforces/bind/verify/", { verification_id })),
  selfUnbind: (current_password) =>
    dataOf(api.post("/pulse/codeforces/unbind/", { current_password })),
  chooseChallenge: (mode) => dataOf(api.post("/pulse/challenges/choose/", { mode })),
  rerollChallenge: () => dataOf(api.post("/pulse/challenges/reroll/")),
  checkChallenge: (assignment_id) =>
    dataOf(api.post("/pulse/challenges/check/", { assignment_id })),
  createMakeup: (target_date, kind) =>
    dataOf(api.post("/pulse/makeups/", { target_date, kind })),
  redeem: (code, idempotency_key) =>
    dataOf(api.post("/pulse/redeem/", { code, idempotency_key })),
  atlas: () => dataOf(api.get("/pulse/atlas/")),
  rankings: (params = {}) => dataOf(api.get("/pulse/rankings/", { params })),
  discussions: (params = {}) => dataOf(api.get("/pulse/discussions/", { params })),
  discussion: (date) => dataOf(api.get(`/pulse/discussions/${date}/`)),
  answerDiscussion: (date, content_md) =>
    dataOf(api.post(`/pulse/discussions/${date}/answers/`, { content_md })),
  topicProposals: () => dataOf(api.get("/pulse/topic-proposals/")),
  proposeTopic: (payload) => dataOf(api.post("/pulse/topic-proposals/", payload)),
  admin: {
    editions: () => dataOf(api.get("/pulse/admin/editions/")),
    createEdition: (payload) => dataOf(api.post("/pulse/admin/editions/", payload)),
    updateEdition: (id, payload) => dataOf(api.patch(`/pulse/admin/editions/${id}/`, payload)),
    topicProposals: (status = "admin_pending") =>
      dataOf(api.get("/pulse/admin/topic-proposals/", { params: { status } })),
    scheduleTopicProposal: (id, payload) =>
      dataOf(api.post(`/pulse/admin/topic-proposals/${id}/schedule/`, payload)),
    rejectTopicProposal: (id, review_note) =>
      dataOf(api.post(`/pulse/admin/topic-proposals/${id}/reject/`, { review_note })),
    bindings: (q = "") => dataOf(api.get("/pulse/admin/bindings/", { params: { q } })),
    unbind: (id, payload) => dataOf(api.post(`/pulse/admin/bindings/${id}/unbind/`, payload)),
    grant: (payload) => dataOf(api.post("/pulse/admin/grants/", payload)),
    campaigns: () => dataOf(api.get("/pulse/admin/campaigns/")),
    createCampaign: (payload) => dataOf(api.post("/pulse/admin/campaigns/", payload)),
    updateCampaign: (id, payload) =>
      dataOf(api.patch(`/pulse/admin/campaigns/${id}/`, payload)),
    codes: () => dataOf(api.get("/pulse/admin/codes/")),
    createCode: (payload) => dataOf(api.post("/pulse/admin/codes/", payload)),
    updateCode: (id, payload) => dataOf(api.patch(`/pulse/admin/codes/${id}/`, payload)),
    ledger: (params = {}) => dataOf(api.get("/pulse/admin/ledger/", { params })),
  },
};

export default pulseApi;

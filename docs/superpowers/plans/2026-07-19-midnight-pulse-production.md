# Midnight Pulse Production Implementation Plan

> **Execution rule:** Complete each behavior with a failing test first, confirm the expected failure, then add the minimum production code and rerun the focused test.

**Goal:** Replace the local-only midnight pulse demo with a transaction-safe Django and Vue feature covering daily content, Codeforces binding and unbinding, both challenge modes, rewards, makeup, redemption codes, rankings, and administration.

**Architecture:** Keep the existing `wiki` Django app for migrations and shared user/community relationships, but place pulse orchestration in a dedicated `wiki/pulse` package. Store rewards as an immutable ledger, store Codeforces submissions as unique evidence, and materialize each Shanghai business day atomically on demand. The Vue page keeps the approved eclipse observatory presentation and reads all authoritative state from the API.

**Tech Stack:** Django 6, Django REST Framework, MySQL/SQLite compatible ORM, Python standard library HTTP client, Vue 3, Pinia, Axios, Vite, Node test runner.

---

## Task 1: Add the pulse persistence model and database constraints

**Files:**

- Create: `backend/wiki/test_pulse_models.py`
- Modify: `backend/wiki/models.py`
- Create: `backend/wiki/migrations/0067_midnight_pulse.py`
- Modify: `backend/wiki/admin.py`

**Steps:**

1. Add failing model tests for active Handle uniqueness, daily user uniqueness, single poll vote, unique evidence, unique ledger event key, and one makeup per target date.
2. Run `python manage.py test wiki.test_pulse_models` and confirm missing-model failures.
3. Add `CodeforcesBinding`, `CodeforcesVerification`, `CodeforcesEvidence`, `PulseDailyEdition`, `PulsePollOption`, `PulsePollVote`, `PulseUserDay`, `PulseChallengeAssignment`, `PulseLedgerEntry`, `PulseMakeup`, `PulseRedemptionCode`, and `PulseRedemption`.
4. Add database indexes and conditional/ordinary uniqueness compatible with MySQL and SQLite.
5. Generate and inspect migration `0067_midnight_pulse.py`.
6. Register operationally useful models in Django admin.
7. Rerun model tests and `python manage.py makemigrations --check --dry-run`.

## Task 2: Implement the Codeforces client and binding proof

**Files:**

- Create: `backend/wiki/pulse/__init__.py`
- Create: `backend/wiki/pulse/codeforces.py`
- Create: `backend/wiki/pulse/services.py`
- Create: `backend/wiki/test_pulse_bindings.py`

**Steps:**

1. Add fake-client tests for Handle normalization, `user.info`, latest submission baseline, ten-minute expiry, old submissions, wrong problem, non-OK verdict, mismatched author, and evidence replay.
2. Confirm the tests fail because the client and service do not exist.
3. Implement a fixed-host Codeforces client with typed domain errors, timeout handling, cache keys, and process-safe cache rate limiting of at least two seconds.
4. Implement `start_binding` and `verify_binding` as atomic services with one pending verification per user and Handle.
5. Store a global unique evidence record for the successful `4A` submission.
6. Rerun focused binding tests.

## Task 3: Implement self-unbind and administrator unbind

**Files:**

- Modify: `backend/wiki/pulse/services.py`
- Modify: `backend/wiki/test_pulse_bindings.py`
- Modify: `backend/wiki/models.py`

**Steps:**

1. Add failing tests for wrong password, successful self-unbind, seven-day transfer cooling, original-owner rebinding, administrator reason requirement, default cooling, cooling override, notification, and security audit metadata.
2. Implement self-unbind with `User.check_password` and immutable history.
3. Implement administrator unbind with required reason and explicit `allow_rebind_now`.
4. Reuse `UserNotification` and `SecurityAuditLog` for both paths.
5. Rerun binding tests.

## Task 4: Materialize daily content and settle community participation

**Files:**

- Modify: `backend/wiki/pulse/services.py`
- Create: `backend/wiki/test_pulse_daily.py`
- Create: `backend/wiki/management/commands/materialize_pulse.py`

**Steps:**

1. Add failing tests for one edition per Shanghai date, no seven-day auto-close, administrator preset priority, deterministic random fallback, first visible answer reward once, and immutable poll vote.
2. Implement atomic `get_or_create_daily_edition` and `get_or_create_user_day`.
3. Create the associated system-authored `Question` with no automatic close.
4. Implement answer creation through existing moderation semantics and an idempotent reroll-ticket ledger reward.
5. Implement poll vote creation and aggregate calculation.
6. Add an optional `materialize_pulse` management command for 00:00 prewarming.
7. Rerun daily tests.

## Task 5: Implement challenge mode A and completion checking

**Files:**

- Modify: `backend/wiki/pulse/codeforces.py`
- Modify: `backend/wiki/pulse/services.py`
- Create: `backend/wiki/test_pulse_challenges.py`

**Steps:**

1. Add failing tests for unrated fallback, 800/3500 clamps, accepted-problem exclusion, nearest rating fallback, mode lock, same-mode rerolls, two-reroll limit, wallet deduction, assignment-time evidence, idempotent completion, one point, and sign-in creation.
2. Implement cached problemset parsing and accepted-problem set extraction.
3. Implement deterministic candidate ordering followed by secure/random selection injection for testability.
4. Implement transactional choose, reroll, and completion services.
5. Rerun mode A tests.

## Task 6: Implement challenge mode B and the 04:00 deadline

**Files:**

- Modify: `backend/wiki/pulse/codeforces.py`
- Modify: `backend/wiki/pulse/services.py`
- Modify: `backend/wiki/test_pulse_challenges.py`

**Steps:**

1. Add failing tests for the three Rating bands, ended-contest filtering, Gym/team exclusion, zero-history requirement, `VIRTUAL` participation, distinct solved counting, `n-2`, duplicate submissions, and next-day 04:00 cutoff.
2. Implement contest classification and contest-problem snapshot retrieval.
3. Implement eligible-contest selection and VP evidence evaluation.
4. Award exactly three points and one sign-in through unique ledger/evidence keys.
5. Rerun challenge tests.

## Task 7: Implement makeup, redemption, wallet, streak, and rankings

**Files:**

- Modify: `backend/wiki/pulse/services.py`
- Create: `backend/wiki/test_pulse_rewards.py`

**Steps:**

1. Add failing tests for ledger idempotency, insufficient balance, normal makeup assignment and completion, super makeup immediate completion, duplicate target prevention, code time windows, total and per-user limits, concurrent-safe redemption, current streak, longest streak, banned-user exclusion, and tie breaks.
2. Implement a single ledger-writing helper used by all rewards and deductions.
3. Implement normal and super makeup flows.
4. Store redemption codes as password-style hashes and verify candidate codes without persisting plaintext.
5. Implement wallet summaries, atlas aggregation, and ranking queries.
6. Rerun reward tests.

## Task 8: Expose authenticated and administrator APIs

**Files:**

- Create: `backend/wiki/pulse/serializers.py`
- Create: `backend/wiki/pulse/views.py`
- Modify: `backend/wiki/urls.py`
- Create: `backend/wiki/test_pulse_api.py`

**Steps:**

1. Add failing API tests for authentication, banned users, validation, conflict status, Codeforces outage status, binding and both unbind paths, today payload, answers, voting, choose/reroll/check, makeup, redeem, atlas, rankings, admin binding search, admin unbind, grants, editions, codes, and ledger.
2. Implement thin serializers and views that call service functions rather than duplicating business rules.
3. Map domain errors consistently to 400, 401, 403, 409, and 503 responses.
4. Register explicit pulse routes before the default router include.
5. Rerun API tests.

## Task 9: Connect the approved Vue experience to the API

**Files:**

- Create: `frontend/src/services/pulse.js`
- Create: `frontend/src/features/pulse/pulseState.js`
- Create: `frontend/src/stores/pulse.js`
- Create: `frontend/tests/pulse-state.test.mjs`
- Modify: `frontend/package.json`
- Modify: `frontend/src/pages/PulseDemoPage.vue`
- Modify: `frontend/src/components/pulse-demo/PulseFirstVisitSheet.vue`
- Modify: `frontend/src/components/pulse-demo/PulseHeaderEntry.vue`
- Modify: `frontend/src/router/index.js`

**Steps:**

1. Add failing pure-state tests for API normalization, current and previous active day, wallet display, binding countdown, cooling status, challenge lock, retryable Codeforces errors, and theme restoration.
2. Implement the Pulse API service and Pinia store with loading, conflict refresh, and retry states.
3. Replace local simulated completion with real binding, verification, choose, reroll, check, answer, vote, makeup, and redeem actions.
4. Add `/pulse`, keep `/pulse-demo` as a redirect, and retain the first-visit sheet and top navigation entry.
5. Preserve the approved no-scroll desktop composition, mobile natural scroll, reduced-motion support, and temporary eclipse theme.
6. Run `npm run test:pulse` and `npm run build`.

## Task 10: Add profile binding and the Pulse management console

**Files:**

- Modify: `frontend/src/pages/ProfilePage.vue`
- Create: `frontend/src/components/admin/PulseManager.vue`
- Modify: `frontend/src/pages/AdminPage.vue`
- Modify: `frontend/src/router/index.js`

**Steps:**

1. Add the Codeforces binding status and password-confirmed self-unbind panel to the profile.
2. Add management tabs for editions, bindings, administrator unbind, grants, redemption codes, and ledger.
3. Require an unbind reason in the client and make immediate rebind an explicit non-default control.
4. Show operation results, notifications, cooling state, and API failures without optimistic mutation.
5. Run frontend tests and production build.

## Task 11: Full verification and browser acceptance

**Files:** Verify all files above.

**Steps:**

1. Run focused backend pulse tests.
2. Run the full Django test suite.
3. Run `python manage.py makemigrations --check --dry-run` and `python manage.py check`.
4. Run frontend pulse tests and the production build.
5. Run `git diff --check` and inspect the complete branch diff against `origin/test`.
6. Start local backend and frontend services from the isolated worktree.
7. Verify desktop and mobile flows in the browser: first visit, temporary dark theme, binding, self-unbind, administrator unbind, daily answer, vote, A/B challenge states, wallet, makeup, rankings, no desktop scrollbar, and reduced-motion fallback.
8. Record any behavior that uses a fake Codeforces test client in the preview so the user can distinguish local demonstration from live Codeforces traffic.

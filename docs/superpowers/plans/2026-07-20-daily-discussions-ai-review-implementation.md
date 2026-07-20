# Daily Discussions and AI Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a main-based test candidate that preserves the approved Midnight Pulse work, adds a permanent daily-discussion archive and topic scheduling, enforces fail-closed AI review on public speech, and paginates the pulse ranking without overlap.

**Architecture:** Start from `origin/main`, merge the approved pulse branch, and keep main ancestry intact. Reuse `Question` and `Answer` for discussion content, add a focused `PulseTopicProposal` workflow, extend the existing AI moderation pipeline with durable retry state, and expose server-side paginated APIs consumed by new Vue routes and the existing ranking panel.

**Tech Stack:** Django 5, Django REST Framework, MySQL and SQLite-compatible ORM queries, Vue 3, Pinia, Vue Router, scoped CSS, Vitest, Docker Compose.

---

## File map

### Backend

- `backend/wiki/models.py`: proposal model, moderation retry fields, target type.
- `backend/wiki/migrations/0070_ai_moderation_retry.py`: retry state and indexes after approved pulse migrations 0067 to 0069.
- `backend/wiki/migrations/0071_pulse_topic_proposal.py`: topic proposal schema and constraints.
- `backend/wiki/ai_moderation.py`: proposal target adapter, fail-closed decisions, retry scheduling and content-version protection.
- `backend/wiki/pulse/services.py`: archive queries, answer reward timing, proposal scheduling and paginated ranking service.
- `backend/wiki/pulse/serializers.py`: archive, proposal, admin scheduling and pagination input validation.
- `backend/wiki/pulse/views.py`: public discussion, proposal, admin queue and ranking endpoints.
- `backend/wiki/urls.py`: endpoint registration.
- `backend/wiki/admin.py`: proposal and moderation retry visibility.
- `backend/wiki/management/commands/process_ai_moderation_queue.py`: durable retry worker.
- `backend/wiki/test_pulse_discussions.py`: archive, historical answers, rewards and proposal flow.
- `backend/wiki/test_ai_moderation_queue.py`: fail-closed coverage, retries, stale-result protection.
- `backend/wiki/test_pulse_api.py`: ranking pagination contract.

### Frontend

- `frontend/src/router/index.js`: discussion archive and detail routes.
- `frontend/src/pages/MomentsPage.vue`: sub-navigation entry without changing the existing feed.
- `frontend/src/pages/PulseDiscussionsPage.vue`: archive, filters, proposal form and responsive layout.
- `frontend/src/pages/PulseDiscussionDetailPage.vue`: question, answer list, composer and moderation states.
- `frontend/src/components/pulse-discussions/DiscussionTimeline.vue`: date-rail list.
- `frontend/src/components/pulse-discussions/TopicProposalForm.vue`: inline proposal editor.
- `frontend/src/components/admin/PulseManager.vue`: proposal review and future-date scheduling.
- `frontend/src/components/pulse-demo/PulseRankingPanel.vue`: stable rows, page-size selector, scrolling and pager.
- `frontend/src/stores/pulse.js`: discussion and paginated ranking state.
- `frontend/src/composables/useHeaderNav.js`: safe dynamic fallback visibility.
- `frontend/src/components/TopNav.vue`: route-aware dynamic subpage active state if required.
- `frontend/src/styles.css`: only shared theme tokens that cannot remain component-scoped.
- `frontend/src/**/*.test.js`: Vitest component and store contract tests.
- `frontend/package.json`, `frontend/package-lock.json`, `frontend/vite.config.js`: test runner setup.

### Deployment and documentation

- `docker-compose.server.yml`: AI moderation worker service.
- `deploy/docker-entrypoint.sh`: no behavior change for web; worker uses its own Compose command.
- `deploy/server-update-from-registry.sh`: post-deploy navigation and route smoke checks.
- `docs/superpowers/specs/2026-07-20-daily-discussions-ai-review-design.md`: approved design reference.

## Task 1: Integrate the approved pulse branch on top of main

**Files:**

- Verify: all tracked files
- Merge source: `origin/codex/midnight-pulse-demo`

- [ ] **Step 1: Record the exact baseline**

Run:

```powershell
git rev-parse origin/main
git merge-base --is-ancestor origin/main HEAD
git diff --name-only origin/main..HEAD
git status --short
```

Expected: `origin/main` is `1eb83e55c8000c54ae146759883c8cac62fdb204`; the ancestry check exits 0; only the committed plan and spec differ from main; the worktree is clean.

- [ ] **Step 2: Merge the approved pulse history**

Run:

```powershell
git merge --no-ff origin/codex/midnight-pulse-demo -m "merge: integrate approved midnight pulse"
```

Expected: merge succeeds or reports conflicts only in files changed by both main and the pulse branch.

- [ ] **Step 3: Resolve conflicts by preserving main plus pulse additions**

For each conflict, compare all three stages:

```powershell
git diff --name-only --diff-filter=U
git show :1:path/to/file
git show :2:path/to/file
git show :3:path/to/file
```

Use main as the base document and reapply only pulse-specific imports, routes, components, models and URLs. Do not choose an entire side for `models.py`, `urls.py`, `router/index.js`, `TopNav.vue`, `HomePage.vue`, `ProfilePage.vue` or `AdminPage.vue`.

- [ ] **Step 4: Prove ancestry and migration continuity**

Run:

```powershell
git merge-base --is-ancestor origin/main HEAD
venv\Scripts\python.exe backend\manage.py showmigrations wiki
venv\Scripts\python.exe backend\manage.py check
```

Expected: ancestry exits 0; migrations include 0067, 0068 and 0069; Django check reports no issues.

- [ ] **Step 5: Commit any conflict resolution**

If Git did not create the merge commit automatically:

```powershell
git add backend frontend deploy docs
git commit -m "merge: integrate approved midnight pulse"
```

## Task 2: Add fail-closed moderation retry state

**Files:**

- Modify: `backend/wiki/models.py`
- Create: `backend/wiki/migrations/0070_ai_moderation_retry.py`
- Test: `backend/wiki/test_ai_moderation_queue.py`

- [ ] **Step 1: Write failing retry-model tests**

Create tests that assert the initial record is queued and due:

```python
class AIModerationRetryModelTests(TestCase):
    def test_new_retry_record_is_due(self):
        record = AIModerationRecord.objects.create(
            target_type=AIModerationRecord.TargetType.ANSWER,
            target_id=41,
            retry_state=AIModerationRecord.RetryState.QUEUED,
            next_retry_at=timezone.now() - timedelta(seconds=1),
        )
        self.assertTrue(record.is_retry_due())

    def test_finished_record_is_not_due(self):
        record = AIModerationRecord.objects.create(
            target_type=AIModerationRecord.TargetType.ANSWER,
            target_id=42,
            retry_state=AIModerationRecord.RetryState.FINISHED,
            next_retry_at=timezone.now() - timedelta(seconds=1),
        )
        self.assertFalse(record.is_retry_due())
```

- [ ] **Step 2: Run the tests and verify failure**

Run:

```powershell
venv\Scripts\python.exe backend\manage.py test wiki.test_ai_moderation_queue.AIModerationRetryModelTests
```

Expected: failure because `RetryState` and `is_retry_due` do not exist.

- [ ] **Step 3: Add retry fields and indexes**

Add to `AIModerationRecord`:

```python
class RetryState(models.TextChoices):
    QUEUED = "queued", "Queued"
    PROCESSING = "processing", "Processing"
    FINISHED = "finished", "Finished"

attempt_count = models.PositiveIntegerField(default=0)
last_attempt_at = models.DateTimeField(null=True, blank=True)
next_retry_at = models.DateTimeField(null=True, blank=True, db_index=True)
retry_state = models.CharField(
    max_length=20,
    choices=RetryState.choices,
    default=RetryState.FINISHED,
    db_index=True,
)
content_fingerprint = models.CharField(max_length=64, blank=True, db_index=True)

def is_retry_due(self, reference_time=None):
    now = reference_time or timezone.now()
    return (
        self.retry_state == self.RetryState.QUEUED
        and self.next_retry_at is not None
        and self.next_retry_at <= now
    )
```

Generate migration 0070 only after the pulse migrations are present.

- [ ] **Step 4: Run model tests and migration checks**

Run:

```powershell
venv\Scripts\python.exe backend\manage.py makemigrations wiki --check --dry-run
venv\Scripts\python.exe backend\manage.py test wiki.test_ai_moderation_queue.AIModerationRetryModelTests
```

Expected: no missing migrations; tests pass.

- [ ] **Step 5: Commit the schema**

```powershell
git add backend/wiki/models.py backend/wiki/migrations/0070_ai_moderation_retry.py backend/wiki/test_ai_moderation_queue.py
git commit -m "feat: add durable AI moderation retries"
```

## Task 3: Enforce AI review and run automatic retries

**Files:**

- Modify: `backend/wiki/ai_moderation.py`
- Modify: `backend/wiki/pulse/services.py`
- Create: `backend/wiki/management/commands/process_ai_moderation_queue.py`
- Modify: `docker-compose.server.yml`
- Test: `backend/wiki/test_ai_moderation_queue.py`

- [ ] **Step 1: Write failing fail-closed tests**

Cover daily answers, provider failures and stale responses:

```python
@patch("wiki.ai_moderation.invoke_ai_moderation_completion")
def test_daily_answer_stays_pending_when_provider_fails(self, invoke):
    invoke.side_effect = AIModerationProviderError("timeout", status_code=502)
    answer = submit_daily_answer(user=self.user, content_md="我会先证明单调性。")
    answer.refresh_from_db()
    self.assertEqual(answer.status, Answer.Status.PENDING)
    record = AIModerationRecord.objects.get(target_id=answer.id, target_type="answer")
    self.assertEqual(record.retry_state, AIModerationRecord.RetryState.QUEUED)

def test_stale_moderation_result_cannot_publish_edited_content(self):
    record = self.make_answer_record(content="旧内容")
    self.answer.content_md = "编辑后的新内容"
    self.answer.save(update_fields=["content_md", "updated_at"])
    apply_moderation_decision(record, approved=True)
    self.answer.refresh_from_db()
    self.assertEqual(self.answer.status, Answer.Status.PENDING)
```

- [ ] **Step 2: Run and confirm failure**

Run:

```powershell
venv\Scripts\python.exe backend\manage.py test wiki.test_ai_moderation_queue.AIModerationFailClosedTests
```

Expected: daily answer is visible or no retry is queued.

- [ ] **Step 3: Make submission pending before moderation**

In `submit_daily_answer`, create `Answer.Status.PENDING`, call `apply_ai_moderation_to_pending`, and grant the daily reward only after a safe decision has made the answer visible. Move reward logic into:

```python
def reward_pulse_answer_if_eligible(answer, *, now=None):
    edition = answer.question.pulse_edition
    if answer.status != Answer.Status.VISIBLE:
        return False
    if shanghai_business_date(now) != edition.date:
        return False
    day = get_or_create_user_day(user=answer.author, edition=edition)
    return mark_community_answer_completed(day=day, answer=answer, now=now)
```

Call this function from the AI approval path after the answer status becomes visible.

- [ ] **Step 4: Queue retryable provider failures**

Create a SHA-256 fingerprint from target type, target id and current text. On provider failure set:

```python
record.status = AIModerationRecord.Status.ERROR
record.retry_state = AIModerationRecord.RetryState.QUEUED
record.attempt_count = F("attempt_count") + 1
record.last_attempt_at = timezone.now()
record.next_retry_at = next_retry_time(record.attempt_count)
```

Use intervals `[1, 5, 15, 60]` minutes and cap subsequent attempts at 60 minutes.

- [ ] **Step 5: Implement a transactional worker command**

The command accepts `--once`, `--limit` and `--interval`. In watch mode it repeatedly calls:

```python
def process_due_records(limit):
    with transaction.atomic():
        ids = list(
            AIModerationRecord.objects.select_for_update(skip_locked=True)
            .filter(
                retry_state=AIModerationRecord.RetryState.QUEUED,
                next_retry_at__lte=timezone.now(),
            )
            .order_by("next_retry_at", "id")
            .values_list("id", flat=True)[:limit]
        )
        AIModerationRecord.objects.filter(id__in=ids).update(
            retry_state=AIModerationRecord.RetryState.PROCESSING
        )
    for record in AIModerationRecord.objects.filter(id__in=ids):
        retry_ai_moderation_record(record)
```

SQLite tests must use the same logic without `skip_locked` when the backend does not support it.

- [ ] **Step 6: Add the worker service**

Add a Compose service using the same image and environment as web:

```yaml
  moderation-worker:
    image: ${APP_IMAGE:-algowiki-web:local}
    env_file:
      - ${APP_ENV_FILE:-deploy/.env.production}
    restart: unless-stopped
    working_dir: /app/backend
    command: ["python", "manage.py", "process_ai_moderation_queue", "--interval", "30"]
```

Use the same database environment and no public port.

- [ ] **Step 7: Verify retries and commit**

Run:

```powershell
venv\Scripts\python.exe backend\manage.py test wiki.test_ai_moderation_queue
docker compose -f docker-compose.server.yml config
```

Expected: all retry tests pass; Compose config includes web and moderation-worker.

Commit:

```powershell
git add backend/wiki/ai_moderation.py backend/wiki/pulse/services.py backend/wiki/management/commands/process_ai_moderation_queue.py backend/wiki/test_ai_moderation_queue.py docker-compose.server.yml
git commit -m "feat: enforce fail-closed AI moderation"
```

## Task 4: Add topic proposals and administrator scheduling

**Files:**

- Modify: `backend/wiki/models.py`
- Create: `backend/wiki/migrations/0071_pulse_topic_proposal.py`
- Modify: `backend/wiki/ai_moderation.py`
- Modify: `backend/wiki/pulse/serializers.py`
- Modify: `backend/wiki/pulse/services.py`
- Modify: `backend/wiki/pulse/views.py`
- Modify: `backend/wiki/urls.py`
- Modify: `backend/wiki/admin.py`
- Test: `backend/wiki/test_pulse_discussions.py`

- [ ] **Step 1: Write failing proposal-flow tests**

```python
def test_safe_proposal_requires_admin_schedule(self):
    response = self.client.post(
        "/api/pulse/topic-proposals/",
        {"title": "赛时先写暴力还是先证明？", "content_md": "讨论时间分配策略。", "tags": ["赛时策略"]},
        format="json",
    )
    self.assertEqual(response.status_code, 201)
    proposal = PulseTopicProposal.objects.get(id=response.data["id"])
    self.assertEqual(proposal.status, PulseTopicProposal.Status.ADMIN_PENDING)
    self.assertFalse(PulseDailyEdition.objects.filter(source_payload__proposal_id=proposal.id).exists())

def test_admin_schedule_reserves_future_date(self):
    response = self.admin_client.post(
        f"/api/pulse/admin/topic-proposals/{self.proposal.id}/schedule/",
        {"scheduled_date": "2026-07-23", "poll_prompt": "你更倾向哪一种？", "poll_options": ["先写暴力", "先证明"]},
        format="json",
    )
    self.assertEqual(response.status_code, 200)
    edition = PulseDailyEdition.objects.get(date="2026-07-23")
    self.assertEqual(edition.source_type, PulseDailyEdition.SourceType.HOT)
    self.assertEqual(edition.status, PulseDailyEdition.Status.DRAFT)
```

- [ ] **Step 2: Run and confirm missing model/endpoints**

Run:

```powershell
venv\Scripts\python.exe backend\manage.py test wiki.test_pulse_discussions.PulseTopicProposalTests
```

Expected: import or 404 failure.

- [ ] **Step 3: Implement `PulseTopicProposal` and AI target mapping**

Use the exact statuses and constraints from the design spec. Add `PULSE_TOPIC_PROPOSAL` to the AI target type and map title plus body into the moderation payload. Safe AI output moves `ai_pending` to `admin_pending`; unsafe output moves it to `rejected`; provider errors remain `ai_pending` and queued.

- [ ] **Step 4: Implement scheduling atomically**

Within `transaction.atomic`, lock the proposal and reject non-future or occupied dates. Create the system-authored `Question`, draft edition and poll options. Update proposal reviewer, date, edition and status in the same transaction.

- [ ] **Step 5: Register endpoints and admin list**

The public create and mine endpoints require an authenticated, non-banned user. Admin list, schedule and reject endpoints require `AdminOrSuperAdmin`.

- [ ] **Step 6: Run tests and commit**

```powershell
venv\Scripts\python.exe backend\manage.py test wiki.test_pulse_discussions.PulseTopicProposalTests
git add backend/wiki/models.py backend/wiki/migrations/0071_pulse_topic_proposal.py backend/wiki/ai_moderation.py backend/wiki/pulse backend/wiki/urls.py backend/wiki/admin.py backend/wiki/test_pulse_discussions.py
git commit -m "feat: schedule community daily topics"
```

## Task 5: Add discussion archive and historical answers API

**Files:**

- Modify: `backend/wiki/pulse/serializers.py`
- Modify: `backend/wiki/pulse/services.py`
- Modify: `backend/wiki/pulse/views.py`
- Modify: `backend/wiki/urls.py`
- Test: `backend/wiki/test_pulse_discussions.py`

- [ ] **Step 1: Write failing archive tests**

Test newest ordering, active ordering, search, mine filtering, public-answer visibility, own pending visibility, historical answering and no historical reward.

```python
def test_historical_answer_is_reviewed_but_not_rewarded(self):
    response = self.client.post(
        f"/api/pulse/discussions/{self.yesterday.date}/answers/",
        {"content_md": "补充一个昨天没想到的反例。"},
        format="json",
    )
    self.assertEqual(response.status_code, 201)
    self.assertEqual(response.data["status"], Answer.Status.PENDING)
    self.approve_answer(response.data["id"])
    self.assertFalse(PulseLedgerEntry.objects.filter(event_key__contains=f":{self.user.id}").exists())
```

- [ ] **Step 2: Run and confirm 404 failure**

```powershell
venv\Scripts\python.exe backend\manage.py test wiki.test_pulse_discussions.PulseDiscussionArchiveTests
```

- [ ] **Step 3: Implement paginated archive services**

Use `Paginator` after filtering published editions. Annotate visible answer count and last visible answer time. `mine=1` filters editions with an answer by the current user. Search matches title and body.

- [ ] **Step 4: Implement detail and answer endpoints**

Public answer queries include only visible answers, plus the authenticated author's own pending or hidden answers. POST always creates a pending answer and invokes AI moderation.

- [ ] **Step 5: Verify and commit**

```powershell
venv\Scripts\python.exe backend\manage.py test wiki.test_pulse_discussions
git add backend/wiki/pulse backend/wiki/urls.py backend/wiki/test_pulse_discussions.py
git commit -m "feat: archive daily discussions"
```

## Task 6: Build the daily-discussion frontend

**Files:**

- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Modify: `frontend/vite.config.js`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/pages/MomentsPage.vue`
- Create: `frontend/src/pages/PulseDiscussionsPage.vue`
- Create: `frontend/src/pages/PulseDiscussionDetailPage.vue`
- Create: `frontend/src/components/pulse-discussions/DiscussionTimeline.vue`
- Create: `frontend/src/components/pulse-discussions/TopicProposalForm.vue`
- Modify: `frontend/src/stores/pulse.js`
- Test: `frontend/src/pages/PulseDiscussionsPage.test.js`
- Test: `frontend/src/pages/PulseDiscussionDetailPage.test.js`

- [ ] **Step 1: Install and configure Vitest**

Add scripts and development dependencies:

```json
{
  "scripts": {"test": "vitest run"},
  "devDependencies": {
    "@vue/test-utils": "^2.4.6",
    "jsdom": "^26.1.0",
    "vitest": "^3.2.4"
  }
}
```

Configure `test.environment = "jsdom"` in `vite.config.js`.

- [ ] **Step 2: Write failing route and rendering tests**

Mount the archive with mocked API results and assert date rows, answer counts, empty state, pending answer badge and page controls. Mount the detail page and assert only one composer submission occurs while saving.

- [ ] **Step 3: Run and confirm component failures**

```powershell
Set-Location frontend
npm test -- --run src/pages/PulseDiscussionsPage.test.js src/pages/PulseDiscussionDetailPage.test.js
```

Expected: missing component or route failures.

- [ ] **Step 4: Add routes and dynamic sub-navigation**

Add named routes `pulse-discussions` and `pulse-discussion-detail`. In MomentsPage, add an underlined two-item local navigation while leaving the existing feed markup unchanged.

- [ ] **Step 5: Implement archive and detail pages**

Use the date-rail layout, existing theme variables, 40px controls, scoped CSS and 180 to 240ms opacity/transform transitions. Use a two-column desktop layout and one-column layout below 860px. Add `lang="zh-CN"` to reading regions.

- [ ] **Step 6: Implement proposal form states**

Validate title, body and five-tag limit inline. After submission show `AI 审核中`; after safe AI review show `等待管理员排期`. Do not use a modal.

- [ ] **Step 7: Run component tests and build**

```powershell
npm test
npm run build
```

Expected: tests and Vite build pass without overflow warnings.

- [ ] **Step 8: Commit**

```powershell
git add frontend/package.json frontend/package-lock.json frontend/vite.config.js frontend/src
git commit -m "feat: add daily discussion experience"
```

## Task 7: Paginate the ranking backend

**Files:**

- Modify: `backend/wiki/pulse/serializers.py`
- Modify: `backend/wiki/pulse/services.py`
- Modify: `backend/wiki/pulse/views.py`
- Test: `backend/wiki/test_pulse_api.py`

- [ ] **Step 1: Write failing pagination tests**

```python
def test_rankings_return_server_pagination(self):
    response = self.client.get("/api/pulse/rankings/?page=2&page_size=10")
    self.assertEqual(response.status_code, 200)
    self.assertEqual(response.data["page"], 2)
    self.assertEqual(response.data["page_size"], 10)
    self.assertEqual(len(response.data["results"]), 10)
    self.assertEqual(response.data["results"][0]["rank"], 11)

def test_rankings_reject_unsupported_page_size(self):
    response = self.client.get("/api/pulse/rankings/?page_size=25")
    self.assertEqual(response.status_code, 400)
```

- [ ] **Step 2: Run and confirm failure**

```powershell
venv\Scripts\python.exe backend\manage.py test wiki.test_pulse_api.PulseRankingApiTests
```

- [ ] **Step 3: Validate page inputs**

Add `page` with minimum 1 and `page_size` as `ChoiceField(choices=(10, 20, 50), default=20)`.

- [ ] **Step 4: Return a page object**

Keep rank calculation over the full filtered set, slice only after ranks are assigned, and calculate streaks for current-page user ids. Return:

```python
{
    "count": count,
    "page": page,
    "page_size": page_size,
    "total_pages": max(1, math.ceil(count / page_size)),
    "results": page_rows,
}
```

- [ ] **Step 5: Run tests and commit**

```powershell
venv\Scripts\python.exe backend\manage.py test wiki.test_pulse_api.PulseRankingApiTests
git add backend/wiki/pulse backend/wiki/test_pulse_api.py
git commit -m "feat: paginate pulse rankings"
```

## Task 8: Fix ranking layout and interactions

**Files:**

- Modify: `frontend/src/components/pulse-demo/PulseRankingPanel.vue`
- Modify: `frontend/src/stores/pulse.js`
- Modify: `frontend/src/pages/PulseDemoPage.vue`
- Test: `frontend/src/components/pulse-demo/PulseRankingPanel.test.js`

- [ ] **Step 1: Write failing component tests**

Assert that selecting 50 emits `{ page: 1, pageSize: 50 }`, next page emits the correct page, scope change resets page, and the table has no fixed five-row class.

- [ ] **Step 2: Run and confirm failure**

```powershell
Set-Location frontend
npm test -- --run src/components/pulse-demo/PulseRankingPanel.test.js
```

- [ ] **Step 3: Implement stable table geometry**

Remove `grid-template-rows: 38px repeat(5, minmax(0, 1fr))`. Use normal block rows with a 64px minimum, sticky 42px header, tabular numeric columns and an internal `overflow-y: auto` viewport. Use 10-row viewport height for 20 and 50 modes.

- [ ] **Step 4: Add pagination controls**

Add a native page-size select with 10, 20 and 50, previous and next buttons, current page text and disabled states. Keep every target at least 40px.

- [ ] **Step 5: Connect Pinia and page metadata**

Store ranking results and pagination separately. Each scope, page or size change sends a new server request. Ignore late responses using an incrementing request id.

- [ ] **Step 6: Test, build and commit**

```powershell
npm test -- --run src/components/pulse-demo/PulseRankingPanel.test.js
npm run build
git add frontend/src/components/pulse-demo/PulseRankingPanel.vue frontend/src/stores/pulse.js frontend/src/pages/PulseDemoPage.vue frontend/src/components/pulse-demo/PulseRankingPanel.test.js
git commit -m "fix: make pulse rankings readable and paginated"
```

## Task 9: Lock dynamic navigation and cache behavior

**Files:**

- Modify: `frontend/src/composables/useHeaderNav.js`
- Test: `frontend/src/composables/useHeaderNav.test.js`
- Modify: `deploy/server-update-from-registry.sh`

- [ ] **Step 1: Write failing fallback navigation test**

Mock `/header-nav/` failure and assert that the returned fallback list still contains visible `moments`.

- [ ] **Step 2: Make the fallback visible**

Set the fallback moments item to `is_visible: true`. Preserve server configuration when the API succeeds.

- [ ] **Step 3: Add deployment smoke checks**

After the existing health check, fetch the rendered root and API navigation. Fail deployment when `/api/header-nav/` has no visible moments item, `/moments` is not HTTP 200 or 302 as expected, or `/pulse` does not return 200.

- [ ] **Step 4: Verify and commit**

```powershell
Set-Location frontend
npm test -- --run src/composables/useHeaderNav.test.js
Set-Location ..
git add frontend/src/composables/useHeaderNav.js frontend/src/composables/useHeaderNav.test.js deploy/server-update-from-registry.sh
git commit -m "fix: keep dynamic navigation available on test"
```

## Task 10: Full verification, diff audit, push and test deployment

**Files:**

- Verify: entire repository
- Update: plan checkboxes as tasks complete

- [ ] **Step 1: Run complete backend verification**

```powershell
venv\Scripts\python.exe backend\manage.py makemigrations wiki --check --dry-run
venv\Scripts\python.exe backend\manage.py check
venv\Scripts\python.exe backend\manage.py test wiki.tests wiki.test_pulse_models wiki.test_pulse_daily wiki.test_pulse_api wiki.test_pulse_bindings wiki.test_pulse_challenges wiki.test_pulse_rewards wiki.test_pulse_discussions wiki.test_ai_moderation_queue
```

Expected: all tests pass and there are no missing migrations.

- [ ] **Step 2: Run complete frontend verification**

```powershell
Set-Location frontend
npm test
npm run build
```

Expected: Vitest and Vite build pass.

- [ ] **Step 3: Verify branch invariants**

```powershell
git merge-base --is-ancestor origin/main HEAD
git merge-base --is-ancestor origin/codex/midnight-pulse-demo HEAD
git diff --check
git status --short
git diff --name-status origin/main..HEAD
```

Expected: both ancestry checks exit 0; no whitespace errors; only approved feature, test, deployment and documentation paths differ.

- [ ] **Step 4: Browser verification**

At 1280px and 375px verify:

- Header contains visible 动态.
- Dynamic local navigation reaches 每日讨论.
- Archive list, detail page, pending answer and proposal states render correctly.
- Ranking 10, 20 and 50 modes do not overlap; 50 mode scrolls inside the table.
- Reduced-motion mode removes positional animation.

- [ ] **Step 5: Commit plan completion**

```powershell
git add docs/superpowers/plans/2026-07-20-daily-discussions-ai-review-implementation.md
git commit -m "docs: record daily discussion implementation"
```

- [ ] **Step 6: Push the archive branch**

```powershell
git push -u origin codex/daily-discussions-ai-review
```

- [ ] **Step 7: Fast-forward test and deploy**

After all checks pass, fast-forward the remote test branch to the verified candidate, build the SHA-tagged image, deploy only the test Compose project, run migrations and health checks, then verify the deployed release SHA equals the candidate SHA. Do not update main or production services.

<template>
  <Teleport to="body">
    <Transition name="aw-modal">
      <div
        v-if="dialog"
        class="confirm-backdrop"
        @click.self="handleCancel"
      >
        <section
          class="confirm-dialog card aw-modal-panel"
          role="alertdialog"
          aria-modal="true"
          :aria-labelledby="titleId"
          :aria-describedby="descId"
        >
          <header class="confirm-head">
            <h3 :id="titleId">{{ dialog.title }}</h3>
            <button
              type="button"
              class="confirm-close"
              aria-label="关闭弹窗"
              @click="handleCancel"
            >
              ×
            </button>
          </header>

          <p v-if="dialog.message" :id="descId" class="confirm-message">{{ dialog.message }}</p>

          <div v-if="dialog.choices && dialog.choices.length" class="confirm-choices" role="radiogroup">
            <button
              v-for="item in dialog.choices"
              :key="item.value"
              type="button"
              class="confirm-choice"
              :class="{ 'is-selected': selectedChoice === item.value }"
              :aria-pressed="selectedChoice === item.value"
              @click="selectedChoice = item.value"
            >
              <strong>{{ item.label }}</strong>
              <small v-if="item.description">{{ item.description }}</small>
            </button>
          </div>

          <div v-if="dialog.requireText" class="confirm-field">
            <label class="confirm-label" :for="requireInputId">
              {{ dialog.requireLabel || `请输入 “${dialog.requireText}” 以确认继续：` }}
            </label>
            <input
              :id="requireInputId"
              ref="primaryInputRef"
              v-model.trim="typedRequireText"
              class="input"
              :placeholder="dialog.requireText"
              autocomplete="off"
              @keyup.enter="handleSubmit"
            />
          </div>

          <div v-if="dialog.inputLabel" class="confirm-field">
            <label class="confirm-label" :for="textInputId">{{ dialog.inputLabel }}</label>
            <textarea
              :id="textInputId"
              ref="secondaryInputRef"
              v-model="typedInput"
              class="textarea confirm-textarea"
              :placeholder="dialog.inputPlaceholder || '请输入内容'"
              rows="3"
            ></textarea>
          </div>

          <p v-if="validationError" class="confirm-error">{{ validationError }}</p>

          <footer class="confirm-actions">
            <button
              ref="cancelBtnRef"
              type="button"
              class="btn"
              @click="handleCancel"
            >
              {{ dialog.cancelText || "取消" }}
            </button>
            <button
              ref="confirmBtnRef"
              type="button"
              class="btn"
              :class="confirmButtonClass"
              :disabled="!canConfirm"
              @click="handleSubmit"
            >
              {{ dialog.confirmText || "确认" }}
            </button>
          </footer>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, ref, watch } from "vue";

import { useOverlayA11y } from "../composables/useOverlayA11y";
import { useUiStore } from "../stores/ui";

const ui = useUiStore();
const dialog = computed(() => ui.confirmDialog);
const titleId = "aw-confirm-title";
const descId = "aw-confirm-desc";
const requireInputId = "aw-confirm-require";
const textInputId = "aw-confirm-text";

const typedRequireText = ref("");
const typedInput = ref("");
const selectedChoice = ref("");
const validationError = ref("");

const primaryInputRef = ref(null);
const secondaryInputRef = ref(null);
const cancelBtnRef = ref(null);
const confirmBtnRef = ref(null);

const canConfirm = computed(() => {
  if (!dialog.value) return false;
  if (dialog.value.requireText && typedRequireText.value !== dialog.value.requireText) {
    return false;
  }
  if (dialog.value.mode === "prompt" && dialog.value.choices?.length && !selectedChoice.value) {
    return false;
  }
  if (dialog.value.mode === "prompt" && dialog.value.inputRequired && !typedInput.value.trim()) {
    return false;
  }
  return true;
});

const confirmButtonClass = computed(() => {
  if (dialog.value?.tone === "danger") return "btn-danger";
  return "btn-accent";
});

function handleCancel() {
  if (!dialog.value) return;
  ui.resolveConfirmDialog(dialog.value.mode === "prompt" ? null : false);
}

function handleSubmit() {
  if (!dialog.value) return;
  if (dialog.value.requireText && typedRequireText.value !== dialog.value.requireText) {
    validationError.value = `请准确输入 “${dialog.value.requireText}”`;
    return;
  }
  if (dialog.value.mode === "prompt" && dialog.value.inputRequired && !typedInput.value.trim()) {
    validationError.value = "请填写必要说明后再提交";
    return;
  }
  if (dialog.value.mode === "prompt") {
    ui.resolveConfirmDialog({
      choice: selectedChoice.value,
      text: typedInput.value.trim(),
    });
    return;
  }
  ui.resolveConfirmDialog(true);
}

useOverlayA11y(() => Boolean(dialog.value), handleCancel);

watch(
  dialog,
  async (nextDialog) => {
    typedRequireText.value = "";
    typedInput.value = nextDialog?.initialInput || "";
    selectedChoice.value = nextDialog?.defaultChoice || nextDialog?.choices?.[0]?.value || "";
    validationError.value = "";
    if (!nextDialog) return;
    await nextTick();
    if (nextDialog.requireText && primaryInputRef.value) {
      primaryInputRef.value.focus();
      return;
    }
    if (nextDialog.inputLabel && secondaryInputRef.value) {
      secondaryInputRef.value.focus();
      return;
    }
    if (nextDialog.tone === "danger") {
      cancelBtnRef.value?.focus();
    } else {
      confirmBtnRef.value?.focus();
    }
  },
  { immediate: true }
);
</script>

<style scoped>
.confirm-backdrop {
  position: fixed;
  inset: 0;
  z-index: var(--z-confirm, 1400);
  display: grid;
  place-items: center;
  padding: 18px;
  background: color-mix(in srgb, #020617 48%, transparent);
}

.confirm-dialog {
  width: min(460px, calc(100vw - 24px));
  padding: 20px;
  display: grid;
  gap: 14px;
  background: var(--surface-overlay);
  border: 1px solid var(--panel-border-strong);
  box-shadow: var(--shadow-md);
}

.confirm-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.confirm-head h3 {
  margin: 0;
  font-size: 19px;
  line-height: 1.35;
  color: var(--text-strong);
}

.confirm-close {
  width: 30px;
  height: 30px;
  flex: 0 0 auto;
  border: 1px solid var(--hairline);
  border-radius: 999px;
  background: var(--surface-soft);
  color: var(--text-soft);
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
  transition:
    background-color var(--dur-fast, 150ms) var(--ease-standard, ease),
    color var(--dur-fast, 150ms) var(--ease-standard, ease),
    transform var(--dur-press, 90ms) var(--ease-out, ease);
}

.confirm-close:hover {
  color: var(--text-strong);
  background: var(--surface-strong);
}

.confirm-close:active {
  transform: scale(0.94);
}

.confirm-message {
  margin: 0;
  color: var(--text);
  font-size: 14.5px;
  line-height: 1.65;
  overflow-wrap: anywhere;
}

.confirm-choices {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.confirm-choice {
  border: 1px solid var(--hairline-strong);
  border-radius: var(--radius-sm);
  padding: 10px 12px;
  background: var(--surface-soft);
  color: var(--text);
  text-align: left;
  cursor: pointer;
  display: grid;
  gap: 3px;
  transition:
    border-color var(--dur-fast, 150ms) var(--ease-standard, ease),
    background-color var(--dur-fast, 150ms) var(--ease-standard, ease),
    transform var(--dur-press, 90ms) var(--ease-out, ease);
}

.confirm-choice strong {
  font-size: 13.5px;
  color: var(--text-strong);
}

.confirm-choice small {
  font-size: 12px;
  color: var(--text-quiet);
  line-height: 1.4;
}

.confirm-choice.is-selected {
  border-color: var(--accent);
  background: color-mix(in srgb, var(--accent) 12%, var(--surface-strong));
}

.confirm-choice:active {
  transform: scale(0.98);
}

.confirm-field {
  display: grid;
  gap: 6px;
}

.confirm-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-soft);
}

.confirm-textarea {
  min-height: 84px;
}

.confirm-error {
  margin: 0;
  font-size: 13px;
  color: var(--danger);
}

.confirm-actions {
  display: flex;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 10px;
}

@media (max-width: 520px) {
  .confirm-choices {
    grid-template-columns: 1fr;
  }
}
</style>

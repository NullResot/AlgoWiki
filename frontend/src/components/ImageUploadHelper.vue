<template>
  <div class="image-upload-helper">
    <button class="btn btn-mini" type="button" :disabled="disabled || uploading" @click="pickFile">
      {{ uploading ? "上传中..." : label }}
    </button>
    <input
      ref="inputRef"
      class="upload-input"
      type="file"
      accept="image/png,image/jpeg,image/gif,image/webp"
      @change="onFileChange"
    />
  </div>
</template>

<script setup>
import { ref } from "vue";

import api from "../services/api";
import { useUiStore } from "../stores/ui";

const props = defineProps({
  label: {
    type: String,
    default: "上传图片",
  },
  disabled: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(["uploaded"]);
const ui = useUiStore();
const inputRef = ref(null);
const uploading = ref(false);

function pickFile() {
  inputRef.value?.click();
}

function resetInput() {
  if (inputRef.value) {
    inputRef.value.value = "";
  }
}

async function onFileChange(event) {
  const file = event?.target?.files?.[0];
  if (!file) return;

  const formData = new FormData();
  formData.append("image", file);
  uploading.value = true;
  try {
    const { data } = await api.post("/uploads/image/", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    emit("uploaded", data);
    ui.success("图片上传成功");
  } catch (error) {
    const payload = error?.response?.data;
    const fallback = "图片上传失败";
    const message =
      typeof payload === "string"
        ? payload
        : typeof payload?.detail === "string"
          ? payload.detail
          : Array.isArray(payload?.image)
            ? payload.image.join(" ")
            : fallback;
    ui.error(message || fallback);
  } finally {
    uploading.value = false;
    resetInput();
  }
}
</script>

<style scoped>
.image-upload-helper {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}

.upload-input {
  display: none;
}
</style>

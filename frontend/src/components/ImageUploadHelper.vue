<template>
  <div v-if="auth.isManager" class="image-upload-helper">
    <button class="btn btn-mini" type="button" :disabled="disabled || uploading" @click="pickFile">
      {{ uploading ? "上传中..." : label }}
    </button>
    <input
      ref="inputRef"
      class="upload-input"
      type="file"
      accept="image/jpeg,image/png,image/webp"
      @change="onFileChange"
    />
  </div>
</template>

<script setup>
import { ref } from "vue";

import api from "../services/api";
import { useAuthStore } from "../stores/auth";
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
const auth = useAuthStore();
const ui = useUiStore();
const inputRef = ref(null);
const uploading = ref(false);
const allowedImageMimeTypes = new Set(["image/jpeg", "image/png", "image/webp"]);
const maxUploadBytes = 8 * 1024 * 1024;

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
  const fileName = String(file.name || "").toLowerCase();
  const hasAllowedExtension = [".jpg", ".jpeg", ".png", ".webp"].some((ext) => fileName.endsWith(ext));
  if (!allowedImageMimeTypes.has(file.type) && !hasAllowedExtension) {
    ui.error("仅支持 JPG、PNG、WebP 图片");
    resetInput();
    return;
  }
  if (file.size > maxUploadBytes) {
    ui.error("单张图片不能超过 8MB");
    resetInput();
    return;
  }

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

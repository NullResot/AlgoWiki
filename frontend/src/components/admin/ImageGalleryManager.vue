<template>
  <section class="gallery-shell">
    <aside class="gallery-sidebar">
      <div class="gallery-actions">
        <button type="button" class="gallery-primary" @click="showUpload = !showUpload">
          上传图片
        </button>
        <button type="button" class="gallery-secondary" @click="showFolderCreator = !showFolderCreator">
          新建文件夹
        </button>
        <form v-if="showFolderCreator" class="gallery-folder-form" @submit.prevent="createFolder">
          <input v-model="folderCreatorName" type="text" maxlength="120" placeholder="输入文件夹名称" />
          <button type="submit" class="gallery-primary" :disabled="creatingFolder || !folderCreatorName.trim()">
            {{ creatingFolder ? "创建中..." : "确认创建" }}
          </button>
        </form>
        <button
          v-if="!isBatchMode"
          type="button"
          class="gallery-secondary"
          :disabled="isRecycleView"
          @click="isBatchMode = true"
        >
          批量管理
        </button>
        <div v-else class="gallery-batch-actions">
          <button type="button" class="gallery-secondary" @click="cancelBatchMode">取消</button>
          <button
            type="button"
            class="gallery-danger"
            :disabled="selectedIds.length === 0"
            @click="bulkRecycleImages"
          >
            删除 {{ selectedIds.length }}
          </button>
        </div>
      </div>

      <nav class="gallery-folders" aria-label="图库分类">
        <p class="gallery-nav-title">图库分类</p>
        <button
          type="button"
          class="gallery-folder"
          :class="{ 'gallery-folder--active': !isRecycleView && activeFolder === 'all' }"
          @click="selectFolder('all')"
        >
          <span>全部图片</span>
          <small>{{ activeCount }}</small>
        </button>
        <button
          v-for="folder in folders"
          :key="folder.id"
          type="button"
          class="gallery-folder"
          :class="{ 'gallery-folder--active': !isRecycleView && String(activeFolder) === String(folder.id) }"
          @click="selectFolder(folder.id)"
        >
          <span>{{ folder.name }}</span>
          <small>{{ folder.active_count || 0 }}</small>
        </button>
        <button
          type="button"
          class="gallery-folder gallery-folder--recycle"
          :class="{ 'gallery-folder--active': isRecycleView }"
          @click="openRecycleBin"
        >
          <span>回收站</span>
          <small>{{ recycledCount }}</small>
        </button>
      </nav>

      <div class="gallery-storage">
        <div class="gallery-storage-row">
          <span>{{ storageUsedLabel }}</span>
          <span>媒体目录</span>
        </div>
        <div class="gallery-storage-track">
          <span :style="{ width: storagePercent }"></span>
        </div>
      </div>
    </aside>

    <main class="gallery-main">
      <header class="gallery-head">
        <div>
          <p class="gallery-kicker">{{ isRecycleView ? "Recycle Bin" : "Image Library" }}</p>
          <h1>{{ currentTitle }}</h1>
          <p class="gallery-subtitle">
            上传后可直接复制图片链接或 Markdown 语法。删除后进入回收站，7 天内可恢复。
          </p>
        </div>
        <div class="gallery-search">
          <input
            v-model="searchQuery"
            type="search"
            placeholder="搜索图片..."
            @input="scheduleLoadImages"
          />
          <button type="button" class="btn btn-mini" @click="loadImages">搜索</button>
        </div>
      </header>

      <section v-if="showUpload" class="gallery-upload-card">
        <div class="gallery-upload-copy">
          <h3>上传图片</h3>
          <p>支持 JPG、PNG、GIF、WebP，单张最大 12MB。为降低 XSS 风险，暂不允许上传 SVG。</p>
        </div>
        <div class="gallery-upload-form">
          <label class="gallery-file-picker">
            <input type="file" accept="image/jpeg,image/png,image/gif,image/webp" @change="onFileSelected" />
            <span>{{ selectedFileName || "选择图片文件" }}</span>
          </label>
          <select v-model="uploadFolderId" :disabled="Boolean(newFolderName.trim())">
            <option value="">默认图库</option>
            <option v-for="folder in folders" :key="folder.id" :value="folder.id">
              {{ folder.name }}
            </option>
          </select>
          <input v-model="newFolderName" type="text" placeholder="新建文件夹名称（可选）" />
          <button type="button" class="gallery-primary" :disabled="uploading || !selectedFile" @click="uploadImage">
            {{ uploading ? "上传中..." : "确认上传" }}
          </button>
        </div>
        <div v-if="lastUploaded" class="gallery-upload-result">
          <strong>已上传：{{ lastUploaded.original_name }}</strong>
          <label>
            图片链接
            <div class="gallery-copy-row">
              <input :value="lastUploaded.url" readonly />
              <button type="button" class="btn btn-mini" @click="copyText(lastUploaded.url)">复制</button>
            </div>
          </label>
          <label>
            Markdown
            <div class="gallery-copy-row">
              <input :value="lastUploaded.markdown" readonly />
              <button type="button" class="btn btn-mini" @click="copyText(lastUploaded.markdown)">复制</button>
            </div>
          </label>
        </div>
      </section>

      <p v-if="feedback" class="gallery-feedback">{{ feedback }}</p>

      <section class="gallery-grid-wrap">
        <div v-if="loading" class="gallery-empty">正在加载图库...</div>
        <div v-else-if="images.length === 0" class="gallery-empty">
          当前{{ isRecycleView ? "回收站" : "文件夹" }}暂无图片
        </div>
        <div v-else class="gallery-grid">
          <article
            v-for="image in images"
            :key="image.id"
            class="gallery-card"
            :class="{ 'gallery-card--selected': selectedIds.includes(image.id) }"
          >
            <button
              v-if="isBatchMode && !isRecycleView"
              type="button"
              class="gallery-select"
              :class="{ 'gallery-select--checked': selectedIds.includes(image.id) }"
              @click="toggleSelected(image.id)"
            >
              {{ selectedIds.includes(image.id) ? "✓" : "" }}
            </button>

            <div class="gallery-thumb">
              <img v-if="image.url" :src="image.url" :alt="image.original_name" loading="lazy" />
              <div v-else class="gallery-thumb-placeholder">
                <span>已在回收站</span>
              </div>
            </div>

            <div class="gallery-card-body">
              <div class="gallery-card-title">
                <strong :title="image.original_name">{{ image.original_name }}</strong>
                <small>{{ image.folder_name }}</small>
              </div>
              <p class="gallery-card-meta">
                <span>{{ image.size_label }}</span>
                <span>{{ formatDate(image.created_at) }}</span>
              </p>

              <div v-if="!isRecycleView" class="gallery-link-box">
                <input :value="image.markdown" readonly @focus="$event.target.select()" />
                <button type="button" class="btn btn-mini" @click="copyText(image.markdown)">复制 Markdown</button>
                <button type="button" class="btn btn-mini" @click="copyText(image.url)">复制链接</button>
              </div>
              <p v-else class="gallery-recycle-note">
                保留至 {{ formatDate(image.delete_after) }}，过期后自动永久删除。
              </p>

              <div class="gallery-card-actions">
                <button
                  v-if="isRecycleView"
                  type="button"
                  class="btn btn-mini"
                  @click="restoreImage(image)"
                >
                  恢复
                </button>
                <button
                  type="button"
                  class="btn btn-mini gallery-danger-text"
                  @click="deleteImage(image)"
                >
                  {{ isRecycleView ? "永久删除" : "删除" }}
                </button>
              </div>
            </div>
          </article>
        </div>
      </section>
    </main>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";

import api from "../../services/api";

const folders = ref([]);
const images = ref([]);
const activeFolder = ref("all");
const statusView = ref("active");
const searchQuery = ref("");
const loading = ref(false);
const showUpload = ref(false);
const selectedFile = ref(null);
const uploadFolderId = ref("");
const newFolderName = ref("");
const uploading = ref(false);
const lastUploaded = ref(null);
const showFolderCreator = ref(false);
const folderCreatorName = ref("");
const creatingFolder = ref(false);
const isBatchMode = ref(false);
const selectedIds = ref([]);
const feedback = ref("");
let searchTimer = null;

const isRecycleView = computed(() => statusView.value === "recycled");
const activeCount = computed(() =>
  folders.value.reduce((total, item) => total + Number(item.active_count || 0), 0)
);
const recycledCount = computed(() =>
  folders.value.reduce((total, item) => total + Number(item.recycled_count || 0), 0)
);
const currentTitle = computed(() => {
  if (isRecycleView.value) return "回收站";
  if (activeFolder.value === "all") return "全部图片";
  return folders.value.find((item) => String(item.id) === String(activeFolder.value))?.name || "图库";
});
const selectedFileName = computed(() => selectedFile.value?.name || "");
const storageUsedBytes = computed(() =>
  images.value.reduce((total, item) => total + Number(item.size_bytes || 0), 0)
);
const storageUsedLabel = computed(() => formatBytes(storageUsedBytes.value));
const storagePercent = computed(() => {
  const percent = Math.max(4, Math.min(100, Math.round((storageUsedBytes.value / (1024 * 1024 * 1024)) * 100)));
  return `${percent}%`;
});

function unpackList(data) {
  if (Array.isArray(data)) return data;
  return Array.isArray(data?.results) ? data.results : [];
}

function showFeedback(message) {
  feedback.value = message;
  window.setTimeout(() => {
    if (feedback.value === message) feedback.value = "";
  }, 2400);
}

async function loadFolders() {
  const { data } = await api.get("/gallery-folders/");
  folders.value = unpackList(data);
  if (!uploadFolderId.value && folders.value.length) {
    uploadFolderId.value = folders.value[0].id;
  }
}

async function loadImages() {
  loading.value = true;
  try {
    const params = {
      status: statusView.value,
      search: searchQuery.value.trim(),
    };
    if (!isRecycleView.value && activeFolder.value !== "all") {
      params.folder = activeFolder.value;
    }
    const { data } = await api.get("/gallery-images/", { params });
    images.value = unpackList(data);
  } finally {
    loading.value = false;
  }
}

function scheduleLoadImages() {
  window.clearTimeout(searchTimer);
  searchTimer = window.setTimeout(loadImages, 280);
}

function selectFolder(folderId) {
  statusView.value = "active";
  activeFolder.value = folderId;
  cancelBatchMode();
  loadImages();
}

function openRecycleBin() {
  statusView.value = "recycled";
  activeFolder.value = "all";
  cancelBatchMode();
  loadImages();
}

function onFileSelected(event) {
  selectedFile.value = event.target.files?.[0] || null;
}

async function createFolder() {
  const name = folderCreatorName.value.trim();
  if (!name) {
    showFeedback("请先填写文件夹名称。");
    return;
  }
  creatingFolder.value = true;
  try {
    const { data } = await api.post("/gallery-folders/", { name });
    folderCreatorName.value = "";
    showFolderCreator.value = false;
    statusView.value = "active";
    activeFolder.value = data.id;
    uploadFolderId.value = data.id;
    await Promise.all([loadFolders(), loadImages()]);
    showFeedback("文件夹已创建。");
  } catch (error) {
    const detail =
      error?.response?.data?.name?.[0] ||
      error?.response?.data?.slug?.[0] ||
      error?.response?.data?.detail ||
      "文件夹创建失败。";
    showFeedback(detail);
  } finally {
    creatingFolder.value = false;
  }
}

async function uploadImage() {
  if (!selectedFile.value) return;
  uploading.value = true;
  try {
    const form = new FormData();
    form.append("image", selectedFile.value);
    if (newFolderName.value.trim()) {
      form.append("folder_name", newFolderName.value.trim());
    } else if (uploadFolderId.value) {
      form.append("folder", uploadFolderId.value);
    }
    const { data } = await api.post("/gallery-images/upload/", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    lastUploaded.value = data;
    selectedFile.value = null;
    newFolderName.value = "";
    await Promise.all([loadFolders(), loadImages()]);
    showFeedback("图片已上传，可以复制链接使用。");
  } finally {
    uploading.value = false;
  }
}

function toggleSelected(id) {
  selectedIds.value = selectedIds.value.includes(id)
    ? selectedIds.value.filter((item) => item !== id)
    : [...selectedIds.value, id];
}

function cancelBatchMode() {
  isBatchMode.value = false;
  selectedIds.value = [];
}

async function bulkRecycleImages() {
  if (!selectedIds.value.length) return;
  if (!window.confirm(`确认删除 ${selectedIds.value.length} 张图片并移入回收站？`)) return;
  await api.post("/gallery-images/bulk-delete/", { ids: selectedIds.value });
  cancelBatchMode();
  await Promise.all([loadFolders(), loadImages()]);
  showFeedback("已移入回收站，7 天内可以恢复。");
}

async function deleteImage(image) {
  const message = isRecycleView.value
    ? "确认永久删除这张图片？此操作不可恢复。"
    : "确认删除这张图片并移入回收站？原图片链接将失效。";
  if (!window.confirm(message)) return;
  await api.delete(`/gallery-images/${image.id}/`);
  await Promise.all([loadFolders(), loadImages()]);
  showFeedback(isRecycleView.value ? "图片已永久删除。" : "图片已移入回收站。");
}

async function restoreImage(image) {
  await api.post(`/gallery-images/${image.id}/restore/`);
  await Promise.all([loadFolders(), loadImages()]);
  showFeedback("图片已恢复到原路径。");
}

async function copyText(text) {
  const value = String(text || "");
  if (!value) return;
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
  } else {
    const textarea = document.createElement("textarea");
    textarea.value = value;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    textarea.remove();
  }
  showFeedback("已复制到剪贴板。");
}

function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function formatBytes(value) {
  const size = Number(value || 0);
  if (size >= 1024 * 1024 * 1024) return `${(size / 1024 / 1024 / 1024).toFixed(1)} GB`;
  if (size >= 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`;
  if (size >= 1024) return `${Math.round(size / 1024)} KB`;
  return `${size} B`;
}

onMounted(async () => {
  await loadFolders();
  await loadImages();
});
</script>

<style scoped>
.gallery-shell {
  min-height: 720px;
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  overflow: hidden;
  border: 1px solid var(--hairline);
  border-radius: 24px;
  background: #fbfbfd;
  color: #1d1d1f;
}

.gallery-sidebar {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  gap: 18px;
  padding: 24px 18px;
  border-right: 1px solid #e5e7eb;
  background: rgba(255, 255, 255, 0.78);
}

.gallery-subtitle,
.gallery-upload-copy p {
  margin: 0;
  color: #667085;
}

.gallery-actions,
.gallery-folders,
.gallery-upload-form,
.gallery-folder-form {
  display: grid;
  gap: 10px;
}

.gallery-folder-form {
  padding: 12px;
  border: 1px solid #edf0f5;
  border-radius: 18px;
  background: #f8fafc;
}

.gallery-primary,
.gallery-secondary,
.gallery-danger {
  border: 0;
  border-radius: 999px;
  min-height: 44px;
  padding: 0 18px;
  font-weight: 700;
  cursor: pointer;
}

.gallery-primary {
  background: #0071e3;
  color: #fff;
  box-shadow: 0 12px 28px rgba(0, 113, 227, 0.22);
}

.gallery-secondary {
  background: #fff;
  color: #344054;
  border: 1px solid #e5e7eb;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.06);
}

.gallery-danger {
  background: #ef4444;
  color: #fff;
}

.gallery-primary:disabled,
.gallery-secondary:disabled,
.gallery-danger:disabled {
  opacity: 0.48;
  cursor: not-allowed;
}

.gallery-batch-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.gallery-nav-title {
  margin: 4px 10px;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #98a2b3;
}

.gallery-folder {
  border: 0;
  border-radius: 14px;
  padding: 11px 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: transparent;
  color: #475467;
  font-size: 14px;
  cursor: pointer;
  text-align: left;
}

.gallery-folder:hover {
  background: #f2f4f7;
}

.gallery-folder--active {
  background: #e8f2ff;
  color: #0071e3;
  font-weight: 800;
}

.gallery-folder--recycle {
  margin-top: 8px;
  color: #b42318;
}

.gallery-storage {
  padding: 14px;
  border: 1px solid #edf0f5;
  border-radius: 16px;
  background: #fff;
}

.gallery-storage-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 12px;
  color: #667085;
}

.gallery-storage-track {
  height: 6px;
  border-radius: 999px;
  background: #e5e7eb;
  overflow: hidden;
}

.gallery-storage-track span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: #0071e3;
}

.gallery-main {
  min-width: 0;
  display: grid;
  grid-template-rows: auto auto auto minmax(0, 1fr);
  gap: 18px;
  padding: 28px 36px 36px;
  overflow: auto;
}

.gallery-head {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 24px;
}

.gallery-kicker {
  margin: 0 0 4px;
  color: #0071e3;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.gallery-head h1 {
  margin: 0;
  font-size: clamp(34px, 4vw, 48px);
  line-height: 1.05;
}

.gallery-search {
  display: flex;
  align-items: center;
  gap: 8px;
}

.gallery-search input,
.gallery-upload-form input,
.gallery-upload-form select,
.gallery-folder-form input,
.gallery-copy-row input,
.gallery-link-box input {
  min-height: 40px;
  border: 1px solid #e5e7eb;
  border-radius: 999px;
  background: #fff;
  color: #1d2939;
  padding: 0 14px;
  outline: none;
}

.gallery-search input {
  width: min(280px, 32vw);
}

.gallery-upload-card {
  display: grid;
  gap: 16px;
  padding: 18px;
  border: 1px solid #e5e7eb;
  border-radius: 22px;
  background: #fff;
  box-shadow: 0 14px 40px rgba(15, 23, 42, 0.06);
}

.gallery-upload-copy h3 {
  margin: 0 0 4px;
  font-size: 20px;
}

.gallery-upload-form {
  grid-template-columns: minmax(180px, 1.2fr) minmax(160px, 0.8fr) minmax(180px, 1fr) auto;
  align-items: center;
}

.gallery-file-picker {
  min-height: 44px;
  border: 1px dashed #98a2b3;
  border-radius: 16px;
  display: flex;
  align-items: center;
  padding: 0 14px;
  cursor: pointer;
  background: #f8fafc;
}

.gallery-file-picker input {
  display: none;
}

.gallery-upload-result {
  display: grid;
  gap: 10px;
  padding: 14px;
  border-radius: 16px;
  background: #f8fafc;
}

.gallery-upload-result label {
  display: grid;
  gap: 6px;
  font-size: 13px;
  font-weight: 700;
  color: #475467;
}

.gallery-copy-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
}

.gallery-feedback {
  margin: 0;
  width: fit-content;
  padding: 8px 12px;
  border-radius: 999px;
  background: #ecfdf3;
  color: #067647;
  font-size: 13px;
  font-weight: 700;
}

.gallery-grid-wrap {
  min-height: 360px;
}

.gallery-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
  gap: 22px;
}

.gallery-card {
  position: relative;
  overflow: hidden;
  border: 1px solid #eaecf0;
  border-radius: 22px;
  background: #fff;
  box-shadow: 0 8px 30px rgba(15, 23, 42, 0.06);
}

.gallery-card--selected {
  border-color: #0071e3;
  box-shadow: 0 0 0 4px rgba(0, 113, 227, 0.12);
}

.gallery-select {
  position: absolute;
  z-index: 2;
  top: 12px;
  left: 12px;
  width: 28px;
  height: 28px;
  border-radius: 999px;
  border: 2px solid rgba(255, 255, 255, 0.9);
  background: rgba(15, 23, 42, 0.32);
  color: #fff;
  cursor: pointer;
}

.gallery-select--checked {
  border-color: #0071e3;
  background: #0071e3;
}

.gallery-thumb {
  aspect-ratio: 1 / 0.74;
  background: #f2f4f7;
  overflow: hidden;
}

.gallery-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.gallery-thumb-placeholder {
  height: 100%;
  display: grid;
  place-items: center;
  color: #98a2b3;
  font-weight: 700;
}

.gallery-card-body {
  display: grid;
  gap: 10px;
  padding: 14px;
}

.gallery-card-title {
  min-width: 0;
  display: grid;
  gap: 2px;
}

.gallery-card-title strong {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.gallery-card-title small,
.gallery-card-meta,
.gallery-recycle-note {
  color: #667085;
  font-size: 12px;
}

.gallery-card-meta {
  margin: 0;
  display: flex;
  justify-content: space-between;
}

.gallery-link-box {
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
}

.gallery-link-box input {
  width: 100%;
  border-radius: 12px;
  font-size: 12px;
}

.gallery-card-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.gallery-danger-text {
  color: #b42318;
}

.gallery-empty {
  min-height: 360px;
  display: grid;
  place-items: center;
  color: #98a2b3;
  font-weight: 700;
}

@media (max-width: 980px) {
  .gallery-shell {
    grid-template-columns: 1fr;
  }

  .gallery-sidebar {
    border-right: 0;
    border-bottom: 1px solid #e5e7eb;
  }

  .gallery-head {
    flex-direction: column;
  }

  .gallery-search,
  .gallery-search input {
    width: 100%;
  }

  .gallery-upload-form {
    grid-template-columns: 1fr;
  }
}
</style>

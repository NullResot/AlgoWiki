<template>
  <section class="gallery-shell">
    <aside class="gallery-sidebar">
      <div class="gallery-actions">
        <button type="button" class="gallery-primary" @click="showUpload = !showUpload">
          {{ showUpload ? "收起上传面板" : "上传图片" }}
        </button>
        <button type="button" class="gallery-secondary" @click="showFolderCreator = !showFolderCreator">
          {{ showFolderCreator ? "取消新建文件夹" : "新建文件夹" }}
        </button>
        <Transition name="aw-collapse">
          <form v-if="showFolderCreator" class="gallery-folder-form" @submit.prevent="createFolder">
            <input v-model="folderCreatorName" type="text" maxlength="120" placeholder="输入文件夹名称" />
            <button type="submit" class="gallery-primary" :disabled="creatingFolder || !folderCreatorName.trim()">
              {{ creatingFolder ? "创建中..." : "确认创建" }}
            </button>
          </form>
        </Transition>
        <button
          v-if="!isBatchMode"
          type="button"
          class="gallery-secondary"
          :disabled="isRecycleView || images.length === 0"
          @click="isBatchMode = true"
        >
          批量管理
        </button>
        <div v-else class="gallery-batch-actions">
          <button type="button" class="gallery-secondary" @click="toggleSelectAllBatch">
            {{ allBatchSelected ? "取消全选" : "全选" }}
          </button>
          <button type="button" class="gallery-secondary" @click="cancelBatchMode">退出</button>
          <button
            type="button"
            class="gallery-danger gallery-batch-delete"
            :disabled="selectedIds.length === 0 || bulkDeleting"
            @click="bulkRecycleImages"
          >
            {{ bulkDeleting ? "删除中..." : `删除 (${selectedIds.length})` }}
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
          <span>当前筛选合计 ({{ images.length }} 项)</span>
        </div>
        <div class="gallery-storage-track">
          <span :style="{ width: storagePercent }"></span>
        </div>
      </div>
    </aside>

    <div class="gallery-main">
      <header class="gallery-head">
        <div>
          <p class="gallery-kicker">{{ isRecycleView ? "Recycle Bin" : "Image Library" }}</p>
          <h2>{{ currentTitle }}</h2>
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
            @keyup.enter="loadImages"
          />
          <button type="button" class="btn btn-mini" :disabled="loading" @click="loadImages">
            {{ loading ? "搜索中..." : "搜索" }}
          </button>
        </div>
      </header>

      <Transition name="aw-collapse">
        <section v-if="showUpload" class="gallery-upload-card">
          <div class="gallery-upload-copy">
            <h3>上传图片</h3>
            <p>支持 JPG、PNG、WebP，单张最大 12MB。为降低 XSS 风险，暂不允许上传 SVG。</p>
          </div>
          <div class="gallery-upload-form">
            <label class="gallery-file-picker">
              <input ref="fileInputEl" type="file" accept="image/jpeg,image/png,image/webp" @change="onFileSelected" />
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
      </Transition>

      <section class="gallery-grid-wrap">
        <div v-if="loading && !images.length" class="gallery-loading-box">
          <SkeletonBlock :lines="5" :line-height="22" label="正在加载图库图片" />
        </div>
        <EmptyErrorState
          v-else-if="loadError && !images.length"
          title="图库内容加载失败"
          :description="loadError"
          action-label="重新加载"
          tone="error"
          @action="loadImages"
        />
        <div v-else-if="images.length === 0" class="gallery-empty">
          当前{{ isRecycleView ? "回收站" : "文件夹" }}暂无图片
        </div>
        <div v-else class="gallery-grid" :class="{ 'is-dimmed': loading }">
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
              :aria-label="selectedIds.includes(image.id) ? `取消选择 ${image.original_name}` : `选择 ${image.original_name}`"
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
                  :disabled="restoringId === image.id || deletingId === image.id"
                  @click="restoreImage(image)"
                >
                  {{ restoringId === image.id ? "恢复中..." : "恢复" }}
                </button>
                <button
                  type="button"
                  class="btn btn-mini btn-danger"
                  :disabled="deletingId === image.id || restoringId === image.id"
                  @click="deleteImage(image)"
                >
                  {{ deletingId === image.id ? "处理中..." : (isRecycleView ? "永久删除" : "删除") }}
                </button>
              </div>
            </div>
          </article>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

import EmptyErrorState from "../EmptyErrorState.vue";
import SkeletonBlock from "../SkeletonBlock.vue";
import { getCaptchaProof, captchaErrorMessage } from "../../composables/useCaptcha";
import api from "../../services/api";
import { useUiStore } from "../../stores/ui";

const ui = useUiStore();

const folders = ref([]);
const images = ref([]);
const activeFolder = ref("all");
const statusView = ref("active");
const searchQuery = ref("");
const loading = ref(false);
const loadError = ref("");
const showUpload = ref(false);
const fileInputEl = ref(null);
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
const bulkDeleting = ref(false);
const deletingId = ref(null);
const restoringId = ref(null);
let searchTimer = null;
const allowedGalleryMimeTypes = new Set(["image/jpeg", "image/png", "image/webp"]);
const galleryMaxUploadBytes = 12 * 1024 * 1024;

const isRecycleView = computed(() => statusView.value === "recycled");
const allBatchSelected = computed(
  () => images.value.length > 0 && selectedIds.value.length === images.value.length
);
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

function getGalleryError(error, fallback = "操作失败，请稍后重试") {
  const payload = error?.response?.data;
  if (typeof payload?.detail === "string" && payload.detail.trim()) return payload.detail;
  if (typeof payload === "string" && payload.trim()) return payload;
  return error?.message || fallback;
}

async function loadFolders() {
  try {
    const { data } = await api.get("/gallery-folders/");
    folders.value = unpackList(data);
    if (!uploadFolderId.value && folders.value.length) {
      uploadFolderId.value = folders.value[0].id;
    }
  } catch (error) {
    ui.error(getGalleryError(error, "图库文件夹加载失败"));
  }
}

async function loadImages() {
  loading.value = true;
  loadError.value = "";
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
  } catch (error) {
    loadError.value = getGalleryError(error, "图库图片加载失败");
    ui.error(loadError.value);
  } finally {
    loading.value = false;
  }
}

function scheduleLoadImages() {
  window.clearTimeout(searchTimer);
  searchTimer = window.setTimeout(loadImages, 280);
}

onBeforeUnmount(() => {
  window.clearTimeout(searchTimer);
});

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
  const file = event.target.files?.[0] || null;
  if (!file) {
    selectedFile.value = null;
    return;
  }
  const fileName = String(file.name || "").toLowerCase();
  const hasAllowedExtension = [".jpg", ".jpeg", ".png", ".webp"].some((ext) => fileName.endsWith(ext));
  if (!allowedGalleryMimeTypes.has(file.type) && !hasAllowedExtension) {
    selectedFile.value = null;
    event.target.value = "";
    ui.error("仅支持 JPG、PNG、WebP 图片。");
    return;
  }
  if (file.size > galleryMaxUploadBytes) {
    selectedFile.value = null;
    event.target.value = "";
    ui.error("单张图片不能超过 12MB。");
    return;
  }
  selectedFile.value = file;
}

async function createFolder() {
  const name = folderCreatorName.value.trim();
  if (!name) {
    ui.info("请先填写文件夹名称。");
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
    ui.success("文件夹已创建。");
  } catch (error) {
    const detail =
      error?.response?.data?.name?.[0] ||
      error?.response?.data?.slug?.[0] ||
      error?.response?.data?.detail ||
      "文件夹创建失败。";
    ui.error(detail);
  } finally {
    creatingFolder.value = false;
  }
}

async function uploadImage() {
  if (!selectedFile.value || uploading.value) return;
  uploading.value = true;
  try {
    const captcha = await getCaptchaProof("upload_image");
    const form = new FormData();
    form.append("image", selectedFile.value);
    form.append("captcha", JSON.stringify(captcha));
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
    if (fileInputEl.value) {
      fileInputEl.value.value = "";
    }
    newFolderName.value = "";
    await Promise.all([loadFolders(), loadImages()]);
    ui.success("图片已上传，可以复制链接使用。");
  } catch (error) {
    ui.error(captchaErrorMessage(error, "图片上传失败。"));
  } finally {
    uploading.value = false;
  }
}

function toggleSelected(id) {
  selectedIds.value = selectedIds.value.includes(id)
    ? selectedIds.value.filter((item) => item !== id)
    : [...selectedIds.value, id];
}

function toggleSelectAllBatch() {
  if (allBatchSelected.value) {
    selectedIds.value = [];
  } else {
    selectedIds.value = images.value.map((item) => item.id);
  }
}

function cancelBatchMode() {
  isBatchMode.value = false;
  selectedIds.value = [];
}

async function bulkRecycleImages() {
  if (!selectedIds.value.length || bulkDeleting.value) return;
  const confirmed = await ui.confirm({
    title: `确认删除选中的 ${selectedIds.value.length} 张图片`,
    message: "删除后这些图片会移入回收站（7 天内可恢复），原引用链接将暂时失效。",
    confirmText: `确认删除 (${selectedIds.value.length})`,
    cancelText: "取消",
    danger: true,
  });
  if (!confirmed) return;
  bulkDeleting.value = true;
  try {
    await api.post("/gallery-images/bulk-delete/", { ids: selectedIds.value });
    cancelBatchMode();
    await Promise.all([loadFolders(), loadImages()]);
    ui.success("已移入回收站，7 天内可以恢复。");
  } catch (error) {
    ui.error(getGalleryError(error, "批量删除失败"));
  } finally {
    bulkDeleting.value = false;
  }
}

async function deleteImage(image) {
  if (!image?.id || deletingId.value === image.id) return;
  const confirmed = isRecycleView.value
    ? await ui.confirm({
        title: `永久删除图片「${image.original_name}」`,
        message: "永久删除会立即销毁服务器上的图片文件，操作不可撤销。",
        confirmText: "确认永久删除",
        cancelText: "取消",
        danger: true,
        requireText: "永久删除",
        requirePlaceholder: "请输入“永久删除”以确认不可逆操作",
      })
    : await ui.confirm({
        title: `删除图片「${image.original_name}」`,
        message: "图片将移入回收站，7 天内可恢复；移入期间外部图片链接将失效。",
        confirmText: "移入回收站",
        cancelText: "取消",
        danger: true,
      });
  if (!confirmed) return;
  deletingId.value = image.id;
  try {
    await api.delete(`/gallery-images/${image.id}/`);
    await Promise.all([loadFolders(), loadImages()]);
    ui.success(isRecycleView.value ? "图片已永久删除。" : "图片已移入回收站。");
  } catch (error) {
    ui.error(getGalleryError(error, "删除图片失败"));
  } finally {
    deletingId.value = null;
  }
}

async function restoreImage(image) {
  if (!image?.id || restoringId.value === image.id) return;
  restoringId.value = image.id;
  try {
    await api.post(`/gallery-images/${image.id}/restore/`);
    await Promise.all([loadFolders(), loadImages()]);
    ui.success("图片已恢复到原路径。");
  } catch (error) {
    ui.error(getGalleryError(error, "恢复图片失败"));
  } finally {
    restoringId.value = null;
  }
}

async function copyText(text) {
  const value = String(text || "");
  if (!value) return;
  try {
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
    ui.success("已复制到剪贴板。");
  } catch {
    ui.error("复制失败，请手动选中复制。");
  }
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
  background: var(--surface);
  color: var(--text);
}

.gallery-sidebar {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  gap: 18px;
  padding: 24px 18px;
  border-right: 1px solid var(--hairline);
  background: var(--surface-soft);
}

.gallery-subtitle,
.gallery-upload-copy p {
  margin: 0;
  color: var(--text-soft);
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
  border: 1px solid var(--hairline);
  border-radius: 18px;
  background: var(--surface-muted);
}

.gallery-primary,
.gallery-secondary,
.gallery-danger {
  border: 0;
  border-radius: 999px;
  min-height: 42px;
  padding: 0 18px;
  font-weight: 700;
  cursor: pointer;
  transition: transform var(--dur-fast) var(--ease-out), opacity var(--dur-fast) var(--ease-out), background-color var(--dur-fast) var(--ease-out);
}

.gallery-primary:not(:disabled):active,
.gallery-secondary:not(:disabled):active,
.gallery-danger:not(:disabled):active {
  transform: scale(0.97);
}

.gallery-primary {
  background: var(--accent);
  color: var(--accent-contrast);
  box-shadow: var(--accent-shadow);
}

.gallery-secondary {
  background: var(--button-bg);
  color: var(--button-text);
  border: 1px solid var(--hairline);
}

.gallery-danger {
  background: var(--danger);
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

.gallery-batch-delete {
  grid-column: 1 / -1;
}

.gallery-nav-title {
  margin: 4px 10px;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-quiet);
}

.gallery-folder {
  border: 0;
  border-radius: 14px;
  padding: 11px 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: transparent;
  color: var(--text-soft);
  font-size: 14px;
  cursor: pointer;
  text-align: left;
  transition: background-color var(--dur-fast) var(--ease-out), color var(--dur-fast) var(--ease-out);
}

.gallery-folder:hover {
  background: color-mix(in srgb, var(--accent) 8%, var(--surface-muted));
  color: var(--text-strong);
}

.gallery-folder--active {
  background: color-mix(in srgb, var(--accent) 15%, var(--surface-strong));
  color: var(--accent);
  font-weight: 800;
}

.gallery-folder--recycle {
  margin-top: 8px;
  color: var(--danger);
}

.gallery-storage {
  padding: 14px;
  border: 1px solid var(--hairline);
  border-radius: 16px;
  background: var(--surface-strong);
}

.gallery-storage-row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  color: var(--text-soft);
}

.gallery-storage-track {
  height: 6px;
  border-radius: 999px;
  background: var(--hairline);
  overflow: hidden;
}

.gallery-storage-track span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--accent);
  transition: width var(--dur-base) var(--ease-out);
}

.gallery-main {
  min-width: 0;
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr);
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
  color: var(--accent);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.gallery-head h2 {
  margin: 0 0 6px;
  color: var(--text-strong);
  font-size: clamp(28px, 3.2vw, 40px);
  line-height: 1.08;
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
  border: 1px solid var(--input-border, var(--hairline));
  border-radius: 999px;
  background: var(--input-bg, var(--surface-strong));
  color: var(--text-strong);
  padding: 0 14px;
  outline: none;
}

.gallery-search input:focus,
.gallery-upload-form input:focus,
.gallery-upload-form select:focus,
.gallery-folder-form input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--input-focus, color-mix(in srgb, var(--accent) 20%, transparent));
}

.gallery-search input {
  width: min(280px, 32vw);
}

.gallery-upload-card {
  display: grid;
  gap: 16px;
  padding: 18px;
  border: 1px solid var(--hairline);
  border-radius: 22px;
  background: var(--surface-strong);
  box-shadow: var(--shadow-sm);
}

.gallery-upload-copy h3 {
  margin: 0 0 4px;
  font-size: 20px;
  color: var(--text-strong);
}

.gallery-upload-form {
  grid-template-columns: minmax(180px, 1.2fr) minmax(160px, 0.8fr) minmax(180px, 1fr) auto;
  align-items: center;
}

.gallery-file-picker {
  min-height: 44px;
  border: 1px dashed var(--hairline-strong);
  border-radius: 16px;
  display: flex;
  align-items: center;
  padding: 0 14px;
  cursor: pointer;
  background: var(--surface-soft);
  color: var(--text);
}

.gallery-file-picker input {
  display: none;
}

.gallery-upload-result {
  display: grid;
  gap: 10px;
  padding: 14px;
  border-radius: 16px;
  background: var(--surface-soft);
  border: 1px solid var(--hairline);
}

.gallery-upload-result label {
  display: grid;
  gap: 6px;
  font-size: 13px;
  font-weight: 700;
  color: var(--text-soft);
}

.gallery-copy-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
}

.gallery-loading-box {
  padding: 14px 0;
}

.gallery-grid-wrap {
  min-height: 360px;
}

.gallery-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
  gap: 22px;
  transition: opacity var(--dur-fast) var(--ease-out);
}

.gallery-grid.is-dimmed {
  opacity: 0.6;
}

.gallery-card {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--hairline);
  border-radius: 22px;
  background: var(--surface-strong);
  box-shadow: var(--shadow-sm);
  transition: transform var(--dur-fast) var(--ease-out), border-color var(--dur-fast) var(--ease-out), box-shadow var(--dur-fast) var(--ease-out);
}

.gallery-card:hover {
  transform: translate3d(0, -2px, 0);
  border-color: color-mix(in srgb, var(--accent) 34%, var(--hairline));
}

.gallery-card--selected {
  border-color: var(--accent);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--accent) 18%, transparent);
}

.gallery-select {
  position: absolute;
  z-index: 2;
  top: 12px;
  left: 12px;
  width: 30px;
  height: 30px;
  border-radius: 999px;
  border: 2px solid rgba(255, 255, 255, 0.92);
  background: rgba(15, 23, 42, 0.48);
  color: #fff;
  cursor: pointer;
}

.gallery-select--checked {
  border-color: var(--accent);
  background: var(--accent);
  color: var(--accent-contrast);
}

.gallery-thumb {
  aspect-ratio: 1 / 0.74;
  background: var(--surface-muted);
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
  color: var(--text-quiet);
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
  color: var(--text-strong);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.gallery-card-title small,
.gallery-card-meta,
.gallery-recycle-note {
  color: var(--text-soft);
  font-size: 12px;
}

.gallery-card-meta {
  margin: 0;
  display: flex;
  justify-content: space-between;
  font-variant-numeric: tabular-nums;
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

.gallery-empty {
  min-height: 360px;
  display: grid;
  place-items: center;
  color: var(--text-quiet);
  font-weight: 700;
}

@media (max-width: 980px) {
  .gallery-shell {
    grid-template-columns: 1fr;
  }

  .gallery-sidebar {
    border-right: 0;
    border-bottom: 1px solid var(--hairline);
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

@media (prefers-reduced-motion: reduce) {
  .gallery-primary,
  .gallery-secondary,
  .gallery-danger,
  .gallery-card,
  .gallery-storage-track span {
    transition: border-color var(--dur-fast) linear, background-color var(--dur-fast) linear, opacity var(--dur-fast) linear;
  }

  .gallery-primary:not(:disabled):active,
  .gallery-secondary:not(:disabled):active,
  .gallery-danger:not(:disabled):active,
  .gallery-card:hover {
    transform: none;
  }
}
</style>

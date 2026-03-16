<script setup lang="ts">
/**
 * 空投包管理页 — 搜索优先的链接检索器 v4
 * 编排器：状态管理 + 数据加载 + 子组件组合
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';

import { CheckCheck, RotateCcw, Search, Trash2 } from '@vben/icons';

import {
  ElAlert,
  ElButton,
  ElCheckbox,
  ElEmpty,
  ElIcon,
  ElInput,
  ElMessage,
  ElMessageBox,
  ElPagination,
  ElRadioButton,
  ElRadioGroup,
} from 'element-plus';

import {
  batchDeletePacksApi,
  batchPurgePacksApi,
  batchRestorePacksApi,
  checkIdentityApi,
  deletePackApi,
  getTagsApi,
  listPacksApi,
  updatePackApi,
} from '#/api/airdrop';
import type { AirdropApi } from '#/api/airdrop';

import AirdropGroupDrawer from './airdrop-group-drawer.vue';
import AirdropMobileTags from './airdrop-mobile-tags.vue';
import AirdropPackCard from './airdrop-pack-card.vue';
import AirdropSidebar from './airdrop-sidebar.vue';

defineOptions({ name: 'AirdropPacks' });

// ─── 状态 ───
const loading = ref(false);
const identityLoading = ref(true);
const identity = ref<AirdropApi.IdentityResult | null>(null);

const searchText = ref('');
const packs = ref<AirdropApi.Pack[]>([]);
const total = ref(0);
const currentPage = ref(1);
const pageSize = ref(20);

// 标签/分组筛选
const tagsData = ref<AirdropApi.TagsResult | null>(null);
const activeGroupId = ref<number>(0);
const activeTag = ref<string>('');
const expandedGroups = ref<string[]>([]);

// 编辑状态
const editingNotePackId = ref<string | null>(null);
const editingNote = ref('');
const editingTagsPackId = ref<string | null>(null);
const editingTagsList = ref<string[]>([]);

// 分组管理 Drawer
const drawerVisible = ref(false);

// 回收站模式
const viewMode = ref<'normal' | 'trash'>('normal');
const isTrashView = computed(() => viewMode.value === 'trash');

// 批量选择
const batchMode = ref(false);
const selectedPacks = ref<Set<string>>(new Set());

// 响应式
const isMobile = ref(false);
function checkMobile() {
  isMobile.value = window.innerWidth < 768;
}

// 搜索防抖
let searchTimer: ReturnType<typeof setTimeout> | null = null;

const isBound = computed(() => identity.value?.bound ?? false);

// 所有已有标签（用于 ElSelect 下拉选项）
const allExistingTags = computed(() => {
  if (!tagsData.value) return [];
  const tags = new Set<string>();
  for (const g of tagsData.value.groups) {
    for (const t of g.tags) tags.add(t.tag);
  }
  for (const t of tagsData.value.ungrouped_tags) tags.add(t.tag);
  return [...tags].sort();
});

// 搜索框 placeholder
const searchPlaceholder = computed(() => {
  if (activeTag.value) return `在 #${activeTag.value} 中搜索...`;
  if (activeGroupId.value > 0) {
    const g = tagsData.value?.groups.find((g) => g.id === activeGroupId.value);
    return g ? `在「${g.name}」中搜索...` : '搜索备注、标签、口令...';
  }
  return '搜索备注、标签、口令...';
});

// ─── 身份检查 ───
async function checkIdentity() {
  identityLoading.value = true;
  try {
    identity.value = await checkIdentityApi();
  } catch {
    identity.value = null;
  } finally {
    identityLoading.value = false;
  }
}

// ─── 标签数据 ───
async function loadTags() {
  try {
    tagsData.value = await getTagsApi();
  } catch {
    tagsData.value = null;
  }
}

// ─── 数据加载 ───
async function loadPacks() {
  if (!isBound.value) return;
  loading.value = true;
  try {
    const params: Record<string, any> = {
      search: searchText.value,
      page: currentPage.value,
      page_size: pageSize.value,
      deleted: isTrashView.value,
    };
    if (!isTrashView.value) {
      if (activeTag.value) params.tag = activeTag.value;
      else if (activeGroupId.value > 0) params.group_id = activeGroupId.value;
    }
    const result = await listPacksApi(params);
    packs.value = result.items;
    total.value = result.total;
  } catch (e: any) {
    ElMessage.error(e?.message || '加载失败');
  } finally {
    loading.value = false;
  }
}

// ─── 视图切换 ───
function switchView(mode: 'normal' | 'trash') {
  viewMode.value = mode;
  currentPage.value = 1;
  searchText.value = '';
  exitBatchMode();
  loadPacks();
}

// ─── 批量选择 ───
function toggleBatchMode() {
  batchMode.value = !batchMode.value;
  if (!batchMode.value) {
    selectedPacks.value.clear();
  }
}

function exitBatchMode() {
  batchMode.value = false;
  selectedPacks.value.clear();
}

function toggleSelect(packId: string) {
  const s = new Set(selectedPacks.value);
  if (s.has(packId)) s.delete(packId);
  else s.add(packId);
  selectedPacks.value = s;
}

function toggleSelectAll() {
  if (selectedPacks.value.size === packs.value.length) {
    selectedPacks.value = new Set();
  } else {
    selectedPacks.value = new Set(packs.value.map((p) => p.pack_id));
  }
}

const isAllSelected = computed(
  () => packs.value.length > 0 && selectedPacks.value.size === packs.value.length,
);
const selectedCount = computed(() => selectedPacks.value.size);

// ─── 搜索 ───
watch(searchText, () => {
  if (searchTimer) clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    currentPage.value = 1;
    loadPacks();
  }, 300);
});
watch(currentPage, () => loadPacks());

// ─── 标签/分组筛选 ───
function toggleGroup(group: AirdropApi.TagGroup) {
  const key = String(group.id);
  const idx = expandedGroups.value.indexOf(key);
  if (idx >= 0) {
    expandedGroups.value.splice(idx, 1);
  } else {
    expandedGroups.value.push(key);
  }
  selectGroup(group.id);
}

function selectGroup(groupId: number) {
  activeGroupId.value = groupId;
  activeTag.value = '';
  currentPage.value = 1;
  loadPacks();
}

function selectTag(tagName: string) {
  activeTag.value = tagName;
  activeGroupId.value = 0;
  currentPage.value = 1;
  loadPacks();
}

function selectUntagged() {
  activeTag.value = '__untagged__';
  activeGroupId.value = 0;
  currentPage.value = 1;
  loadPacks();
}

function clearFilter() {
  activeGroupId.value = 0;
  activeTag.value = '';
  currentPage.value = 1;
  loadPacks();
}

// ─── 复制 ───
async function copyToClipboard(text: string, label: string) {
  try {
    await navigator.clipboard.writeText(text);
    ElMessage.success(`${label} 已复制`);
  } catch {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    document.body.removeChild(textarea);
    ElMessage.success(`${label} 已复制`);
  }
}

// ─── 备注编辑 ───
function startEditNote(pack: AirdropApi.Pack) {
  editingNotePackId.value = pack.pack_id;
  editingNote.value = pack.name || '';
}

async function saveNote(pack: AirdropApi.Pack) {
  if (editingNotePackId.value !== pack.pack_id) return;
  try {
    await updatePackApi(pack.pack_id, { name: editingNote.value });
    pack.name = editingNote.value;
    ElMessage.success('备注已更新');
  } catch (e: any) {
    ElMessage.error(e?.message || '更新失败');
  } finally {
    editingNotePackId.value = null;
  }
}

function cancelEditNote() {
  editingNotePackId.value = null;
}

// ─── 标签编辑 ───
function startEditTags(pack: AirdropApi.Pack) {
  editingTagsPackId.value = pack.pack_id;
  editingTagsList.value = pack.tags
    ? pack.tags.split(',').map((t) => t.trim()).filter(Boolean)
    : [];
}

async function saveTagsEdit(pack: AirdropApi.Pack) {
  if (editingTagsPackId.value !== pack.pack_id) return;
  try {
    const newTags = editingTagsList.value.join(',');
    await updatePackApi(pack.pack_id, { tags: newTags });
    pack.tags = newTags;
    ElMessage.success('标签已更新');
    await loadTags();
  } catch (e: any) {
    ElMessage.error(e?.message || '更新失败');
  } finally {
    editingTagsPackId.value = null;
  }
}

// ─── 快速删除标签 ───
async function handleRemoveTag(pack: AirdropApi.Pack, tagToRemove: string) {
  const currentTags = pack.tags
    ? pack.tags.split(',').map((t) => t.trim()).filter(Boolean)
    : [];
  const newTags = currentTags.filter((t) => t !== tagToRemove).join(',');
  
  try {
    await updatePackApi(pack.pack_id, { tags: newTags });
    pack.tags = newTags;
    ElMessage.success('标签已删除');
    await loadTags();
  } catch (e: any) {
    ElMessage.error(e?.message || '删除失败');
  }
}

// ─── 删除（移入回收站） ───
async function handleDelete(packId: string) {
  try {
    await ElMessageBox.confirm('确认将此空投包移入回收站？', '提示', {
      confirmButtonText: '移入回收站',
      cancelButtonText: '取消',
      type: 'warning',
    });
    await deletePackApi(packId);
    ElMessage.success('已移入回收站');
    await Promise.all([loadPacks(), loadTags()]);
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e?.message || '操作失败');
    }
  }
}

// ─── 恢复（从回收站移出） ───
async function handleRestore(packId: string) {
  try {
    await batchRestorePacksApi([packId]);
    ElMessage.success('已恢复');
    await loadPacks();
  } catch (e: any) {
    ElMessage.error(e?.message || '恢复失败');
  }
}

// ─── 批量操作 ───
async function handleBatchDelete() {
  const ids = [...selectedPacks.value];
  if (!ids.length) return;
  try {
    await ElMessageBox.confirm(
      `确认将选中的 ${ids.length} 个空投包移入回收站？`,
      '批量删除',
      { confirmButtonText: '移入回收站', cancelButtonText: '取消', type: 'warning' },
    );
    const result = await batchDeletePacksApi(ids);
    ElMessage.success(`已移入回收站 ${result.affected} 个`);
    exitBatchMode();
    await Promise.all([loadPacks(), loadTags()]);
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error(e?.message || '操作失败');
  }
}

async function handleBatchRestore() {
  const ids = [...selectedPacks.value];
  if (!ids.length) return;
  try {
    const result = await batchRestorePacksApi(ids);
    ElMessage.success(`已恢复 ${result.affected} 个`);
    exitBatchMode();
    await loadPacks();
  } catch (e: any) {
    ElMessage.error(e?.message || '恢复失败');
  }
}

async function handleBatchPurge() {
  const ids = [...selectedPacks.value];
  if (!ids.length) return;
  try {
    const { value: cleanChannel } = await ElMessageBox.confirm(
      `<p>确认<b>彻底删除</b>选中的 <b>${ids.length}</b> 个空投包？此操作不可恢复。</p>
       <label style="display:flex;align-items:center;gap:6px;margin-top:12px;cursor:pointer">
         <input type="checkbox" id="purge-clean-channel" />
         同时清理 TG 频道中的文件消息
       </label>`,
      '彻底删除',
      {
        confirmButtonText: '彻底删除',
        cancelButtonText: '取消',
        type: 'error',
        dangerouslyUseHTMLString: true,
        confirmButtonClass: 'el-button--danger',
      },
    );
    const checkbox = document.getElementById('purge-clean-channel') as HTMLInputElement | null;
    const clean = checkbox?.checked ?? false;
    const result = await batchPurgePacksApi(ids, clean);
    let msg = `已彻底删除 ${result.affected} 个`;
    if (result.channel_deleted && result.channel_deleted > 0) {
      msg += `，已清理 ${result.channel_deleted} 条频道消息`;
    }
    ElMessage.success(msg);
    exitBatchMode();
    await loadPacks();
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error(e?.message || '操作失败');
  }
}

// ─── 键盘快捷键 ───
function handleKeydown(e: KeyboardEvent) {
  if (e.key === '/' && !['INPUT', 'TEXTAREA', 'SELECT'].includes((e.target as HTMLElement)?.tagName)) {
    e.preventDefault();
    document.querySelector<HTMLInputElement>('.search-input input')?.focus();
  }
  if (e.key === 'Escape') {
    clearFilter();
    searchText.value = '';
  }
}

// ─── 生命周期 ───
onMounted(async () => {
  checkMobile();
  window.addEventListener('resize', checkMobile);
  window.addEventListener('keydown', handleKeydown);
  await checkIdentity();
  if (isBound.value) {
    await Promise.all([loadPacks(), loadTags()]);
  }
});

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile);
  window.removeEventListener('keydown', handleKeydown);
});
</script>

<template>
  <div class="airdrop-page">
    <!-- 未绑定 / 加载中 -->
    <div v-if="identityLoading" v-loading="true" style="padding: 80px 0" />

    <template v-else-if="!isBound">
      <ElAlert
        type="warning"
        show-icon
        :closable="false"
        class="mx-auto mt-10 max-w-lg"
        title="需要绑定站点账号"
        description="请先在 Telegram 小芽精灵中发送 /bind 绑定站点账号后，刷新此页面即可使用空投包管理。"
      />
    </template>

    <template v-else>
      <div class="airdrop-layout">
        <!-- 侧边栏（桌面端） -->
        <AirdropSidebar
          v-if="!isMobile"
          :tags-data="tagsData"
          :active-group-id="activeGroupId"
          :active-tag="activeTag"
          :expanded-groups="expandedGroups"
          @clear-filter="clearFilter"
          @select-group="selectGroup"
          @select-tag="selectTag"
          @select-untagged="selectUntagged"
          @toggle-group="toggleGroup"
          @open-drawer="drawerVisible = true"
        />

        <!-- 移动端顶部标签栏 -->
        <AirdropMobileTags
          v-if="isMobile"
          :tags-data="tagsData"
          :active-group-id="activeGroupId"
          :active-tag="activeTag"
          @clear-filter="clearFilter"
          @select-group="selectGroup"
          @select-tag="selectTag"
          @select-untagged="selectUntagged"
          @open-drawer="drawerVisible = true"
        />

        <!-- 主内容区 -->
        <main class="airdrop-main">
          <!-- 顶部工具栏：搜索 + 视图切换 + 批量按钮 -->
          <div class="toolbar">
            <div class="search-bar">
              <ElInput
                v-model="searchText"
                :placeholder="searchPlaceholder"
                size="large"
                clearable
                class="search-input"
              >
                <template #prefix>
                  <ElIcon :size="18"><Search /></ElIcon>
                </template>
              </ElInput>
              <span class="search-count">共 {{ total }} 个</span>
            </div>

            <div class="toolbar-actions">
              <ElRadioGroup
                :model-value="viewMode"
                size="small"
                @update:model-value="(v: string) => switchView(v as 'normal' | 'trash')"
              >
                <ElRadioButton value="normal">空投包</ElRadioButton>
                <ElRadioButton value="trash">
                  <ElIcon :size="13" style="margin-right: 3px; vertical-align: -1px"><Trash2 /></ElIcon>
                  回收站
                </ElRadioButton>
              </ElRadioGroup>

              <ElButton
                size="small"
                :type="batchMode ? 'primary' : 'default'"
                plain
                @click="toggleBatchMode"
              >
                <ElIcon :size="14" style="margin-right: 4px"><CheckCheck /></ElIcon>
                {{ batchMode ? '退出批量' : '批量操作' }}
              </ElButton>
            </div>
          </div>

          <!-- 批量操作栏 -->
          <div v-if="batchMode" class="batch-bar">
            <ElCheckbox
              :model-value="isAllSelected"
              :indeterminate="selectedCount > 0 && !isAllSelected"
              @update:model-value="toggleSelectAll"
            >
              全选 ({{ selectedCount }}/{{ packs.length }})
            </ElCheckbox>

            <div class="batch-actions">
              <template v-if="isTrashView">
                <ElButton
                  size="small"
                  type="success"
                  :disabled="selectedCount === 0"
                  @click="handleBatchRestore"
                >
                  <ElIcon :size="14" style="margin-right: 4px"><RotateCcw /></ElIcon>
                  批量恢复
                </ElButton>
                <ElButton
                  size="small"
                  type="danger"
                  :disabled="selectedCount === 0"
                  @click="handleBatchPurge"
                >
                  <ElIcon :size="14" style="margin-right: 4px"><Trash2 /></ElIcon>
                  彻底删除
                </ElButton>
              </template>
              <template v-else>
                <ElButton
                  size="small"
                  type="danger"
                  :disabled="selectedCount === 0"
                  @click="handleBatchDelete"
                >
                  <ElIcon :size="14" style="margin-right: 4px"><Trash2 /></ElIcon>
                  批量删除
                </ElButton>
              </template>
            </div>
          </div>

          <div v-loading="loading" class="pack-grid">
            <div v-if="packs.length === 0 && !loading" style="padding: 60px 0; grid-column: 1 / -1">
              <ElEmpty :description="isTrashView ? '回收站为空' : '暂无空投包'" />
            </div>

            <AirdropPackCard
              v-for="pack in packs"
              :key="pack.pack_id"
              :pack="pack"
              :search-text="searchText"
              :editing-note-pack-id="editingNotePackId"
              :editing-note="editingNote"
              :editing-tags-pack-id="editingTagsPackId"
              :editing-tags-list="editingTagsList"
              :all-existing-tags="allExistingTags"
              :batch-mode="batchMode"
              :selected="selectedPacks.has(pack.pack_id)"
              :is-trash="isTrashView"
              @start-edit-note="startEditNote"
              @update:editing-note="editingNote = $event"
              @save-note="saveNote"
              @cancel-edit-note="cancelEditNote"
              @start-edit-tags="startEditTags"
              @update:editing-tags-list="editingTagsList = $event"
              @save-tags-edit="saveTagsEdit"
              @select-tag="selectTag"
              @remove-tag="handleRemoveTag"
              @copy-to-clipboard="copyToClipboard"
              @delete-pack="handleDelete"
              @restore-pack="handleRestore"
              @toggle-select="toggleSelect"
            />
          </div>

          <div v-if="total > pageSize" class="pack-pagination">
            <ElPagination
              v-model:current-page="currentPage"
              :total="total"
              :page-size="pageSize"
              :layout="isMobile ? 'prev, pager, next' : 'total, prev, pager, next, jumper'"
              :small="isMobile"
              background
            />
          </div>
        </main>
      </div>

      <!-- 分组管理 Drawer -->
      <AirdropGroupDrawer
        v-model:visible="drawerVisible"
        :tags-data="tagsData"
        :is-mobile="isMobile"
        @tags-changed="loadTags"
      />
    </template>
  </div>
</template>

<style scoped>
.airdrop-page {
  height: 100%;
  overflow: hidden;
  background-color: var(--el-bg-color-page);
  color: var(--el-text-color-primary);
}
.airdrop-layout {
  display: flex;
  height: calc(100vh - 90px);
  overflow: hidden;
}

/* 主内容区 */
.airdrop-main {
  flex: 1;
  overflow-y: auto;
  padding: 24px 28px;
  min-width: 0;
  background-color: var(--el-bg-color-page);
}
/* 工具栏 */
.toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}
.search-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  flex: 1;
  min-width: 0;
}
.search-input {
  flex: 1;
  max-width: 560px;
}
.search-count {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}

/* 批量操作栏 */
.batch-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 16px;
  margin-bottom: 12px;
  background-color: var(--el-fill-color-light);
  border-radius: 8px;
  border: 1px solid var(--el-border-color-lighter);
}
.batch-actions {
  display: flex;
  gap: 8px;
}

/* 卡片网格 */
.pack-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  min-height: 200px;
}

/* 分页 */
.pack-pagination {
  display: flex;
  justify-content: center;
  padding: 20px 0 8px;
}

/* 响应式 */
@media (max-width: 1199px) {
  .pack-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 767px) {
  .airdrop-layout {
    flex-direction: column;
    height: auto;
  }
  .airdrop-main {
    padding: 16px 12px;
  }
  .toolbar {
    flex-direction: column;
    gap: 10px;
  }
  .toolbar-actions {
    width: 100%;
    justify-content: space-between;
  }
  .search-bar {
    flex-direction: column;
    align-items: stretch;
    gap: 8px;
    width: 100%;
  }
  .search-input {
    max-width: none;
  }
  .search-count {
    text-align: right;
  }
  .batch-bar {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
  .pack-grid {
    gap: 10px;
  }
}
</style>

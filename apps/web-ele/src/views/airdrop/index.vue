<script setup lang="ts">
/**
 * 空投包管理页 — 搜索优先的链接检索器
 * 核心交互：搜索框 → 输入关键词 → 列表实时过滤 → 复制链接/口令 → 走人
 */
import { computed, onMounted, ref, watch } from 'vue';

import {
  ElAlert,
  ElButton,
  ElCard,
  ElEmpty,
  ElInput,
  ElLoading,
  ElMessage,
  ElMessageBox,
  ElPagination,
  ElSpace,
  ElTag,
  ElTooltip,
} from 'element-plus';

import {
  checkIdentityApi,
  deletePackApi,
  listPacksApi,
  updatePackApi,
} from '#/api/airdrop';
import type { AirdropApi } from '#/api/airdrop';

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

// 搜索防抖
let searchTimer: ReturnType<typeof setTimeout> | null = null;

const isBound = computed(() => identity.value?.bound ?? false);

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

// ─── 数据加载 ───
async function loadPacks() {
  if (!isBound.value) return;
  loading.value = true;
  try {
    const result = await listPacksApi({
      search: searchText.value,
      page: currentPage.value,
      page_size: pageSize.value,
    });
    packs.value = result.items;
    total.value = result.total;
  } catch (e: any) {
    ElMessage.error(e?.message || '加载失败');
  } finally {
    loading.value = false;
  }
}

// ─── 搜索 ───
watch(searchText, () => {
  if (searchTimer) clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    currentPage.value = 1;
    loadPacks();
  }, 300);
});

watch(currentPage, () => loadPacks());

// ─── 复制 ───
async function copyToClipboard(text: string, label: string) {
  try {
    await navigator.clipboard.writeText(text);
    ElMessage.success(`${label} 已复制`);
  } catch {
    // fallback
    const textarea = document.createElement('textarea');
    textarea.value = text;
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    document.body.removeChild(textarea);
    ElMessage.success(`${label} 已复制`);
  }
}

// ─── 行内编辑 ───
const editingPackId = ref<string | null>(null);
const editingName = ref('');

function startEditName(pack: AirdropApi.Pack) {
  editingPackId.value = pack.pack_id;
  editingName.value = pack.name || '';
}

async function saveEditName(pack: AirdropApi.Pack) {
  try {
    await updatePackApi(pack.pack_id, { name: editingName.value });
    pack.name = editingName.value;
    ElMessage.success('名称已更新');
  } catch (e: any) {
    ElMessage.error(e?.message || '更新失败');
  } finally {
    editingPackId.value = null;
  }
}

function cancelEditName() {
  editingPackId.value = null;
}

// ─── 标签编辑 ───
const editingTagsPackId = ref<string | null>(null);
const editingTags = ref('');

function startEditTags(pack: AirdropApi.Pack) {
  editingTagsPackId.value = pack.pack_id;
  editingTags.value = pack.tags || '';
}

async function saveEditTags(pack: AirdropApi.Pack) {
  try {
    await updatePackApi(pack.pack_id, { tags: editingTags.value });
    pack.tags = editingTags.value;
    ElMessage.success('标签已更新');
  } catch (e: any) {
    ElMessage.error(e?.message || '更新失败');
  } finally {
    editingTagsPackId.value = null;
  }
}

// ─── 删除 ───
async function handleDelete(packId: string) {
  try {
    await ElMessageBox.confirm('确认删除此空投包？', '提示', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    });
    await deletePackApi(packId);
    ElMessage.success('删除成功');
    await loadPacks();
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e?.message || '删除失败');
    }
  }
}

// ─── 格式化 ───
function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-';
  const d = new Date(dateStr);
  const month = d.getMonth() + 1;
  const day = d.getDate();
  const hour = String(d.getHours()).padStart(2, '0');
  const min = String(d.getMinutes()).padStart(2, '0');
  return `${month}月${day}日 ${hour}:${min}`;
}

function parseTags(tags: string | null): string[] {
  if (!tags) return [];
  return tags
    .split(',')
    .map((t) => t.trim())
    .filter(Boolean);
}

// ─── 生命周期 ───
onMounted(async () => {
  await checkIdentity();
  if (isBound.value) {
    await loadPacks();
  }
});
</script>

<template>
  <div class="p-5">
    <!-- 未绑定提示 -->
    <div v-if="identityLoading" v-loading="true" class="py-20" />

    <template v-else-if="!isBound">
      <ElAlert
        type="warning"
        show-icon
        :closable="false"
        class="mx-auto max-w-lg"
        title="需要绑定站点账号"
        description="请先在 Telegram 小芽精灵中发送 /bind 绑定站点账号后，刷新此页面即可使用空投包管理。"
      />
    </template>

    <template v-else>
      <!-- 搜索栏 -->
      <div class="mb-5 flex items-center gap-3">
        <ElInput
          v-model="searchText"
          placeholder="搜索包名、口令、标签..."
          size="large"
          clearable
          class="max-w-xl flex-1"
          prefix-icon="Search"
        />
        <span class="text-sm text-gray-400 whitespace-nowrap">
          共 {{ total }} 个空投包
        </span>
      </div>

      <!-- 列表 -->
      <div v-loading="loading">
        <div v-if="packs.length === 0 && !loading" class="py-20">
          <ElEmpty description="暂无空投包" />
        </div>

        <div class="space-y-3">
          <ElCard
            v-for="pack in packs"
            :key="pack.pack_id"
            shadow="hover"
            :body-style="{ padding: '16px' }"
          >
            <div class="flex items-start justify-between gap-4">
              <!-- 左侧：包名 + 标签 + 时间 -->
              <div class="min-w-0 flex-1">
                <!-- 包名 -->
                <div class="mb-1 flex items-center gap-2">
                  <span class="text-lg">📦</span>
                  <template v-if="editingPackId === pack.pack_id">
                    <ElInput
                      v-model="editingName"
                      size="small"
                      class="max-w-xs"
                      placeholder="输入包名..."
                      @keyup.enter="saveEditName(pack)"
                      @blur="saveEditName(pack)"
                    />
                    <ElButton size="small" link @click="cancelEditName">
                      取消
                    </ElButton>
                  </template>
                  <template v-else>
                    <span
                      class="cursor-pointer font-medium hover:text-blue-500"
                      @click="startEditName(pack)"
                    >
                      {{ pack.name || '(未命名 - 点击编辑)' }}
                    </span>
                    <span class="text-xs text-gray-400">
                      {{ pack.item_count }} 项
                    </span>
                  </template>
                </div>

                <!-- 标签 -->
                <div class="mb-1 flex flex-wrap items-center gap-1">
                  <template v-if="editingTagsPackId === pack.pack_id">
                    <ElInput
                      v-model="editingTags"
                      size="small"
                      class="max-w-xs"
                      placeholder="标签逗号分隔，如：设计,教程"
                      @keyup.enter="saveEditTags(pack)"
                      @blur="saveEditTags(pack)"
                    />
                  </template>
                  <template v-else>
                    <ElTag
                      v-for="tag in parseTags(pack.tags)"
                      :key="tag"
                      size="small"
                      class="cursor-pointer"
                      @click="startEditTags(pack)"
                    >
                      #{{ tag }}
                    </ElTag>
                    <ElTag
                      v-if="!pack.tags"
                      size="small"
                      type="info"
                      class="cursor-pointer"
                      style="border-style: dashed"
                      @click="startEditTags(pack)"
                    >
                      + 添加标签
                    </ElTag>
                  </template>
                </div>

                <!-- 时间 -->
                <span class="text-xs text-gray-400">
                  {{ formatDate(pack.created_at) }}
                </span>
              </div>

              <!-- 右侧：口令 + 操作按钮 -->
              <div class="flex shrink-0 flex-col items-end gap-2">
                <!-- 口令展示 -->
                <div v-if="pack.auto_code" class="flex items-center gap-1">
                  <code class="rounded bg-gray-100 px-2 py-0.5 font-mono text-sm">
                    🔑 {{ pack.auto_code }}
                  </code>
                </div>

                <!-- 操作按钮 -->
                <ElSpace>
                  <ElTooltip content="复制提货口令" placement="top">
                    <ElButton
                      v-if="pack.auto_code"
                      size="small"
                      @click="copyToClipboard(pack.auto_code!, '口令')"
                    >
                      📋 口令
                    </ElButton>
                  </ElTooltip>
                  <ElTooltip content="复制分享链接" placement="top">
                    <ElButton
                      size="small"
                      type="primary"
                      plain
                      @click="copyToClipboard(pack.share_link, '链接')"
                    >
                      🔗 链接
                    </ElButton>
                  </ElTooltip>
                  <ElButton
                    size="small"
                    type="danger"
                    plain
                    @click="handleDelete(pack.pack_id)"
                  >
                    删除
                  </ElButton>
                </ElSpace>
              </div>
            </div>
          </ElCard>
        </div>
      </div>

      <!-- 分页 -->
      <div v-if="total > pageSize" class="mt-5 flex justify-center">
        <ElPagination
          v-model:current-page="currentPage"
          :total="total"
          :page-size="pageSize"
          layout="total, prev, pager, next, jumper"
        />
      </div>
    </template>
  </div>
</template>

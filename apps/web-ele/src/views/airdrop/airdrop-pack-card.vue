<script setup lang="ts">
/**
 * 空投包管理 — 单个空投包卡片
 */
import {
  Copy,
  Hash,
  KeyRound,
  Link,
  Package,
  Plus,
  RotateCcw,
  ShieldCheck,
  ShieldOff,
  Timer,
  Trash2,
  X,
} from '@vben/icons';

import {
  ElButton,
  ElCard,
  ElCheckbox,
  ElIcon,
  ElInput,
  ElOption,
  ElSelect,
  ElTag,
  ElTooltip,
} from 'element-plus';

import type { AirdropApi } from '#/api/airdrop';

const props = defineProps<{
  pack: AirdropApi.Pack;
  searchText: string;
  editingNotePackId: string | null;
  editingNote: string;
  editingTagsPackId: string | null;
  editingTagsList: string[];
  allExistingTags: string[];
  batchMode: boolean;
  selected: boolean;
  isTrash: boolean;
  globalProtect: boolean;
  globalMaxClaims: number;
  globalAutoDelete: number;
}>();

const emit = defineEmits<{
  startEditNote: [pack: AirdropApi.Pack];
  'update:editingNote': [value: string];
  saveNote: [pack: AirdropApi.Pack];
  cancelEditNote: [];
  startEditTags: [pack: AirdropApi.Pack];
  'update:editingTagsList': [value: string[]];
  saveTagsEdit: [pack: AirdropApi.Pack];
  selectTag: [tagName: string];
  removeTag: [pack: AirdropApi.Pack, tag: string];
  copyToClipboard: [text: string, label: string];
  deletePack: [packId: string];
  restorePack: [packId: string];
  toggleSelect: [packId: string];
  updateProtect: [packId: string, value: boolean | null];
  updateMaxClaims: [packId: string, value: number | null];
  updateAutoDelete: [packId: string, value: number | null];
}>();

function parseTags(tags: string | null): string[] {
  if (!tags) return [];
  return tags
    .split(',')
    .map((t) => t.trim())
    .filter(Boolean);
}

function highlightText(text: string | null, keyword: string): string {
  if (!text || !keyword.trim()) return text || '';
  const escaped = keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const regex = new RegExp(`(${escaped})`, 'gi');
  return text.replace(regex, '<mark class="bg-yellow-200 px-0.5 rounded">$1</mark>');
}

// 内容保护三态循环：null(继承) -> true(强制保护) -> false(强制不保护) -> null
function cycleProtect() {
  const current = props.pack.protect_content;
  let next: boolean | null;
  if (current === null || current === undefined) {
    next = true;
  } else if (current === true) {
    next = false;
  } else {
    next = null;
  }
  emit('updateProtect', props.pack.pack_id, next);
}

// 获取最终生效的保护状态
function effectiveProtect(): boolean {
  if (props.pack.protect_content !== null && props.pack.protect_content !== undefined) {
    return props.pack.protect_content;
  }
  return props.globalProtect;
}

function protectLabel(): { text: string; type: 'inherited' | 'on' | 'off' } {
  const pc = props.pack.protect_content;
  if (pc === null || pc === undefined) {
    return { text: props.globalProtect ? '继承·保护' : '继承·公开', type: 'inherited' };
  }
  return pc
    ? { text: '强制保护', type: 'on' }
    : { text: '强制公开', type: 'off' };
}

// 领取限制三态循环：null(继承) -> 1(限1次) -> 0(不限) -> null
function cycleMaxClaims() {
  const current = props.pack.max_claims_per_user;
  let next: number | null;
  if (current === null || current === undefined) {
    next = 1;
  } else if (current > 0) {
    next = 0;
  } else {
    next = null;
  }
  emit('updateMaxClaims', props.pack.pack_id, next);
}

function claimsLabel(): { text: string; type: 'inherited' | 'limited' | 'unlimited' } {
  const v = props.pack.max_claims_per_user;
  if (v === null || v === undefined) {
    return {
      text: props.globalMaxClaims === 0 ? '继承·不限' : `继承·${props.globalMaxClaims}次`,
      type: 'inherited',
    };
  }
  return v === 0
    ? { text: '不限次数', type: 'unlimited' }
    : { text: `限${v}次`, type: 'limited' };
}

// 自动删除三态循环：null(继承) -> 60(60秒) -> 0(不删) -> null
function cycleAutoDelete() {
  const current = props.pack.auto_delete_seconds;
  let next: number | null;
  if (current === null || current === undefined) {
    next = 60;
  } else if (current > 0) {
    next = 0;
  } else {
    next = null;
  }
  emit('updateAutoDelete', props.pack.pack_id, next);
}

function autoDeleteLabel(): { text: string; type: 'inherited' | 'active' | 'disabled' } {
  const v = props.pack.auto_delete_seconds;
  if (v === null || v === undefined) {
    return {
      text: props.globalAutoDelete === 0 ? '继承·不删' : `继承·${props.globalAutoDelete}s`,
      type: 'inherited',
    };
  }
  return v === 0
    ? { text: '不自动删', type: 'disabled' }
    : { text: `${v}s后删`, type: 'active' };
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-';
  const d = new Date(dateStr);
  const month = d.getMonth() + 1;
  const day = d.getDate();
  const hour = String(d.getHours()).padStart(2, '0');
  const min = String(d.getMinutes()).padStart(2, '0');
  return `${month}月${day}日 ${hour}:${min}`;
}
</script>

<template>
  <ElCard
    shadow="hover"
    class="pack-card"
    :class="{ 'pack-card--selected': selected, 'pack-card--trash': isTrash }"
    :body-style="{ padding: '16px 20px' }"
    @click="batchMode ? emit('toggleSelect', pack.pack_id) : undefined"
  >
    <!-- 顶部：备注 + 操作 -->
    <div class="pack-card-header">
      <ElCheckbox
        v-if="batchMode"
        :model-value="selected"
        class="pack-checkbox"
        @update:model-value="emit('toggleSelect', pack.pack_id)"
        @click.stop
      />
      <div class="pack-card-title">
        <ElIcon :size="18" class="pack-card-icon"><Package /></ElIcon>
        <template v-if="editingNotePackId === pack.pack_id">
          <ElInput
            :model-value="editingNote"
            size="small"
            class="note-input"
            placeholder="添加备注，方便下次搜索..."
            @update:model-value="(v: string) => emit('update:editingNote', v)"
            @keyup.enter="emit('saveNote', pack)"
            @blur="emit('saveNote', pack)"
          />
          <ElButton size="small" link @click="emit('cancelEditNote')">
            <ElIcon :size="14"><X /></ElIcon>
          </ElButton>
        </template>
        <template v-else>
          <span
            v-if="pack.name"
            class="pack-name"
            v-html="highlightText(pack.name, searchText)"
            @click="emit('startEditNote', pack)"
          />
          <span v-else class="pack-name-empty" @click="emit('startEditNote', pack)">
            + 添加备注
          </span>
        </template>
      </div>
      <div class="pack-card-meta">
        <span
          class="protect-badge"
          :class="`protect-badge--${protectLabel().type}`"
          @click.stop="cycleProtect()"
        >
          <ElIcon :size="12">
            <ShieldCheck v-if="protectLabel().type === 'on'" />
            <ShieldOff v-if="protectLabel().type === 'off'" />
            <ShieldCheck v-if="protectLabel().type === 'inherited'" />
          </ElIcon>
          <span class="protect-badge-text">{{ protectLabel().text }}</span>
        </span>
        <span
          class="claims-badge"
          :class="`claims-badge--${claimsLabel().type}`"
          @click.stop="cycleMaxClaims()"
        >
          <ElIcon :size="12"><Hash /></ElIcon>
          <span class="claims-badge-text">{{ claimsLabel().text }}</span>
        </span>
        <span
          class="autodel-badge"
          :class="`autodel-badge--${autoDeleteLabel().type}`"
          @click.stop="cycleAutoDelete()"
        >
          <ElIcon :size="12"><Timer /></ElIcon>
          <span class="autodel-badge-text">{{ autoDeleteLabel().text }}</span>
        </span>
        <span class="meta-badge">{{ pack.item_count }} 项</span>
        <span class="meta-date">{{ formatDate(pack.created_at) }}</span>
        <template v-if="isTrash">
          <ElButton
            size="small"
            type="success"
            text
            :icon="RotateCcw"
            @click="emit('restorePack', pack.pack_id)"
          />
        </template>
        <template v-else>
          <ElButton
            size="small"
            type="danger"
            text
            :icon="Trash2"
            @click="emit('deletePack', pack.pack_id)"
          />
        </template>
      </div>
    </div>

    <!-- 口令 + 链接 -->
    <div class="pack-card-links">
      <ElTooltip v-if="pack.auto_code" content="点击复制口令" placement="top">
        <ElTag
          effect="light"
          type="warning"
          round
          class="copy-tag"
          @click="emit('copyToClipboard', pack.auto_code!, '口令')"
        >
          <ElIcon :size="12"><KeyRound /></ElIcon>
          <span class="copy-tag-text">{{ pack.auto_code }}</span>
          <ElIcon :size="11" class="copy-icon"><Copy /></ElIcon>
        </ElTag>
      </ElTooltip>
      <ElTooltip content="点击复制链接" placement="top">
        <ElTag
          effect="light"
          type="success"
          round
          class="copy-tag"
          @click="emit('copyToClipboard', pack.share_link, '链接')"
        >
          <ElIcon :size="12"><Link /></ElIcon>
          <span class="copy-tag-text">{{ pack.share_link.length > 32 ? pack.share_link.slice(0, 32) + '...' : pack.share_link }}</span>
          <ElIcon :size="11" class="copy-icon"><Copy /></ElIcon>
        </ElTag>
      </ElTooltip>
    </div>

    <!-- 标签 -->
    <div class="pack-card-tags">
      <template v-if="editingTagsPackId === pack.pack_id">
        <ElSelect
          :model-value="editingTagsList"
          multiple
          filterable
          allow-create
          default-first-option
          placeholder="选择或输入标签..."
          size="small"
          class="tags-select"
          @update:model-value="(v: string[]) => emit('update:editingTagsList', v)"
          @visible-change="(v: boolean) => { if (!v) emit('saveTagsEdit', pack); }"
        >
          <ElOption
            v-for="t in allExistingTags"
            :key="t"
            :label="t"
            :value="t"
          />
        </ElSelect>
      </template>
      <template v-else>
        <ElTag
          v-for="tag in parseTags(pack.tags)"
          :key="tag"
          size="small"
          effect="light"
          type="primary"
          round
          closable
          class="clickable-tag"
          @click="emit('selectTag', tag)"
          @close.stop="emit('removeTag', pack, tag)"
        >
          <span v-html="highlightText(tag, searchText)" />
        </ElTag>
        <ElButton
          size="small"
          text
          :type="pack.tags ? 'info' : 'primary'"
          @click="emit('startEditTags', pack)"
        >
          <ElIcon :size="12"><Plus /></ElIcon>
          <span v-if="!pack.tags" style="margin-left: 2px">添加标签</span>
        </ElButton>
      </template>
    </div>
  </ElCard>
</template>

<style scoped>
.pack-card {
  border-radius: 10px;
  transition: box-shadow 0.2s ease, border-color 0.2s ease;
}
.pack-card--selected {
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 1px var(--el-color-primary-light-5);
}
.pack-card--trash {
  opacity: 0.75;
}
.pack-checkbox {
  flex-shrink: 0;
  margin-right: 4px;
}

/* 卡片头部 */
.pack-card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 10px;
}
.pack-card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1;
}
.pack-card-icon {
  color: var(--el-color-primary);
  flex-shrink: 0;
}
.pack-name {
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  color: var(--el-text-color-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.4;
}
.pack-name:hover {
  color: var(--el-color-primary);
}
.pack-name-empty {
  font-size: 13px;
  color: var(--el-text-color-placeholder);
  cursor: pointer;
}
.pack-name-empty:hover {
  color: var(--el-color-primary);
}
.note-input {
  max-width: 280px;
}

/* 搜索高亮 */
:deep(mark) {
  background-color: rgba(234, 179, 8, 0.35);
  color: inherit;
  padding: 1px 3px;
  border-radius: 3px;
}

/* 卡片元数据 */
.pack-card-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
/* 内容保护徽章 */
.protect-badge {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
  user-select: none;
  white-space: nowrap;
  border: 1px solid transparent;
}
.protect-badge:hover {
  transform: scale(1.05);
  filter: brightness(0.95);
}
.protect-badge-text {
  line-height: 1.4;
}
/* 继承全局 — 虚线边框 + 柔和蓝灰 */
.protect-badge--inherited {
  color: var(--el-text-color-secondary);
  background-color: var(--el-fill-color);
  border: 1px dashed var(--el-border-color);
}
/* 强制保护 — 绿色实底 */
.protect-badge--on {
  color: #fff;
  background-color: var(--el-color-success);
}
/* 强制公开 — 橙色实底 */
.protect-badge--off {
  color: #fff;
  background-color: var(--el-color-warning);
}

/* 领取限制徽章 */
.claims-badge {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
  user-select: none;
  white-space: nowrap;
  border: 1px solid transparent;
}
.claims-badge:hover {
  transform: scale(1.05);
  filter: brightness(0.95);
}
.claims-badge-text {
  line-height: 1.4;
}
.claims-badge--inherited {
  color: var(--el-text-color-secondary);
  background-color: var(--el-fill-color);
  border: 1px dashed var(--el-border-color);
}
.claims-badge--limited {
  color: #fff;
  background-color: var(--el-color-primary);
}
.claims-badge--unlimited {
  color: #fff;
  background-color: #6b7280;
}

/* 自动删除徽章 */
.autodel-badge {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
  user-select: none;
  white-space: nowrap;
  border: 1px solid transparent;
}
.autodel-badge:hover {
  transform: scale(1.05);
  filter: brightness(0.95);
}
.autodel-badge-text {
  line-height: 1.4;
}
.autodel-badge--inherited {
  color: var(--el-text-color-secondary);
  background-color: var(--el-fill-color);
  border: 1px dashed var(--el-border-color);
}
.autodel-badge--active {
  color: #fff;
  background-color: var(--el-color-danger);
}
.autodel-badge--disabled {
  color: #fff;
  background-color: #6b7280;
}

.meta-badge {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  background-color: var(--el-fill-color);
  padding: 2px 8px;
  border-radius: 10px;
  white-space: nowrap;
}
.meta-date {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  white-space: nowrap;
}

/* 卡片标签 */
.pack-card-tags {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: 14px;
  margin-bottom: 10px;
}
.clickable-tag {
  cursor: pointer;
  transition: all 0.15s;
  --el-tag-bg-color: rgba(147, 51, 234, 0.1) !important;
  --el-tag-border-color: rgba(147, 51, 234, 0.2) !important;
  --el-tag-text-color: #9333ea !important;
}
.clickable-tag:hover {
  opacity: 0.85;
  transform: scale(1.03);
  --el-tag-bg-color: rgba(147, 51, 234, 0.18) !important;
}
.tags-select {
  min-width: 220px;
  max-width: 400px;
}

/* 卡片链接行 */
.pack-card-links {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.copy-tag {
  cursor: pointer;
  transition: all 0.15s;
  user-select: none;
  max-width: 100%;
}
.copy-tag :deep(.el-tag__content) {
  display: inline-flex !important;
  align-items: center !important;
  white-space: nowrap !important;
}
.copy-tag:hover {
  opacity: 0.85;
  transform: scale(1.02);
}
.copy-tag-text {
  margin: 0 4px;
  font-family: 'SF Mono', 'Cascadia Code', 'Menlo', monospace;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.copy-icon {
  opacity: 0.5;
  margin-left: 2px;
  flex-shrink: 0;
}
.copy-tag:hover .copy-icon {
  opacity: 1;
}

/* ═══ 响应式 ═══ */
@media (max-width: 767px) {
  .pack-card-header {
    flex-direction: column;
    gap: 6px;
  }
  .pack-card-meta {
    align-self: flex-end;
  }
  .pack-card-links {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>

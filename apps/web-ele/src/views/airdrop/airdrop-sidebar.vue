<script setup lang="ts">
/**
 * 空投包管理 — 桌面端侧边栏（标签分组导航）
 */
import {
  ChevronRight,
  FolderOpen,
  Hash,
  Inbox,
  Package,
  Settings,
  Tag,
} from '@vben/icons';

import { ElIcon, ElTag } from 'element-plus';

import type { AirdropApi } from '#/api/airdrop';

const props = defineProps<{
  tagsData: AirdropApi.TagsResult | null;
  activeGroupId: number;
  activeTag: string;
  expandedGroups: string[];
}>();

const emit = defineEmits<{
  clearFilter: [];
  selectGroup: [groupId: number];
  selectTag: [tagName: string];
  selectUntagged: [];
  toggleGroup: [group: AirdropApi.TagGroup];
  openDrawer: [];
}>();

function groupTotalCount(group: AirdropApi.TagGroup): number {
  return group.tags.reduce((sum, t) => sum + t.count, 0);
}
</script>

<template>
  <aside class="airdrop-sidebar">
    <div class="sidebar-header">
      <ElIcon :size="16"><Tag /></ElIcon>
      <span>标签分类</span>
    </div>

    <!-- 全部 -->
    <div
      class="sidebar-nav-item"
      :class="{ active: !activeGroupId && !activeTag }"
      @click="emit('clearFilter')"
    >
      <span class="sidebar-nav-label">
        <ElIcon :size="15"><Package /></ElIcon>
        全部
      </span>
      <ElTag size="small" round effect="plain" type="info">{{ tagsData?.total ?? 0 }}</ElTag>
    </div>

    <!-- 无标签 -->
    <div
      class="sidebar-nav-item"
      :class="{ active: activeTag === '__untagged__' }"
      @click="emit('selectUntagged')"
    >
      <span class="sidebar-nav-label">
        <ElIcon :size="15"><Inbox /></ElIcon>
        无标签
      </span>
      <ElTag size="small" round effect="plain" type="info">{{ tagsData?.untagged_count ?? 0 }}</ElTag>
    </div>

    <div class="sidebar-divider" />

    <!-- 分组 -->
    <template v-if="tagsData?.groups.length">
      <div
        v-for="group in tagsData.groups"
        :key="group.id"
        class="sidebar-group"
      >
        <div
          class="sidebar-nav-item group-header"
          :class="{ active: activeGroupId === group.id && !activeTag }"
          @click="emit('toggleGroup', group)"
        >
          <span class="sidebar-nav-label">
            <ElIcon :size="15"><FolderOpen /></ElIcon>
            {{ group.name }}
          </span>
          <span class="sidebar-group-right">
            <ElTag size="small" round effect="plain" type="info">{{ groupTotalCount(group) }}</ElTag>
            <ElIcon
              :size="14"
              class="sidebar-chevron"
              :class="{ expanded: expandedGroups.includes(String(group.id)) }"
            >
              <ChevronRight />
            </ElIcon>
          </span>
        </div>
        <transition name="slide-fade">
          <div v-if="expandedGroups.includes(String(group.id))" class="sidebar-sub-list">
            <div
              v-for="t in group.tags"
              :key="t.tag"
              class="sidebar-nav-item sub"
              :class="{ active: activeTag === t.tag }"
              @click.stop="emit('selectTag', t.tag)"
            >
              <span class="sidebar-nav-label">
                <ElIcon :size="12"><Hash /></ElIcon>
                {{ t.tag }}
              </span>
              <span class="sidebar-sub-count">{{ t.count }}</span>
            </div>
          </div>
        </transition>
      </div>
    </template>

    <!-- 未分组标签 -->
    <template v-if="tagsData?.ungrouped_tags.length">
      <div class="sidebar-divider" />
      <div class="sidebar-section-label">其他标签</div>
      <div
        v-for="t in tagsData.ungrouped_tags"
        :key="t.tag"
        class="sidebar-nav-item"
        :class="{ active: activeTag === t.tag }"
        @click="emit('selectTag', t.tag)"
      >
        <span class="sidebar-nav-label">
          <ElIcon :size="12"><Hash /></ElIcon>
          {{ t.tag }}
        </span>
        <span class="sidebar-sub-count">{{ t.count }}</span>
      </div>
    </template>

    <!-- 管理标签分组 -->
    <div class="sidebar-divider" />
    <div class="sidebar-nav-item manage" @click="emit('openDrawer')">
      <span class="sidebar-nav-label">
        <ElIcon :size="15"><Settings /></ElIcon>
        管理标签分组
      </span>
    </div>
  </aside>
</template>

<style scoped>
.airdrop-sidebar {
  width: 240px;
  min-width: 240px;
  border-right: 1px solid var(--el-border-color-lighter);
  overflow-y: auto;
  padding: 8px 0;
  background-color: var(--el-bg-color);
}

.sidebar-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px 16px;
  font-weight: 600;
  font-size: 15px;
  color: var(--el-text-color-primary);
  letter-spacing: 0.5px;
}

.sidebar-nav-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 16px;
  min-height: 40px;
  cursor: pointer;
  font-size: 13px;
  color: var(--el-text-color-regular);
  transition: all 0.2s ease;
  border-left: 3px solid transparent;
  margin: 1px 0;
}
.sidebar-nav-item:hover {
  background-color: var(--el-fill-color-light);
}
.sidebar-nav-item.active {
  background-color: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  font-weight: 500;
  border-left-color: var(--el-color-primary);
}

.sidebar-nav-label {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sidebar-nav-item.sub {
  padding-left: 44px;
  min-height: 34px;
  font-size: 12.5px;
}

.sidebar-nav-item.manage {
  color: var(--el-text-color-secondary);
}
.sidebar-nav-item.manage:hover {
  color: var(--el-color-primary);
}

.sidebar-group-right {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.sidebar-chevron {
  transition: transform 0.25s ease;
  color: var(--el-text-color-placeholder);
}
.sidebar-chevron.expanded {
  transform: rotate(90deg);
}

.sidebar-sub-list {
  overflow: hidden;
}
.sidebar-sub-count {
  font-size: 11px;
  color: var(--el-text-color-placeholder);
  flex-shrink: 0;
}

.sidebar-divider {
  height: 1px;
  background-color: var(--el-border-color-extra-light);
  margin: 8px 16px;
}
.sidebar-section-label {
  padding: 8px 20px 4px;
  font-size: 11px;
  color: var(--el-text-color-placeholder);
  text-transform: uppercase;
  letter-spacing: 1px;
  font-weight: 500;
}

/* 展开收起动画 */
.slide-fade-enter-active {
  transition: all 0.25s ease;
}
.slide-fade-leave-active {
  transition: all 0.2s ease;
}
.slide-fade-enter-from,
.slide-fade-leave-to {
  opacity: 0;
  max-height: 0;
}
.slide-fade-enter-to,
.slide-fade-leave-from {
  opacity: 1;
  max-height: 500px;
}
</style>

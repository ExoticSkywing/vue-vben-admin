<script setup lang="ts">
/**
 * 空投包管理 — 移动端顶部标签滚动栏
 */
import { Settings } from '@vben/icons';

import { ElIcon, ElScrollbar, ElTag } from 'element-plus';

import type { AirdropApi } from '#/api/airdrop';

const props = defineProps<{
  tagsData: AirdropApi.TagsResult | null;
  activeGroupId: number;
  activeTag: string;
}>();

const emit = defineEmits<{
  clearFilter: [];
  selectGroup: [groupId: number];
  selectTag: [tagName: string];
  selectUntagged: [];
  openDrawer: [];
}>();

function groupTotalCount(group: AirdropApi.TagGroup): number {
  return group.tags.reduce((sum, t) => sum + t.count, 0);
}

function activeGroupTags(): AirdropApi.TagItem[] {
  return props.tagsData?.groups.find((g) => g.id === props.activeGroupId)?.tags ?? [];
}
</script>

<template>
  <div class="mobile-tags">
    <ElScrollbar class="mobile-tags-scroll">
      <div class="mobile-tags-row">
        <ElTag
          :effect="!activeGroupId && !activeTag ? 'dark' : 'plain'"
          :type="!activeGroupId && !activeTag ? 'primary' : 'info'"
          round
          class="mobile-pill"
          @click="emit('clearFilter')"
        >
          全部 {{ tagsData?.total ?? 0 }}
        </ElTag>
        <ElTag
          v-for="group in tagsData?.groups ?? []"
          :key="group.id"
          :effect="activeGroupId === group.id ? 'dark' : 'plain'"
          :type="activeGroupId === group.id ? 'primary' : 'info'"
          round
          class="mobile-pill"
          @click="emit('selectGroup', group.id)"
        >
          {{ group.name }} {{ groupTotalCount(group) }}
        </ElTag>
        <ElTag
          v-for="t in tagsData?.ungrouped_tags ?? []"
          :key="t.tag"
          :effect="activeTag === t.tag ? 'dark' : 'plain'"
          :type="activeTag === t.tag ? 'primary' : 'info'"
          round
          class="mobile-pill"
          @click="emit('selectTag', t.tag)"
        >
          #{{ t.tag }} {{ t.count }}
        </ElTag>
        <ElTag
          :effect="activeTag === '__untagged__' ? 'dark' : 'plain'"
          :type="activeTag === '__untagged__' ? 'primary' : 'info'"
          round
          class="mobile-pill"
          @click="emit('selectUntagged')"
        >
          未分类 {{ tagsData?.untagged_count ?? 0 }}
        </ElTag>
        <ElTag round effect="plain" type="info" class="mobile-pill" @click="emit('openDrawer')">
          <ElIcon :size="14"><Settings /></ElIcon>
        </ElTag>
      </div>
    </ElScrollbar>
    <!-- 二级：选中分组后显示组内标签 -->
    <ElScrollbar
      v-if="activeGroupId > 0 && activeGroupTags().length"
      class="mobile-tags-scroll sub"
    >
      <div class="mobile-tags-row">
        <ElTag
          :effect="!activeTag ? 'dark' : 'light'"
          :type="!activeTag ? 'primary' : 'info'"
          round
          size="small"
          class="mobile-pill"
          @click="emit('selectGroup', activeGroupId)"
        >
          全部
        </ElTag>
        <ElTag
          v-for="t in activeGroupTags()"
          :key="t.tag"
          :effect="activeTag === t.tag ? 'dark' : 'light'"
          :type="activeTag === t.tag ? 'primary' : 'info'"
          round
          size="small"
          class="mobile-pill"
          @click="emit('selectTag', t.tag)"
        >
          #{{ t.tag }} {{ t.count }}
        </ElTag>
      </div>
    </ElScrollbar>
  </div>
</template>

<style scoped>
.mobile-tags {
  padding: 10px 12px 6px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  background-color: var(--el-bg-color);
}
.mobile-tags-scroll {
  margin-bottom: 4px;
}
.mobile-tags-scroll.sub {
  margin-top: 6px;
}
.mobile-tags-row {
  display: flex;
  gap: 6px;
  white-space: nowrap;
  padding-bottom: 4px;
}
.mobile-pill {
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.15s;
}
</style>

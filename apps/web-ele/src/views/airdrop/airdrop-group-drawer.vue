<script setup lang="ts">
/**
 * 空投包管理 — 分组管理 Drawer
 */
import { ref } from 'vue';

import { FolderOpen, Pencil, Plus, Trash2 } from '@vben/icons';

import {
  ElButton,
  ElDrawer,
  ElIcon,
  ElInput,
  ElMessage,
  ElOption,
  ElPopconfirm,
  ElSelect,
  ElTag,
} from 'element-plus';

import type { AirdropApi } from '#/api/airdrop';
import {
  createTagGroupApi,
  deleteTagGroupApi,
  setGroupMembersApi,
  updateTagGroupApi,
} from '#/api/airdrop';

const props = defineProps<{
  visible: boolean;
  tagsData: AirdropApi.TagsResult | null;
  isMobile: boolean;
}>();

const emit = defineEmits<{
  'update:visible': [value: boolean];
  tagsChanged: [];
}>();

const newGroupName = ref('');
const renamingGroupId = ref<number | null>(null);
const renamingGroupName = ref('');
const drawerAddingGroupId = ref<number | null>(null);
const drawerAddingTag = ref('');

async function createGroup() {
  if (!newGroupName.value.trim()) return;
  try {
    await createTagGroupApi({ group_name: newGroupName.value.trim() });
    newGroupName.value = '';
    ElMessage.success('分组已创建');
    emit('tagsChanged');
  } catch (e: any) {
    ElMessage.error(e?.message || '创建失败');
  }
}

function startRenameGroup(group: AirdropApi.TagGroup) {
  renamingGroupId.value = group.id;
  renamingGroupName.value = group.name;
}

async function saveRenameGroup(groupId: number) {
  try {
    await updateTagGroupApi(groupId, {
      group_name: renamingGroupName.value.trim(),
    });
    ElMessage.success('已重命名');
    emit('tagsChanged');
  } catch (e: any) {
    ElMessage.error(e?.message || '重命名失败');
  } finally {
    renamingGroupId.value = null;
  }
}

async function deleteGroup(groupId: number) {
  try {
    await deleteTagGroupApi(groupId);
    ElMessage.success('分组已删除');
    emit('tagsChanged');
  } catch (e: any) {
    ElMessage.error(e?.message || '删除失败');
  }
}

async function removeTagFromGroup(groupId: number, tagName: string) {
  const group = props.tagsData?.groups.find((g) => g.id === groupId);
  if (!group) return;
  const remaining = group.tags.map((t) => t.tag).filter((t) => t !== tagName);
  try {
    await setGroupMembersApi(groupId, { tags: remaining });
    emit('tagsChanged');
  } catch (e: any) {
    ElMessage.error(e?.message || '操作失败');
  }
}

async function addTagToGroup(groupId: number, tagName: string) {
  const group = props.tagsData?.groups.find((g) => g.id === groupId);
  if (!group) return;
  const current = group.tags.map((t) => t.tag);
  if (current.includes(tagName)) return;
  try {
    await setGroupMembersApi(groupId, { tags: [...current, tagName] });
    emit('tagsChanged');
  } catch (e: any) {
    ElMessage.error(e?.message || '操作失败');
  } finally {
    drawerAddingGroupId.value = null;
    drawerAddingTag.value = '';
  }
}
</script>

<template>
  <ElDrawer
    :model-value="visible"
    title="管理标签分组"
    :size="isMobile ? '100%' : '440px'"
    direction="rtl"
    @update:model-value="(v: boolean) => emit('update:visible', v)"
  >
    <!-- 新建分组 -->
    <div class="drawer-section">
      <div class="drawer-row">
        <ElInput
          v-model="newGroupName"
          placeholder="新分组名称..."
          size="default"
          @keyup.enter="createGroup"
        >
          <template #prefix>
            <ElIcon><FolderOpen /></ElIcon>
          </template>
        </ElInput>
        <ElButton type="primary" :icon="Plus" @click="createGroup">创建</ElButton>
      </div>
    </div>

    <!-- 分组列表 -->
    <div
      v-for="group in tagsData?.groups ?? []"
      :key="group.id"
      class="drawer-group"
    >
      <div class="drawer-group-header">
        <template v-if="renamingGroupId === group.id">
          <ElInput
            v-model="renamingGroupName"
            size="small"
            class="flex-1"
            @keyup.enter="saveRenameGroup(group.id)"
            @blur="saveRenameGroup(group.id)"
          />
        </template>
        <template v-else>
          <span class="drawer-group-name">
            <ElIcon :size="16"><FolderOpen /></ElIcon>
            {{ group.name }}
          </span>
        </template>
        <div class="drawer-group-actions">
          <ElButton size="small" text :icon="Pencil" @click="startRenameGroup(group)" />
          <ElPopconfirm title="确认删除此分组？" @confirm="deleteGroup(group.id)">
            <template #reference>
              <ElButton size="small" text type="danger" :icon="Trash2" />
            </template>
          </ElPopconfirm>
        </div>
      </div>
      <div class="drawer-group-tags">
        <ElTag
          v-for="t in group.tags"
          :key="t.tag"
          closable
          effect="light"
          type="primary"
          round
          @close="removeTagFromGroup(group.id, t.tag)"
        >
          {{ t.tag }}
          <span class="drawer-tag-count">({{ t.count }})</span>
        </ElTag>
        <!-- 添加标签到分组 -->
        <template v-if="drawerAddingGroupId === group.id">
          <ElSelect
            v-model="drawerAddingTag"
            filterable
            placeholder="选择标签..."
            size="small"
            class="drawer-add-select"
            @change="(v: string) => addTagToGroup(group.id, v)"
          >
            <ElOption
              v-for="ut in tagsData?.ungrouped_tags ?? []"
              :key="ut.tag"
              :label="`${ut.tag} (${ut.count})`"
              :value="ut.tag"
            />
          </ElSelect>
        </template>
        <ElButton
          v-else
          size="small"
          text
          type="primary"
          :icon="Plus"
          @click="drawerAddingGroupId = group.id"
        >
          添加标签
        </ElButton>
      </div>
    </div>

    <!-- 未分组标签 -->
    <template v-if="tagsData?.ungrouped_tags.length">
      <div class="drawer-divider">未分组标签</div>
      <div class="drawer-ungrouped">
        <ElTag
          v-for="ut in tagsData.ungrouped_tags"
          :key="ut.tag"
          effect="plain"
          type="info"
          round
        >
          {{ ut.tag }}
          <span class="drawer-tag-count">({{ ut.count }})</span>
        </ElTag>
      </div>
    </template>
  </ElDrawer>
</template>

<style scoped>
.drawer-section {
  margin-bottom: 20px;
}
.drawer-row {
  display: flex;
  gap: 10px;
}
.drawer-group {
  margin-bottom: 16px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  padding: 14px 16px;
  background-color: var(--el-bg-color);
}
.drawer-group-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.drawer-group-name {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  font-size: 14px;
  color: var(--el-text-color-primary);
}
.drawer-group-actions {
  display: flex;
  gap: 2px;
}
.drawer-group-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}
.drawer-tag-count {
  font-size: 11px;
  opacity: 0.65;
  margin-left: 2px;
}
.drawer-add-select {
  min-width: 150px;
}
.drawer-divider {
  font-size: 12px;
  font-weight: 500;
  color: var(--el-text-color-secondary);
  padding: 12px 0 6px;
  border-top: 1px solid var(--el-border-color-extra-light);
  margin-top: 12px;
}
.drawer-ungrouped {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 6px 0;
}
</style>

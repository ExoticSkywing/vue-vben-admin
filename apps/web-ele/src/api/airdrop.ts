/**
 * 空投机管理 API
 */
import { requestClient } from '#/api/request';

export namespace AirdropApi {
  export interface Pack {
    pack_id: string;
    admin_id: number;
    item_count: number;
    name: string | null;
    tags: string | null;
    protect_content: boolean | null;
    max_claims_per_user: number | null;
    auto_delete_seconds: number | null;
    created_at: string | null;
    updated_at: string | null;
    deleted_at: string | null;
    share_link: string;
    auto_code: string | null;
    codes: PackCode[];
  }

  export interface Settings {
    protect_content: boolean;
    max_claims_per_user: number;
    auto_delete_time: number;
  }

  export interface BatchResult {
    affected: number;
    channel_deleted?: number;
  }

  export interface PackCode {
    id: number;
    code: string;
    code_type: 'auto' | 'custom';
    is_active: boolean | number;
    use_count: number;
    max_uses: number;
    expires_at: string | null;
    created_at: string | null;
  }

  export interface PackListResult {
    items: Pack[];
    total: number;
    page: number;
    page_size: number;
  }

  export interface IdentityResult {
    wp_openid: string | null;
    tg_user_id: number | null;
    is_super: boolean;
    bound: boolean;
  }

  export interface TagItem {
    tag: string;
    count: number;
  }

  export interface TagGroup {
    id: number;
    name: string;
    sort_order: number;
    tags: TagItem[];
  }

  export interface TagsResult {
    groups: TagGroup[];
    ungrouped_tags: TagItem[];
    untagged_count: number;
    total: number;
  }
}

/** 检查身份绑定状态 */
export async function checkIdentityApi() {
  return requestClient.get<AirdropApi.IdentityResult>('/airdrop/identity');
}

/** 列出空投包（支持搜索/分页/标签筛选/分组筛选/回收站） */
export async function listPacksApi(params: {
  search?: string;
  tag?: string;
  group_id?: number;
  page?: number;
  page_size?: number;
  deleted?: boolean;
}) {
  return requestClient.get<AirdropApi.PackListResult>('/airdrop/packs', {
    params,
  });
}

/** 获取空投包详情 */
export async function getPackDetailApi(packId: string) {
  return requestClient.get<AirdropApi.Pack>(`/airdrop/packs/${packId}`);
}

/** 编辑空投包元数据 */
export async function updatePackApi(
  packId: string,
  data: {
    name?: string;
    tags?: string;
    protect_content?: string;
    max_claims_per_user?: string;
    auto_delete_seconds?: string;
  },
) {
  return requestClient.put(`/airdrop/packs/${packId}`, data);
}

/** 删除空投包（移入回收站） */
export async function deletePackApi(packId: string) {
  return requestClient.delete(`/airdrop/packs/${packId}`);
}

/** 批量删除（移入回收站） */
export async function batchDeletePacksApi(packIds: string[]) {
  return requestClient.post<AirdropApi.BatchResult>(
    '/airdrop/packs/batch-delete',
    { pack_ids: packIds },
  );
}

/** 批量恢复（从回收站移出） */
export async function batchRestorePacksApi(packIds: string[]) {
  return requestClient.post<AirdropApi.BatchResult>(
    '/airdrop/packs/batch-restore',
    { pack_ids: packIds },
  );
}

/** 彻底删除（物理删除，可选清理频道消息） */
export async function batchPurgePacksApi(
  packIds: string[],
  cleanChannel: boolean = false,
) {
  return requestClient.post<AirdropApi.BatchResult>(
    '/airdrop/packs/batch-purge',
    { pack_ids: packIds, clean_channel: cleanChannel },
  );
}

/** 生成分享链接 */
export async function getPackLinkApi(packId: string) {
  return requestClient.get<{ share_link: string; pack_id: string }>(
    `/airdrop/packs/${packId}/link`,
  );
}

/** 新增自定义口令 */
export async function createCodeApi(
  packId: string,
  data: { code: string; max_uses?: number; expires_at?: string },
) {
  return requestClient.post(`/airdrop/packs/${packId}/codes`, data);
}

/** 编辑口令状态 */
export async function updateCodeApi(
  codeId: number,
  data: { is_active?: boolean },
) {
  return requestClient.put(`/airdrop/codes/${codeId}`, data);
}

/** 获取标签列表（含分组、计数） */
export async function getTagsApi() {
  return requestClient.get<AirdropApi.TagsResult>('/airdrop/tags');
}

/** 创建标签分组 */
export async function createTagGroupApi(data: { group_name: string }) {
  return requestClient.post<{ id: number }>('/airdrop/tag-groups', data);
}

/** 更新标签分组 */
export async function updateTagGroupApi(
  groupId: number,
  data: { group_name?: string; sort_order?: number },
) {
  return requestClient.put(`/airdrop/tag-groups/${groupId}`, data);
}

/** 删除标签分组 */
export async function deleteTagGroupApi(groupId: number) {
  return requestClient.delete(`/airdrop/tag-groups/${groupId}`);
}

/** 设置分组内标签列表 */
export async function setGroupMembersApi(
  groupId: number,
  data: { tags: string[] },
) {
  return requestClient.put(`/airdrop/tag-groups/${groupId}/members`, data);
}

/** 获取全局设置 */
export async function getSettingsApi() {
  return requestClient.get<AirdropApi.Settings>('/airdrop/settings');
}

/** 更新全局设置 */
export async function updateSettingsApi(data: {
  protect_content?: boolean;
  max_claims_per_user?: number;
  auto_delete_time?: number;
}) {
  return requestClient.put('/airdrop/settings', data);
}

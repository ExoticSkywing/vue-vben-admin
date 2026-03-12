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
    created_at: string | null;
    updated_at: string | null;
    share_link: string;
    auto_code: string | null;
    codes: PackCode[];
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
}

/** 检查身份绑定状态 */
export async function checkIdentityApi() {
  return requestClient.get<AirdropApi.IdentityResult>('/airdrop/identity');
}

/** 列出空投包（支持搜索/分页） */
export async function listPacksApi(params: {
  search?: string;
  page?: number;
  page_size?: number;
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
  data: { name?: string; tags?: string },
) {
  return requestClient.put(`/airdrop/packs/${packId}`, data);
}

/** 删除空投包 */
export async function deletePackApi(packId: string) {
  return requestClient.delete(`/airdrop/packs/${packId}`);
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

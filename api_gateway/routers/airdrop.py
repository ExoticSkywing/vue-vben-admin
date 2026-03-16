"""
空投机管理路由模块
提供资源包的检索、元数据编辑、口令管理、分享链接生成等 API。
核心聚焦：海量空投包中立即检索到目标 URL 并复制走人。

身份解析：完全从 JWT 取 tg_uid，零 DB 查询。
数据访问：通过空投机内部 API（精灵模式），不直连数据库。
"""

import hashlib
import logging
import httpx
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Request, Query, Body
from pydantic import BaseModel
from core.config import settings
from core.security import verify_token

logger = logging.getLogger(__name__)

router = APIRouter()


# ─── 空投机内部 API 调用工具（精灵模式） ───

def _make_sign(tg_uid: int) -> str:
    """生成签名: md5(str(tg_uid) + API_KEY)"""
    return hashlib.md5((str(tg_uid) + settings.AIRDROP_API_KEY).encode()).hexdigest()


async def _call_airdrop(
    method: str,
    path: str,
    tg_uid: int,
    params: dict = None,
    json_body: dict = None,
) -> dict:
    """调用空投机内部 API"""
    sign = _make_sign(tg_uid)
    headers = {"X-Sign": sign}
    url = f"{settings.AIRDROP_API_BASE}{path}"

    async with httpx.AsyncClient(timeout=15.0) as client:
        if method == "GET":
            resp = await client.get(url, params=params, headers=headers)
        elif method == "POST":
            resp = await client.post(url, json=json_body, headers=headers)
        elif method == "PUT":
            resp = await client.put(url, json=json_body, headers=headers)
        elif method == "DELETE":
            resp = await client.delete(url, params=params, headers=headers)
        else:
            raise ValueError(f"Unsupported method: {method}")

    if resp.status_code >= 400:
        detail = "内部服务错误"
        try:
            detail = resp.json().get("detail", detail)
        except Exception:
            pass
        raise HTTPException(status_code=resp.status_code, detail=detail)

    return resp.json()


# ─── 身份解析（纯 JWT，零 DB 查询） ───

def _get_current_user(request: Request) -> dict:
    """
    从 JWT 中直接解析用户身份，零 DB 查询。
    JWT 在登录时已包含 tg_uid / is_super / name 等全部信息。
    返回 {"wp_openid": str, "tg_user_id": int|None, "is_super": bool}
    """
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "").strip() if auth_header else ""

    if not token:
        raise HTTPException(status_code=401, detail="未登录")

    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")

    sub = payload.get("sub", "")
    wp_openid = sub.replace("wp_", "", 1) if sub.startswith("wp_") else None
    tg_user_id = payload.get("tg_uid")  # 登录时已从 WP usermeta 解析
    is_super = payload.get("is_super", False)

    logger.info(f"[identity] sub={sub!r}, tg_uid={tg_user_id!r}, is_super={is_super}")

    return {
        "wp_openid": wp_openid,
        "tg_user_id": tg_user_id,
        "is_super": is_super,
    }


def _require_tg_uid(user: dict) -> int:
    """从用户身份中提取 tg_uid，未绑定则抛 403"""
    tg_uid = user["tg_user_id"]
    if not tg_uid:
        raise HTTPException(
            status_code=403,
            detail="请先在小芽精灵中发送 /bind 绑定站点账号后使用",
        )
    return tg_uid


# ─── Pydantic 模型 ───

class PackUpdateRequest(BaseModel):
    name: Optional[str] = None
    tags: Optional[str] = None


class CodeCreateRequest(BaseModel):
    code: str
    max_uses: int = 0
    expires_at: Optional[str] = None


class CodeUpdateRequest(BaseModel):
    is_active: Optional[bool] = None


class TagGroupCreateRequest(BaseModel):
    group_name: str


class TagGroupUpdateRequest(BaseModel):
    group_name: Optional[str] = None
    sort_order: Optional[int] = None


class TagGroupMembersRequest(BaseModel):
    tags: List[str]


class BatchPacksRequest(BaseModel):
    pack_ids: List[str]
    clean_channel: bool = False


# ═══════════════════════════════════════════════════
# API 路由 — 全部转发到空投机内部 API
# ═══════════════════════════════════════════════════

@router.get("/packs")
async def list_packs(
    request: Request,
    search: str = Query("", description="搜索包名、标签、口令"),
    tag: str = Query("", description="筛选标签，__untagged__ 表示无标签"),
    group_id: int = Query(0, description="筛选标签分组 ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    deleted: bool = Query(False, description="是否查看回收站"),
):
    """列出空投包（支持搜索/分页/标签筛选/分组筛选/回收站）"""
    user = _get_current_user(request)
    tg_uid = _require_tg_uid(user)

    return await _call_airdrop("GET", "/api/packs", tg_uid, params={
        "tg_uid": tg_uid,
        "is_super": user["is_super"],
        "search": search,
        "tag": tag,
        "group_id": group_id,
        "page": page,
        "page_size": page_size,
        "deleted": deleted,
    })


@router.get("/packs/{pack_id}")
async def get_pack_detail(request: Request, pack_id: str):
    """空投包详情"""
    user = _get_current_user(request)
    tg_uid = _require_tg_uid(user)

    return await _call_airdrop("GET", f"/api/packs/{pack_id}", tg_uid, params={
        "tg_uid": tg_uid,
        "is_super": user["is_super"],
    })


@router.put("/packs/{pack_id}")
async def update_pack(request: Request, pack_id: str, body: PackUpdateRequest):
    """编辑空投包元数据（name, tags）"""
    user = _get_current_user(request)
    tg_uid = _require_tg_uid(user)

    return await _call_airdrop("PUT", f"/api/packs/{pack_id}", tg_uid, json_body={
        "tg_uid": tg_uid,
        "is_super": user["is_super"],
        "name": body.name,
        "tags": body.tags,
    })


@router.delete("/packs/{pack_id}")
async def delete_pack(request: Request, pack_id: str):
    """删除空投包（移入回收站）"""
    user = _get_current_user(request)
    tg_uid = _require_tg_uid(user)

    return await _call_airdrop("DELETE", f"/api/packs/{pack_id}", tg_uid, params={
        "tg_uid": tg_uid,
        "is_super": user["is_super"],
    })


# ─── 批量操作 ───

@router.post("/packs/batch-delete")
async def batch_delete(request: Request, body: BatchPacksRequest):
    """批量删除（移入回收站）"""
    user = _get_current_user(request)
    tg_uid = _require_tg_uid(user)

    return await _call_airdrop("POST", "/api/packs/batch-delete", tg_uid, json_body={
        "tg_uid": tg_uid,
        "is_super": user["is_super"],
        "pack_ids": body.pack_ids,
    })


@router.post("/packs/batch-restore")
async def batch_restore(request: Request, body: BatchPacksRequest):
    """批量恢复（从回收站移出）"""
    user = _get_current_user(request)
    tg_uid = _require_tg_uid(user)

    return await _call_airdrop("POST", "/api/packs/batch-restore", tg_uid, json_body={
        "tg_uid": tg_uid,
        "is_super": user["is_super"],
        "pack_ids": body.pack_ids,
    })


@router.post("/packs/batch-purge")
async def batch_purge(request: Request, body: BatchPacksRequest):
    """彻底删除（物理删除，可选清理频道消息）"""
    user = _get_current_user(request)
    tg_uid = _require_tg_uid(user)

    return await _call_airdrop("POST", "/api/packs/batch-purge", tg_uid, json_body={
        "tg_uid": tg_uid,
        "is_super": user["is_super"],
        "pack_ids": body.pack_ids,
        "clean_channel": body.clean_channel,
    })


@router.get("/packs/{pack_id}/link")
async def get_pack_link(request: Request, pack_id: str):
    """生成分享链接"""
    user = _get_current_user(request)
    tg_uid = _require_tg_uid(user)

    return await _call_airdrop("GET", f"/api/packs/{pack_id}/link", tg_uid, params={
        "tg_uid": tg_uid,
        "is_super": user["is_super"],
    })


# ─── 口令管理 ───

@router.post("/packs/{pack_id}/codes")
async def create_code(request: Request, pack_id: str, body: CodeCreateRequest):
    """新增自定义口令"""
    user = _get_current_user(request)
    tg_uid = _require_tg_uid(user)

    return await _call_airdrop("POST", f"/api/packs/{pack_id}/codes", tg_uid, json_body={
        "tg_uid": tg_uid,
        "is_super": user["is_super"],
        "code": body.code,
        "max_uses": body.max_uses,
        "expires_at": body.expires_at,
    })


@router.put("/codes/{code_id}")
async def update_code(request: Request, code_id: int, body: CodeUpdateRequest):
    """编辑口令状态（启用/禁用）"""
    user = _get_current_user(request)
    tg_uid = _require_tg_uid(user)

    return await _call_airdrop("PUT", f"/api/codes/{code_id}", tg_uid, json_body={
        "tg_uid": tg_uid,
        "is_super": user["is_super"],
        "is_active": body.is_active,
    })


# ─── 标签聚合 + 分组管理 ───

@router.get("/tags")
async def get_tags(request: Request):
    """获取标签列表（含分组、计数），侧边栏导航数据源"""
    user = _get_current_user(request)
    tg_uid = _require_tg_uid(user)

    return await _call_airdrop("GET", "/api/tags", tg_uid, params={
        "tg_uid": tg_uid,
        "is_super": user["is_super"],
    })


@router.post("/tag-groups")
async def create_tag_group(request: Request, body: TagGroupCreateRequest):
    """创建标签分组"""
    user = _get_current_user(request)
    tg_uid = _require_tg_uid(user)

    return await _call_airdrop("POST", "/api/tag-groups", tg_uid, json_body={
        "tg_uid": tg_uid,
        "group_name": body.group_name,
    })


@router.put("/tag-groups/{group_id}")
async def update_tag_group(request: Request, group_id: int, body: TagGroupUpdateRequest):
    """重命名/排序标签分组"""
    user = _get_current_user(request)
    tg_uid = _require_tg_uid(user)

    return await _call_airdrop("PUT", f"/api/tag-groups/{group_id}", tg_uid, json_body={
        "tg_uid": tg_uid,
        "group_name": body.group_name,
        "sort_order": body.sort_order,
    })


@router.delete("/tag-groups/{group_id}")
async def delete_tag_group(request: Request, group_id: int):
    """删除标签分组（标签回到未分组）"""
    user = _get_current_user(request)
    tg_uid = _require_tg_uid(user)

    return await _call_airdrop("DELETE", f"/api/tag-groups/{group_id}", tg_uid, params={
        "tg_uid": tg_uid,
    })


@router.put("/tag-groups/{group_id}/members")
async def set_group_members(request: Request, group_id: int, body: TagGroupMembersRequest):
    """设置分组内标签列表（全量替换）"""
    user = _get_current_user(request)
    tg_uid = _require_tg_uid(user)

    return await _call_airdrop("PUT", f"/api/tag-groups/{group_id}/members", tg_uid, json_body={
        "tg_uid": tg_uid,
        "tags": body.tags,
    })


# ─── 身份状态检查 ───

@router.get("/identity")
async def check_identity(request: Request):
    """检查当前用户的 TG 身份绑定状态"""
    user = _get_current_user(request)
    return {
        "code": 0,
        "data": {
            "wp_openid": user["wp_openid"],
            "tg_user_id": user["tg_user_id"],
            "is_super": user["is_super"],
            "bound": user["tg_user_id"] is not None,
        },
        "message": "ok",
    }

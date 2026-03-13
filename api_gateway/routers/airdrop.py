"""
空投机管理路由模块
提供资源包的检索、元数据编辑、口令管理、分享链接生成等 API。
核心聚焦：海量空投包中立即检索到目标 URL 并复制走人。

身份解析：完全从 JWT 取 tg_uid，零 DB 查询。
tg_uid 在 OAuth 登录时由 auth.py 一次性从 WP usermeta(_xingxy_telegram_uid) 解析。
"""

import base64
import logging
import httpx
import pymysql
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Request, Query, Body
from pydantic import BaseModel
from core.config import settings
from core.security import verify_token

logger = logging.getLogger(__name__)

router = APIRouter()

# ─── 缓存 Bot username（启动后首次请求时获取） ───
_bot_username_cache: Optional[str] = None


async def _get_bot_username() -> str:
    """动态获取空投机 Bot 的 username（缓存）"""
    global _bot_username_cache
    if _bot_username_cache:
        return _bot_username_cache

    if not settings.AIRDROP_BOT_TOKEN:
        raise HTTPException(status_code=500, detail="AIRDROP_BOT_TOKEN 未配置")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"https://api.telegram.org/bot{settings.AIRDROP_BOT_TOKEN}/getMe"
            )
            data = resp.json()
            if data.get("ok"):
                _bot_username_cache = data["result"]["username"]
                logger.info(f"Bot username 已缓存: @{_bot_username_cache}")
                return _bot_username_cache
            else:
                raise HTTPException(status_code=500, detail=f"TG API 错误: {data}")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=500, detail=f"获取 Bot 信息失败: {e}")


# ─── DB 连接工具 ───

def _get_airdrop_conn():
    """获取空投机 MySQL 连接"""
    return pymysql.connect(
        host=settings.AIRDROP_DB_HOST,
        port=settings.AIRDROP_DB_PORT,
        user=settings.AIRDROP_DB_USER,
        password=settings.AIRDROP_DB_PASSWORD,
        database=settings.AIRDROP_DB_NAME,
        charset="utf8mb4",
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )


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


# ─── 链接生成工具 ───

def _encode_pack_link(pack_id: str) -> str:
    """生成 base64 编码的 pack 参数（与 Bot 的 encode 逻辑一致）"""
    raw = f"pack-{pack_id}"
    b64 = base64.urlsafe_b64encode(raw.encode("ascii")).decode("ascii").rstrip("=")
    return b64


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


# ═══════════════════════════════════════════════════
# API 路由
# ═══════════════════════════════════════════════════

@router.get("/packs")
async def list_packs(
    request: Request,
    search: str = Query("", description="搜索包名、标签、口令"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """列出空投包（支持搜索/分页），核心检索接口"""
    user = _get_current_user(request)
    tg_id = user["tg_user_id"]

    if not tg_id:
        raise HTTPException(
            status_code=403,
            detail="请先在小芽精灵中发送 /bind 绑定站点账号后使用",
        )

    conn = _get_airdrop_conn()
    try:
        with conn.cursor() as cur:
            # 构建查询条件
            conditions = ["rp.status = 'done'"]
            params = []

            # 权限过滤：超级管理员看所有，其他人只看自己的
            if not user["is_super"]:
                conditions.append("rp.admin_id = %s")
                params.append(tg_id)

            # 搜索：匹配包名、标签、口令
            if search.strip():
                search_term = f"%{search.strip()}%"
                conditions.append(
                    "(rp.name LIKE %s OR rp.tags LIKE %s OR rp.pack_id LIKE %s "
                    "OR EXISTS (SELECT 1 FROM pack_codes pc WHERE pc.pack_id = rp.pack_id AND pc.code LIKE %s))"
                )
                params.extend([search_term, search_term, search_term, search_term])

            where_clause = " AND ".join(conditions)

            # 总数
            cur.execute(f"SELECT COUNT(*) as total FROM resource_packs rp WHERE {where_clause}", params)
            total = cur.fetchone()["total"]

            # 分页查询
            offset = (page - 1) * page_size
            cur.execute(
                f"""
                SELECT rp.pack_id, rp.admin_id, rp.item_count, rp.name, rp.tags,
                       rp.created_at, rp.updated_at
                FROM resource_packs rp
                WHERE {where_clause}
                ORDER BY rp.created_at DESC
                LIMIT %s OFFSET %s
                """,
                params + [page_size, offset],
            )
            packs = cur.fetchall()

            # 批量获取每个包的口令
            if packs:
                pack_ids = [p["pack_id"] for p in packs]
                placeholders = ",".join(["%s"] * len(pack_ids))
                cur.execute(
                    f"SELECT pack_id, code, code_type, is_active, use_count, max_uses "
                    f"FROM pack_codes WHERE pack_id IN ({placeholders})",
                    pack_ids,
                )
                codes_rows = cur.fetchall()
                codes_map = {}
                for row in codes_rows:
                    codes_map.setdefault(row["pack_id"], []).append(row)
            else:
                codes_map = {}

            # 获取 bot username 用于生成链接
            bot_username = await _get_bot_username()

            # 组装结果
            results = []
            for p in packs:
                pid = p["pack_id"]
                b64 = _encode_pack_link(pid)
                codes = codes_map.get(pid, [])
                auto_code = next((c["code"] for c in codes if c["code_type"] == "auto"), None)

                results.append({
                    "pack_id": pid,
                    "admin_id": p["admin_id"],
                    "item_count": p["item_count"],
                    "name": p["name"],
                    "tags": p["tags"],
                    "created_at": str(p["created_at"]) if p["created_at"] else None,
                    "updated_at": str(p["updated_at"]) if p["updated_at"] else None,
                    "share_link": f"https://t.me/{bot_username}?start={b64}",
                    "auto_code": auto_code,
                    "codes": codes,
                })

            return {
                "code": 0,
                "data": {
                    "items": results,
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                },
                "message": "ok",
            }
    finally:
        conn.close()


@router.get("/packs/{pack_id}")
async def get_pack_detail(request: Request, pack_id: str):
    """空投包详情"""
    user = _get_current_user(request)
    tg_id = user["tg_user_id"]

    if not tg_id:
        raise HTTPException(status_code=403, detail="请先绑定站点账号")

    conn = _get_airdrop_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM resource_packs WHERE pack_id = %s AND status = 'done'",
                (pack_id,),
            )
            pack = cur.fetchone()
            if not pack:
                raise HTTPException(status_code=404, detail="空投包不存在")

            # 权限检查
            if not user["is_super"] and pack["admin_id"] != tg_id:
                raise HTTPException(status_code=403, detail="无权访问")

            # 获取口令列表
            cur.execute("SELECT * FROM pack_codes WHERE pack_id = %s", (pack_id,))
            codes = cur.fetchall()

            # 获取资源条目数
            cur.execute(
                "SELECT COUNT(*) as cnt FROM pack_items WHERE pack_id = %s",
                (pack_id,),
            )
            item_count = cur.fetchone()["cnt"]

            bot_username = await _get_bot_username()
            b64 = _encode_pack_link(pack_id)

            return {
                "code": 0,
                "data": {
                    "pack_id": pack["pack_id"],
                    "admin_id": pack["admin_id"],
                    "item_count": item_count,
                    "name": pack["name"],
                    "tags": pack["tags"],
                    "created_at": str(pack["created_at"]) if pack["created_at"] else None,
                    "updated_at": str(pack["updated_at"]) if pack["updated_at"] else None,
                    "share_link": f"https://t.me/{bot_username}?start={b64}",
                    "codes": [
                        {
                            "id": c["id"],
                            "code": c["code"],
                            "code_type": c["code_type"],
                            "is_active": c["is_active"],
                            "use_count": c["use_count"],
                            "max_uses": c["max_uses"],
                            "expires_at": str(c["expires_at"]) if c["expires_at"] else None,
                            "created_at": str(c["created_at"]) if c["created_at"] else None,
                        }
                        for c in codes
                    ],
                },
                "message": "ok",
            }
    finally:
        conn.close()


@router.put("/packs/{pack_id}")
async def update_pack(request: Request, pack_id: str, body: PackUpdateRequest):
    """编辑空投包元数据（name, tags）"""
    user = _get_current_user(request)
    tg_id = user["tg_user_id"]

    if not tg_id:
        raise HTTPException(status_code=403, detail="请先绑定站点账号")

    conn = _get_airdrop_conn()
    try:
        with conn.cursor() as cur:
            # 检查存在性和权限
            cur.execute("SELECT admin_id FROM resource_packs WHERE pack_id = %s", (pack_id,))
            pack = cur.fetchone()
            if not pack:
                raise HTTPException(status_code=404, detail="空投包不存在")
            if not user["is_super"] and pack["admin_id"] != tg_id:
                raise HTTPException(status_code=403, detail="无权编辑")

            # 构建更新
            updates = []
            params = []
            if body.name is not None:
                updates.append("name = %s")
                params.append(body.name)
            if body.tags is not None:
                updates.append("tags = %s")
                params.append(body.tags)

            if not updates:
                return {"code": 0, "message": "无需更新"}

            params.append(pack_id)
            cur.execute(
                f"UPDATE resource_packs SET {', '.join(updates)} WHERE pack_id = %s",
                params,
            )

            return {"code": 0, "message": "更新成功"}
    finally:
        conn.close()


@router.delete("/packs/{pack_id}")
async def delete_pack(request: Request, pack_id: str):
    """删除空投包"""
    user = _get_current_user(request)
    tg_id = user["tg_user_id"]

    if not tg_id:
        raise HTTPException(status_code=403, detail="请先绑定站点账号")

    conn = _get_airdrop_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT admin_id FROM resource_packs WHERE pack_id = %s", (pack_id,))
            pack = cur.fetchone()
            if not pack:
                raise HTTPException(status_code=404, detail="空投包不存在")
            if not user["is_super"] and pack["admin_id"] != tg_id:
                raise HTTPException(status_code=403, detail="无权删除")

            cur.execute("DELETE FROM pack_codes WHERE pack_id = %s", (pack_id,))
            cur.execute("DELETE FROM pack_items WHERE pack_id = %s", (pack_id,))
            cur.execute("DELETE FROM resource_packs WHERE pack_id = %s", (pack_id,))

            return {"code": 0, "message": "删除成功"}
    finally:
        conn.close()


@router.get("/packs/{pack_id}/link")
async def get_pack_link(request: Request, pack_id: str):
    """生成分享链接（纯计算）"""
    user = _get_current_user(request)
    tg_id = user["tg_user_id"]

    if not tg_id:
        raise HTTPException(status_code=403, detail="请先绑定站点账号")

    conn = _get_airdrop_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT admin_id FROM resource_packs WHERE pack_id = %s AND status = 'done'",
                (pack_id,),
            )
            pack = cur.fetchone()
            if not pack:
                raise HTTPException(status_code=404, detail="空投包不存在")
            if not user["is_super"] and pack["admin_id"] != tg_id:
                raise HTTPException(status_code=403, detail="无权访问")

        bot_username = await _get_bot_username()
        b64 = _encode_pack_link(pack_id)

        return {
            "code": 0,
            "data": {
                "share_link": f"https://t.me/{bot_username}?start={b64}",
                "pack_id": pack_id,
            },
            "message": "ok",
        }
    finally:
        conn.close()


# ─── 口令管理 ───

@router.post("/packs/{pack_id}/codes")
async def create_code(request: Request, pack_id: str, body: CodeCreateRequest):
    """新增自定义口令"""
    user = _get_current_user(request)
    tg_id = user["tg_user_id"]

    if not tg_id:
        raise HTTPException(status_code=403, detail="请先绑定站点账号")

    conn = _get_airdrop_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT admin_id FROM resource_packs WHERE pack_id = %s", (pack_id,))
            pack = cur.fetchone()
            if not pack:
                raise HTTPException(status_code=404, detail="空投包不存在")
            if not user["is_super"] and pack["admin_id"] != tg_id:
                raise HTTPException(status_code=403, detail="无权操作")

            # 检查口令是否已存在
            cur.execute("SELECT 1 FROM pack_codes WHERE code = %s", (body.code,))
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="口令已存在")

            cur.execute(
                "INSERT INTO pack_codes (pack_id, code, code_type, max_uses, expires_at) "
                "VALUES (%s, %s, 'custom', %s, %s)",
                (pack_id, body.code, body.max_uses, body.expires_at),
            )

            return {"code": 0, "message": "口令创建成功"}
    finally:
        conn.close()


@router.put("/codes/{code_id}")
async def update_code(request: Request, code_id: int, body: CodeUpdateRequest):
    """编辑口令状态（启用/禁用）"""
    user = _get_current_user(request)
    tg_id = user["tg_user_id"]

    if not tg_id:
        raise HTTPException(status_code=403, detail="请先绑定站点账号")

    conn = _get_airdrop_conn()
    try:
        with conn.cursor() as cur:
            # 查口令及其所属资源包
            cur.execute(
                "SELECT pc.pack_id, rp.admin_id FROM pack_codes pc "
                "JOIN resource_packs rp ON pc.pack_id = rp.pack_id "
                "WHERE pc.id = %s",
                (code_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="口令不存在")
            if not user["is_super"] and row["admin_id"] != tg_id:
                raise HTTPException(status_code=403, detail="无权操作")

            if body.is_active is not None:
                cur.execute(
                    "UPDATE pack_codes SET is_active = %s WHERE id = %s",
                    (1 if body.is_active else 0, code_id),
                )

            return {"code": 0, "message": "更新成功"}
    finally:
        conn.close()


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

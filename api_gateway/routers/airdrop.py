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


class TagGroupCreateRequest(BaseModel):
    group_name: str


class TagGroupUpdateRequest(BaseModel):
    group_name: Optional[str] = None
    sort_order: Optional[int] = None


class TagGroupMembersRequest(BaseModel):
    tags: List[str]


# ═══════════════════════════════════════════════════
# API 路由
# ═══════════════════════════════════════════════════

@router.get("/packs")
async def list_packs(
    request: Request,
    search: str = Query("", description="搜索包名、标签、口令"),
    tag: str = Query("", description="筛选标签，__untagged__ 表示无标签"),
    group_id: int = Query(0, description="筛选标签分组 ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """列出空投包（支持搜索/分页/标签筛选/分组筛选），核心检索接口"""
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

            # 标签筛选
            if tag.strip():
                if tag.strip() == "__untagged__":
                    conditions.append("(rp.tags IS NULL OR rp.tags = '')")
                else:
                    conditions.append("FIND_IN_SET(%s, rp.tags)")
                    params.append(tag.strip())

            # 分组筛选：查该组所有 tag_name，OR 拼接 FIND_IN_SET
            if group_id > 0 and not tag.strip():
                cur.execute(
                    "SELECT tag_name FROM tag_group_members WHERE group_id = %s",
                    (group_id,),
                )
                group_tags = [r["tag_name"] for r in cur.fetchall()]
                if group_tags:
                    tag_conditions = " OR ".join(["FIND_IN_SET(%s, rp.tags)"] * len(group_tags))
                    conditions.append(f"({tag_conditions})")
                    params.extend(group_tags)
                else:
                    conditions.append("0")

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


# ─── 标签聚合 + 分组管理 ───

@router.get("/tags")
async def get_tags(request: Request):
    """获取标签列表（含分组、计数），侧边栏导航数据源"""
    user = _get_current_user(request)
    tg_id = user["tg_user_id"]

    if not tg_id:
        raise HTTPException(status_code=403, detail="请先绑定站点账号")

    conn = _get_airdrop_conn()
    try:
        with conn.cursor() as cur:
            # 权限过滤条件
            owner_cond = ""
            owner_params = []
            if not user["is_super"]:
                owner_cond = "AND rp.admin_id = %s"
                owner_params = [tg_id]

            # 1. 获取所有标签及计数（从 resource_packs.tags 逗号分隔字段拆分）
            cur.execute(
                f"""
                SELECT TRIM(SUBSTRING_INDEX(SUBSTRING_INDEX(rp.tags, ',', numbers.n), ',', -1)) AS tag_name,
                       COUNT(*) AS cnt
                FROM resource_packs rp
                JOIN (
                    SELECT 1 AS n UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4
                    UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8
                    UNION ALL SELECT 9 UNION ALL SELECT 10
                ) numbers
                ON CHAR_LENGTH(rp.tags) - CHAR_LENGTH(REPLACE(rp.tags, ',', '')) >= numbers.n - 1
                WHERE rp.status = 'done'
                  AND rp.tags IS NOT NULL AND rp.tags != ''
                  {owner_cond}
                GROUP BY tag_name
                HAVING tag_name != ''
                ORDER BY cnt DESC
                """,
                owner_params,
            )
            all_tags = {row["tag_name"]: row["cnt"] for row in cur.fetchall()}

            # 2. 未分类数量（无标签的包）
            cur.execute(
                f"""
                SELECT COUNT(*) AS cnt FROM resource_packs rp
                WHERE rp.status = 'done' AND (rp.tags IS NULL OR rp.tags = '')
                {owner_cond}
                """,
                owner_params,
            )
            untagged_count = cur.fetchone()["cnt"]

            # 3. 总数
            cur.execute(
                f"SELECT COUNT(*) AS cnt FROM resource_packs rp WHERE rp.status = 'done' {owner_cond}",
                owner_params,
            )
            total = cur.fetchone()["cnt"]

            # 4. 获取用户的标签分组
            cur.execute(
                "SELECT id, group_name, sort_order FROM tag_groups WHERE owner_tg_id = %s ORDER BY sort_order, id",
                (tg_id,),
            )
            groups_rows = cur.fetchall()

            # 5. 获取所有分组成员
            group_ids = [g["id"] for g in groups_rows]
            grouped_tag_names = set()
            groups_result = []

            if group_ids:
                placeholders = ",".join(["%s"] * len(group_ids))
                cur.execute(
                    f"SELECT group_id, tag_name FROM tag_group_members WHERE group_id IN ({placeholders})",
                    group_ids,
                )
                members_rows = cur.fetchall()
                
                # 清理计数为0的标签（自动从分组中移除）
                tags_to_remove = []
                for m in members_rows:
                    if m["tag_name"] not in all_tags:
                        tags_to_remove.append((m["group_id"], m["tag_name"]))
                
                if tags_to_remove:
                    for group_id, tag_name in tags_to_remove:
                        cur.execute(
                            "DELETE FROM tag_group_members WHERE group_id = %s AND tag_name = %s",
                            (group_id, tag_name),
                        )
                
                # 构建分组结果（只包含计数>0的标签）
                members_map = {}
                for m in members_rows:
                    if m["tag_name"] in all_tags:  # 只保留有计数的标签
                        members_map.setdefault(m["group_id"], []).append(m["tag_name"])
                        grouped_tag_names.add(m["tag_name"])

                for g in groups_rows:
                    g_tags = members_map.get(g["id"], [])
                    groups_result.append({
                        "id": g["id"],
                        "name": g["group_name"],
                        "sort_order": g["sort_order"],
                        "tags": [
                            {"tag": t, "count": all_tags[t]}
                            for t in g_tags
                        ],
                    })
            else:
                for g in groups_rows:
                    groups_result.append({
                        "id": g["id"],
                        "name": g["group_name"],
                        "sort_order": g["sort_order"],
                        "tags": [],
                    })

            # 6. 未分组标签
            ungrouped_tags = [
                {"tag": t, "count": c}
                for t, c in all_tags.items()
                if t not in grouped_tag_names
            ]
            ungrouped_tags.sort(key=lambda x: x["count"], reverse=True)

            return {
                "code": 0,
                "data": {
                    "groups": groups_result,
                    "ungrouped_tags": ungrouped_tags,
                    "untagged_count": untagged_count,
                    "total": total,
                },
                "message": "ok",
            }
    finally:
        conn.close()


@router.post("/tag-groups")
async def create_tag_group(request: Request, body: TagGroupCreateRequest):
    """创建标签分组"""
    user = _get_current_user(request)
    tg_id = user["tg_user_id"]
    if not tg_id:
        raise HTTPException(status_code=403, detail="请先绑定站点账号")

    conn = _get_airdrop_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO tag_groups (owner_tg_id, group_name) VALUES (%s, %s)",
                (tg_id, body.group_name.strip()),
            )
            new_id = cur.lastrowid
            return {"code": 0, "data": {"id": new_id}, "message": "分组创建成功"}
    finally:
        conn.close()


@router.put("/tag-groups/{group_id}")
async def update_tag_group(request: Request, group_id: int, body: TagGroupUpdateRequest):
    """重命名/排序标签分组"""
    user = _get_current_user(request)
    tg_id = user["tg_user_id"]
    if not tg_id:
        raise HTTPException(status_code=403, detail="请先绑定站点账号")

    conn = _get_airdrop_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM tag_groups WHERE id = %s AND owner_tg_id = %s",
                (group_id, tg_id),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="分组不存在")

            updates, params = [], []
            if body.group_name is not None:
                updates.append("group_name = %s")
                params.append(body.group_name.strip())
            if body.sort_order is not None:
                updates.append("sort_order = %s")
                params.append(body.sort_order)

            if not updates:
                return {"code": 0, "message": "无需更新"}

            params.append(group_id)
            cur.execute(
                f"UPDATE tag_groups SET {', '.join(updates)} WHERE id = %s",
                params,
            )
            return {"code": 0, "message": "分组更新成功"}
    finally:
        conn.close()


@router.delete("/tag-groups/{group_id}")
async def delete_tag_group(request: Request, group_id: int):
    """删除标签分组（标签回到未分组）"""
    user = _get_current_user(request)
    tg_id = user["tg_user_id"]
    if not tg_id:
        raise HTTPException(status_code=403, detail="请先绑定站点账号")

    conn = _get_airdrop_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM tag_groups WHERE id = %s AND owner_tg_id = %s",
                (group_id, tg_id),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="分组不存在")

            cur.execute("DELETE FROM tag_group_members WHERE group_id = %s", (group_id,))
            cur.execute("DELETE FROM tag_groups WHERE id = %s", (group_id,))

            return {"code": 0, "message": "分组已删除"}
    finally:
        conn.close()


@router.put("/tag-groups/{group_id}/members")
async def set_group_members(request: Request, group_id: int, body: TagGroupMembersRequest):
    """设置分组内标签列表（全量替换）"""
    user = _get_current_user(request)
    tg_id = user["tg_user_id"]
    if not tg_id:
        raise HTTPException(status_code=403, detail="请先绑定站点账号")

    conn = _get_airdrop_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM tag_groups WHERE id = %s AND owner_tg_id = %s",
                (group_id, tg_id),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="分组不存在")

            # 先从其他分组中移除这些标签（一个标签只属于一个组）
            if body.tags:
                tag_placeholders = ",".join(["%s"] * len(body.tags))
                cur.execute(
                    f"DELETE FROM tag_group_members WHERE tag_name IN ({tag_placeholders})",
                    body.tags,
                )

            # 清空当前分组
            cur.execute("DELETE FROM tag_group_members WHERE group_id = %s", (group_id,))

            # 重新插入
            if body.tags:
                values = [(group_id, t.strip()) for t in body.tags if t.strip()]
                if values:
                    cur.executemany(
                        "INSERT INTO tag_group_members (group_id, tag_name) VALUES (%s, %s)",
                        values,
                    )

            return {"code": 0, "message": "分组标签已更新"}
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

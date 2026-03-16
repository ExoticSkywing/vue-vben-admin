"""
业务路由模板 — 精灵模式标准实现
TODO: 复制此文件，重命名为 routes_你的业务.py，替换所有 TODO 标记处。

端点编写三原则：
  1. 第一行永远是 verify_sign() — 未通过签名验证的请求立即 401
  2. tg_uid + is_super 是必传参数 — Gateway 从 JWT 解析后传入
  3. 响应格式统一 {"code": 0, "data": ..., "message": "ok"}
"""

import logging
import pymysql
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Header, Query
from pydantic import BaseModel
from config import (
    MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE,
    INTERNAL_API_KEY,
)
from auth import verify_sign

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_conn():
    """获取 MySQL 连接（短连接模式）"""
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        charset="utf8mb4",
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )


# ─── Pydantic 请求模型（POST/PUT 用） ───

class ItemCreateBody(BaseModel):
    tg_uid: int
    is_super: bool = False
    name: str
    # TODO: 添加你的业务字段


class ItemUpdateBody(BaseModel):
    tg_uid: int
    is_super: bool = False
    name: Optional[str] = None
    # TODO: 添加你的业务字段


# ═══════════════════════════════════════════════════
# GET 端点模板 — 列表查询
# ═══════════════════════════════════════════════════

@router.get("/api/items")
async def list_items(
    tg_uid: int = Query(...),
    is_super: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    x_sign: str = Header(..., alias="X-Sign"),
):
    verify_sign(tg_uid, x_sign, INTERNAL_API_KEY)

    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            conditions = ["1=1"]  # TODO: 替换为你的基础条件
            params = []

            if not is_super:
                conditions.append("owner_id = %s")
                params.append(tg_uid)

            where = " AND ".join(conditions)

            cur.execute(f"SELECT COUNT(*) AS total FROM your_table WHERE {where}", params)
            total = cur.fetchone()["total"]

            offset = (page - 1) * page_size
            cur.execute(
                f"SELECT * FROM your_table WHERE {where} ORDER BY id DESC LIMIT %s OFFSET %s",
                params + [page_size, offset],
            )
            items = cur.fetchall()

            return {
                "code": 0,
                "data": {
                    "items": items,
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                },
                "message": "ok",
            }
    finally:
        conn.close()


# ═══════════════════════════════════════════════════
# GET 端点模板 — 单条详情
# ═══════════════════════════════════════════════════

@router.get("/api/items/{item_id}")
async def get_item(
    item_id: int,
    tg_uid: int = Query(...),
    is_super: bool = Query(False),
    x_sign: str = Header(..., alias="X-Sign"),
):
    verify_sign(tg_uid, x_sign, INTERNAL_API_KEY)

    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM your_table WHERE id = %s", (item_id,))
            item = cur.fetchone()
            if not item:
                raise HTTPException(status_code=404, detail="记录不存在")
            if not is_super and item["owner_id"] != tg_uid:
                raise HTTPException(status_code=403, detail="无权访问")

            return {"code": 0, "data": item, "message": "ok"}
    finally:
        conn.close()


# ═══════════════════════════════════════════════════
# POST 端点模板 — 创建
# ═══════════════════════════════════════════════════

@router.post("/api/items")
async def create_item(
    body: ItemCreateBody,
    x_sign: str = Header(..., alias="X-Sign"),
):
    verify_sign(body.tg_uid, x_sign, INTERNAL_API_KEY)

    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO your_table (owner_id, name) VALUES (%s, %s)",
                (body.tg_uid, body.name),
            )
            new_id = cur.lastrowid
            return {"code": 0, "data": {"id": new_id}, "message": "创建成功"}
    finally:
        conn.close()


# ═══════════════════════════════════════════════════
# PUT 端点模板 — 更新
# ═══════════════════════════════════════════════════

@router.put("/api/items/{item_id}")
async def update_item(
    item_id: int,
    body: ItemUpdateBody,
    x_sign: str = Header(..., alias="X-Sign"),
):
    verify_sign(body.tg_uid, x_sign, INTERNAL_API_KEY)

    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT owner_id FROM your_table WHERE id = %s", (item_id,))
            item = cur.fetchone()
            if not item:
                raise HTTPException(status_code=404, detail="记录不存在")
            if not body.is_super and item["owner_id"] != body.tg_uid:
                raise HTTPException(status_code=403, detail="无权编辑")

            updates, params = [], []
            if body.name is not None:
                updates.append("name = %s")
                params.append(body.name)

            if not updates:
                return {"code": 0, "message": "无需更新"}

            params.append(item_id)
            cur.execute(f"UPDATE your_table SET {', '.join(updates)} WHERE id = %s", params)
            return {"code": 0, "message": "更新成功"}
    finally:
        conn.close()


# ═══════════════════════════════════════════════════
# DELETE 端点模板 — 删除
# ═══════════════════════════════════════════════════

@router.delete("/api/items/{item_id}")
async def delete_item(
    item_id: int,
    tg_uid: int = Query(...),
    is_super: bool = Query(False),
    x_sign: str = Header(..., alias="X-Sign"),
):
    verify_sign(tg_uid, x_sign, INTERNAL_API_KEY)

    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT owner_id FROM your_table WHERE id = %s", (item_id,))
            item = cur.fetchone()
            if not item:
                raise HTTPException(status_code=404, detail="记录不存在")
            if not is_super and item["owner_id"] != tg_uid:
                raise HTTPException(status_code=403, detail="无权删除")

            cur.execute("DELETE FROM your_table WHERE id = %s", (item_id,))
            return {"code": 0, "message": "删除成功"}
    finally:
        conn.close()

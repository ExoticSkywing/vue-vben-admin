"""
Gateway 路由模板 -- 精灵模式标准实现
TODO: 复制此文件到 api_gateway/routers/，重命名为你的业务名.py
      替换所有 TODO 标记处。

核心原则：Gateway 路由只做三件事：
  1. JWT 鉴权 -- 拿到 tg_uid + is_super
  2. 参数整理 -- 转发给 Bot 内部 API
  3. 返回结果 -- 前端无感知

零业务逻辑、零 DB 操作、零 import pymysql。
"""

import hashlib
import logging
import httpx
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel
from core.config import settings
from core.security import verify_token

logger = logging.getLogger(__name__)
router = APIRouter()


# --- 通用工具（每个 Bot 路由文件都需要这三个函数） ---

def _make_sign(tg_uid: int) -> str:
    """生成签名: md5(str(tg_uid) + API_KEY)"""
    # TODO: 替换为你在 config.py 中定义的 API_KEY
    return hashlib.md5((str(tg_uid) + settings.YOUR_BOT_API_KEY).encode()).hexdigest()


async def _call_bot(
    method: str,
    path: str,
    tg_uid: int,
    params: dict = None,
    json_body: dict = None,
) -> dict:
    """调用 Bot 内部 API"""
    sign = _make_sign(tg_uid)
    headers = {"X-Sign": sign}
    # TODO: 替换为你在 config.py 中定义的 API_BASE
    url = f"{settings.YOUR_BOT_API_BASE}{path}"

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


def _get_current_user(request: Request) -> dict:
    """从 JWT 中解析用户身份，零 DB 查询"""
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "").strip() if auth_header else ""
    if not token:
        raise HTTPException(status_code=401, detail="未登录")
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")

    sub = payload.get("sub", "")
    return {
        "wp_openid": sub.replace("wp_", "", 1) if sub.startswith("wp_") else None,
        "tg_user_id": payload.get("tg_uid"),
        "is_super": payload.get("is_super", False),
    }


def _require_tg_uid(user: dict) -> int:
    """从用户身份中提取 tg_uid，未绑定则抛 403"""
    tg_uid = user["tg_user_id"]
    if not tg_uid:
        raise HTTPException(status_code=403, detail="请先绑定站点账号")
    return tg_uid


# --- Pydantic 模型（按你的业务需求定义） ---

class ItemCreateRequest(BaseModel):
    name: str
    # TODO: 添加你的字段


class ItemUpdateRequest(BaseModel):
    name: Optional[str] = None
    # TODO: 添加你的字段


# === 端点（全部是薄薄的转发层） ===

@router.get("/items")
async def list_items(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    user = _get_current_user(request)
    tg_uid = _require_tg_uid(user)

    return await _call_bot("GET", "/api/items", tg_uid, params={
        "tg_uid": tg_uid,
        "is_super": user["is_super"],
        "page": page,
        "page_size": page_size,
    })


@router.get("/items/{item_id}")
async def get_item(request: Request, item_id: int):
    user = _get_current_user(request)
    tg_uid = _require_tg_uid(user)

    return await _call_bot("GET", f"/api/items/{item_id}", tg_uid, params={
        "tg_uid": tg_uid,
        "is_super": user["is_super"],
    })


@router.post("/items")
async def create_item(request: Request, body: ItemCreateRequest):
    user = _get_current_user(request)
    tg_uid = _require_tg_uid(user)

    return await _call_bot("POST", "/api/items", tg_uid, json_body={
        "tg_uid": tg_uid,
        "is_super": user["is_super"],
        "name": body.name,
        # TODO: 添加你的字段
    })


@router.put("/items/{item_id}")
async def update_item(request: Request, item_id: int, body: ItemUpdateRequest):
    user = _get_current_user(request)
    tg_uid = _require_tg_uid(user)

    return await _call_bot("PUT", f"/api/items/{item_id}", tg_uid, json_body={
        "tg_uid": tg_uid,
        "is_super": user["is_super"],
        "name": body.name,
        # TODO: 添加你的字段
    })


@router.delete("/items/{item_id}")
async def delete_item(request: Request, item_id: int):
    user = _get_current_user(request)
    tg_uid = _require_tg_uid(user)

    return await _call_bot("DELETE", f"/api/items/{item_id}", tg_uid, params={
        "tg_uid": tg_uid,
        "is_super": user["is_super"],
    })

"""
认证路由模块
实现了完整的 OAuth2 Authorization Code Grant 流程：
1. /api/auth/wp-login     — 组装授权 URL 并重定向至星小芽
2. /api/auth/wp-callback  — 接收 code 回调，换取 access_token，获取用户信息，签发本地 JWT
3. /api/auth/login         — Vben 标准账密登录（开发期兼容保留）
4. /api/auth/codes         — Vben 菜单权限码
5. /api/auth/logout        — 登出
6. /api/user/info          — 当前登录用户信息（从 JWT 解析，无状态）
"""

import logging
import secrets
import httpx
import pymysql
from urllib.parse import urlencode
from cachetools import TTLCache

from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import RedirectResponse
from core.config import settings
from core.security import create_access_token, verify_token

logger = logging.getLogger(__name__)

router_auth = APIRouter()
router_user = APIRouter()

# ──────────────────── 无状态化 ────────────────────
# state 防 CSRF：TTLCache 自动 10 分钟过期，最多 1000 条
_oauth_states: TTLCache = TTLCache(maxsize=1000, ttl=600)


def _resolve_tg_uid_from_wp(wp_uid: int) -> Optional[int]:
    """登录时一次性从 WP usermeta 查 _xingxy_telegram_uid"""
    if not wp_uid:
        return None
    try:
        conn = pymysql.connect(
            host=settings.WP_DB_HOST, port=settings.WP_DB_PORT,
            user=settings.WP_DB_USER, password=settings.WP_DB_PASSWORD,
            database=settings.WP_DB_NAME, charset="utf8mb4", autocommit=True,
            cursorclass=pymysql.cursors.DictCursor,
        )
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT meta_value FROM {settings.WP_TABLE_PREFIX}usermeta "
                    "WHERE user_id = %s AND meta_key = '_xingxy_telegram_uid' LIMIT 1",
                    (wp_uid,),
                )
                row = cur.fetchone()
                return int(row["meta_value"]) if row else None
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"[auth] 查询 WP usermeta _xingxy_telegram_uid 失败: {e}")
        return None


# ═══════════════════════════════════════════════════════════════
# 一、WordPress (Zibll) OAuth2 流程
# ═══════════════════════════════════════════════════════════════

@router_auth.get("/wp-login")
async def wp_login(redirect: str = Query(None, description="OAuth 完成后跳转的前端路径")):
    """
    步骤 1：组装星小芽 OAuth 授权页面 URL，302 跳转用户浏览器。
    用户会在星小芽主站看到授权确认页面。
    支持 redirect 参数，OAuth 完成后会带回前端目标页。
    """
    # 生成防 CSRF 的 state 随机串
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = {"redirect": redirect}

    # 按照 Zibll OAuth 开发文档拼装 authorize 请求参数
    params = {
        "response_type": "code",
        "client_id": settings.WP_OAUTH_CLIENT_ID,
        "redirect_uri": settings.WP_OAUTH_REDIRECT_URI,
        "state": state,
        "scope": settings.WP_OAUTH_SCOPE,
    }

    authorize_url = f"{settings.WP_OAUTH_AUTHORIZE_URL}?{urlencode(params)}"
    return RedirectResponse(url=authorize_url)


@router_auth.get("/wp-callback")
async def wp_callback(code: str = Query(None), state: str = Query(None)):
    """
    步骤 2：星小芽授权成功后浏览器带着 code 和 state 回调到这里。
    后端用 code + client_secret 去星小芽换取 access_token，
    再用 access_token 获取用户信息，最后签发本系统 JWT 并重定向到前端。
    """
    # ── 2.1 校验 state 防止 CSRF ──
    if not state or state not in _oauth_states:
        raise HTTPException(status_code=400, detail="无效的 state 参数，可能是 CSRF 攻击")
    state_data = _oauth_states.pop(state)
    oauth_redirect = state_data.get("redirect") if isinstance(state_data, dict) else None

    if not code:
        raise HTTPException(status_code=400, detail="缺少授权码 code")

    # ── 2.2 用 code 换取 access_token ──
    async with httpx.AsyncClient(timeout=15.0) as client:
        token_resp = await client.post(
            settings.WP_OAUTH_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": settings.WP_OAUTH_CLIENT_ID,
                "client_secret": settings.WP_OAUTH_CLIENT_SECRET,
                "code": code,
                "redirect_uri": settings.WP_OAUTH_REDIRECT_URI,
            },
        )

    if token_resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"星小芽换签失败: {token_resp.text}"
        )

    token_data = token_resp.json()
    wp_access_token = token_data.get("access_token")
    if not wp_access_token:
        raise HTTPException(status_code=502, detail="星小芽未返回 access_token")

    # ── 2.3 用 access_token 获取用户信息 + unionid（单次连接） ──
    async with httpx.AsyncClient(timeout=10.0) as client:
        user_resp = await client.get(
            settings.WP_OAUTH_USERINFO_URL,
            headers={"Authorization": f"Bearer {wp_access_token}"},
        )
        # 同时获取 unionid (WP user ID)
        wp_uid = None
        try:
            unionid_resp = await client.get(
                f"{settings.WP_OAUTH_BASE}/unionid",
                headers={"Authorization": f"Bearer {wp_access_token}"},
            )
            if unionid_resp.status_code == 200:
                wp_uid = unionid_resp.json().get("unionid")
        except Exception:
            pass  # unionid 获取失败不阻塞登录

    if user_resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"获取星小芽用户信息失败: {user_resp.text}"
        )

    wp_user = user_resp.json()
    userinfo = wp_user.get("userinfo", wp_user)

    openid = userinfo.get("openid", "")
    name = userinfo.get("name", "星小芽用户")
    avatar = userinfo.get("avatar", "")

    # ── 2.4 从 WP usermeta 解析 tg_uid（一次性桥接） ──
    tg_uid = None
    if wp_uid:
        tg_uid = _resolve_tg_uid_from_wp(int(wp_uid))

    is_super = tg_uid == settings.SUPER_ADMIN_TG_ID if tg_uid else False

    logger.info(
        f"[oauth] openid={openid!r}, name={name!r}, wp_uid={wp_uid!r}, "
        f"tg_uid={tg_uid!r}, is_super={is_super}"
    )

    # ── 2.5 签发自包含 JWT（无需服务端 session） ──
    jwt_sub = f"wp_{openid}" if openid else f"wp_{name}"
    extra = {
        "wp_uid": int(wp_uid) if wp_uid else None,
        "tg_uid": tg_uid,
        "is_super": is_super,
        "name": name,
        "avatar": avatar,
    }
    local_token = create_access_token(subject=jwt_sub, extra_claims=extra)

    # ── 2.6 重定向到前端，URL 中携带 accessToken ──
    # 根据前端路由模式选择 URL 格式：hash mode 需要 /#/ 前缀，history mode 不需要
    hash_prefix = "/#" if settings.frontend_hash_mode else ""
    redirect_param = f"&redirect={oauth_redirect}" if oauth_redirect else ""
    redirect_url = f"{settings.FRONTEND_URL}{hash_prefix}/auth/oauth-callback?accessToken={local_token}{redirect_param}"
    return RedirectResponse(url=redirect_url)


# ═══════════════════════════════════════════════════════════════
# 二、Vben 标准接口（保持兼容）
# ═══════════════════════════════════════════════════════════════

@router_auth.post("/login")
async def login(request: Request):
    """
    Vben 标准账密登录接口（开发期兼容保留）。
    生产环境下建议仅使用 OAuth 流程。
    """
    body = await request.json()
    username = body.get("username", "")

    if username == "admin":
        token = create_access_token(subject="admin_user_id")
        return {
            "code": 0,
            "data": {"accessToken": token},
            "message": "ok",
        }

    return {"code": 401, "message": "用户名或密码错误", "data": None}


@router_auth.get("/codes")
async def get_codes():
    """Vben 获取用户的权限标识码（控制菜单和按钮显隐）"""
    return {
        "code": 0,
        "data": ["AC_100100", "AC_100110", "AC_100120", "AC_100010"],
        "message": "ok",
    }


@router_user.get("/info")
async def get_userinfo(request: Request):
    """
    获取当前登录用户的信息。
    完全从 JWT 解析，无需服务端 session，Gateway 重启不影响。
    """
    # 从 Authorization header 中提取 token
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "").strip() if auth_header else ""

    if token:
        payload = verify_token(token)
        if payload:
            sub = payload.get("sub", "")
            name = payload.get("name", "")
            avatar = payload.get("avatar", "")
            # JWT 自包含用户信息 → 直接返回
            if name:
                return {
                    "code": 0,
                    "data": {
                        "userId": sub,
                        "username": name,
                        "realName": name,
                        "avatar": avatar,
                        "desc": "星小芽授权用户",
                        "roles": [{"roleName": "Super Admin", "value": "super"}],
                    },
                    "message": "ok",
                }

    # 兜底：返回默认管理员（兼容开发期 admin 账号登录）
    return {
        "code": 0,
        "data": {
            "userId": "1",
            "username": "admin",
            "realName": "Manyuzo Admin",
            "avatar": "https://avatars.githubusercontent.com/u/102008?v=4",
            "desc": "浪漫宇宙生态管理员",
            "roles": [{"roleName": "Super Admin", "value": "super"}],
        },
        "message": "ok",
    }


@router_auth.post("/logout")
async def logout():
    return {"code": 0, "message": "ok"}

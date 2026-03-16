# Nebuluxe 可迁移 Bot 服务接入范式指南

> **版本**：v1.0 — 2026-03-16
> **开拓实现**：小芽空投机（File-Sharing-Bot）— 第一个完成范式改造的服务
> **前置阅读**：[CENTER_FRONTEND_GUIDE.md](./CENTER_FRONTEND_GUIDE.md)（前端开发范式）
> **定位**：本文档面向所有需要**将 TG Bot 服务接入 Nebuluxe Center 管理后台**的开发者。无论是新增 Bot、迁移现有服务，还是理解系统架构，本文都是你的起点。

---

## 〇、为什么需要这个范式？

### 问题

Gateway 直连各 Bot 的 MySQL 数据库 → Bot 迁移时 Gateway 必须跟着改 DB 配置、开放端口、处理跨服务器安全问题。

```
❌ 改造前 — 紧耦合
Center 前端 → Gateway → Bot A 的 MySQL（直连）
                     → Bot B 的 MySQL（直连）
                     → Bot C 的 MySQL（直连）

每个 Bot 迁移 = Gateway 改配置 + 开放 3306 + SSL 隧道 + 运维噩梦
```

### 解法

每个 Bot 自带一个轻量内部 API 服务，Gateway 只做 JWT 鉴权 + HTTP 转发。

```
✅ 改造后 — 精灵模式
Center 前端 → Gateway (JWT) → Bot A 内部 API → Bot A 本地 MySQL
                            → Bot B 内部 API → Bot B 本地 MySQL
                            → Bot C 内部 API → Bot C 本地 MySQL

每个 Bot 迁移 = Gateway 改一行 URL，完事
```

### 范式命名：精灵模式

因为小芽精灵（tgbot-verify）是第一个实现内部 API 的服务，后续所有 Bot 都复用这套模式。

---

## 一、架构全景

### 1.1 不变的核心（万古不变三件套）

| 组件 | 位置 | 说明 |
|------|------|------|
| 星小芽站点 + DB | 主服务器 | WordPress Zibll，用户身份唯一源头 |
| Nebuluxe Center | 主服务器 | Vue3 前端 + FastAPI Gateway |
| 小芽精灵 | 主服务器 | TG 侧身份权威，所有 Bot 的绑定查询入口 |

### 1.2 可迁移的 Bot 服务

| 组件 | 当前位置 | 可迁移 | 内部 API |
|------|---------|--------|----------|
| 小芽空投机 | 主服务器 | ✅ | port 18690 |
| 未来 Bot X | 任意服务器 | ✅ | 按范式接入 |

### 1.3 通信协议

```
┌─────────────────────────────────────────────────────────┐
│                    Nebuluxe Center                       │
│  ┌──────────┐    ┌─────────────┐    ┌────────────────┐  │
│  │ Vue3 前端 │───→│ API Gateway │───→│ Bot 内部 API   │  │
│  │ (JWT)     │    │ (FastAPI)   │    │ (FastAPI)      │  │
│  └──────────┘    └─────────────┘    └────────────────┘  │
│                        │                    │            │
│                   JWT 鉴权            md5 签名认证       │
│                   用户身份            数据库操作          │
│                   httpx 转发          业务逻辑           │
└─────────────────────────────────────────────────────────┘
```

**分工原则**：
- **Gateway**：只做 JWT → 用户身份，然后转发。**零业务逻辑、零 DB 操作**。
- **Bot 内部 API**：负责所有 DB 操作、业务逻辑、Bot 特有功能（如生成分享链接）。
- **前端**：只和 Gateway 通信，完全不感知后端是直连 DB 还是转发 API。

---

## 二、签名认证协议

### 2.1 算法

```
sign = md5( str(tg_uid) + INTERNAL_API_KEY )
```

- **tg_uid**：当前操作用户的 Telegram User ID（从 Gateway JWT 解析）
- **INTERNAL_API_KEY**：Gateway 与 Bot 共享的密钥（环境变量配置）
- **传输方式**：HTTP Header `X-Sign`

### 2.2 为什么只签 tg_uid？

1. **简洁**：与精灵 `/api/check-bind` 签名协议完全一致，零学习成本
2. **充分**：内部 API 不对公网暴露（Nginx 反代 + 仅信任来源），签名只防未授权调用
3. **无状态**：不依赖时间戳或 nonce，不需要时钟同步

### 2.3 安全层级

```
第1层：Nginx — 仅反代，不直接暴露端口
第2层：HTTPS — 传输加密（迁移到外部服务器时）
第3层：md5签名 — 验证调用者持有 API_KEY
第4层：tg_uid 权限过滤 — Bot API 内部按用户过滤数据
```

---

## 三、接入一个新 Bot 的完整步骤

> 以下以接入一个假想的「小芽抽奖机」为例，完整演示从零到上线的全过程。

### Step 1：Bot 端 — 创建 internal_api 目录

```
YourBot/
├── internal_api/
│   ├── __init__.py          # 空文件
│   ├── auth.py              # 签名认证（直接复制）
│   ├── routes_xxx.py        # 你的业务路由
│   ├── main.py              # FastAPI 入口
│   └── requirements.txt
├── config.py                # 新增 INTERNAL_API_KEY, INTERNAL_API_PORT
├── database/
│   └── database.py          # 你已有的 DB 层
└── ...
```

### Step 2：Bot 端 — auth.py（直接复制，不用改）

```python
"""签名认证 — 精灵模式标准实现"""
import hashlib
from fastapi import HTTPException


def verify_sign(tg_uid: int, sign: str, api_key: str):
    expected = hashlib.md5((str(tg_uid) + api_key).encode()).hexdigest()
    if sign != expected:
        raise HTTPException(status_code=401, detail="Invalid signature")
```

### Step 3：Bot 端 — 编写业务路由

```python
"""routes_lottery.py — 抽奖机业务路由示例"""
import pymysql
from fastapi import APIRouter, HTTPException, Header, Query
from pydantic import BaseModel
from config import (
    MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE,
    INTERNAL_API_KEY,
)
from auth import verify_sign

router = APIRouter()


def _get_conn():
    return pymysql.connect(
        host=MYSQL_HOST, port=MYSQL_PORT,
        user=MYSQL_USER, password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        charset="utf8mb4", autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )


# ─── 标准端点模板 ───

@router.get("/api/lotteries")
async def list_lotteries(
    tg_uid: int = Query(...),
    is_super: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    x_sign: str = Header(..., alias="X-Sign"),
):
    # 1. 验签
    verify_sign(tg_uid, x_sign, INTERNAL_API_KEY)

    # 2. DB 操作
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            # ... 你的 SQL 查询 ...
            pass
        return {"code": 0, "data": {...}, "message": "ok"}
    finally:
        conn.close()
```

**端点编写三原则**：
1. **第一行永远是 `verify_sign()`** — 未通过签名验证的请求立即 401
2. **tg_uid + is_super 是必传参数** — Gateway 从 JWT 解析后传入，用于权限过滤
3. **响应格式统一 `{"code": 0, "data": ..., "message": "ok"}`** — 前端零适配

### Step 4：Bot 端 — main.py

```python
"""Bot 内部 API 入口"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from fastapi import FastAPI
from routes_lottery import router as lottery_router  # ← 换成你的路由

logging.basicConfig(level=logging.INFO, format="[%(asctime)s %(levelname)s] %(name)s - %(message)s")

app = FastAPI(title="小芽抽奖机内部 API")  # ← 换成你的服务名
app.include_router(lottery_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "lottery-internal-api"}  # ← 换成你的服务名


if __name__ == "__main__":
    import uvicorn
    from config import INTERNAL_API_PORT
    uvicorn.run("main:app", host="127.0.0.1", port=INTERNAL_API_PORT, log_level="info")
```

### Step 5：Bot 端 — config.py 新增两行

```python
# 内部 API（供 Gateway 调用）
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "你的密钥")
INTERNAL_API_PORT = int(os.environ.get("INTERNAL_API_PORT", "你的端口"))
```

**端口分配约定**：

| Bot 服务 | 端口 |
|---------|------|
| 小芽精灵 | 8443 |
| 小芽空投机 | 18690 |
| 下一个 Bot | 18691 |
| 再下一个 | 18692 |

### Step 6：Gateway 端 — config.py 新增

```python
# ─── 小芽抽奖机内部 API ───
LOTTERY_API_BASE: str = os.getenv("LOTTERY_API_BASE", "http://127.0.0.1:18691")
LOTTERY_API_KEY: str = os.getenv("LOTTERY_API_KEY", "你的密钥")
```

### Step 7：Gateway 端 — 新建路由文件

```python
"""lottery.py — 抽奖机管理路由（精灵模式：纯转发，零 DB）"""
import hashlib
import logging
import httpx
from fastapi import APIRouter, HTTPException, Request, Query
from core.config import settings
from core.security import verify_token

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── 通用工具（每个 Bot 路由文件都需要这三个函数） ───

def _make_sign(tg_uid: int) -> str:
    return hashlib.md5((str(tg_uid) + settings.LOTTERY_API_KEY).encode()).hexdigest()


async def _call_lottery(method: str, path: str, tg_uid: int,
                        params: dict = None, json_body: dict = None) -> dict:
    sign = _make_sign(tg_uid)
    headers = {"X-Sign": sign}
    url = f"{settings.LOTTERY_API_BASE}{path}"

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
    tg_uid = user["tg_user_id"]
    if not tg_uid:
        raise HTTPException(status_code=403, detail="请先绑定站点账号")
    return tg_uid


# ─── 业务端点（全部是薄薄的转发层） ───

@router.get("/lotteries")
async def list_lotteries(request: Request, page: int = Query(1, ge=1), page_size: int = Query(20)):
    user = _get_current_user(request)
    tg_uid = _require_tg_uid(user)

    return await _call_lottery("GET", "/api/lotteries", tg_uid, params={
        "tg_uid": tg_uid,
        "is_super": user["is_super"],
        "page": page,
        "page_size": page_size,
    })
```

### Step 8：Gateway 端 — 注册路由

在 `api_gateway/main.py` 中：

```python
from routers import lottery
app.include_router(lottery.router, prefix="/api/lottery", tags=["lottery"])
```

### Step 9：部署

```bash
# 1. 启动 Bot 内部 API
cd YourBot/internal_api
nohup python3 -m uvicorn main:app --host 127.0.0.1 --port 18691 > ../internal_api.log 2>&1 &

# 2. 验证健康检查
curl http://127.0.0.1:18691/health

# 3. 重启 Gateway
kill $(pgrep -f "uvicorn.*8555")
cd api_gateway
nohup python3 -m uvicorn main:app --host 127.0.0.1 --port 8555 > /dev/null 2>&1 &
```

### Step 10：前端页面

参照 [CENTER_FRONTEND_GUIDE.md](./CENTER_FRONTEND_GUIDE.md) 新增管理页面，API 层调用 Gateway 的 `/api/lottery/*` 端点即可。

---

## 四、迁移到其他服务器

当需要将 Bot 迁移到另一台服务器时：

### 4.1 新服务器操作

```bash
# 1. 部署 Bot 代码 + 数据库
# 2. 启动内部 API
cd YourBot/internal_api
nohup python3 -m uvicorn main:app --host 127.0.0.1 --port 18691 > ../internal_api.log 2>&1 &

# 3. 配置 Nginx（HTTPS 反代）
```

Nginx 模板：

```nginx
server {
    listen 443 ssl http2;
    server_name lottery-api.manyuzo.com;

    ssl_certificate     /path/to/fullchain.pem;
    ssl_certificate_key /path/to/privkey.pem;

    location /api {
        proxy_pass http://127.0.0.1:18691;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /health {
        proxy_pass http://127.0.0.1:18691;
    }
}
```

### 4.2 主服务器操作

```bash
# 只改一行环境变量
export LOTTERY_API_BASE="https://lottery-api.manyuzo.com"

# 重启 Gateway
kill $(pgrep -f "uvicorn.*8555")
cd api_gateway && nohup python3 -m uvicorn main:app --host 127.0.0.1 --port 8555 > /dev/null 2>&1 &
```

**前端零改动。用户无感知。**

---

## 五、已实现的服务参照

### 5.1 小芽空投机（标准范例 ⭐）

| 项 | 详情 |
|----|------|
| Bot 目录 | `File-Sharing-Bot/` |
| 内部 API | `File-Sharing-Bot/internal_api/` |
| 端口 | 18690 |
| Gateway 路由 | `api_gateway/routers/airdrop.py` |
| 端点数量 | 12 个（7 资源包 + 5 标签） |
| Gateway 代码量 | 325 行（改造前 822 行，减少 60%） |
| 前端改动 | 零 |

### 5.2 小芽精灵（原型参照）

| 项 | 详情 |
|----|------|
| Bot 目录 | `tgbot-verify/` |
| 内部 API | 嵌入 Bot 进程（aiohttp, port 8443） |
| 域名 | `xyjl.1yo.cc` |
| 端点 | `GET /api/check-bind`（身份权威） |
| 签名 | `md5(tg_uid + INTERNAL_API_KEY)` |

---

## 六、一图总览

```
新 TG Bot 接入清单
═══════════════════════════════════════════

Bot 端（4 个文件）
├── internal_api/auth.py        ← 复制，不改
├── internal_api/routes_xxx.py  ← 写你的业务
├── internal_api/main.py        ← 改服务名
└── config.py                   ← 加 2 行

Gateway 端（2 个改动）
├── core/config.py              ← 加 2 行
└── routers/xxx.py              ← 写转发层

前端（按需）
└── apps/web-ele/src/views/xxx/ ← 管理页面

部署
├── 启动 Bot 内部 API
├── 重启 Gateway
└── 迁移时只改 1 行 URL
```

---

## 七、FAQ

**Q: 为什么不用 gRPC 或消息队列？**
A: 内部 API 调用量不大（管理后台级别），HTTP + JSON 最简单、最容易调试、最低运维成本。等日活破万再考虑升级协议。

**Q: 签名只用 md5 安全吗？**
A: 签名只是「门禁卡」，不是加密。真正的安全来自 Nginx 反代（不暴露端口）+ HTTPS（传输加密）+ API_KEY 保密。对内部服务间通信，md5 足够。

**Q: Bot 挂了 Gateway 会怎样？**
A: httpx 有 15 秒超时，Bot API 无响应时 Gateway 返回 500。前端会显示错误提示。不会影响其他服务。

**Q: 能不能让多个 Bot 共用一个内部 API 服务？**
A: 技术上可以，但不建议。每个 Bot 独立 API = 独立部署 = 独立迁移 = 故障隔离。这是微服务的核心价值。

**Q: _get_current_user 能不能抽成公共模块？**
A: 可以，但目前只有几个路由文件，复制比抽象更清晰。等 Bot 超过 5 个再考虑抽取到 `core/auth_helpers.py`。

**Q: Bot 按钮跳转 Center 时，URL 要注意什么？**
A: **必须加 `#`，否则 hash 路由会错位**。常见错误：
```python
# ❌ 错误 — 缺少 #
url="https://center.manyuzo.com/airdrop/packs"
# 结果：所有路由变成 /airdrop/packs#/xxx

# ✅ 正确 — 标准 hash 路由
url="https://center.manyuzo.com/#/airdrop/packs"
# 结果：路由正常 /#/xxx
```
原因：缺少 `#` 会让浏览器把 `/airdrop/packs` 当成服务器路径，导致 Vue Router 的 base path 错位。

---

> 🌱 *本文档由小芽空投机 API 化改造实践总结而来。每一行代码都经过生产验证。*
> *愿后来者少踩坑，多造福。*

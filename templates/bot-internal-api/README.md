# Bot 内部 API 脚手架模板

> 精灵模式 — 可迁移 Bot 服务的标准接入模板

## 使用方法

```bash
# 1. 复制到你的 Bot 项目
cp -r templates/bot-internal-api/ /path/to/YourBot/internal_api/

# 2. 删除本 README 和 gateway 模板（它属于 Gateway 侧）
rm internal_api/README.md internal_api/gateway_router_template.py

# 3. 重命名 routes_example.py 为你的业务名
mv internal_api/routes_example.py internal_api/routes_yourservice.py

# 4. 全局搜索 TODO，逐个替换
grep -rn "TODO" internal_api/

# 5. 启动
cd internal_api && python3 -m uvicorn main:app --host 127.0.0.1 --port <端口>
```

## 文件说明

| 文件 | 用途 | 需要改？ |
|------|------|---------|
| `auth.py` | md5 签名认证 | **不改** |
| `main.py` | FastAPI 入口 | 改服务名 |
| `routes_example.py` | 业务路由模板（CRUD） | **重写** |
| `gateway_router_template.py` | Gateway 侧路由模板 | 复制到 Gateway |
| `requirements.txt` | Python 依赖 | 按需加 |

## 完整文档

详见 [BOT_SERVICE_PARADIGM.md](../../BOT_SERVICE_PARADIGM.md)

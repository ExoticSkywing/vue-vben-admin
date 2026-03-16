"""
Bot 内部 API 入口 — 精灵模式标准模板
使用方法：
    1. 复制整个 bot-internal-api/ 到你的 Bot 项目下，重命名为 internal_api/
    2. 修改下方 TODO 标记处
    3. cd internal_api && python3 -m uvicorn main:app --host 127.0.0.1 --port <你的端口>
"""

import sys
import os

# 将 Bot 根目录加入 Python 路径，以便 import config / database
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from fastapi import FastAPI

# TODO: 替换为你的业务路由模块
from routes_example import router as example_router

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s %(levelname)s] %(name)s - %(message)s",
)

app = FastAPI(
    title="TODO: 你的 Bot 内部 API",          # TODO: 改成你的服务名
    description="供 Nebuluxe Center API Gateway 调用的数据服务",
    version="1.0.0",
)

# TODO: 注册你的业务路由
app.include_router(example_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "TODO-internal-api"}  # TODO: 改成你的服务名


if __name__ == "__main__":
    import uvicorn
    from config import INTERNAL_API_PORT

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=INTERNAL_API_PORT,
        log_level="info",
    )

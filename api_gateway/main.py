from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import auth, airdrop
import uvicorn

app = FastAPI(
    title="Manyuzo Control Center API",
    description="浪漫宇宙统一管控后台接口网关",
    version="1.0.0"
)

# 前端开发环境的地址和生产环境的地址
origins = [
    "http://localhost:5777",
    "http://127.0.0.1:5777",
    "https://center.manyuzo.com",
    "http://center.manyuzo.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health_check():
    """网关健康检查"""
    return {"status": "ok", "message": "API Gateway is running"}

app.include_router(auth.router_auth, prefix="/api/auth", tags=["Authentication"])
app.include_router(auth.router_user, prefix="/api/user", tags=["User Info"])
app.include_router(airdrop.router, prefix="/api/airdrop", tags=["Airdrop Management"])

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8555, reload=True)

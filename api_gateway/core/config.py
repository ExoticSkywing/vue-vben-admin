import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # JWT 设置
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-super-secret-key-change-it-in-prod")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 天

    # ─── 星小芽 (WordPress Zibll OAuth) 配置 ───
    # 应用凭证
    WP_OAUTH_CLIENT_ID: str = os.getenv("WP_OAUTH_CLIENT_ID", "zo_mtyp66yphlz55g")
    WP_OAUTH_CLIENT_SECRET: str = os.getenv("WP_OAUTH_CLIENT_SECRET", "jYwWBCSdqPcBBjx7lmMvTa64G3HqUXWF")

    # Zibll OAuth REST API 端点（基于开发文档 Base URL 格式）
    WP_SITE_URL: str = "https://xingxy.manyuzo.com"
    WP_OAUTH_BASE: str = f"{WP_SITE_URL}/wp-json/zibll-oauth/v1"

    WP_OAUTH_AUTHORIZE_URL: str = f"{WP_OAUTH_BASE}/authorize"
    WP_OAUTH_TOKEN_URL: str = f"{WP_OAUTH_BASE}/token"
    WP_OAUTH_USERINFO_URL: str = f"{WP_OAUTH_BASE}/userinfo"

    # 本系统的回调接收地址（在星小芽后台配置的 redirect_uri 必须与此完全一致）
    WP_OAUTH_REDIRECT_URI: str = "https://center.manyuzo.com/api/auth/wp-callback"

    # Nebuluxe Center 前端地址
    # 有环境变量就用环境变量，没有就自动判断：FastAPI 绑定在 127.0.0.1 上则认为是线上
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "https://center.manyuzo.com")

    # 前端路由模式自动识别：
    # FRONTEND_URL 包含 localhost → 开发环境 → history mode（无 #/ 前缀）
    # 否则 → 生产环境 → hash mode（加 #/ 前缀）
    @property
    def frontend_hash_mode(self) -> bool:
        return "localhost" not in self.FRONTEND_URL

    # 授权 scope
    WP_OAUTH_SCOPE: str = "basic email profile"

settings = Settings()

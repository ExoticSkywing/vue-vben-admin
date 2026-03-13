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

    # ─── 小芽空投机 MySQL (xiaoyaairdrop) ───
    AIRDROP_DB_HOST: str = os.getenv("AIRDROP_DB_HOST", "localhost")
    AIRDROP_DB_PORT: int = int(os.getenv("AIRDROP_DB_PORT", "3306"))
    AIRDROP_DB_USER: str = os.getenv("AIRDROP_DB_USER", "xiaoyaairdrop")
    AIRDROP_DB_PASSWORD: str = os.getenv("AIRDROP_DB_PASSWORD", "L3Ht7WJJmdAjDF6h")
    AIRDROP_DB_NAME: str = os.getenv("AIRDROP_DB_NAME", "xiaoyaairdrop")

    # ─── 星小芽 WordPress 数据库（只读，登录时查 _xingxy_telegram_uid） ───
    WP_DB_HOST: str = os.getenv("WP_DB_HOST", "localhost")
    WP_DB_PORT: int = int(os.getenv("WP_DB_PORT", "3306"))
    WP_DB_USER: str = os.getenv("WP_DB_USER", "xingxy_manyuzo")
    WP_DB_PASSWORD: str = os.getenv("WP_DB_PASSWORD", "xingxymanyuzo_8501")
    WP_DB_NAME: str = os.getenv("WP_DB_NAME", "xingxy_manyuzo")
    WP_TABLE_PREFIX: str = os.getenv("WP_TABLE_PREFIX", "wp_")

    # ─── TG Bot 配置（用于动态获取 Bot username 和生成分享链接） ───
    AIRDROP_BOT_TOKEN: str = os.getenv("AIRDROP_BOT_TOKEN", "8714950601:AAHJyeekNJ5EovgA7SEjm4XIbFf3iU3W2kU")

    # 超级管理员 TG user ID（可查看所有空投包）
    SUPER_ADMIN_TG_ID: int = int(os.getenv("SUPER_ADMIN_TG_ID", "1861667385"))

settings = Settings()

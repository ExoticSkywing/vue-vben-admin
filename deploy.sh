#!/bin/bash
# ==========================================
# Vben Admin 安全构建与部署脚本
# ==========================================

# 1. 配置参数
PROJECT_DIR="/www/wwwroot/xingxy.manyuzo.com/wp-content/plugins/services/vue-vben-admin"
TARGET_DIR="/www/wwwroot/center.manyuzo.com"
APP_NAME="web-ele" # 这里固定使用 Element Plus 版本
DIST_DIR="$PROJECT_DIR/apps/$APP_NAME/dist"

echo "🚀 开始构建与部署..."
cd "$PROJECT_DIR" || exit 1

# 3. 执行构建
echo "📦 正在执行 pnpm run build:ele (只打包 $APP_NAME)..."
# 使用 filter 参数只打包我们要的 app，防止全量打包爆内存
# --concurrency=1 防止多个包同时编译导致瞬间拉高内存
pnpm run build:ele --concurrency=1

if [ $? -ne 0 ]; then
    echo "❌ 构建失败，请检查上方日志！"
    exit 1
fi

echo "✅ 构建成功！"

# 4. 准备部署目录
# 确保目标目录存在
if [ ! -d "$TARGET_DIR" ]; then
    echo "创建目标网站目录: $TARGET_DIR"
    mkdir -p "$TARGET_DIR"
fi

# 5. 清理旧文件并同步新文件
echo "🔄 正在同步文件到目标站点..."

# 安全清理旧的静态文件（保留可能存在的一些特殊隐藏文件）
rm -rf "$TARGET_DIR"/*

# 复制新构建的静态文件
cp -r "$DIST_DIR"/* "$TARGET_DIR"/

echo "✨ 部署完成！"
echo "🌐 线上访问地址: https://center.manyuzo.com"

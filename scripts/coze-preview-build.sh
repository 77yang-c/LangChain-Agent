#!/usr/bin/env bash
set -euo pipefail

# 基于脚本位置定位项目根目录（scripts/ 的上一级）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo "[coze-preview-build] 安装 Python 依赖..."

# 使用 uv 安装依赖到虚拟环境
if command -v uv &> /dev/null; then
    uv pip install -r requirements.txt
else
    echo "警告: uv 未找到，尝试使用 pip"
    pip install -r requirements.txt
fi

echo "[coze-preview-build] 依赖安装完成"

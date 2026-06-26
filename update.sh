#!/usr/bin/env bash
# ai-pulse 更新 — 当 ai-pulse 仓本身有新版本时
#
# v2（vendored）：ai-pulse 自包含，更新 = git pull + 重跑 setup.sh（pip-only 本地化）。
# 不再重新 clone/patch 上游。用户的 workspace/config/ 配置会被保留
# （setup.sh 对 competitor-profiles.json 不覆盖；follow-news-sources.json 是幂等重写的占位符解析）。
#
# 用法：
#   bash update.sh [--skip-deps]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=================================================="
echo "AI Pulse 更新（独立 skill）"
echo "=================================================="

# Step 1: pull ai-pulse 自身
echo "▶ git pull ai-pulse..."
cd "$SCRIPT_DIR"
git pull --rebase

# Step 2: 重跑 setup（pip-only 本地化）
echo ""
echo "▶ 重跑 setup.sh..."
bash "$SCRIPT_DIR/setup.sh" "$@"

echo ""
echo "✅ 更新完成"

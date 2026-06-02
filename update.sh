#!/usr/bin/env bash
# ai-pulse 更新 — 当 ai-pulse 仓本身有新版本时
#
# 工作原理：
#   git pull ai-pulse → 重新跑 install.sh 应用新 patch + 新 addons
#   保留 follow-news/workspace/config/ 用户配置

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=================================================="
echo "AI Pulse 更新"
echo "=================================================="

# Step 1: pull ai-pulse 自身
echo "▶ git pull ai-pulse..."
cd "$SCRIPT_DIR"
git pull --rebase

# Step 2: 重跑 install
echo ""
echo "▶ 重跑 install.sh..."
bash "$SCRIPT_DIR/install.sh" "$@"

echo ""
echo "✅ 更新完成"

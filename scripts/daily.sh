#!/usr/bin/env bash
# 每日采集 — 只跑一路必须每日累积的源：
#   1) TrendRadar — 中文热榜接口返回当前快照，要日跑攒进 SQLite，
#      供 weekly.sh 触发时从 SQLite 拉 7 天
#
# 其余 RSS / GitHub / Web / Twitter 在 weekly.sh 触发时现抓 7 天，无需每日跑。
#
# 用法：
#   bash daily.sh
#
# 环境变量（按需）：
#   TRENDRADAR_DIR        — TrendRadar 仓路径，默认仓内 ../trendradar
#   FOLLOW_NEWS_DIR       — follow-news 引擎路径，默认仓内 ../follow-news-addons
#   FOLLOW_NEWS_WORKSPACE — workspace 目录，默认 $FOLLOW_NEWS_DIR/workspace

set -e

THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── 部署模式自检：deploy-skill.sh 复制本脚本到 skill/scripts/ai-pulse/ 时，
#    skill 根（$THIS_DIR/../..）会有 .ai-pulse-config 指定 TrendRadar 路径
DEPLOY_CONFIG="$THIS_DIR/../../.ai-pulse-config"
if [ -f "$DEPLOY_CONFIG" ]; then
    # shellcheck disable=SC1090
    . "$DEPLOY_CONFIG"
    FOLLOW_NEWS_DIR="${FOLLOW_NEWS_DIR:-$THIS_DIR/../..}"
    AI_PULSE_DIR_FROM_CONFIG="$AI_PULSE_DIR"
fi

TRENDRADAR_DIR="${TRENDRADAR_DIR:-$THIS_DIR/../trendradar}"
FOLLOW_NEWS_DIR="${FOLLOW_NEWS_DIR:-$THIS_DIR/../follow-news-addons}"
FOLLOW_NEWS_WORKSPACE="${FOLLOW_NEWS_WORKSPACE:-$FOLLOW_NEWS_DIR/workspace}"

# 强制 Python UTF-8 模式（修复 Windows GBK 编码问题，让所有 open()/print() 默认 UTF-8）
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

# 加载 .env（如果存在，含 API keys / 代理）
ENV_FILE="${AI_PULSE_DIR_FROM_CONFIG:-$THIS_DIR/..}/.env"
if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$ENV_FILE"
    set +a
fi

echo "=================================================="
echo "AI Pulse — 每日采集（TrendRadar 累积）"
echo "=================================================="
echo "时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "--------------------------------------------------"

# Python 命令检测（Windows 上 'python3' 是 Microsoft Store 占位符，必须用 'python'）
if command -v python3 >/dev/null 2>&1 && python3 --version >/dev/null 2>&1; then
    PYTHON_BIN=python3
else
    PYTHON_BIN=python
fi

# Step 1: TrendRadar（写入 SQLite，供 weekly 时从中拉 7 天）
echo ""
echo "▶ Step 1/1: TrendRadar 抓中文热榜 → SQLite"
cd "$TRENDRADAR_DIR"
"$PYTHON_BIN" -m trendradar

echo ""
echo "=================================================="
echo "✅ 每日采集完成"
echo ""
echo "TrendRadar SQLite: $TRENDRADAR_DIR/output/news/$(date '+%Y-%m-%d').db"
echo ""
echo "周末跑 weekly.sh 时会拉 TrendRadar 最近 7 天的 SQLite 数据，"
echo "其他信源（RSS/GitHub/Web/Twitter）会现抓 7 天。"
echo "=================================================="

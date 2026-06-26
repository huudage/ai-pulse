#!/usr/bin/env bash
# 每日新闻摘要（日报） — follow-news 聚合引擎现抓最近 24h，输出结构化 JSON + 摘要，
# 供 OpenClaw agent 读 references/digest-prompt.md 后撰写日报。
#
# 与 daily.sh 区别：
#   - daily.sh   = 累积 cron（TrendRadar 快照攒 SQLite），喂给 weekly
#   - daily-digest.sh = 端到端日报（现抓 24h → merged.json → summarize），本 skill 的 "日报"
#
# 用法：
#   bash daily-digest.sh
#
# 环境变量（按需）：
#   TRENDRADAR_DIR / FOLLOW_NEWS_DIR / FOLLOW_NEWS_WORKSPACE
#   HOURS（默认 24） / OUTPUT（默认 /tmp/td-merged.json） / TOP（默认 5）

set -e

THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── 部署模式自检：deploy 把本脚本放进 ai-pulse-engine/scripts/，
#    同级 engine 根目录的 .ai-pulse-config 提供 AI_PULSE_DIR / 引擎路径
DEPLOY_CONFIG="$THIS_DIR/../.ai-pulse-config"
if [ -f "$DEPLOY_CONFIG" ]; then
    # shellcheck disable=SC1090
    . "$DEPLOY_CONFIG"
    AI_PULSE_DIR_FROM_CONFIG="$AI_PULSE_DIR"
fi

TRENDRADAR_DIR="${TRENDRADAR_DIR:-$THIS_DIR/../trendradar}"
FOLLOW_NEWS_DIR="${FOLLOW_NEWS_DIR:-$THIS_DIR/../follow-news-addons}"
FOLLOW_NEWS_WORKSPACE="${FOLLOW_NEWS_WORKSPACE:-$FOLLOW_NEWS_DIR/workspace}"
HOURS="${HOURS:-24}"
OUTPUT="${OUTPUT:-/tmp/td-merged.json}"
TOP="${TOP:-5}"

# 强制 Python UTF-8 模式（修复 Windows GBK 编码问题）
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

# 加载 .env（如果存在）
ENV_FILE="${AI_PULSE_DIR_FROM_CONFIG:-$THIS_DIR/..}/.env"
if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$ENV_FILE"
    set +a
fi

echo "=================================================="
echo "AI Pulse — 每日新闻摘要（日报）"
echo "=================================================="
echo "时间窗口: 最近 $HOURS 小时（现抓 RSS/GitHub/Web/播客）"
echo "时间:     $(date '+%Y-%m-%d %H:%M:%S')"
echo "LLM:      由 OpenClaw agent 在阅读结果时处理（脚本不调 API）"
echo "--------------------------------------------------"

cd "$FOLLOW_NEWS_DIR"

# Python 命令检测（Windows 上 'python3' 是 Microsoft Store 占位符，必须用 'python'）
if command -v python3 >/dev/null 2>&1 && python3 --version >/dev/null 2>&1; then
    PYTHON_BIN=python3
else
    PYTHON_BIN=python
fi

"$PYTHON_BIN" scripts/run-pipeline.py \
    --defaults "$FOLLOW_NEWS_DIR/config/defaults" \
    --config "$FOLLOW_NEWS_WORKSPACE/config" \
    --hours "$HOURS" \
    --freshness pd \
    --archive-dir "$FOLLOW_NEWS_WORKSPACE/archive/follow-news/" \
    --output "$OUTPUT" \
    --verbose \
    --force

echo ""
echo "▶ 生成 Top $TOP 摘要"
"$PYTHON_BIN" scripts/summarize-merged.py --input "$OUTPUT" --top "$TOP"

echo ""
echo "=================================================="
echo "✅ 日报数据准备完成"
echo ""
echo "结构化 JSON: $OUTPUT"
echo ""
echo "下一步：agent 读 references/digest-prompt.md，按其结构撰写日报，"
echo "并按需用 references/templates/{chat,discord,email,pdf}.md 渲染。"
echo "只用数据里的 url 字段，禁止编造链接。"
echo "=================================================="

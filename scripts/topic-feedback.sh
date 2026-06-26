#!/usr/bin/env bash
# 单事件社区反馈 — 针对单个事件/话题抓多源社区反应
# （HN/V2EX 评论原文 + 中文热榜 + KOL B站/知乎/即刻/公众号 + Twitter best-effort），
# 供 OpenClaw agent 读 references/prompts/topic-feedback.md 后解读。
#
# 用法：
#   bash topic-feedback.sh --query "Cursor agent mode"
#   bash topic-feedback.sh --query "通义灵码" --days 14
#
# HN + V2EX 评论原文与 KOL 内容默认抓取，无需 flag。只要标题+元数据可加 --no-comments。
# 透传所有参数给 topic-feedback.py（用户至少要给 --query）。
# 未显式指定时自动注入 --trendradar-dir / --output / --markdown 默认值。
#
# 环境变量（按需）：
#   TRENDRADAR_DIR / FOLLOW_NEWS_DIR

set -e

THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

DEPLOY_CONFIG="$THIS_DIR/../.ai-pulse-config"
if [ -f "$DEPLOY_CONFIG" ]; then
    # shellcheck disable=SC1090
    . "$DEPLOY_CONFIG"
    AI_PULSE_DIR_FROM_CONFIG="$AI_PULSE_DIR"
fi

TRENDRADAR_DIR="${TRENDRADAR_DIR:-$THIS_DIR/../trendradar}"
FOLLOW_NEWS_DIR="${FOLLOW_NEWS_DIR:-$THIS_DIR/../follow-news-addons}"

export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

ENV_FILE="${AI_PULSE_DIR_FROM_CONFIG:-$THIS_DIR/..}/.env"
if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$ENV_FILE"
    set +a
fi

# 解析用户参数：缺哪个默认值就补哪个
ARGS=("$@")
has_flag() { local f="$1"; shift; for a in "$@"; do [ "$a" = "$f" ] && return 0; done; return 1; }

has_flag --trendradar-dir "${ARGS[@]}" || ARGS+=(--trendradar-dir "$TRENDRADAR_DIR")
has_flag --output         "${ARGS[@]}" || ARGS+=(--output /tmp/td-topic.json)
has_flag --markdown       "${ARGS[@]}" || ARGS+=(--markdown /tmp/td-topic.md)

echo "=================================================="
echo "AI Pulse — 单事件社区反馈"
echo "=================================================="
echo "时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "--------------------------------------------------"

cd "$FOLLOW_NEWS_DIR"

if command -v python3 >/dev/null 2>&1 && python3 --version >/dev/null 2>&1; then
    PYTHON_BIN=python3
else
    PYTHON_BIN=python
fi

"$PYTHON_BIN" scripts/topic-feedback.py "${ARGS[@]}"

echo ""
echo "=================================================="
echo "✅ 单事件社区反馈数据准备完成"
echo ""
echo "下一步：agent 读 references/prompts/topic-feedback.md，按其输入数据契约解读。"
echo "只用数据里的 url 字段，禁止编造链接。"
echo "=================================================="

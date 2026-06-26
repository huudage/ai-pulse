#!/usr/bin/env bash
# 按需竞品调研 — 针对某个国产 agent 产品 / 行业抓官方动态 + KOL 内容，
# 供 OpenClaw agent 读 references/prompts/competitor-brief.md 后撰写竞品简报。
#
# 用法：
#   bash competitor-brief.sh                       # 默认：抓全部 28 个竞品出长报告
#   bash competitor-brief.sh --all                 # 同上，显式
#   bash competitor-brief.sh --product "通义灵码"
#   bash competitor-brief.sh --industry "金融" --window-days 30
#
# 透传所有参数给 competitor-brief.py（--all / --product / --industry 三选一互斥；
# 无 flag 时默认全量）。未显式指定时自动注入 --profiles / --out-json / --out-md 默认值。
#
# 环境变量（按需）：
#   FOLLOW_NEWS_DIR / FOLLOW_NEWS_WORKSPACE

set -e

THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

DEPLOY_CONFIG="$THIS_DIR/../.ai-pulse-config"
if [ -f "$DEPLOY_CONFIG" ]; then
    # shellcheck disable=SC1090
    . "$DEPLOY_CONFIG"
    AI_PULSE_DIR_FROM_CONFIG="$AI_PULSE_DIR"
fi

FOLLOW_NEWS_DIR="${FOLLOW_NEWS_DIR:-$THIS_DIR/../follow-news-addons}"
FOLLOW_NEWS_WORKSPACE="${FOLLOW_NEWS_WORKSPACE:-$FOLLOW_NEWS_DIR/workspace}"

export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

ENV_FILE="${AI_PULSE_DIR_FROM_CONFIG:-$THIS_DIR/..}/.env"
if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$ENV_FILE"
    set +a
fi

ARGS=("$@")
has_flag() { local f="$1"; shift; for a in "$@"; do [ "$a" = "$f" ] && return 0; done; return 1; }

has_flag --profiles "${ARGS[@]}" || ARGS+=(--profiles "$FOLLOW_NEWS_WORKSPACE/config/competitor-profiles.json")
has_flag --out-json "${ARGS[@]}" || ARGS+=(--out-json /tmp/competitor-brief.json)
has_flag --out-md   "${ARGS[@]}" || ARGS+=(--out-md /tmp/competitor-brief.md)

echo "=================================================="
echo "AI Pulse — 按需竞品调研"
echo "=================================================="
echo "时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "--------------------------------------------------"

cd "$FOLLOW_NEWS_DIR"

if command -v python3 >/dev/null 2>&1 && python3 --version >/dev/null 2>&1; then
    PYTHON_BIN=python3
else
    PYTHON_BIN=python
fi

"$PYTHON_BIN" scripts/competitor-brief.py "${ARGS[@]}"

echo ""
echo "=================================================="
echo "✅ 竞品调研数据准备完成"
echo ""
echo "下一步：agent 读 references/prompts/competitor-brief.md，按其报告结构撰写。"
echo "官方动态三要素必须基于数据里的 url；方向/场景 synthesis 须标注\"推断\"。"
echo "只用数据里的 url 字段，禁止编造链接。"
echo "=================================================="

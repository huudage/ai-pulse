#!/usr/bin/env bash
# 每周聚合 — 现抓 7 天数据 + 启发式 Tier 分级 + HN/Reddit 评论 enrichment
#
# 行为：
#   - 触发时现抓 7 天（RSS / GitHub / Web 搜索 / Twitter / 播客）
#   - 从 TrendRadar SQLite 拉最近 7 天（之前 daily.sh 累积的）
#   - pool 本周 Reddit daily archive
#   - 启发式 Tier 1/2/3 预标签（35+ 厂商正则白名单）
#   - 对 Tier 1 抓 HN/Reddit Top 评论原文（零鉴权 JSON API）
#   - 输出结构化 JSON + markdown 给 OpenClaw agent 后续处理
#   - agent 读 competitor-monitor.md 后做 4 阶段（语义去重 / 发布验证 / 三维度分类 / 撰写）
#
# 用法：
#   bash weekly.sh
#
# 环境变量：
#   TRENDRADAR_DIR / FOLLOW_NEWS_DIR / FOLLOW_NEWS_WORKSPACE — 同 daily.sh

set -e

THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── 部署模式自检：当脚本被 deploy-skill.sh 复制到 skill/scripts/ai-pulse/ 时，
#    skill 根（$THIS_DIR/../..）会有 .ai-pulse-config，里面有 AI_PULSE_DIR / TRENDRADAR_DIR
DEPLOY_CONFIG="$THIS_DIR/../../.ai-pulse-config"
if [ -f "$DEPLOY_CONFIG" ]; then
    # shellcheck disable=SC1090
    . "$DEPLOY_CONFIG"
    FOLLOW_NEWS_DIR="${FOLLOW_NEWS_DIR:-$THIS_DIR/../..}"
    AI_PULSE_DIR_FROM_CONFIG="$AI_PULSE_DIR"
fi

TRENDRADAR_DIR="${TRENDRADAR_DIR:-$THIS_DIR/../../TrendRadar}"
FOLLOW_NEWS_DIR="${FOLLOW_NEWS_DIR:-$THIS_DIR/../../follow-news}"
FOLLOW_NEWS_WORKSPACE="${FOLLOW_NEWS_WORKSPACE:-$FOLLOW_NEWS_DIR/workspace}"
DAYS="${DAYS:-7}"
OUTPUT="${OUTPUT:-/tmp/td-weekly-merged.json}"
MARKDOWN="${MARKDOWN:-/tmp/td-weekly.md}"

# 强制 Python UTF-8 模式（修复 Windows GBK 编码问题，让所有 open()/print() 默认 UTF-8）
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

# 加载 .env（如果存在，含 API keys / 代理）
# 部署模式优先用 .ai-pulse-config 里的 AI_PULSE_DIR；开发模式回退到 $THIS_DIR/..
ENV_FILE="${AI_PULSE_DIR_FROM_CONFIG:-$THIS_DIR/..}/.env"
if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$ENV_FILE"
    set +a
fi

echo "=================================================="
echo "AI Pulse — 每周竞品监控周报"
echo "=================================================="
echo "时间窗口: 最近 $DAYS 天（现抓 + SQLite 累积）"
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

"$PYTHON_BIN" scripts/weekly-feedback.py \
    --fetch-now \
    --trendradar-dir "$TRENDRADAR_DIR" \
    --days "$DAYS" \
    --output "$OUTPUT" \
    --markdown "$MARKDOWN" \
    --enrich-tier1 \
    --verbose

echo ""
echo "=================================================="
echo "✅ 周报数据准备完成"
echo ""
echo "结构化 JSON: $OUTPUT"
echo "原始 markdown: $MARKDOWN"
echo ""
echo "下一步：在 OpenClaw 里说"
echo '  "本周 AI 圈竞品监控周报"'
echo ""
echo "agent 会："
echo "  1. 读 competitor-monitor.md 拿到产品规则"
echo "  2. 读上面的 JSON 数据"
echo "  3. 按 4 阶段处理（语义去重 → 发布验证 → 三维度分类 → 写报告）"
echo "  4. 生成自然语言周报返回"
echo "=================================================="

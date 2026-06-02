#!/usr/bin/env bash
# 验证 ai-pulse 安装是否完整 — 跑前用一下，跑出问题用一下
#
# 用法：
#   bash verify.sh [--target DIR]
#   默认 target 是 ../upstream

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${1:-$SCRIPT_DIR/../upstream}"

if [ "$1" = "--target" ]; then
    TARGET_DIR="$2"
fi

TRENDRADAR_DIR="$TARGET_DIR/TrendRadar"
FOLLOW_NEWS_DIR="$TARGET_DIR/follow-news"

PASS=0
FAIL=0

check() {
    local desc="$1"
    local cmd="$2"
    if eval "$cmd" >/dev/null 2>&1; then
        echo "  ✅ $desc"
        PASS=$((PASS+1))
    else
        echo "  ❌ $desc"
        FAIL=$((FAIL+1))
    fi
}

echo "=================================================="
echo "AI Pulse 安装验证"
echo "=================================================="
echo "TrendRadar:  $TRENDRADAR_DIR"
echo "follow-news: $FOLLOW_NEWS_DIR"
echo "--------------------------------------------------"

echo ""
echo "▶ 目录结构"
check "TrendRadar 仓存在" "[ -d '$TRENDRADAR_DIR/.git' ]"
check "follow-news 仓存在" "[ -d '$FOLLOW_NEWS_DIR/.git' ]"

echo ""
echo "▶ TrendRadar 新增文件"
check "trendradar/crawler/comments/" "[ -d '$TRENDRADAR_DIR/trendradar/crawler/comments' ]"
check "trendradar/report/rss_export.py" "[ -f '$TRENDRADAR_DIR/trendradar/report/rss_export.py' ]"
check "trendradar/report/weekly_export.py" "[ -f '$TRENDRADAR_DIR/trendradar/report/weekly_export.py' ]"
check "config/custom/keyword/ai_focus.txt" "[ -f '$TRENDRADAR_DIR/config/custom/keyword/ai_focus.txt' ]"

echo ""
echo "▶ TrendRadar patch 已应用"
check "config.yaml 含 comments: 段" "grep -q '^comments:' '$TRENDRADAR_DIR/config/config.yaml'"
check "__main__.py 含 CommentDispatcher 导入" "grep -q 'CommentDispatcher' '$TRENDRADAR_DIR/trendradar/__main__.py'"
check "loader.py 含 _load_comments_config" "grep -q '_load_comments_config' '$TRENDRADAR_DIR/trendradar/core/loader.py'"
check "report/__init__.py 导出 export_rss" "grep -q 'export_rss' '$TRENDRADAR_DIR/trendradar/report/__init__.py'"

echo ""
echo "▶ follow-news 新增文件"
check "scripts/weekly-feedback.py" "[ -f '$FOLLOW_NEWS_DIR/scripts/weekly-feedback.py' ]"
check "scripts/enrich_comments.py" "[ -f '$FOLLOW_NEWS_DIR/scripts/enrich_comments.py' ]"
check "scripts/llm-filter.py" "[ -f '$FOLLOW_NEWS_DIR/scripts/llm-filter.py' ]"
check "references/prompts/competitor-monitor.md" "[ -f '$FOLLOW_NEWS_DIR/references/prompts/competitor-monitor.md' ]"

echo ""
echo "▶ follow-news patch 已应用"
check "fetch-rss.py 含 file:// 支持" "grep -q 'file://' '$FOLLOW_NEWS_DIR/scripts/fetch-rss.py'"
check "run-pipeline.py 含 archive-json 逻辑" "grep -qE 'archive_json|--no-archive-json' '$FOLLOW_NEWS_DIR/scripts/run-pipeline.py'"
check "SKILL.md 含路由规则 5" "grep -q 'Weekly competitor monitor' '$FOLLOW_NEWS_DIR/SKILL.md'"

echo ""
echo "▶ workspace 配置"
check "follow-news-sources.json 存在" "[ -f '$FOLLOW_NEWS_DIR/workspace/config/follow-news-sources.json' ]"
check "follow-news-sources.json 已替换占位符" "! grep -q '<TRENDRADAR_PATH>' '$FOLLOW_NEWS_DIR/workspace/config/follow-news-sources.json'"

echo ""
echo "▶ Python 可执行检查"
# Prefer python over python3 on Windows (python3 may be the Microsoft Store shim)
if command -v python >/dev/null 2>&1 && python -c "import sys" >/dev/null 2>&1; then
    PYTHON=python
elif command -v python3 >/dev/null 2>&1 && python3 -c "import sys" >/dev/null 2>&1; then
    PYTHON=python3
else
    PYTHON=python3
fi
check "weekly-feedback.py --help 含 --fetch-now" "'$PYTHON' '$FOLLOW_NEWS_DIR/scripts/weekly-feedback.py' --help 2>&1 | grep -q fetch-now"
check "TrendRadar 主模块可导入" "cd '$TRENDRADAR_DIR' && '$PYTHON' -c 'from trendradar.crawler.comments import CommentDispatcher; from trendradar.report import export_rss'"

echo ""
echo "=================================================="
echo "结果: ✅ $PASS 通过  ❌ $FAIL 失败"
echo "=================================================="

if [ "$FAIL" -gt 0 ]; then
    echo ""
    echo "有失败项，建议重新跑 install.sh"
    exit 1
fi

echo ""
echo "全部通过 ✨ 可以跑 daily.sh / weekly.sh 了"

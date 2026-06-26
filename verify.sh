#!/usr/bin/env bash
# 验证 ai-pulse 独立 skill 安装是否完整 — 跑前用一下，跑出问题用一下
#
# v2（vendored）：ai-pulse 自包含，follow-news 引擎在 follow-news-addons/，
# TrendRadar 在 trendradar/。不再校验外部上游 clone / patch 是否应用，
# 改为校验仓内 vendored 文件齐全 + 模块可导入 + 入口脚本 --help。
#
# 用法：
#   bash verify.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 强制 UTF-8（修复 Windows GBK）
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

TRENDRADAR_DIR="$SCRIPT_DIR/trendradar"
FOLLOW_NEWS_DIR="$SCRIPT_DIR/follow-news-addons"

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
echo "AI Pulse 安装验证（独立 skill）"
echo "=================================================="
echo "TrendRadar (仓内):  $TRENDRADAR_DIR"
echo "follow-news 引擎:    $FOLLOW_NEWS_DIR"
echo "--------------------------------------------------"

echo ""
echo "▶ 仓内 vendored 目录结构"
check "trendradar/ 包存在" "[ -d '$TRENDRADAR_DIR/trendradar' ]"
check "follow-news-addons/scripts/ 存在" "[ -d '$FOLLOW_NEWS_DIR/scripts' ]"
check "follow-news-addons/config/defaults/ 存在" "[ -d '$FOLLOW_NEWS_DIR/config/defaults' ]"

echo ""
echo "▶ TrendRadar 关键文件（含 ai-pulse 集成模块）"
check "trendradar/crawler/comments/" "[ -d '$TRENDRADAR_DIR/trendradar/crawler/comments' ]"
check "trendradar/report/rss_export.py" "[ -f '$TRENDRADAR_DIR/trendradar/report/rss_export.py' ]"
check "trendradar/report/weekly_export.py" "[ -f '$TRENDRADAR_DIR/trendradar/report/weekly_export.py' ]"
check "config/custom/keyword/ai_focus.txt" "[ -f '$TRENDRADAR_DIR/config/custom/keyword/ai_focus.txt' ]"
check "config.yaml 含 comments: 段" "grep -q '^comments:' '$TRENDRADAR_DIR/config/config.yaml'"

echo ""
echo "▶ follow-news 引擎闭包（vendored）"
check "scripts/run-pipeline.py" "[ -f '$FOLLOW_NEWS_DIR/scripts/run-pipeline.py' ]"
check "scripts/config_loader.py" "[ -f '$FOLLOW_NEWS_DIR/scripts/config_loader.py' ]"
check "scripts/merge-sources.py" "[ -f '$FOLLOW_NEWS_DIR/scripts/merge-sources.py' ]"
check "scripts/fetch-rss.py" "[ -f '$FOLLOW_NEWS_DIR/scripts/fetch-rss.py' ]"
check "scripts/weekly-feedback.py" "[ -f '$FOLLOW_NEWS_DIR/scripts/weekly-feedback.py' ]"
check "config/defaults/sources.json" "[ -f '$FOLLOW_NEWS_DIR/config/defaults/sources.json' ]"
check "config/defaults/topics.json" "[ -f '$FOLLOW_NEWS_DIR/config/defaults/topics.json' ]"

echo ""
echo "▶ 集成行为已 vendored（patch 已 bake-in）"
check "fetch-rss.py 含 file:// 支持" "grep -q 'file://' '$FOLLOW_NEWS_DIR/scripts/fetch-rss.py'"
check "run-pipeline.py 含 archive-json 逻辑" "grep -qE 'archive_json|--no-archive-json' '$FOLLOW_NEWS_DIR/scripts/run-pipeline.py'"

echo ""
echo "▶ 006 竞品监测脚本"
check "scripts/fetch-competitor-official.py" "[ -f '$FOLLOW_NEWS_DIR/scripts/fetch-competitor-official.py' ]"
check "scripts/competitor_tagging.py" "[ -f '$FOLLOW_NEWS_DIR/scripts/competitor_tagging.py' ]"
check "scripts/competitor-brief.py" "[ -f '$FOLLOW_NEWS_DIR/scripts/competitor-brief.py' ]"
check "scripts/fetch-competitor-kol.py" "[ -f '$FOLLOW_NEWS_DIR/scripts/fetch-competitor-kol.py' ]"
check "references/prompts/competitor-monitor.md" "[ -f '$FOLLOW_NEWS_DIR/references/prompts/competitor-monitor.md' ]"

echo ""
echo "▶ workspace 配置（setup.sh 解析后产物）"
check "workspace-config 模板存在" "[ -f '$FOLLOW_NEWS_DIR/workspace-config/follow-news-sources.json' ]"
if [ -f "$FOLLOW_NEWS_DIR/workspace/config/follow-news-sources.json" ]; then
    check "follow-news-sources.json 已替换占位符" "! grep -q '<TRENDRADAR_PATH>' '$FOLLOW_NEWS_DIR/workspace/config/follow-news-sources.json'"
else
    echo "  ⚠️ workspace/config/follow-news-sources.json 未生成（先跑 bash setup.sh）"
fi

echo ""
echo "▶ 多-skill bundle（4 个 skill 清单 + 新增 wrapper）"
for n in ai-pulse-daily ai-pulse-weekly ai-pulse-topic ai-pulse-brief; do
    check "skills/$n/SKILL.md 存在" "[ -f '$SCRIPT_DIR/skills/$n/SKILL.md' ]"
    check "skills/$n/SKILL.md 含 <ENGINE_DIR> 占位符" "grep -q '<ENGINE_DIR>' '$SCRIPT_DIR/skills/$n/SKILL.md'"
done
for w in daily-digest topic-feedback competitor-brief; do
    check "scripts/$w.sh 存在" "[ -f '$SCRIPT_DIR/scripts/$w.sh' ]"
    check "scripts/$w.sh 语法 OK" "bash -n '$SCRIPT_DIR/scripts/$w.sh'"
done
check "references/prompts/topic-feedback.md" "[ -f '$FOLLOW_NEWS_DIR/references/prompts/topic-feedback.md' ]"
check "references/prompts/competitor-brief.md" "[ -f '$FOLLOW_NEWS_DIR/references/prompts/competitor-brief.md' ]"
check "references/digest-prompt.md" "[ -f '$FOLLOW_NEWS_DIR/references/digest-prompt.md' ]"

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
check "Python ≥ 3.12（TrendRadar 要求）" "'$PYTHON' -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3,12) else 1)'"
check "weekly-feedback.py --help 含 --fetch-now" "'$PYTHON' '$FOLLOW_NEWS_DIR/scripts/weekly-feedback.py' --help 2>&1 | grep -q fetch-now"
check "run-pipeline.py --help 可跑" "cd '$FOLLOW_NEWS_DIR' && '$PYTHON' scripts/run-pipeline.py --help"
check "config_loader 可导入" "cd '$FOLLOW_NEWS_DIR' && '$PYTHON' -c 'import sys; sys.path.insert(0, \"scripts\"); import config_loader'"
check "TrendRadar 主模块可导入" "cd '$TRENDRADAR_DIR' && '$PYTHON' -c 'from trendradar.crawler.comments import CommentDispatcher; from trendradar.report import export_rss'"

echo ""
echo "=================================================="
echo "结果: ✅ $PASS 通过  ❌ $FAIL 失败"
echo "=================================================="

if [ "$FAIL" -gt 0 ]; then
    echo ""
    echo "有失败项，建议重新跑 bash setup.sh"
    exit 1
fi

echo ""
echo "全部通过 ✨ 可以跑 scripts/daily.sh / scripts/weekly.sh 了"

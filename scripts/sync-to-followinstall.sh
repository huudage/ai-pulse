#!/usr/bin/env bash
# 把 ai-pulse 的 addons 同步到一个已存在的 follow-news 安装
#
# 用法（默认目标是 ../../follow-news）：
#   bash sync-to-followinstall.sh
#
# 显式指定目标路径：
#   bash sync-to-followinstall.sh /path/to/your/follow-news
#
# 脚本会：
#   1) 备份会被覆盖的现有文件到 <target>/.ai-pulse-backup/<timestamp>/
#   2) 复制 ai-pulse 的新文件和修改后的文件
#   3) 提示需要手动改的 3 个上游文件（fetch-rss.py / run-pipeline.py / SKILL.md）
#
# 如果是首次同步、未应用过 PATCHES 里的 3 处手动修改，脚本会列出来让你确认

set -e

THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AI_PULSE_ROOT="$(cd "$THIS_DIR/.." && pwd)"
TARGET="${1:-$THIS_DIR/../../follow-news}"

if [ ! -d "$TARGET" ]; then
    echo "❌ 目标 follow-news 目录不存在: $TARGET"
    echo "用法: bash $0 [/path/to/follow-news]"
    exit 1
fi

TARGET="$(cd "$TARGET" && pwd)"
TIMESTAMP="$(date '+%Y%m%d-%H%M%S')"
BACKUP_DIR="$TARGET/.ai-pulse-backup/$TIMESTAMP"

echo "=================================================="
echo "AI Pulse → follow-news 同步"
echo "=================================================="
echo "ai-pulse 源:   $AI_PULSE_ROOT"
echo "follow-news:  $TARGET"
echo "备份目录:      $BACKUP_DIR"
echo "--------------------------------------------------"

# 帮助函数：复制一个文件，先把目标已有版本备份
copy_with_backup() {
    local src="$1"
    local dst="$2"
    if [ -f "$dst" ]; then
        local rel="${dst#$TARGET/}"
        local backup_path="$BACKUP_DIR/$rel"
        mkdir -p "$(dirname "$backup_path")"
        cp "$dst" "$backup_path"
        echo "  📦 备份 $rel"
    fi
    mkdir -p "$(dirname "$dst")"
    cp "$src" "$dst"
    local rel="${dst#$TARGET/}"
    echo "  ✚ 写入 $rel"
}

echo ""
echo "▶ 同步脚本"
copy_with_backup "$AI_PULSE_ROOT/follow-news-addons/scripts/weekly-feedback.py" "$TARGET/scripts/weekly-feedback.py"
copy_with_backup "$AI_PULSE_ROOT/follow-news-addons/scripts/enrich_comments.py" "$TARGET/scripts/enrich_comments.py"
copy_with_backup "$AI_PULSE_ROOT/follow-news-addons/scripts/llm-filter.py" "$TARGET/scripts/llm-filter.py"

echo ""
echo "▶ 同步提示词模板"
copy_with_backup "$AI_PULSE_ROOT/follow-news-addons/references/prompts/competitor-monitor.md" "$TARGET/references/prompts/competitor-monitor.md"

echo ""
echo "▶ 同步 workspace 自定义信源"
if [ -f "$TARGET/workspace/config/follow-news-sources.json" ]; then
    echo "  ⚠️ 已存在 $TARGET/workspace/config/follow-news-sources.json"
    echo "    跳过覆盖（你的本地版本可能有自定义 URL）"
    echo "    参考新版本：$AI_PULSE_ROOT/follow-news-addons/workspace-config/follow-news-sources.json"
else
    copy_with_backup "$AI_PULSE_ROOT/follow-news-addons/workspace-config/follow-news-sources.json" "$TARGET/workspace/config/follow-news-sources.json"
    echo ""
    echo "  ⚠️ 请编辑 $TARGET/workspace/config/follow-news-sources.json"
    echo "    把 url 字段改为你本机 TrendRadar 的输出路径！"
fi

echo ""
echo "▶ 检查 3 个上游文件是否已应用 patches"
echo ""

# Check fetch-rss.py for file:// support
if grep -q 'url.startswith("file://")' "$TARGET/scripts/fetch-rss.py" 2>/dev/null; then
    echo "  ✅ scripts/fetch-rss.py 已含 file:// 支持"
else
    echo "  ❌ scripts/fetch-rss.py 缺 file:// 协议支持"
    echo "     按 ai-pulse/follow-news-addons/PATCHES.md 第 1 节手动改"
fi

# Check run-pipeline.py for archive-json flag
if grep -q "archive_json\|--no-archive-json" "$TARGET/scripts/run-pipeline.py" 2>/dev/null; then
    echo "  ✅ scripts/run-pipeline.py 已含 daily JSON archive 逻辑"
else
    echo "  ❌ scripts/run-pipeline.py 缺 daily JSON archive 逻辑"
    echo "     按 ai-pulse/follow-news-addons/PATCHES.md 第 2 节手动改"
fi

# Check SKILL.md for routing rule 5
if grep -q "Weekly competitor monitor" "$TARGET/SKILL.md" 2>/dev/null; then
    echo "  ✅ SKILL.md 已含路由规则 5（Weekly competitor monitor digest）"
else
    echo "  ❌ SKILL.md 缺路由规则 5"
    echo "     按 ai-pulse/follow-news-addons/PATCHES.md 第 3 节手动加"
fi

echo ""
echo "=================================================="
echo "✅ 同步完成"
echo ""
echo "如有 ❌ 项，请按提示完成手动 patch。"
echo "之后可跑："
echo "  cd $TARGET"
echo "  python3 scripts/weekly-feedback.py --help"
echo "确认输出含 --fetch-now / --llm-filter / --trendradar-dir。"
echo "=================================================="

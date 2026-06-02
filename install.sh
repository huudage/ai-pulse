#!/usr/bin/env bash
# ai-pulse 一键安装脚本
#
# 工作原理：
#   1. clone 上游 TrendRadar 和 follow-news 到 ../upstream/ (或 --target 指定的目录)
#   2. checkout 到固定 SHA（保证 patch 能干净应用）
#   3. 应用 patches/*/upstream.patch
#   4. 复制 addons 文件到对应位置
#   5. 写入 follow-news 的 workspace 配置（自动替换 TrendRadar 路径占位符）
#   6. 安装 Python 依赖
#   7. 跑一次 doctor 验证
#
# 用法：
#   bash install.sh                                # 安装到 ../upstream/
#   bash install.sh --target ~/ai-pulse-install    # 安装到指定目录
#   bash install.sh --skip-deps                    # 跳过 pip install
#   bash install.sh --help

set -e

# ─── 上游 SHA pin（保证 patch 能干净应用）───
# 升级上游版本时同步更新 PINNED_TRENDRADAR_SHA / PINNED_FOLLOW_NEWS_SHA + patches/*/upstream.patch
PINNED_TRENDRADAR_SHA="68db3a9aeb84b585540b40270dff3374cc8ed74b"
PINNED_FOLLOW_NEWS_SHA="640901d45fbaa66a499c5f4c469f8cfb0efaa82e"

TRENDRADAR_REPO="https://github.com/sansan0/TrendRadar.git"
FOLLOW_NEWS_REPO="https://github.com/tangwz/follow-news.git"

# ─── 默认参数 ───
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR=""
SKIP_DEPS=false

# ─── 强制 UTF-8 模式（修复 Windows GBK 编码问题）───
# Python 3.7+ 的 UTF-8 模式：让所有 open() 不带 encoding= 都默认走 UTF-8
# 这是修复上游 follow-news / TrendRadar 大量未指定 encoding 的 open() 调用最稳的方法
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

# ─── 加载 .env（如果存在）───
# 用户的 API key / 代理配置等
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a  # 自动 export
    # shellcheck disable=SC1090
    . "$SCRIPT_DIR/.env"
    set +a
    echo "[配置] 已加载 $SCRIPT_DIR/.env"
fi

# ─── 参数解析 ───
while [[ $# -gt 0 ]]; do
    case "$1" in
        --target)
            TARGET_DIR="$2"
            shift 2
            ;;
        --skip-deps)
            SKIP_DEPS=true
            shift
            ;;
        --help|-h)
            sed -n '/^# /,/^$/p' "$0" | sed 's/^# \?//' | head -25
            exit 0
            ;;
        *)
            echo "未知参数: $1"
            echo "用法: bash install.sh [--target DIR] [--skip-deps]"
            exit 1
            ;;
    esac
done

if [ -z "$TARGET_DIR" ]; then
    TARGET_DIR="$(cd "$SCRIPT_DIR/.." && pwd)/upstream"
fi
mkdir -p "$TARGET_DIR"
TARGET_DIR="$(cd "$TARGET_DIR" && pwd)"

TRENDRADAR_DIR="$TARGET_DIR/TrendRadar"
FOLLOW_NEWS_DIR="$TARGET_DIR/follow-news"

echo "=================================================="
echo "AI Pulse 安装"
echo "=================================================="
echo "ai-pulse 仓库:    $SCRIPT_DIR"
echo "目标目录:         $TARGET_DIR"
echo "TrendRadar:       $TRENDRADAR_DIR"
echo "follow-news:      $FOLLOW_NEWS_DIR"
echo ""
echo "上游 pin SHA:"
echo "  TrendRadar:     $PINNED_TRENDRADAR_SHA"
echo "  follow-news:    $PINNED_FOLLOW_NEWS_SHA"
echo "=================================================="
echo ""

# ─── 前置检查 ───
echo "▶ 前置检查"
command -v git >/dev/null 2>&1 || { echo "❌ 需要 git"; exit 1; }
# Prefer python over python3 on Windows (python3 may be Microsoft Store shim)
if command -v python >/dev/null 2>&1 && python -c "import sys" >/dev/null 2>&1; then
    PYTHON=python
elif command -v python3 >/dev/null 2>&1 && python3 -c "import sys" >/dev/null 2>&1; then
    PYTHON=python3
else
    echo "❌ 需要可用的 python3 或 python"; exit 1
fi
echo "  ✓ git, $PYTHON"

# ─── Step 1: 克隆 / 更新 TrendRadar ───
echo ""
echo "▶ Step 1: TrendRadar 上游"
if [ -d "$TRENDRADAR_DIR/.git" ]; then
    echo "  已存在，重置到 pin SHA..."
    cd "$TRENDRADAR_DIR"
    if ! git diff --quiet || ! git diff --cached --quiet; then
        echo "  ⚠️ 有未提交变更，先 stash"
        git stash push -m "ai-pulse-install $(date +%s)" || true
    fi
    git fetch origin
    git checkout "$PINNED_TRENDRADAR_SHA" 2>/dev/null || git checkout -b ai-pulse-pin "$PINNED_TRENDRADAR_SHA"
else
    echo "  克隆 $TRENDRADAR_REPO..."
    git clone "$TRENDRADAR_REPO" "$TRENDRADAR_DIR"
    cd "$TRENDRADAR_DIR"
    git checkout "$PINNED_TRENDRADAR_SHA" 2>/dev/null || git checkout -b ai-pulse-pin "$PINNED_TRENDRADAR_SHA"
fi
echo "  ✓ TrendRadar @ $PINNED_TRENDRADAR_SHA"

# ─── Step 2: 应用 TrendRadar patch ───
echo ""
echo "▶ Step 2: 应用 TrendRadar patch"
cd "$TRENDRADAR_DIR"
if git apply --check "$SCRIPT_DIR/patches/trendradar/upstream.patch" 2>/dev/null; then
    git apply "$SCRIPT_DIR/patches/trendradar/upstream.patch"
    echo "  ✓ patch 应用成功"
elif git diff --stat | grep -qE "config/config.yaml|trendradar/__main__.py|trendradar/core/loader.py|trendradar/report/__init__.py|trendradar/report/formatter.py"; then
    echo "  ⚠️ 检测到 patch 已经应用过（diff 含修改文件），跳过"
else
    echo "  ❌ patch 应用失败 — 上游可能已经改了相关文件，需要更新 patches/trendradar/upstream.patch"
    echo "     运行 'git apply -v $SCRIPT_DIR/patches/trendradar/upstream.patch' 看具体失败原因"
    exit 1
fi

# ─── Step 3: 复制 TrendRadar addons ───
echo ""
echo "▶ Step 3: 复制 TrendRadar 新模块"
mkdir -p "$TRENDRADAR_DIR/trendradar/crawler"
cp -r "$SCRIPT_DIR/trendradar-addons/crawler/comments" "$TRENDRADAR_DIR/trendradar/crawler/"
cp "$SCRIPT_DIR/trendradar-addons/report/rss_export.py" "$TRENDRADAR_DIR/trendradar/report/"
cp "$SCRIPT_DIR/trendradar-addons/report/weekly_export.py" "$TRENDRADAR_DIR/trendradar/report/"
mkdir -p "$TRENDRADAR_DIR/config/custom/keyword"
cp "$SCRIPT_DIR/trendradar-addons/keywords/ai_focus.txt" "$TRENDRADAR_DIR/config/custom/keyword/"
echo "  ✓ comments/, rss_export.py, weekly_export.py, ai_focus.txt"

# ─── Step 4: 克隆 / 更新 follow-news ───
echo ""
echo "▶ Step 4: follow-news 上游"
if [ -d "$FOLLOW_NEWS_DIR/.git" ]; then
    echo "  已存在，重置到 pin SHA..."
    cd "$FOLLOW_NEWS_DIR"
    if ! git diff --quiet || ! git diff --cached --quiet; then
        echo "  ⚠️ 有未提交变更，先 stash"
        git stash push -m "ai-pulse-install $(date +%s)" || true
    fi
    git fetch origin
    git checkout "$PINNED_FOLLOW_NEWS_SHA" 2>/dev/null || git checkout -b ai-pulse-pin "$PINNED_FOLLOW_NEWS_SHA"
else
    echo "  克隆 $FOLLOW_NEWS_REPO..."
    git clone "$FOLLOW_NEWS_REPO" "$FOLLOW_NEWS_DIR"
    cd "$FOLLOW_NEWS_DIR"
    git checkout "$PINNED_FOLLOW_NEWS_SHA" 2>/dev/null || git checkout -b ai-pulse-pin "$PINNED_FOLLOW_NEWS_SHA"
fi
echo "  ✓ follow-news @ $PINNED_FOLLOW_NEWS_SHA"

# ─── Step 5: 应用 follow-news patch ───
echo ""
echo "▶ Step 5: 应用 follow-news patch"
cd "$FOLLOW_NEWS_DIR"
if git apply --check "$SCRIPT_DIR/patches/follow-news/upstream.patch" 2>/dev/null; then
    git apply "$SCRIPT_DIR/patches/follow-news/upstream.patch"
    echo "  ✓ patch 应用成功"
elif git diff --stat | grep -qE "SKILL.md|scripts/fetch-rss.py|scripts/run-pipeline.py"; then
    echo "  ⚠️ 检测到 patch 已经应用过，跳过"
else
    echo "  ❌ patch 应用失败"
    exit 1
fi

# ─── Step 6: 复制 follow-news addons ───
echo ""
echo "▶ Step 6: 复制 follow-news 新脚本 + 提示词"
cp "$SCRIPT_DIR/follow-news-addons/scripts/weekly-feedback.py" "$FOLLOW_NEWS_DIR/scripts/"
cp "$SCRIPT_DIR/follow-news-addons/scripts/enrich_comments.py" "$FOLLOW_NEWS_DIR/scripts/"
cp "$SCRIPT_DIR/follow-news-addons/scripts/llm-filter.py" "$FOLLOW_NEWS_DIR/scripts/"
# fetch-reddit / fetch-twitter 以 overlay 方式复制（替换上游同名文件）
cp "$SCRIPT_DIR/follow-news-addons/scripts/fetch-reddit.py" "$FOLLOW_NEWS_DIR/scripts/"
cp "$SCRIPT_DIR/follow-news-addons/scripts/fetch-twitter.py" "$FOLLOW_NEWS_DIR/scripts/"
mkdir -p "$FOLLOW_NEWS_DIR/references/prompts"
cp "$SCRIPT_DIR/follow-news-addons/references/prompts/competitor-monitor.md" "$FOLLOW_NEWS_DIR/references/prompts/"
echo "  ✓ weekly-feedback.py, enrich_comments.py, llm-filter.py, fetch-reddit.py, fetch-twitter.py, competitor-monitor.md"

# ─── Step 7: 写 workspace 配置（替换 TrendRadar 路径占位符）───
echo ""
echo "▶ Step 7: 写 follow-news workspace 配置"
mkdir -p "$FOLLOW_NEWS_DIR/workspace/config"
WS_CONFIG="$FOLLOW_NEWS_DIR/workspace/config/follow-news-sources.json"

# 适配 file:// URL：Windows 是 file:///C:/...，Unix 是 file:///home/...
case "$OSTYPE" in
    msys*|cygwin*|win32)
        TR_URL_PATH="$(cygpath -m "$TRENDRADAR_DIR" 2>/dev/null || echo "$TRENDRADAR_DIR" | sed 's|^/\([a-zA-Z]\)/|\1:/|')"
        ;;
    *)
        TR_URL_PATH="$TRENDRADAR_DIR"
        ;;
esac

if [ -f "$WS_CONFIG" ]; then
    echo "  ⚠️ 已存在 $WS_CONFIG (跳过覆盖)"
    echo "    如需重置，删除后重跑 install.sh"
else
    # 替换 TrendRadar 路径占位符 <TRENDRADAR_PATH>
    sed "s|<TRENDRADAR_PATH>|$TR_URL_PATH|g" \
        "$SCRIPT_DIR/follow-news-addons/workspace-config/follow-news-sources.json" \
        > "$WS_CONFIG"

    # 如果用户在 .env 设了 ENABLE_KOL_BLOGS=false，把所有 kol-* 源标记为 enabled:false
    if [ "${ENABLE_KOL_BLOGS:-true}" = "false" ]; then
        "$PYTHON" -c "
import json
p = '$WS_CONFIG'
with open(p, 'r', encoding='utf-8') as f:
    data = json.load(f)
for src in data['sources']:
    if src.get('id', '').startswith('kol-'):
        src['enabled'] = False
with open(p, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print('  ENABLE_KOL_BLOGS=false: KOL 博客已禁用')
"
    fi
    echo "  ✓ 写入 $WS_CONFIG"
    echo "    (TrendRadar URL: file://$TR_URL_PATH/output/rss/weekly-ai_focus.xml)"
fi

# ─── Step 8: Python 依赖 ───
if [ "$SKIP_DEPS" = false ]; then
    echo ""
    echo "▶ Step 8: 安装 Python 依赖"
    cd "$TRENDRADAR_DIR" && "$PYTHON" -m pip install -r requirements.txt -q 2>&1 | tail -3
    "$PYTHON" -m pip install -q pytz feedparser jsonschema 2>&1 | tail -2
    echo "  ✓ TrendRadar 依赖"
    cd "$FOLLOW_NEWS_DIR" && "$PYTHON" -m pip install -r requirements.txt -q 2>&1 | tail -3
    echo "  ✓ follow-news 依赖"
else
    echo ""
    echo "▶ Step 8: 跳过依赖安装 (--skip-deps)"
    echo "  手动跑: pip install -r $TRENDRADAR_DIR/requirements.txt"
    echo "         pip install -r $FOLLOW_NEWS_DIR/requirements.txt"
fi

# ─── Step 9: 验证 ───
echo ""
echo "▶ Step 9: 验证安装"
cd "$TRENDRADAR_DIR"
if "$PYTHON" -c "from trendradar.crawler.comments import CommentDispatcher; from trendradar.report import export_rss; print('TR imports OK')" 2>&1 | grep -q "OK"; then
    echo "  ✓ TrendRadar imports OK"
else
    echo "  ⚠️ TrendRadar imports 异常（看上面错误）"
fi

cd "$FOLLOW_NEWS_DIR"
if "$PYTHON" scripts/weekly-feedback.py --help 2>&1 | grep -q "fetch-now"; then
    echo "  ✓ follow-news weekly-feedback.py OK"
else
    echo "  ⚠️ follow-news weekly-feedback.py 异常"
fi

# ─── 完成 ───
echo ""
echo "=================================================="
echo "✅ 安装完成"
echo ""
echo "下一步："
echo "  bash $SCRIPT_DIR/verify.sh        # 验证安装完整性"
echo "  bash $SCRIPT_DIR/doctor.sh        # 检查 .env API key 配置度"
echo "  bash $SCRIPT_DIR/deploy-skill.sh  # 安装为 OpenClaw skill"
echo ""
echo "详细流程见 $SCRIPT_DIR/README.md"
echo "=================================================="

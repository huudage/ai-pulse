#!/usr/bin/env bash
# ai-pulse 一键安装（独立 skill，无需克隆上游）
#
# 工作原理（v2 — vendored）：
#   ai-pulse 现在是一个自包含仓库：follow-news 引擎已 vendored 进 follow-news-addons/，
#   TrendRadar 已 vendored 进 trendradar/。本脚本只做克隆机本地化，不再 clone/patch 上游：
#     1. 加载 .env（API key / 代理）
#     2. pip install -r requirements.txt（union of follow-news + TrendRadar 依赖）
#     3. 写 follow-news workspace 配置：把 <TRENDRADAR_PATH> 占位符替换成仓内 trendradar/ 绝对路径
#        （file:// RSS 需绝对路径），落 follow-news-addons/workspace/config/
#     4. 建 trendradar/output/{news,rss,html} 运行时目录
#     5. 冒烟 --help / import 验证
#
# 用法：
#   bash setup.sh                  # 完整安装
#   bash setup.sh --skip-deps      # 跳过 pip install
#   bash setup.sh --help
#
# 升级 vendored 上游：见 follow-news-addons/PATCHES.md + patches/ + 固定 SHA（provenance 记录）。

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKIP_DEPS=false

# ─── 强制 UTF-8 模式（修复 Windows GBK 编码问题）───
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

# ─── 加载 .env（如果存在）───
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$SCRIPT_DIR/.env"
    set +a
    echo "[配置] 已加载 $SCRIPT_DIR/.env"
fi

# ─── 参数解析 ───
while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-deps) SKIP_DEPS=true; shift ;;
        --help|-h)
            sed -n '/^# /,/^$/p' "$0" | sed 's/^# \?//' | head -25
            exit 0
            ;;
        *)
            echo "未知参数: $1"
            echo "用法: bash setup.sh [--skip-deps]"
            exit 1
            ;;
    esac
done

# 仓内 vendored 路径
TRENDRADAR_DIR="$SCRIPT_DIR/trendradar"
FOLLOW_NEWS_DIR="$SCRIPT_DIR/follow-news-addons"

echo "=================================================="
echo "AI Pulse 安装（独立 skill）"
echo "=================================================="
echo "ai-pulse 仓库:    $SCRIPT_DIR"
echo "TrendRadar (仓内): $TRENDRADAR_DIR"
echo "follow-news 引擎:  $FOLLOW_NEWS_DIR"
echo "=================================================="
echo ""

# ─── 前置检查 ───
echo "▶ 前置检查"
# Prefer python over python3 on Windows (python3 may be Microsoft Store shim)
if command -v python >/dev/null 2>&1 && python -c "import sys" >/dev/null 2>&1; then
    PYTHON=python
elif command -v python3 >/dev/null 2>&1 && python3 -c "import sys" >/dev/null 2>&1; then
    PYTHON=python3
else
    echo "❌ 需要可用的 python3 或 python"; exit 1
fi
# TrendRadar 要求 Python >= 3.12
PYVER="$("$PYTHON" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
echo "  ✓ $PYTHON (版本 $PYVER)"
if ! "$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3,12) else 1)'; then
    echo "  ⚠️ TrendRadar 要求 Python ≥ 3.12（当前 $PYVER）。中文热榜功能可能无法导入。"
fi
if [ ! -d "$TRENDRADAR_DIR/trendradar" ]; then
    echo "❌ 仓内缺 trendradar/ — 仓库不完整，请重新 git clone"; exit 1
fi
if [ ! -f "$FOLLOW_NEWS_DIR/scripts/weekly-feedback.py" ]; then
    echo "❌ 仓内缺 follow-news-addons/scripts/weekly-feedback.py — 仓库不完整"; exit 1
fi

# ─── Step 1: Python 依赖 ───
if [ "$SKIP_DEPS" = false ]; then
    echo ""
    echo "▶ Step 1: 安装 Python 依赖（requirements.txt）"
    "$PYTHON" -m pip install -r "$SCRIPT_DIR/requirements.txt" -q 2>&1 | tail -5 || {
        echo "  ⚠️ pip install 有报错（见上）。可 --skip-deps 后手动安装。"
    }
    echo "  ✓ 依赖安装完成"
else
    echo ""
    echo "▶ Step 1: 跳过依赖安装 (--skip-deps)"
    echo "  手动跑: $PYTHON -m pip install -r $SCRIPT_DIR/requirements.txt"
fi

# ─── Step 2: 建 TrendRadar 运行时输出目录 ───
echo ""
echo "▶ Step 2: 建 trendradar/output 运行时目录"
mkdir -p "$TRENDRADAR_DIR/output/news" "$TRENDRADAR_DIR/output/rss" "$TRENDRADAR_DIR/output/html"
echo "  ✓ output/{news,rss,html}"

# ─── Step 3: 写 follow-news workspace 配置（替换 TrendRadar 路径占位符）───
echo ""
echo "▶ Step 3: 写 follow-news workspace 配置（解析 TrendRadar file:// 绝对路径）"
mkdir -p "$FOLLOW_NEWS_DIR/workspace/config"
WS_CONFIG="$FOLLOW_NEWS_DIR/workspace/config/follow-news-sources.json"

# 适配 file:// URL：Windows 是 file:///C:/...，Unix 是 file:///home/...
case "$OSTYPE" in
    msys*|cygwin*|win32)
        # 前置 / 让 file:// + /D:/... = file:///D:/...（三斜杠）。
        # 两斜杠时 urlparse 会把 "D:" 当成 netloc 丢掉盘符。
        TR_URL_PATH="/$(cygpath -m "$TRENDRADAR_DIR" 2>/dev/null || echo "$TRENDRADAR_DIR" | sed 's|^/\([a-zA-Z]\)/|\1:/|')"
        ;;
    *)
        TR_URL_PATH="$TRENDRADAR_DIR"
        ;;
esac

# 每次安装都重写（占位符解析是机器本地化，幂等）
sed "s|<TRENDRADAR_PATH>|$TR_URL_PATH|g" \
    "$FOLLOW_NEWS_DIR/workspace-config/follow-news-sources.json" \
    > "$WS_CONFIG"

# 如果用户在 .env 设了 ENABLE_KOL_BLOGS=false，把所有 kol-* 源标记为 enabled:false
if [ "${ENABLE_KOL_BLOGS:-true}" = "false" ]; then
    "$PYTHON" -c "
import json
p = r'$WS_CONFIG'
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

# 006 竞品 profiles：复制到 workspace/config（已存在则不覆盖，保留用户填写的官方源）
COMP_PROFILES="$FOLLOW_NEWS_DIR/workspace/config/competitor-profiles.json"
if [ -f "$COMP_PROFILES" ]; then
    echo "  ⚠️ 已存在 $COMP_PROFILES (跳过覆盖，保留你填写的官方源)"
else
    cp "$FOLLOW_NEWS_DIR/workspace-config/competitor-profiles.json" "$COMP_PROFILES"
    echo "  ✓ 写入 $COMP_PROFILES（按需补全各产品 official_sources 后竞品章才会有数据）"
fi

# ─── Step 4: 冒烟验证 ───
echo ""
echo "▶ Step 4: 冒烟验证"
cd "$TRENDRADAR_DIR"
if "$PYTHON" -c "from trendradar.crawler.comments import CommentDispatcher; from trendradar.report import export_rss; print('OK')" 2>&1 | grep -q "OK"; then
    echo "  ✓ TrendRadar 模块可导入"
else
    echo "  ⚠️ TrendRadar imports 异常（检查 Python ≥ 3.12 + 依赖）"
fi

cd "$FOLLOW_NEWS_DIR"
for s in weekly-feedback.py:fetch-now \
         fetch-competitor-official.py:profiles \
         competitor-brief.py:industry \
         fetch-competitor-kol.py:platforms; do
    script="${s%%:*}"; needle="${s##*:}"
    if "$PYTHON" "scripts/$script" --help 2>&1 | grep -q "$needle"; then
        echo "  ✓ $script OK"
    else
        echo "  ⚠️ $script --help 异常"
    fi
done

# ─── 完成 ───
echo ""
echo "=================================================="
echo "✅ 安装完成（独立 skill，无外部上游依赖）"
echo ""
echo "下一步："
echo "  bash $SCRIPT_DIR/doctor.sh        # 检查 .env API key 配置度"
echo "  bash $SCRIPT_DIR/scripts/daily.sh   # 每日累积（TrendRadar 中文热榜）"
echo "  bash $SCRIPT_DIR/scripts/weekly.sh  # 生成本周周报数据"
echo "  bash $SCRIPT_DIR/deploy-skill.sh  # 安装为 OpenClaw skill（可选）"
echo "=================================================="

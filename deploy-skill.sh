#!/usr/bin/env bash
# ai-pulse 一句话部署：把单仓多-skill bundle 部署成 OpenClaw skills。
#
# v2.1（多-skill bundle）：本仓既是共享引擎也是 4 个 skill 的来源。部署后：
#   ~/.openclaw/skills/
#   ├── ai-pulse-engine/    共享引擎（follow-news-addons + trendradar + scripts + references
#   │                       + workspace + .env），无 SKILL.md ⇒ 不被注册为 skill
#   ├── ai-pulse-daily/     SKILL.md（指向 ai-pulse-engine） + .ai-pulse-config
#   ├── ai-pulse-weekly/    同上
#   ├── ai-pulse-topic/     同上
#   └── ai-pulse-brief/     同上
#
# OpenClaw 平铺扫描 <skills>/<name>/SKILL.md（一层），故 4 个 skill = 4 个兄弟顶层目录，
# 各自指向共享引擎（绝对路径写进各 skill 的 SKILL.md 的 <ENGINE_DIR> 占位符 + .ai-pulse-config）。
#
# 工作流：
#   1. 在仓内跑 setup.sh（pip install + 解析 workspace 配置 + 建 output 目录）
#   2. 把仓库（剔除 .git / 运行时状态 / 开发文件 / 密钥 / skills/ / 根 SKILL.md）复制到 ai-pulse-engine/
#   3. 在 ai-pulse-engine/ 写 .ai-pulse-config、重建 output、重解析 file:// 占位符
#   4. fan-out 4 个 skill 目录：拷各自 SKILL.md（替换 <ENGINE_DIR>）+ 写 .ai-pulse-config
#   5. 跑 doctor.sh 验证
#
# 用法：
#   bash deploy-skill.sh                              # 默认 ~/.openclaw/skills/
#   bash deploy-skill.sh --skills-dir /custom/path    # 自定义 skill 目录
#   bash deploy-skill.sh --skip-install               # 跳过 setup.sh（已装过依赖）
#   bash deploy-skill.sh --skip-doctor                # 跳过最后 doctor 验证

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DIR="${SKILLS_DIR:-$HOME/.openclaw/skills}"
SKIP_INSTALL=false
SKIP_DOCTOR=false

export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

# 4 个 skill 目录名（= 注册的 skill 名）
SKILL_NAMES=(ai-pulse-daily ai-pulse-weekly ai-pulse-topic ai-pulse-brief)

while [[ $# -gt 0 ]]; do
    case "$1" in
        --skills-dir) SKILLS_DIR="$2"; shift 2 ;;
        --skip-install) SKIP_INSTALL=true; shift ;;
        --skip-doctor)  SKIP_DOCTOR=true;  shift ;;
        --target)
            echo "⚠️ --target 已废弃（ai-pulse 现为自包含多-skill bundle，无外部 upstream 目录）。忽略：$2"
            shift 2
            ;;
        --help|-h)
            sed -n '/^# /,/^$/p' "$0" | sed 's/^# \?//' | head -34
            exit 0
            ;;
        *) echo "未知参数: $1"; exit 1 ;;
    esac
done

ENGINE_DST="$SKILLS_DIR/ai-pulse-engine"

echo "=================================================="
echo "AI Pulse — 一键部署 OpenClaw skills（多-skill bundle）"
echo "=================================================="
echo "ai-pulse 仓:   $SCRIPT_DIR"
echo "共享引擎:      $ENGINE_DST"
echo "4 个 skill:    ${SKILL_NAMES[*]}"
echo "=================================================="
echo ""

# ─── Step 1: 跑 setup.sh（除非显式跳过）───
if [ "$SKIP_INSTALL" = false ]; then
    echo "▶ Step 1: 运行 setup.sh（pip install + 本地化配置）"
    bash "$SCRIPT_DIR/setup.sh"
    echo ""
fi

# ─── Step 2: 校验仓内就绪 ───
echo "▶ Step 2: 校验仓内源就绪"
if [ ! -f "$SCRIPT_DIR/follow-news-addons/scripts/weekly-feedback.py" ]; then
    echo "  ❌ 缺 follow-news-addons/scripts/weekly-feedback.py — 仓库不完整"
    exit 1
fi
if [ ! -d "$SCRIPT_DIR/trendradar/trendradar" ]; then
    echo "  ❌ 缺 trendradar/ 包 — 仓库不完整"
    exit 1
fi
for n in "${SKILL_NAMES[@]}"; do
    if [ ! -f "$SCRIPT_DIR/skills/$n/SKILL.md" ]; then
        echo "  ❌ 缺 skills/$n/SKILL.md — bundle 不完整"
        exit 1
    fi
done
echo "  ✓ 引擎 + 4 个 skill 清单齐全"

# ─── Step 3: 复制共享引擎 → ai-pulse-engine/（剔除 .git/运行时/开发文件/密钥/skills/根 SKILL.md）───
echo ""
echo "▶ Step 3: 复制共享引擎 → $ENGINE_DST"
mkdir -p "$SKILLS_DIR"
if [ -d "$ENGINE_DST" ]; then
    BAK="${ENGINE_DST}.bak.$(date +%Y%m%d-%H%M%S)"
    echo "  已存在，备份到 $BAK 并替换"
    mv "$ENGINE_DST" "$BAK"
fi
mkdir -p "$ENGINE_DST"

# 引擎不含 skills/ 与根 SKILL.md（引擎目录无 SKILL.md ⇒ 不被注册为 skill）
tar -C "$SCRIPT_DIR" \
    --exclude='./.git' \
    --exclude='./.git/*' \
    --exclude='./.pytest_cache' \
    --exclude='*/__pycache__' \
    --exclude='*.pyc' \
    --exclude='*.bak' \
    --exclude='./.env' \
    --exclude='./skills' \
    --exclude='./skills/*' \
    --exclude='./SKILL.md' \
    --exclude='./trendradar/output/news/*' \
    --exclude='./trendradar/output/rss/*' \
    --exclude='./trendradar/output/html/*' \
    --exclude='*/.ai-pulse-backup' \
    -cf - . | tar -C "$ENGINE_DST" -xf -
echo "  ✓ $ENGINE_DST"

# ─── Step 4: 引擎内重建 output + 写 .ai-pulse-config + 重解析 file:// 占位符 ───
echo ""
echo "▶ Step 4: 引擎内重建 output + 写 .ai-pulse-config"
mkdir -p "$ENGINE_DST/trendradar/output/news" \
         "$ENGINE_DST/trendradar/output/rss" \
         "$ENGINE_DST/trendradar/output/html"

cat > "$ENGINE_DST/.ai-pulse-config" <<EOF
# 由 ai-pulse/deploy-skill.sh 生成，记录共享引擎路径
# （路径含空格时必须加引号；引擎内 scripts/*.sh 会 source 本文件）
AI_PULSE_DIR="$ENGINE_DST"
TRENDRADAR_DIR="$ENGINE_DST/trendradar"
FOLLOW_NEWS_DIR="$ENGINE_DST/follow-news-addons"
DEPLOYED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
EOF
echo "  ✓ $ENGINE_DST/.ai-pulse-config"

echo ""
echo "▶ Step 4b: 按引擎绝对路径重新解析 workspace file:// 占位符"
WS_TEMPLATE="$ENGINE_DST/follow-news-addons/workspace-config/follow-news-sources.json"
WS_CONFIG="$ENGINE_DST/follow-news-addons/workspace/config/follow-news-sources.json"
mkdir -p "$(dirname "$WS_CONFIG")"
case "$OSTYPE" in
    msys*|cygwin*|win32)
        TR_URL_PATH="/$(cygpath -m "$ENGINE_DST/trendradar" 2>/dev/null || echo "$ENGINE_DST/trendradar")"
        ;;
    *)
        TR_URL_PATH="$ENGINE_DST/trendradar"
        ;;
esac
if [ -f "$WS_TEMPLATE" ]; then
    sed "s|<TRENDRADAR_PATH>|$TR_URL_PATH|g" "$WS_TEMPLATE" > "$WS_CONFIG"
    echo "  ✓ $WS_CONFIG"
else
    echo "  ⚠️ 缺 $WS_TEMPLATE（跳过 file:// 解析）"
fi

# ─── Step 5: fan-out 4 个 skill 目录 ───
echo ""
echo "▶ Step 5: fan-out 4 个 skill 目录（指向共享引擎）"
for n in "${SKILL_NAMES[@]}"; do
    SKILL_DST="$SKILLS_DIR/$n"
    if [ -d "$SKILL_DST" ]; then
        mv "$SKILL_DST" "${SKILL_DST}.bak.$(date +%Y%m%d-%H%M%S)"
    fi
    mkdir -p "$SKILL_DST"
    # 替换 <ENGINE_DIR> 占位符为引擎绝对路径
    sed "s|<ENGINE_DIR>|$ENGINE_DST|g" "$SCRIPT_DIR/skills/$n/SKILL.md" > "$SKILL_DST/SKILL.md"
    cat > "$SKILL_DST/.ai-pulse-config" <<EOF
# 由 deploy-skill.sh 生成 — 本 skill 共用的引擎路径
AI_PULSE_DIR="$ENGINE_DST"
ENGINE_DIR="$ENGINE_DST"
EOF
    echo "  ✓ $SKILL_DST"
done

# ─── Step 6: doctor 验证（除非显式跳过）───
if [ "$SKIP_DOCTOR" = false ] && [ -f "$SCRIPT_DIR/doctor.sh" ]; then
    echo ""
    echo "▶ Step 6: 运行 doctor.sh 验证"
    bash "$SCRIPT_DIR/doctor.sh" 2>&1 | tail -20 || true
fi

# ─── 完成 ───
echo ""
echo "=================================================="
echo "✅ Bundle 部署完成"
echo ""
echo "共享引擎: $ENGINE_DST"
echo "已部署 skill:"
for n in "${SKILL_NAMES[@]}"; do
    echo "  - $SKILLS_DIR/$n"
done
echo ""
echo "下一步（在 OpenClaw 里说一句）："
echo "  \"用 ai-pulse 给我跑本周 AI 竞品监控周报\"       → ai-pulse-weekly"
echo "  \"今天 AI 圈有什么\"                              → ai-pulse-daily"
echo "  \"调研一下通义灵码最近在做什么\"                  → ai-pulse-brief"
echo "  \"社区对 Cursor agent mode 怎么看\"               → ai-pulse-topic"
echo ""
echo "或命令行直接触发："
echo "  bash $ENGINE_DST/scripts/weekly.sh"
echo "=================================================="

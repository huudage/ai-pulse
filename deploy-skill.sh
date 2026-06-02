#!/usr/bin/env bash
# ai-pulse 一句话部署：把 follow-news + TrendRadar + ai-pulse addons 打包成
# OpenClaw skill，复制到 ~/.openclaw/skills/follow-news/。
#
# 工作流：
#   1. 跑 install.sh 把上游 + addons 装到 <target>/ (默认 ../upstream/)
#   2. 把 <target>/follow-news 整个目录拷到 SKILLS_DIR/follow-news/
#   3. 写一个 SKILL.md 头部，标注 ai-pulse 版本和 TrendRadar 依赖路径
#   4. 跑 doctor.sh 验证
#
# 用法：
#   bash deploy-skill.sh                              # 默认 ~/.openclaw/skills/
#   bash deploy-skill.sh --skills-dir /custom/path    # 自定义 skill 目录
#   bash deploy-skill.sh --target ~/ai-pulse-install  # 自定义 upstream 目录
#   bash deploy-skill.sh --skip-install               # 跳过 install.sh（已装过）
#   bash deploy-skill.sh --skip-doctor                # 跳过最后 doctor 验证

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DIR="${SKILLS_DIR:-$HOME/.openclaw/skills}"
TARGET_DIR=""
SKIP_INSTALL=false
SKIP_DOCTOR=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --skills-dir) SKILLS_DIR="$2"; shift 2 ;;
        --target)     TARGET_DIR="$2"; shift 2 ;;
        --skip-install) SKIP_INSTALL=true; shift ;;
        --skip-doctor)  SKIP_DOCTOR=true;  shift ;;
        --help|-h)
            sed -n '/^# /,/^$/p' "$0" | sed 's/^# \?//' | head -20
            exit 0
            ;;
        *) echo "未知参数: $1"; exit 1 ;;
    esac
done

if [ -z "$TARGET_DIR" ]; then
    TARGET_DIR="$(cd "$SCRIPT_DIR/.." && pwd)/upstream"
fi

FOLLOW_NEWS_SRC="$TARGET_DIR/follow-news"
TRENDRADAR_SRC="$TARGET_DIR/TrendRadar"
SKILL_DST="$SKILLS_DIR/follow-news"

echo "=================================================="
echo "AI Pulse — 一键部署 OpenClaw Skill"
echo "=================================================="
echo "ai-pulse 源:  $SCRIPT_DIR"
echo "upstream:     $TARGET_DIR"
echo "目标 skill:   $SKILL_DST"
echo "=================================================="
echo ""

# ─── Step 1: 跑 install.sh（除非显式跳过）───
if [ "$SKIP_INSTALL" = false ]; then
    echo "▶ Step 1: 运行 install.sh"
    bash "$SCRIPT_DIR/install.sh" --target "$TARGET_DIR"
    echo ""
fi

# ─── Step 2: 检查源齐全 ───
echo "▶ Step 2: 校验源就绪"
if [ ! -f "$FOLLOW_NEWS_SRC/SKILL.md" ]; then
    echo "  ❌ 缺 $FOLLOW_NEWS_SRC/SKILL.md（install.sh 没跑过？加 --skip-install 前先跑一遍）"
    exit 1
fi
if [ ! -f "$FOLLOW_NEWS_SRC/scripts/weekly-feedback.py" ]; then
    echo "  ❌ 缺 weekly-feedback.py — install.sh 没把 addons 复制进去"
    exit 1
fi
echo "  ✓ follow-news skill 文件齐全"

# ─── Step 3: 复制到 skill 目录 ───
echo ""
echo "▶ Step 3: 复制 follow-news → $SKILL_DST"
mkdir -p "$SKILLS_DIR"
if [ -d "$SKILL_DST" ]; then
    echo "  已存在，备份到 ${SKILL_DST}.bak.$(date +%Y%m%d-%H%M%S) 并替换"
    mv "$SKILL_DST" "${SKILL_DST}.bak.$(date +%Y%m%d-%H%M%S)"
fi
# 用 cp -r 而不是 mv，保留 upstream 原副本作为开发用
cp -r "$FOLLOW_NEWS_SRC" "$SKILL_DST"
echo "  ✓ $SKILL_DST"

# ─── Step 4: 在 skill 里固化 TrendRadar / ai-pulse 路径 ───
echo ""
echo "▶ Step 4: 写 .ai-pulse-config（skill 用来定位 TrendRadar）"
cat > "$SKILL_DST/.ai-pulse-config" <<EOF
# 由 ai-pulse/deploy-skill.sh 生成，记录依赖路径
# （路径里含空格的情况下必须加引号，weekly.sh 会 source 本文件）
AI_PULSE_DIR="$SCRIPT_DIR"
TRENDRADAR_DIR="$TRENDRADAR_SRC"
DEPLOYED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
EOF
echo "  ✓ $SKILL_DST/.ai-pulse-config"

# ─── Step 5: 把 ai-pulse 的 weekly/daily 脚本作为 skill 入口暴露 ───
# 这样 OpenClaw skill 触发时能直接看到入口脚本而不用再找 ai-pulse 目录
echo ""
echo "▶ Step 5: 暴露入口脚本（weekly.sh / daily.sh 软链 / 复制）"
mkdir -p "$SKILL_DST/scripts/ai-pulse"
cp "$SCRIPT_DIR/scripts/weekly.sh" "$SKILL_DST/scripts/ai-pulse/"
cp "$SCRIPT_DIR/scripts/daily.sh"  "$SKILL_DST/scripts/ai-pulse/"
echo "  ✓ scripts/ai-pulse/{weekly,daily}.sh"

# ─── Step 6: doctor 验证（除非显式跳过）───
if [ "$SKIP_DOCTOR" = false ] && [ -f "$SCRIPT_DIR/doctor.sh" ]; then
    echo ""
    echo "▶ Step 6: 运行 doctor.sh 验证"
    bash "$SCRIPT_DIR/doctor.sh" 2>&1 | tail -20 || true
fi

# ─── 完成 ───
echo ""
echo "=================================================="
echo "✅ Skill 部署完成"
echo ""
echo "目标:  $SKILL_DST"
echo "版本:  $(grep -m1 '^version:' "$SKILL_DST/SKILL.md" | awk '{print $2}' | tr -d '\"')"
echo ""
echo "下一步（在 OpenClaw 里说一句）："
echo "  \"用 follow-news skill 给我跑本周 AI 竞品监控周报\""
echo ""
echo "或命令行直接触发："
echo "  bash $SKILL_DST/scripts/ai-pulse/weekly.sh"
echo "=================================================="

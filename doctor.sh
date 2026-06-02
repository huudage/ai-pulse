#!/usr/bin/env bash
# AI Pulse — 配置体检
#
# 读 .env，报告哪些功能已就绪、哪些缺 key，并给出申请链接
#
# 用法：
#   bash doctor.sh

set -e

THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 加载 .env
if [ -f "$THIS_DIR/.env" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$THIS_DIR/.env"
    set +a
    echo "[配置] 已加载 $THIS_DIR/.env"
else
    echo "⚠️ 未找到 $THIS_DIR/.env"
    echo "   建议: cp .env.example .env && 然后填入你的 key"
    echo ""
fi

ok() { echo "  ✅ $1"; }
warn() { echo "  ⚠️  $1"; }
fail() { echo "  ❌ $1"; }

echo ""
echo "=================================================="
echo "AI Pulse 体检"
echo "=================================================="

# ───────────────────────────────────────────
echo ""
echo "▶ GitHub (官方 release 监控)"
if [ -n "$GITHUB_TOKEN" ]; then
    ok "GITHUB_TOKEN 已配置 (5000 req/h)"
else
    fail "GITHUB_TOKEN 未配置"
    echo "     ↳ 不配会导致 GitHub release 全失败 (匿名 60 req/h，22 个 repo)"
    echo "     ↳ 免费申请: https://github.com/settings/tokens (classic, 不勾任何 scope)"
fi

# ───────────────────────────────────────────
echo ""
echo "▶ Web 搜索 (Tavily / Brave)"
if [ -n "$BRAVE_API_KEYS" ] || [ -n "$BRAVE_API_KEY" ]; then
    ok "Brave API 已配置 (2000 query/月 免费)"
elif [ -n "$TAVILY_API_KEY" ]; then
    ok "Tavily API 已配置 (1000 query/月 免费)"
else
    warn "无 Web 搜索 API key (Web 这一路 0 items)"
    echo "     ↳ Brave 免费: https://brave.com/search/api/  (2000 query/月，无信用卡)"
    echo "     ↳ Tavily 免费: https://app.tavily.com/  (1000 query/月)"
fi

# ───────────────────────────────────────────
echo ""
echo "▶ Twitter / X"

# 优先检测 OpenCLI（首选方案）
if command -v opencli >/dev/null 2>&1; then
    OPENCLI_BIN_PATH="$(command -v opencli)"
    ok "OpenCLI 二进制已装: $OPENCLI_BIN_PATH"
    # 检查 daemon + extension 状态
    if doctor_out=$(opencli doctor 2>&1); then
        if echo "$doctor_out" | grep -q "Everything looks good"; then
            ok "OpenCLI 状态: 完全就绪（daemon + extension + 浏览器连接）"
            echo "     ↳ 推荐 .env 设 TWITTER_API_BACKEND=opencli, OPENCLI_MAX_WORKERS=3"
        elif echo "$doctor_out" | grep -q "Extension: not connected"; then
            warn "OpenCLI daemon OK，但 Chrome 扩展未连接"
            echo "     ↳ 装扩展: chrome://extensions/ → Developer mode →"
            echo "       Load unpacked → 选 opencli release 里的 extension/ 文件夹"
        else
            warn "OpenCLI 有问题，跑 'opencli doctor' 看详情"
        fi
    else
        warn "opencli doctor 执行失败"
    fi
elif [ -n "$OPENCLI_BIN" ] && [ -x "$OPENCLI_BIN" ]; then
    ok "OPENCLI_BIN 已配置: $OPENCLI_BIN"
else
    warn "OpenCLI 未安装（Twitter 没数据）"
    echo "     ↳ 推荐方案（零成本）: https://github.com/jackwener/opencli/releases"
    echo "     ↳ 详细步骤见 .env.example 里的 Twitter 段"
fi

# 检查付费 API（备选）
if [ -n "$X_BEARER_TOKEN" ] || [ -n "$GETX_API_KEY" ] || [ -n "$TWITTERAPI_IO_KEY" ]; then
    ok "follow-news Twitter API key 已配置（备选方案）"
fi

echo "     当前后端选择: TWITTER_API_BACKEND=${TWITTER_API_BACKEND:-auto}"
echo "     当前并发上限: OPENCLI_MAX_WORKERS=${OPENCLI_MAX_WORKERS:-10}"
if [ "${OPENCLI_MAX_WORKERS:-10}" -gt 5 ] 2>/dev/null; then
    warn "OPENCLI_MAX_WORKERS 偏高，并发过高容易触发超时"
    echo "     ↳ 建议设为 3 以提高成功率"
fi

# KOL 博客状态（独立于 Twitter）
echo ""
echo "▶ AI KOL 博客（独立补充信源）"
if [ "${ENABLE_KOL_BLOGS:-true}" = "true" ]; then
    ok "KOL 博客已启用（11 个：Simon Willison / Latent Space / Ethan Mollick 等）"
else
    warn "KOL 博客已禁用 (ENABLE_KOL_BLOGS=false)"
fi

# ───────────────────────────────────────────
echo ""
echo "▶ 代理 (按需，国内访问 reddit/github/twitter)"
if [ -n "$HTTPS_PROXY" ] || [ -n "$HTTP_PROXY" ]; then
    ok "代理已配置: ${HTTPS_PROXY:-$HTTP_PROXY}"
else
    echo "  (未配置 — 如果国内访问 reddit/github 慢，可在 .env 设 HTTPS_PROXY)"
fi

# ───────────────────────────────────────────
echo ""
echo "▶ Python UTF-8 模式"
if [ "$PYTHONUTF8" = "1" ]; then
    ok "PYTHONUTF8=1 (Windows GBK 修复已就位)"
else
    warn "PYTHONUTF8 未设为 1 (Windows 上会有编码问题)"
    echo "     ↳ 把 .env.example 复制为 .env 即可，里面已有这两行"
fi

# ───────────────────────────────────────────
echo ""
echo "=================================================="
echo "总结"
echo "=================================================="

# 计算分数
score=0
max=4

if [ -n "$GITHUB_TOKEN" ]; then
    score=$((score+1))
fi
if [ -n "$BRAVE_API_KEYS" ] || [ -n "$BRAVE_API_KEY" ] || [ -n "$TAVILY_API_KEY" ]; then
    score=$((score+1))
fi
# Twitter: OpenCLI 完全就绪 OR 配了 KOL 博客 OR 配了 X API
if command -v opencli >/dev/null 2>&1 && opencli doctor 2>&1 | grep -q "Everything looks good"; then
    score=$((score+1))
elif [ "${ENABLE_KOL_BLOGS:-true}" = "true" ] || [ -n "$X_BEARER_TOKEN" ]; then
    score=$((score+1))
fi
if [ "$PYTHONUTF8" = "1" ]; then
    score=$((score+1))
fi

echo "  $score / $max 项配置完成"

if [ "$score" -ge 3 ]; then
    echo ""
    echo "  ✨ 准备好跑周报了"
    echo ""
    echo "  下一步: bash scripts/weekly.sh"
elif [ "$score" -ge 1 ]; then
    echo ""
    echo "  部分功能就绪。建议至少补上 GITHUB_TOKEN (最关键)。"
else
    echo ""
    echo "  ⚠️ 几乎都没配。复制 .env.example → .env，至少填 GITHUB_TOKEN。"
fi

echo "=================================================="

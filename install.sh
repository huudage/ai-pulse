#!/usr/bin/env bash
# install.sh — 兼容别名（已废弃 clone+patch 流程）
#
# ai-pulse 现在是自包含独立 skill：follow-news 引擎 vendored 进 follow-news-addons/，
# TrendRadar vendored 进 trendradar/。不再 clone/patch 上游。
#
# 本脚本仅为向后兼容保留：转发给 setup.sh（pip-only 本地化安装）。
# 历史的 --target 参数已无意义（无外部安装目录），传入会被忽略并提示。
#
# 请改用：bash setup.sh [--skip-deps]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 过滤掉已废弃的 --target DIR（吞掉它的参数值），其余原样转发给 setup.sh
FORWARD=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --target)
            echo "⚠️ install.sh 的 --target 已废弃（ai-pulse 现为自包含仓库，无外部安装目录）。忽略：--target $2"
            shift 2
            ;;
        *)
            FORWARD+=("$1")
            shift
            ;;
    esac
done

echo "ℹ️ install.sh 已废弃，转发给 setup.sh ..."
exec bash "$SCRIPT_DIR/setup.sh" "${FORWARD[@]}"

# Contributing to AI Pulse

## 如果你只是想用，看 [README.md](README.md)

下面是给项目维护者 / PR 贡献者看的。

---

## 仓库设计

ai-pulse 是一个**整合层**，自身不做大量计算。核心抽象是：

| 概念 | 实现 |
|---|---|
| 上游不动 | 我们用 `git apply patches/*/upstream.patch` 应用修改，pin 在固定 SHA 保证稳定 |
| 上游可控加料 | 我们用 `*-addons/` 目录里的"add-only"文件复制到上游 |
| 用户配置外置 | follow-news 的 workspace 配置由 install.sh 自动渲染（占位符替换）|
| 一键安装/验证 | `install.sh` 编排所有上面的事情 |

---

## 开发常见任务

### 任务 A：上游发了新版本，我想升级

1. **先在你本地把上游升级**：
   ```bash
   cd ../upstream/TrendRadar
   git fetch origin && git checkout main && git pull
   # 看新 SHA
   git rev-parse HEAD
   ```

2. **重新 rebase 我们的 addons**（应用旧 patch 看会不会冲突）：
   ```bash
   git apply ../../ai-pulse/patches/trendradar/upstream.patch
   # 如果失败，根据冲突手动改，然后跑测试
   ```

3. **改完测试通过后，重新生成 patch**：
   ```bash
   cd ../upstream/TrendRadar
   git diff config/config.yaml \
            trendradar/__main__.py \
            trendradar/core/loader.py \
            trendradar/report/__init__.py \
            trendradar/report/formatter.py \
     > ../../ai-pulse/patches/trendradar/upstream.patch
   ```

4. **更新 `install.sh` 里的 PIN SHA**：
   ```bash
   # 编辑 install.sh
   PINNED_TRENDRADAR_SHA="<新 SHA>"
   ```

5. **完全干净环境测试 install.sh**：
   ```bash
   rm -rf ../upstream-test
   bash install.sh --target ../upstream-test
   bash verify.sh --target ../upstream-test
   ```

6. **commit + PR**：
   - patches 改动
   - install.sh 的 SHA 改动
   - 必要时改 README 说明上游兼容版本

follow-news 同理，文件清单不一样：
- `SKILL.md`
- `scripts/fetch-rss.py`
- `scripts/run-pipeline.py`

### 任务 B：添加新平台到中文评论抓取

例如加微博。`trendradar-addons/crawler/comments/` 下加 `weibo.py`，照 `bilibili.py` 的格式实现 `WeiboCommentFetcher`，然后在 `dispatcher.py` 的 `PLATFORM_REGISTRY` 注册：

```python
PLATFORM_REGISTRY: Dict[str, Type[CommentFetcher]] = {
    "zhihu": ZhihuCommentFetcher,
    "bilibili-hot-search": BilibiliCommentFetcher,
    "weibo": WeiboCommentFetcher,  # ← 新增
}
```

最后改 `trendradar-addons/config-snippets/comments.yaml` 的 platforms 列表。

### 任务 C：改 Tier 1 厂商白名单

**两处必须同步改**：

1. `follow-news-addons/scripts/weekly-feedback.py` 的 `TIER1_VENDOR_PATTERNS` 列表 — 这是程序启发式预标签
2. `follow-news-addons/references/prompts/competitor-monitor.md` 的"Tier 1 评级规则"段 — 这是给 OpenClaw agent 看的

如果只改一处，会出现：脚本预标签是 Tier 1，agent 看 prompt 觉得不该是 Tier 1（或反过来），最终行为不可预期。

### 任务 D：改 OpenClaw 路由触发条件

OpenClaw 路由 5（"Weekly competitor monitor digest"）和路由 6（"Topic feedback search"）都写在 `patches/follow-news/upstream.patch` 里，对应上游 `SKILL.md` 的修改。

修改步骤：
1. 在 `../upstream/follow-news/SKILL.md` 改路由 5 / 6 的触发词或命令模板
2. 按"任务 A"的步骤重新生成 `patches/follow-news/upstream.patch`

### 任务 E：调主题反馈检索（topic-feedback）

`topic-feedback.py` 是单主题的 4 路并发社区检索（HN / Reddit / Twitter / TrendRadar 中文），由路由 6 触发。零 LLM key 设计：脚本只做机械搜索，所有语义工作（关键词提取、观点分类、翻译）由 OpenClaw agent 按 `topic-feedback.md` 完成。

常见调整场景：

1. **Reddit AI 加权 sub 列表** — `follow-news-addons/scripts/topic-feedback.py` 的 `REDDIT_AI_SUBS` 集合。新加 sub 名直接加进去，加权倍数（×1.3）写死在 `search_reddit` 里
2. **HN 搜索的 story / 评论数量** — 同文件 `search_hn` 函数：默认拉 15 个 story、对前 3 个抓 top 3 评论。改这两个常量看 prompt 数据契约段是否要同步说
3. **TrendRadar SQLite 检索窗口** — 默认 last 7 个 db 文件（`search_trendradar(query, dir, days=7)`）。改成更长会稳但更慢
4. **加新源**（例如 Mastodon、bluesky）：
   - 在 `topic-feedback.py` 里加 `search_mastodon(query, days)` 函数，返回 `{"status": ..., "count": ..., "results": [...]}`
   - 在 `main()` 的 `workers` dict 里注册新 worker
   - 在 `render_markdown()` 里加新源章节
   - **同时改** `follow-news-addons/references/prompts/topic-feedback.md` 的"输入数据契约"段，列出新源 JSON shape，否则 agent 不知道怎么读

5. **改 Twitter 抓取策略**（当前是 best-effort 探测 `opencli twitter --help`）：如果上游 opencli 加了 `twitter search` 子命令，把 `search_twitter` 里的 `subprocess.run(['opencli', 'twitter', '--help'])` 探测改为直接调用即可。如果改成浏览器抓取，注意保留 `status: "skipped: ..."` 的回退路径

⚠ 跟"任务 C"一样的同步纪律：脚本行为和 prompt 描述必须同步改，否则 agent 行为不可预期。

---

## 测试 patch 是否仍然干净

测试 patches 在新 clone 的上游上能不能干净 apply：

```bash
mkdir /tmp/test-trendradar
cd /tmp/test-trendradar
git clone https://github.com/sansan0/TrendRadar.git
cd TrendRadar
git checkout <PINNED_TRENDRADAR_SHA>
git apply --check $AI_PULSE_DIR/patches/trendradar/upstream.patch
echo $?  # 0 = 干净，可以应用；非 0 = 冲突
```

---

## 仓库不收什么

- `upstream/` — install.sh 克隆的上游仓
- `.ai-pulse-backup/` — 安装时的备份文件
- `__pycache__/` — Python 缓存
- 用户私有 workspace 数据
- TrendRadar 的 `output/` 数据库

详见 `.gitignore`。

---

## 提 PR 之前

- [ ] 跑 `bash install.sh --target /tmp/test-install`
- [ ] 跑 `bash verify.sh --target /tmp/test-install`
- [ ] 跑 `cd /tmp/test-install/follow-news && python3 scripts/weekly-feedback.py --help` 看新 flag 是否齐全
- [ ] 跑 `cd /tmp/test-install/follow-news && python3 scripts/topic-feedback.py --help` 看新 flag 是否齐全
- [ ] 如果改了 Tier 规则，确认两处都改了
- [ ] 如果改了 patch，确认 PINNED SHA 有更新

提交时 commit message 格式建议：
```
[scope] short summary

Detailed why/what.
```

scope 比如：`patches/trendradar`、`addons/comments`、`scripts`、`docs`、`install`。

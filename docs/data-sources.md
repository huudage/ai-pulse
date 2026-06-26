# 信源完整清单（共 165+ 个）

按数据通路分两端：**TrendRadar 端**（中文社区） + **follow-news 端**（英文社区 + 全球深度）。

---

## A. TrendRadar 端 — 11 个中文热榜

通过 NewsNow 聚合 API（`https://newsnow.busiyi.world/api/s`）抓取，**经 AI 关键词过滤**后只保留 AI 相关条目。

| ID | 显示名 | 类型 | 评论抓取 |
|---|---|---|---|
| `toutiao` | 今日头条 | 综合热搜 | ❌ |
| `baidu` | 百度热搜 | 综合热搜 | ❌ |
| `wallstreetcn-hot` | 华尔街见闻 | 财经资讯 | ❌ |
| `thepaper` | 澎湃新闻 | 综合新闻 | ❌ |
| `bilibili-hot-search` | B站热搜 | 视频社区 | ✅（搜索→Top视频→评论）|
| `cls-hot` | 财联社热门 | 财经资讯 | ❌ |
| `ifeng` | 凤凰网 | 综合新闻 | ❌ |
| `tieba` | 贴吧 | 论坛 | 🟡（暂未实现）|
| `weibo` | 微博 | 社交热搜 | 🟡（需 cookie，暂未实现）|
| `douyin` | 抖音 | 视频社区 | ❌（反爬强）|
| `zhihu` | 知乎 | 问答社区 | 🟡（需 cookie，未默认启用）|

**AI 关键词过滤**：见 [trendradar-addons/keywords/ai_focus.txt](../trendradar-addons/keywords/ai_focus.txt)，覆盖以下分组：
- 大模型公司海外（OpenAI / Anthropic / DeepMind / Meta / Mistral / xAI / Hugging Face / Perplexity / Microsoft Copilot / Stable Diffusion 类）
- 大模型公司国产（DeepSeek / Qwen / 智谱 GLM / MiniMax / Kimi / 百川 / 文心 / 盘古 / 混元 / 豆包 / 讯飞星火 / 阶跃星辰）
- AI 算力（NVIDIA / AMD / 华为昇腾 / Groq / Cerebras / 国产 AI 芯片）
- AI Agent 应用（Cursor / Devin / Claude Code / Aider / Windsurf / ComfyUI / LangChain / vLLM / Ollama）
- AI 通用概念（AI / 人工智能 / 大模型 / LLM / AGI / RAG / MCP / 多模态 / RLHF）
- 具身智能（宇树 / 智元 / 众擎 / Figure AI / Optimus）
- 自动驾驶（FSD / Waymo / 智驾 / 端到端）
- AI 监管

输出：`output/rss/ai_focus.xml`（Atom XML，每个 entry 含标题/链接/排名/评论）

---

## B. follow-news 端 — 154+ 个全球信源

### B.1 RSS — 65 个（部分代表）

| 类别 | 代表来源 |
|---|---|
| AI 公司官方 | OpenAI Blog、Anthropic、Google AI、Hugging Face、Meta AI、Stability AI |
| 研究/博客 | Simon Willison、Andrej Karpathy 博客、distill.pub、Lil'Log |
| 聚合站 | Hacker News、Lobsters、AI News by Smol |
| 中文科技媒体 | 36 氪、雷锋网、机器之心、量子位 |
| 财经/产业 | The Information、Bloomberg AI、TechCrunch |

完整列表在 follow-news 仓的 `config/defaults/sources.json` 中，按 `"type": "rss"` 过滤。

### B.2 Twitter/X — 68 个（部分代表）

| 类别 | 代表账号 |
|---|---|
| OpenAI 系 | @sama、@gdb、@miramurati |
| Anthropic 系 | @darioamodei、@karpathy（前 OpenAI 现 Anthropic）|
| 研究者 | @ylecun、@jeffdean、@DemisHassabis、@AndrewYNg |
| VC/创业者 | @paulg、@garrytan、@brian_armstrong |
| 中文 | @dotey、@op7418、@aiwanderer |
| Agent/Builder | @amasad、@PatrickCollison |
| 国产竞品官方 | @deepseek_ai、@Kimi_Moonshot、@alibaba_qwen、@MiniMax_AI、@Zai_org、@StepFun_ai、@manusai（均联网核实官方 handle） |

**抓取后端推荐**：OpenCLI（复用浏览器登录态，零鉴权），fallback 到 GetXAPI / twitterapi.io / 官方 X API。

### B.3 GitHub Release 监控 — 23 个仓库

| 类别 | 代表仓库 |
|---|---|
| 训练/推理框架 | vllm-project/vllm、ggerganov/llama.cpp、microsoft/DeepSpeed、sgl-project/sglang |
| Agent 框架 | langchain-ai/langchain、microsoft/autogen、crewAIInc/crewAI |
| 模型仓库 | meta-llama/llama、deepseek-ai/DeepSeek-V3、QwenLM/Qwen |
| Agent 产品 | continuedev/continue、cline/cline |
| 工具链 | ollama/ollama、huggingface/transformers |

完整列表在 `config/defaults/sources.json` 按 `"type": "github"` 过滤。

### B.4 Web 搜索 — 6 主题

通过 Tavily 或 Brave Search API（需 API key），按主题词搜索，**带时效过滤**（默认 24h）：

| 主题 ID | 关键词 |
|---|---|
| `llm` | LLM, Claude, Gemini, GPT, foundation model |
| `ai-agent` | autonomous agent, AI agent framework, agentic AI |
| `builder` | AI startup, AI builder, founder |
| `kol` | AI keynote, AI thought leader |
| `frontier-tech` | AI policy, AI governance, AI safety, AI regulation |
| `podcast` | AI podcast episode |

### B.5 播客 — 自定义

支持 RSS 播客订阅源 + YouTube 播放列表/频道。可选 `yt-dlp` 抓元数据和转录文本。

### B.6 TrendRadar 中文 RSS（旁路注入）— 1 个

通过 `workspace/config/follow-news-sources.json` 注册，URL 为 `file:///path/to/TrendRadar/output/rss/ai_focus.xml`，topics 标记为 `["llm", "frontier-tech"]`、`priority: true`（质量评分 +3）。

---

## C. Tier 1 厂商白名单（35+ 个，影响周报分级）

固化在 [follow-news-addons/scripts/weekly-feedback.py](../follow-news-addons/scripts/weekly-feedback.py) 的 `TIER1_VENDOR_PATTERNS` + [follow-news-addons/references/prompts/competitor-monitor.md](../follow-news-addons/references/prompts/competitor-monitor.md) 里。

**改厂商范围时两处都要同步改**。

| 维度 | Tier 1 厂商 |
|---|---|
| 海外闭源模型 | OpenAI、Anthropic、Google DeepMind、xAI |
| 海外开源模型 | Meta（Llama）、Mistral |
| 国内大模型 | DeepSeek、Qwen、Kimi/Moonshot、智谱 GLM、MiniMax、阶跃星辰 |
| Agent 产品 | Cursor、Devin、Claude Code、GitHub Copilot、Windsurf |
| 算力基础设施 | NVIDIA（Blackwell/Hopper）、AMD（MI 系列）、华为昇腾 |

---

## D. 总数计算

```
TrendRadar:      11 个中文平台
follow-news:     64 RSS + 68 Twitter + 23 GitHub + 6 Web 主题 + 6 播客
                 = 167 个
TrendRadar RSS（注入 follow-news）: 1 个
────────────────────────────────
合计:            179 个信源
```

每天大致经过：**抓取 → 去重 → 多源加分 → topic 分组**，输出约 400-500 篇文章（视当日热度）。

经过 **AI 关键词过滤 + Tier 启发式** 后，进入周报视野的通常是 **20-60 篇 announcement**，其中 Tier 1 通常 **3-10 篇**，每篇配 ≤5 个 reactions + Tier 1 额外的 HN/V2EX 评论原文。

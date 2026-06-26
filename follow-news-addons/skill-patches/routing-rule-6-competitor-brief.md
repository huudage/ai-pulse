6. **On-demand competitor brief（按需竞品调研）**
   - When user asks to research a specific domestic agent product or industry, e.g.
     "调研一下通义灵码 / Trae / Manus 最近在做什么"、"<竞品> 最新动态/方向"、
     "<行业>（金融/医疗/教育/政务/电商/制造/法律/内容媒体）有哪些 agent 竞品在布局".
   - This is product/industry-scoped (NOT the weekly community digest, NOT single-topic
     community feedback). It pulls each tracked product's **official** updates and
     (when available) KOL industry/role content, then asks you to synthesize 方向/场景.
   - Execute (产品维度，--product 与 --industry 互斥)：
     ```bash
     PYTHONUTF8=1 python3 scripts/competitor-brief.py \
       --product "通义灵码" \
       --profiles workspace/config/competitor-profiles.json \
       --window-days 30 \
       --out-json /tmp/competitor-brief.json --out-md /tmp/competitor-brief.md
     ```
     行业维度改用 `--industry "金融"`（取值须在骨架字典内）。
   - **CRITICAL — Read `references/prompts/competitor-brief.md` first and follow it strictly.**
     That template defines the report structure, the 官方动态三要素（类型+标题+链接），the
     方向/场景 synthesis（必须标注"推断"），and the data contract. Do not improvise links.
   - `updates` 与 `kol_contents` 都为空时脚本写"暂无足够数据"——照实告知用户并建议放宽
     `--window-days` 或补全 `workspace/config/competitor-profiles.json` 的 official_sources。
   - KOL 采集依赖 005 抓取器，未就绪时 `kol_contents` 为空 → 跳过 KOL 小节，不报错、不编造。
   - 竞品清单与官方源配置在 `workspace/config/competitor-profiles.json`（install.sh 已复制骨架）。

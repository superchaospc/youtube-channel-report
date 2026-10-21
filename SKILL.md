---
name: youtube-channel-report
description: >-
  Analyze a YouTube creator end to end and deliver a data-backed Chinese PowerPoint report in two formats — a 16:9 landscape deck and a 9:16 portrait (竖屏/竖版) deck for vertical screens and phones: exact per-video
  views (long videos vs Shorts), revenue estimated from RPM or back-calculated from income the creator disclosed,
  monthly and per-video income in USD/CNY, the top-10 videos and what each earned, topic popularity vs. how often
  each topic is filmed, upload cadence over time, the creator's account matrix (sub-channels, TikTok, Instagram,
  Buy Me a Coffee tips), and how they film — shooting styles counted from frames plus the likely camera / mic
  setup (拍摄器材, 用什么拍, 拍摄方式). Use this WHENEVER the user wants to 分析/拆解 a YouTube 频道 or 博主, asks how much a
  channel earns (赚了多少钱, 收入估算, 月入, 每个视频赚多少, RPM 多少, 反推 RPM), wants views without Shorts
  (去掉 shorts 的播放), the most-viewed videos and their earnings, 题材分析, 更新频率, 拍摄器材 / 用什么设备拍, or a 频道分析 PPT / 竖屏 PPT / 报告 /
  数据统计 — even if they only paste a channel URL like youtube.com/@xxx and ask about money. Also use it to
  extend or restyle a report this skill made before. NOT for downloading videos or subtitles (yt-dlp-download),
  not for a single video's content summary, and not for comment-only keyword studies.
---

# YouTube 频道分析报告

把一个 YouTube 频道（或一个博主的整套账号）做成有数据支撑的中文 PPT：播放、收入、爆款、题材、更新频率、账号矩阵。脚本负责抓数和算数，AI 负责判断（RPM 用多少、题材怎么分、标题翻译、结论和启示）。

所有脚本都在本 skill 的 `scripts/` 目录，下文用 `$S` 指代它。

## 流程

### 1. 建工作目录，抓数据

```bash
W=~/youtube-<handle>-report-$(date +%F); mkdir -p $W
python3 $S/fetch_channel.py @handle --out $W/data
```

- 每个频道生成 `about.json`（订阅、总播放、建号日期、简介里的外链）、`long.json`、`shorts.json`（每条视频的**精确播放**和**发布日期**）。
- 看输出里的完整性校验：长视频 + Shorts 的播放之和应接近频道总播放（95%–102% 都正常）。差太多先查原因，再往下做。
- **副频道**：看 `about.json` 的外链，或者用频道名搜 “X Eats / X Vlog / X Shorts”，也一起抓下来。
- 抓不到、被 YouTube 判定为机器人、日期有疑问时，读 `references/data-gotchas.md`。

### 2. 账号矩阵（可选，有其他平台时做）

```bash
python3 $S/social_stats.py --tiktok <handle> --bmc <slug>
```

Instagram 用 curl 抓不到，要用浏览器工具打开 `instagram.com/<handle>/`，读取 `og:description`（例如 “218K Followers, 97 Posts”）。数字写进 config 的 `accounts`。

### 2b. 拍摄器材和拍摄方式（可选，用户问器材、或者报告要讲“怎么拍”时做）

```bash
python3 $S/gear_scan.py $W/data/<handle> --out $W/gear      # 本机被 YouTube 拦截时加 --proxy socks5://…
```

这个脚本会扫描简介和评论里的器材线索，下载截帧拼成联系表，并读取分辨率和帧率。然后**一张张看联系表**，逐帧统计拍摄方式（手持自拍 / 固定机位 / 第一视角 / 车载 / 别人帮忙拍），把结论写进 `gear.json`，再在 config 里加 `"gear": "gear.json"`。做法和写法要求见 `references/gear.md`。型号只能写“类似 X”，每一条都要标明是“有证据”还是“推断”。

### 3. 定 RPM

优先级如下：
1. 用户给了 RPM 就用。
2. 频道主公开过累计收入，就**反推**：在 config 里写 `disclosure`，并让主频道 `"rpm": "backcalc"`。
3. 都没有，就按 `references/rpm-and-income.md` 的默认表选，并在回复里说明这是假设。

用户给了一个 RPM 区间（比如 5–7）时，分别算两端和中值，结论用中值。汇率默认实时获取。

### 4. AI 补两份文件

- `titles_zh.json`：`{视频ID: 中文标题}`。把主频道全部长视频的标题，以及副频道前 3 条的标题，翻成简洁自然的中文。
- `topics.json`：`{题材: [视频ID…]}`。把主频道长视频按标题人工分成 6–10 类，每条只归一类。题材名要具体到能当选题用，比如“低收入与省钱”，不要写成“生活”。

### 5. 写 config，跑计算

字段说明见 `references/config.md`。最小配置只要 `channels`：

```json
{"title": "XX 频道分析", "channels": [{"data": "data/handle", "label": "主频道", "rpm": 5}]}
```

**只有一个频道时不要叫“主频道”**（用户明确要求）：`label` 写 `"YouTube"`；跑完计算后把 `deck.json` 里的“主频道长视频”改成“长视频”、“YouTube 主频道”改成“YouTube 频道”、“主频道平均每条”改成“平均每条”，其余“主频道”也一并改掉，最后 `grep 主频道 out/deck.json` 确认一处都不剩。有副频道时才用“主频道 / 副频道”。

```bash
python3 $S/compute_report.py $W/config.json
```

输出到 config 的 `out` 目录：
- `report.md`：中文摘要表。
- `numbers.json`：所有计算结果。
- `<频道>_long.csv`：逐条明细，含中文标题、题材和收入，用 Excel 打开不会乱码。
- `deck.json`：PPT 初稿，有 10–16 页，没有数据的部分自动省略。

**用户只问数字、不要 PPT 时**，到这一步就结束，按 `report.md` 回答，并说明假设。

### 6. 加叙述页（可选）

`deck.json` 是一个页面列表，可以直接编辑：改标题和结论、删页、调顺序，或者插入自定义页。常见的自定义页有“给我们的启示”、“哪些人可以拍”、“还可以拍哪些题材”、“如何开始”、“开通 YPP 的门槛”、“起步建议”。用户给了提纲时，按提纲的顺序排。

各种页面类型和字段见 `references/deck-json.md`。写结论时要给出证据，比如数字、代表视频、评论里反复出现的说法。没有数据支撑的建议，要标明是建议。

### 7. 生成 PPT 并检查（横版、竖版各一份）

**每次都交付两份 PPT**（用户要求）：16:9 横版，和 9:16 竖版（竖屏播放、手机上看）。两份用同一份 `deck.json`，改内容只改 deck.json，然后两份一起重新生成，不要只更新其中一份。

```bash
$S/build_decks.sh $W/out/deck.json $W "<标题>"
```

这一条命令会依次：
1. 第一次运行时自动装 pptxgenjs；
2. 用 `build_deck.js` 生成横版 `<标题>.pptx`；
3. 用 `build_deck_portrait.js` 生成竖版 `<标题>-竖屏.pptx`（7.5×13.33 英寸，每种页面都重新上下排版，字号放大，表格、卡片、图表自动撑满屏幕）；
4. 用 Keynote 把两份都渲染成图片（`png/`、`png-portrait/`），并各导出一份 PDF。

只想单独重做某一份时：

```bash
NODE_PATH=~/.cache/ycr-node/node_modules node $S/build_deck.js $W/out/deck.json "$W/<标题>.pptx"
NODE_PATH=~/.cache/ycr-node/node_modules node $S/build_deck_portrait.js $W/out/deck.json "$W/<标题>-竖屏.pptx"
$S/render_check.sh "$W/<标题>.pptx" $W/png --pdf            # macOS + Keynote
```

检查要求：
- 两个脚本都会打印 `WARN … may not fit` / `content runs to …`，提示哪页文字放不下或超出底部。把对应文字改短，或者换个字段放。
- 两份都要看渲染图（`sheet-N.png`，或把 png 拼成联系表），检查文字溢出、重叠、折行压到下一行，竖版再看页面下方有没有大片空白。改完只需重渲染、复查改过的页。
- **竖版专用字段**（写在 deck.json 的对应页上，横版会忽略）：
  - `"portrait": {...}`：只在竖版里覆盖该页的字段。4 列以上的宽表格在竖屏里太挤，用它只保留关键列，例如 `"portrait": {"columns": [...], "rows": [...]}` 去掉美元列、代表标题列。
  - `"portrait": false`：这一页不进竖版。
  - `title_portrait`：手动给竖版标题断行（`\n`）。默认会在中文标点（：，、—）处自动断行，避免末行只剩一个字；数字里的英文逗号不会被断开。
  - 封面 `title_size_portrait`：竖版封面标题字号，不填时自动选能放下的最大字号。

### 8. 交付

- 工作目录里放：横版 `.pptx` + PDF、竖版 `-竖屏.pptx` + PDF、CSV、`report.md`，然后用 `open -R <横版 pptx>` 在 Finder 里定位。
- 回复里讲清楚三件事：
  1. 核心数字：累计、月均、每条，以及主频道的 RPM。
  2. 用了哪些假设：RPM、汇率、计算月均的起点、哪些平台没算进收入。
  3. 加了哪些提纲以外的页面；竖版里删掉了哪些表格列。
- 要发给别人时，发 PDF。PPT 用的是 Mac 字体（宋体/苹方），在 Windows 上打开会被替换成别的字体。

## 口径（每次都一样，别临时改）

- **长视频和 Shorts 分开算**：长视频按 RPM 算；Shorts 按每千次播放 0.10 美元算（可配置）。“去掉 Shorts”指收入和播放都不算 Shorts。
- **月均** = 累计收入 ÷ 月数。月数从主频道第一条长视频算到今天，用户给了别的起点就用用户的。
- **每条** = 长视频收入 ÷ 长视频条数。同时给出中位数，因为平均值常被爆款拉高。
- **会员和 Super Thanks** 不单独估算，反推出来的 RPM 里已经包含了它们。
- **日期用精确日期**，不要用频道页上的“10 months ago”换算。这种相对时间和日历月份对不上，用户按它数会数错。
- 题材分类、标题翻译、站外打赏的分档比例都是人工判断或假设，PPT 里要写明。

## 参考文件

- `references/data-gotchas.md`：抓数据时的坑，包括 innertube 字段变化、被判定为机器人时的绕法、精确时间戳、Instagram/TikTok。
- `references/rpm-and-income.md`：RPM 默认表、反推方法、Shorts、打赏手续费、汇率。
- `references/config.md`：config 的全部字段。
- `references/deck-json.md`：20 种页面类型和字段。
- `references/gear.md`：拍摄器材和拍摄方式怎么找证据、怎么归类、`gear.json` 的格式。

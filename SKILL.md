---
name: youtube-channel-report
description: >-
  Analyze a YouTube creator end to end and deliver a data-backed Chinese PowerPoint report in three files — a 16:9 landscape deck, a 9:16 portrait (竖屏/竖版) reading deck for phones, and a 9:16 portrait video deck that keeps the whole bottom free for the user's own 16:9 landscape facecam (视频制作版): exact per-video
  views (long videos vs Shorts), revenue estimated from RPM or back-calculated from income the creator disclosed,
  monthly and per-video income in USD/CNY, the top-10 videos and what each earned, topic popularity vs. how often
  each topic is filmed, upload cadence over time, the creator's account matrix (sub-channels, TikTok, Instagram,
  Buy Me a Coffee tips), who the creator is (人物背景: age, hometown, past jobs, family, how their background
  turns into topics, what top comments love about them), and how they film — shooting styles counted from frames plus the likely camera / mic
  setup (拍摄器材, 用什么拍, 拍摄方式). Use this WHENEVER the user wants to 分析/拆解 a YouTube 频道 or 博主, asks how much a
  channel earns (赚了多少钱, 收入估算, 月入, 每个视频赚多少, RPM 多少, 反推 RPM), wants views without Shorts
  (去掉 shorts 的播放), the most-viewed videos and their earnings, 题材分析, 更新频率, 人物背景 / 他是谁 / 家庭成员, 拍摄器材 / 用什么设备拍, or a 频道分析 PPT / 竖屏 PPT / 报告 /
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

### 2c. 多人协作分工（出镜、掌镜、故事核心不是同一个人时必做）

家庭、情侣、搭档类频道，用户最关心**分工**：谁出镜、谁拍、视频围着谁转，和单人自拍有什么不同。这时分工是报告主线（用户要求，2026-10-22）：

```bash
python3 $S/frame_sample.py $W/data/<handle> --out $W/collab --every 20
```

每 20 秒抽一帧拼联系表，逐帧记录画面里有谁、主角出镜时谁在拍，再用字幕统计旁白提到每个人的次数，写进 `collab/roles.json`，然后加一组“家庭协作”页面。和单人频道的对比，数据要取之前报告的 `gear.json`。做法和页面见 `references/collab.md`。

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

**人物背景（必做，不是可选）**（用户要求，2026-10-22；2026-10-23 起改为必做，之前有报告漏做）：只要频道以出镜人为核心（个人或家庭 vlog、讲自己经历的频道），就必须在“一页看懂”后面加一组 `section: "人物背景"` 的页面，交付前确认 deck.json 里有这一组：
1. “她/他是谁”（`cards`）：`statement` 写网名、年龄、哪里人、职业或几年级；6 张卡片写性格和特点。
2. “经历”（`rows`，最多 6 行）：按时间写入行前做什么、怎么开始拍、频道起量的节点。
3. “家人和身边人”（`cards`）：每位家人或关键人物一张（年龄、职业、在视频里做什么、出镜几条和播放），幕后帮忙拍的朋友也算。
4. “背景即题材”（`table`）：他的每段背景对应哪个题材、条数、平均播放，用数字说明观众最爱看哪一面。
5. “观众喜欢他什么”（`cards`）：高赞评论里反复出现的说法，`note` 写视频名和赞数。

怎么找料：把全部长视频的英文自动字幕下下来（`yt-dlp --skip-download --write-auto-subs --sub-langs en-orig`），用正则捞 “I'm 40 / my mom / divorced / I used to work / my hometown” 这类自述句；再抓 3 条代表作的高赞评论（`--write-comments --extractor-args "youtube:comment_sort=top;max_comments=40,all,0"`）。每一条都要出自视频简介、视频内容或高赞评论，卡片的 `note` 写出处。地域只写到省或城市，不写就读学校、详细地址、家人真名、离婚原因、健康状况这类隐私，出镜人是未成年人时尤其注意。横版每张卡片的 `body` 控制在约 20 个汉字，否则 3×2 排不下。`compliance_check.py` 对成年人也会拦“离婚 / 前妻 / 月入 / 第一笔”，改写成“恢复单身 / 结束的婚姻 / 工资每月约 / 后台收益”，前妻这类不出镜的人不单列卡片。

**起飞原因（必做）**（用户要求，2026-10-23）：频道有明显起量的拐点时（某个月播放比上个月翻好几倍），在“更新频率”后面加一组 `section: "起飞原因"` 的页面：
1. “发展历程”（`rows`）：按月写每个阶段拍什么、播放多少。
2. “两次起飞”（`table`）：每月新增播放（Social Blade）、发了几条、当月视频中位播放、当月最高的一条。
3. “拍法有没有变”（`three_cols`）：起飞前后各抽几条视频看帧，再看分辨率变化（`yt-dlp --print '%(height)sp' -f 'bv*'`），回答起飞是不是因为换了器材或拍法。
4. “做了哪些改变”（`lessons`，之前 vs 之后）：题材、开头第一句（看字幕前 300 字）、标题格式、封面，以及发片数量。
5. 封面前后对比（`images`）：起飞前后各 4 张。
6. 某个题材从背景变成主角时（比如外卖从“一天里顺带”变成“冒雨 12 小时”挑战），单独做一页对比。
7. 最近几条是不是又回到老路（`table`）：把起飞后的视频按标题分成两类，比平均播放，再列最近 6 条。

结论要写“时间上对得上，不一定是因果”，因为开通收益后平台推荐变多也可能起作用。

各种页面类型和字段见 `references/deck-json.md`。

**抖音 / 小红书合规**（用户要求）：竖版会发到抖音和小红书，deck.json 里所有文字都不能出现站外平台名（YouTube 写成“油管”）、@handle 和链接、导流 / 引流、翻墙、收益承诺（“赚了多少”写成“收益估算”）、极限词、未成年人家庭隐私、募捐。封面写明“收益为估算，不构成收益承诺”。`build_decks.sh` 会先跑 `compliance_check.py`，有命中就改到 clean 再交付。规则和改法见 `references/compliance.md`。

写结论时要给出证据，比如数字、代表视频、评论里反复出现的说法。没有数据支撑的建议，要标明是建议。

### 7. 生成 PPT 并检查（横版 + 竖屏阅读版 + 竖屏视频版）

**每分析一个频道，都交付三份 PPT**（用户要求，2026-10-22 起，固定规矩）：
1. 16:9 **横版**；
2. 9:16 **竖屏阅读版**：手机上看，不留窗口；
3. 9:16 **竖屏视频版**：用户录讲解视频用，底部整条留给 16:9 横屏自拍画面。

用户只说“做个 PPT”“出报告”，或者没提格式，也要三份一起交，不要只做其中一份，也不要先问要哪种。三份用同一份 `deck.json`，改内容只改 deck.json，然后三份一起重新生成，不要只更新其中一份。

**字体固定用苹果风**（用户要求，2026-10-23 起）：标题和正文都用苹方（PingFang SC），标题加粗。这是 `build_deck.js` 和 `build_deck_portrait.js` 的默认值，`deck.json` 的 `meta.fonts` 不用写；不要换回宋体。截帧拼图上自己加的说明字也用苹方：`fc-list | grep "PingFang SC"` 找到 PingFang.ttc，用 Pillow 按 `index` 选 SC 的字重（常见是 Semibold = 11）。

```bash
$S/build_decks.sh $W/out/deck.json $W "<标题>"
```

这一条命令会依次：
1. 第一次运行时自动装 pptxgenjs；
2. 用 `build_deck.js` 生成横版 `<标题>.pptx`；
3. 用 `build_deck_portrait.js` 生成竖屏阅读版 `<标题>-竖屏阅读版.pptx`（7.5×13.33 英寸，每种页面都重新上下排版，字号放大，表格、卡片、图表自动撑满屏幕；带 `--no-facecam`，即使 deck.json 写了 facecam 也不留窗口）；
4. 用 `build_deck_portrait.js --facecam` 生成竖屏视频版 `<标题>-竖屏视频版.pptx`（底部留 16:9 自拍区、顶部避开状态栏和灵动岛，见下文）；
5. 用 Keynote 把三份都渲染成图片（`png/`、`png-portrait/`、`png-facecam/`），并各导出一份 PDF。

只想单独重做某一份时：

```bash
NODE_PATH=~/.cache/ycr-node/node_modules node $S/build_deck.js $W/out/deck.json "$W/<标题>.pptx"
NODE_PATH=~/.cache/ycr-node/node_modules node $S/build_deck_portrait.js $W/out/deck.json "$W/<标题>-竖屏阅读版.pptx" --no-facecam
NODE_PATH=~/.cache/ycr-node/node_modules node $S/build_deck_portrait.js $W/out/deck.json "$W/<标题>-竖屏视频版.pptx" --facecam
$S/render_check.sh "$W/<标题>.pptx" $W/png --pdf            # macOS + Keynote
```

检查要求：
- 两个脚本都会打印 `WARN … may not fit` / `content runs to …`，提示哪页文字放不下或超出底部。把对应文字改短，或者换个字段放。
- 三份都要看渲染图（`sheet-N.png`，或把 png 拼成联系表），检查文字溢出、重叠、折行压到下一行，竖版再看页面下方有没有大片空白，视频版看 `png-facecam/preview/preview-N.png`（底部叠了 16:9 自拍占位、顶部模拟了时间、灵动岛、信号和返回 / 搜索键、两侧标出抖音裁掉的部分），确认内容没压进自拍区、两侧不贴边。改完只需重渲染、复查改过的页。
- **竖版专用字段**（写在 deck.json 的对应页上，横版会忽略）：
  - `"portrait": {...}`：只在竖版里覆盖该页的字段。4 列以上的宽表格在竖屏里太挤，用它只保留关键列，例如 `"portrait": {"columns": [...], "rows": [...]}` 去掉美元列、代表标题列。
  - `"portrait": false`：这一页不进竖版。
  - `title_portrait`：手动给竖版标题断行（`\n`）。默认会在中文标点（：，、—）处自动断行，避免末行只剩一个字；数字里的英文逗号不会被断开。
  - **视频版版式**（用户要求，2026-10-22 改）：用户把自己的 **16:9 横屏自拍**整条放在竖屏底部（2026-10-22 试过 21:9，用户最后定为 16:9），所以视频版：
    - **底部完全空出**：整宽 × 4.22 英寸（约下 32%，`meta.facecam_ratio` 可改比例），不放任何内容，页脚和页码也去掉，小字说明移进演讲者备注。
    - **页边距加大**：抖音按高度铺满会裁掉左右各约 0.37 英寸，右侧还有点赞列，所以左右边距 0.85 英寸（阅读版仍是 0.5），标题从 1.62 英寸往下排（见下一条）。
    - **顶部**：手机状态栏（时间、灵动岛、信号、电池）占顶部约 0–0.92 英寸，**什么都不放**。下面一行左边是抖音返回箭头、右边是放大镜（中心距顶约 1.26 英寸），这一行**不要空着**（空着很怪，用户要求）：把 eyebrow 小标题当成导航栏标题，放在箭头和放大镜中间、水平居中；页面标题紧接着从 1.62 英寸开始。不加色条，不放频道名（用户试过后明确不要，2026-10-22）。
    - **放不下就分页**：先按最小字号（约 86%）决定分几页，放不下的拆成同标题的续页（卡片、行、要点、表格行、图片、器材条目都会拆；卡片保持同样的列数，编号接着往下数）。图片缩到不足内容宽度约 70% 时也拆页，不出现小缩略图。只想在视频版删减文字时，在该页写 `"video": {...}` 覆盖字段。
    - **每页尽量填满**（用户要求，2026-10-22）：分好页后，每页各自挑能放下的最大字号——卡片、行、要点、表格这类随文字长高的页面最大到 140%；有固定高度色块的页面（数字方块、器材、图表、面板、编号列表、封面）最大到 110%，否则字会溢出色块。剩余的高度再均分给卡片和色块，让它们拉长到自拍区上方；只剩一个要点框时，框直接撑满，文字垂直居中。页面标题最多放大到 110%，导航行小标题固定 14 号，所以各页标题大小一致。
    - 阅读版不受影响。
  - 封面 `title_size_portrait`：竖版封面标题字号，不填时自动选能放下的最大字号。

### 8. 交付

- 交付前 `grep 人物背景 out/deck.json`：以出镜人为核心的频道必须有这一组页面（见第 6 步），没有就补上再生成。
- 工作目录里放：横版 `.pptx` + PDF、`-竖屏阅读版.pptx` + PDF、`-竖屏视频版.pptx` + PDF、CSV、`report.md`，然后用 `open -R <横版 pptx>` 在 Finder 里定位。
- 回复里讲清楚三件事：
  1. 核心数字：累计、月均、每条，以及主频道的 RPM。
  2. 用了哪些假设：RPM、汇率、计算月均的起点、哪些平台没算进收入。
  3. 加了哪些提纲以外的页面；竖版里删掉了哪些表格列。
- 要发给别人时，发 PDF。PPT 用的是 Mac 字体（苹方），在 Windows 上打开会被替换成别的字体。

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
- `references/collab.md`：多人协作频道的分工分析，包括抽帧、逐帧记录和对应页面。
- `references/compliance.md`：抖音 / 小红书合规规则、`compliance_check.py` 的命中怎么改。
- `references/gear.md`：拍摄器材和拍摄方式怎么找证据、怎么归类、`gear.json` 的格式。

# deck.json

`compute_report.py` 会生成一份初稿，`build_deck.js` 再把它变成 .pptx。可以直接编辑这个文件：改文字、删页、调顺序，或者插入下面的叙述页。

```json
{"meta": {"title": "Zaza 频道分析", "footer": "Zaza 频道分析 · 数据截至 2026-10-10",
          "fonts": {"head": "PingFang SC", "body": "PingFang SC"}},
 "slides": [ {"type": "cover", ...}, ... ]}
```

## 所有页面通用的字段

| 字段 | 作用 |
|---|---|
| `type` | 页面类型，见下文。 |
| `eyebrow` | 标题上方的小标签。 |
| `title` | 页面标题。单行最多约 22 个汉字，超出会被提示。 |
| `bg` | 填 `"alt"` 用米色底，默认是浅色底。相邻两页最好交替使用。 |
| `section` | 从这一页起开始一个新的分节（显示在 PowerPoint 的大纲里）。 |
| `note` | 页面底部的一行说明。 |
| `notes` | 演讲者备注。 |

颜色字段可以写名字或十六进制。可用的名字有：`accent`（砖红）、`accentLight`（浅红）、`blue`、`lightBlue`、`muted`（灰褐）、`gray`、`ink`（深色）、`paper`、`paper2`。

字体默认是苹果风：标题和正文都用 Mac 自带的苹方（PingFang SC），标题加粗（用户要求，2026-10-23）。不要再换回宋体；用户另有要求时才在 `meta.fonts` 里改。要发给 Windows 用户，最好导出成 PDF。

## 数据页（compute_report 会自动生成）

| type | 字段 |
|---|---|
| `cover` | `eyebrow` `title` `title_size`（可选。默认自动选能让每行放下的最大字号，54→32；用 `\n` 手动分行）`subtitle` `kpi{label,value,sub}` `meta` |
| `kpis` | `tiles[{value,label,desc,dark}]`（最多 4 个）、`findings[{title,text}]`（最多 3 个） |
| `accounts` | `accounts[{platform,name,value,unit,detail,highlight}]`（最多 5 个） |
| `disclosure` | `amount` `amount_sub` `caption` `parts_title` `parts[]`（最多 4 条）、`parts_note` |
| `backcalc` | `steps[{label,value,desc}]`（最多 4 步）、`result{label,value,sub}` |
| `explainer` | `example` `left{title,bullets[]}` `right{title,chips[],text}` |
| `channel_card` | `tiles[{value,label,accent}]`（4 个）、`total{label,value}` `list_title` `list[{title,value}]`（3 条）、`side_note` |
| `tips` | `table_title` `columns[{label,align}]` `rows[[...]]` `steps_title` `steps[{label,desc,value,dark}]` |
| `table` | `columns[{label,align,width}]`（width 是占比，加起来等于 1）、`rows[[...]]` `total_row` `bold_col` `font_size` `row_h`、`bar[{label,value,color}]`（可选，表格上方的占比条） |
| `monthly` | `total{label,value,sub,caption}` `items[{label,value,share,color}]`（最多 4 条） |
| `stats4` | `tiles[{label,value,sub,dark}]` `bullets[]` |
| `topic_bars` | `left/right{title,items[{label,value,text,highlight,bar}]}` `insight`。`bar:false` 表示这一项只显示文字，不画条，可用于并列项。 |
| `stacked_columns` | `series[{label,color}]` `categories[]` `values[[每个类别下各系列的数值]]`。超过 14 个类别时，月份标签会自动缩写并隔几个显示一个。 |
| `gear` | `frames` `style[{label,count}]` `specs` `items[{category,name,basis,level}]`（最多 5 条，level 填“有证据”或“推断”）、`summary` |
| `three_cols` | `cols[{title,bullets[],dark}]`（最多 3 栏）、`banner` |

## 叙述页（按需要手动加）

**`lessons`**：要点 / 怎么做 / 数据佐证，三列共 5 行。

```json
{"type": "lessons", "eyebrow": "启示", "title": "Zaza 给我们的 5 点启示",
 "headers": ["启示", "怎么做", "数据佐证"],
 "rows": [{"title": "英文内容", "how": "用英语讲，面向全球观众，广告单价更高", "evidence": "热门评论 89% 是英文"}],
 "note": "数据来自……"}
```

**`cards`**：卡片网格，最多 8 张，列数自动决定（也可以用 `columns` 指定）。可以加顶部的深色核心句 `statement`（或浅色说明 `lead`），以及底部的 `banner`。每张卡片可选的字段：`num`（编号）、`body`、`note`（底部小字）、`dark`、`fill`，以及 `bar{value,max,base,good,label}`（一条小条形图，`base` 画一条基准线）。适合“哪些人可以拍”“还可以拍哪些题材”“需要准备什么”这类页面。

```json
{"type": "cards", "eyebrow": "哪些人可以拍", "title": "哪些人可以拍？每个人都可以",
 "statement": "外国人很少有渠道了解中国普通人的生活……这个信息差就是机会。",
 "cards": [{"title": "外卖员的一天", "body": "一天跑多少单、挣多少钱", "note": "实例：Gangzi，640 万播放"}],
 "banner": "任何人都可以：……"}
```

```json
{"type": "cards", "eyebrow": "题材分析", "title": "还可以拍哪些题材？", "bg": "alt",
 "lead": "爆款率 = 播放达到本频道中位数 2 倍以上的视频占比，赛道平均 26%（竖线）。",
 "cards": [{"title": "中国人的房子", "body": "$X 能租到什么、几平米的小房间",
            "bar": {"value": 44, "max": 50, "base": 26, "good": true, "label": "爆款率 44% · 148 条"},
            "note": "6㎡ 房间一条 450 万播放"}]}
```

**`numbered`**：2×2 的编号卡片，可加底部深色 `banner`。适合“起步建议”这类页面。
`items[{title,body}]`

**`panels`**：左右两块对比面板，加一个说明框，适合“现在的门槛 vs 2027 年起”这类对比。
`panels[{title,big,line,sub,dark}]`（2 块）、`box{title,text}`

**`rows`**：带编号的横条列表（最多 6 行），每行显示 名称 / 说明 / 右侧标签，适合“收入来源构成”这类页面。
`rows[{name,desc,tag}]`

**`images`**：1–3 张图片并排（`layout: "stack"` 时上下排），按比例缩放放进格子里，不会变形。适合缩略图前后对比、截帧联系表、后台截图。可加顶部深色 `statement` 和底部 `banner`。
`images[{path,caption,ratio,accent}]`：`path` 相对于 deck.json 所在目录；`ratio` 是宽÷高（不填按 16:9），要和图片实际比例一致，否则会被拉伸；`accent: true` 时标题用砖红色。

```json
{"type": "images", "eyebrow": "缩略图", "title": "从各写各的，到统一模板",
 "statement": "改版后 5 张缩略图用同一套模板：2–3 个大字 + 夜景 + 落魄姿态",
 "images": [{"path": "../thumbs_old.jpg", "caption": "改版前 16 条", "ratio": 1.778},
            {"path": "../thumbs_new_grid.jpg", "caption": "改版后 5 条", "ratio": 1.778, "accent": true}]}
```

## 写作和排版要点

- 标题要能概括结论，比如“累计约 ¥118 万，平均每月约 ¥11.5 万”，而不是只写“收入”。
- 结论要带数字或例子。是假设或人工判断的，写进 `note`。
- 文字放不下就改短，不要缩小字号。`build_deck.js` 打印的 WARN 指的是哪一页、哪段文字。
- 生成后一定要用 `render_check.sh` 渲染出图片，用眼睛检查一遍。
- 渲染检查用的是 Keynote：占位符里放不下的文字会被 Keynote 悄悄缩小，PowerPoint 不会，会直接溢出错位（用户在 PowerPoint 里遇到过封面错位）。所以 WARN 一条都不能放过，标题必须一行放得下。

## 竖版（9:16）专用字段

`build_deck_portrait.js` 用同一份 deck.json 生成竖屏版，每种页面都有对应的竖排版式。横版会忽略下面这些字段：

| 字段 | 作用 |
|---|---|
| `portrait` | 对象：只在竖版里覆盖该页的字段，最常用来删表格列，例如 `{"columns": [...], "rows": [...], "bold_col": 3}`。填 `false` 表示这一页不进竖版。 |
| `title_portrait` | 竖版标题，可用 `\n` 手动断行。不填时在中文标点（：，、—）处自动断成两行。 |
| `title_size_portrait` | 只用于封面：竖版封面标题字号。 |
| `font_size_portrait` / `row_h_portrait` | 只用于 `table`：竖版表格字号和最小行高（默认 15–16pt、0.56 英寸，短表格会自动拉高铺满）。 |

竖版每页大约放 15 个汉字一行（30pt 标题）或 26 个汉字一行（15pt 正文）。4 列以上、单元格文字长的表格，竖版里要删列。

`meta.facecam: true`（只影响竖版，平时由 `build_decks.sh` 的 `--facecam` 打开）：底部整条留给 16:9 横屏自拍（宽 7.5、高 4.22 英寸；`meta.facecam_ratio` 可改，例如 `2.3333` 即 21:9），左右边距 0.85 英寸，状态栏（0–0.92 英寸，时间、灵动岛、信号）里不放任何内容；`eyebrow` 放在下一行抖音返回箭头和放大镜中间、水平居中，标题从 1.62 英寸开始；不加色条。放不下的页自动拆成续页；`note` 小字改放演讲者备注；不显示页脚和页码。单页可写 `"video": {...}` 只覆盖视频版字段。

**视频版只放关键词**（视频版默认开启，`meta.video_full: true` 关闭）：
- `"video": false`：这一页不进视频版（用于和别页重复的明细页）。
- `"one_per_page": true`（`images` 页，可写在 `video` 里）：视频版每张图单独一页、占满宽度，适合几组截帧拼图。
- 自动移进演讲者备注的小字：`tiles[].desc/sub`、`cards[].note`、`lead`、器材 `items[].basis`、`panels[].sub`、`total.caption`、说明页 `left/right.text`、封面 `subtitle`；`video` 覆盖掉的原文也写进该页备注。
- 紧凑版式：`rows` 一行一条（`name` 加粗 + `desc` 灰色小注 + `tag`，放不下时自动改两行）；`lessons` 一行写 `how → evidence`（第二个表头含“前”时用箭头，否则用“ · ”）；`three_cols` 每栏的 `bullets` 连成一行；`kpis` 的 `findings` 一条一行；数字格去掉说明后变矮。
- 字数检查（超了打印 `video text too long`）：卡片标题 / 行标题 12 字，卡片正文 / 行说明 / 要点说明 / 表格单元格 14 字，做法 / 证据 / 要点 / 正文 16 字，器材名、图注 18 字，statement / banner / insight / summary / box 24 字；表格最多 3 列 7 行，卡片最多 6 张，每组要点最多 3 条。拉丁字母和数字按 0.55 个字算。

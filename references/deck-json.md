# deck.json

`compute_report.py` 会生成一份初稿，`build_deck.js` 再把它变成 .pptx。可以直接编辑这个文件：改文字、删页、调顺序，或者插入下面的叙述页。

```json
{"meta": {"title": "Zaza 频道分析", "footer": "Zaza 频道分析 · 数据截至 2026-10-10",
          "fonts": {"head": "Songti SC", "body": "PingFang SC"}},
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

字体默认用 Mac 自带的宋体（标题）和苹方（正文）。要发给 Windows 用户，最好导出成 PDF。

## 数据页（compute_report 会自动生成）

| type | 字段 |
|---|---|
| `cover` | `eyebrow` `title` `subtitle` `kpi{label,value,sub}` `meta` |
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
| `three_cols` | `cols[{title,bullets[],dark}]`（最多 3 栏）、`banner` |

## 叙述页（按需要手动加）

**`lessons`**：要点 / 怎么做 / 数据佐证，三列共 5 行。

```json
{"type": "lessons", "eyebrow": "启示", "title": "Zaza 给我们的 5 点启示",
 "headers": ["启示", "怎么做", "数据佐证"],
 "rows": [{"title": "英文内容", "how": "用英语讲，面向全球观众，广告单价更高", "evidence": "热门评论 89% 是英文；反推 RPM 约 $6.6"}],
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

## 写作和排版要点

- 标题要能概括结论，比如“累计约 ¥118 万，平均每月约 ¥11.5 万”，而不是只写“收入”。
- 结论要带数字或例子。是假设或人工判断的，写进 `note`。
- 文字放不下就改短，不要缩小字号。`build_deck.js` 打印的 WARN 指的是哪一页、哪段文字。
- 生成后一定要用 `render_check.sh` 渲染出图片，用眼睛检查一遍。

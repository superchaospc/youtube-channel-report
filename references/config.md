# config.json

`compute_report.py` 读的配置文件。路径都相对于 config 文件本身。只有 `channels` 是必填。

```json
{
  "title": "Zaza 频道分析",
  "as_of": "2026-10-10",
  "fx": "auto",
  "out": "out",
  "period_start": "2025-12-01",
  "channels": [
    {"data": "data/zazainchina", "label": "主频道", "rpm": "backcalc", "shorts_rpm": 0.1},
    {"data": "data/zazaeatschina", "label": "副频道", "rpm": 3, "rpm_note": "美食探店"}
  ],
  "disclosure": {
    "amount_usd": 150000,
    "date": "2026-09-19",
    "includes": ["YouTube 长视频广告分成", "YouTube Shorts 分成", "YouTube 频道会员", "YouTube 打赏（Super Thanks）"],
    "note": "不含站外的 Buy Me a Coffee 打赏，也不含副频道的收入。",
    "snapshot": {"date": "2026-09-27", "long_views": 22370000, "shorts_views": 19180000}
  },
  "tips": {
    "platform": "Buy Me a Coffee", "handle": "zazainchina", "supporters": 1239,
    "tiers": [[10, 0.8], [15, 0.15], [25, 0.05]],
    "platform_fee": 0.05, "payment_pct": 0.029, "payment_fixed": 0.30
  },
  "accounts": [
    {"platform": "TikTok", "name": "@zazainchina", "followers": 86000, "unit": "粉丝", "detail": "110 万获赞\n96 条视频"},
    {"platform": "Instagram", "name": "@zazainchina", "followers": 218000, "unit": "粉丝", "detail": "97 条帖子"},
    {"platform": "Buy Me a Coffee", "name": "zazainchina", "value": "1,239", "unit": "位支持者", "detail": "站外打赏"}
  ],
  "titles_zh": "titles_zh.json",
  "topics": "topics.json",
  "explain_rpm": true
}
```

| 键 | 含义 |
|---|---|
| `title` | 报告标题，用于封面和页脚。默认是“<频道名> 频道分析”。 |
| `as_of` | 统计截止日，默认今天。 |
| `fx` | 美元兑人民币汇率。填 `"auto"` 时从 open.er-api.com 获取，也可以直接写数字。 |
| `out` | 输出目录，默认是 config 所在目录。 |
| `period_start` | 计算月均的起点，默认是主频道第一条长视频的日期。 |
| `channels[]` | **第一个是主频道**。前 10 名、平均每条、题材都只按主频道算。`data` 指向 `fetch_channel.py` 生成的频道目录。`rpm` 填数字，或者填 `"backcalc"`（需要同时写 `disclosure`）。`shorts_rpm` 默认 0.10。`rpm_note` 会显示在副频道页上。 |
| `disclosure` | 公开过的累计收入（美元）。`snapshot` 填离公开日期最近的那次播放量；不填就用当前播放，这样反推出的 RPM 会偏低。`other_usd` 是要先扣掉的其他已知收入。 |
| `tips` | 站外打赏。`tiers` 是若干个 `[金额, 人数占比]`，占比加起来等于 1。手续费参数可以省略，用默认值。 |
| `accounts[]` | 其他平台账号，会显示在账号矩阵页。填了 `followers` 会计入全平台粉丝数；也可以直接给 `value` 文本。YouTube 频道不用写，脚本会自动加。 |
| `titles_zh` | `{视频ID: 中文标题}`。没有翻译的标题会去掉 emoji 并截短后原样显示。 |
| `topics` | `{题材: [视频ID…]}` 或 `{视频ID: 题材}`。没写这个就不生成题材页。 |
| `explain_rpm` | 是否生成“什么是 RPM”说明页，默认 `true`。 |

# 抓数据的坑

## innertube（`scripts/yt.py`）

- 用的是 WEB client 的公开 key，`browse` 列视频，`next` 拿单条详情。`/player` 端点最先被机器人检测拦截（返回 `LOGIN_REQUIRED`），所以全程不用它。
- **播放量**：`videoViewCountRenderer.originalViewCount` 现在经常是字符串 `"0"`，要回退到解析 `viewCount.simpleText`（例如 `"2,129,772 views"`）。列表页给的 “2.1M views” 是约数，只能用来排序。
- **Shorts 标签页**用的是 `shortsLockupViewModel`：videoId 在 `reelWatchEndpoint` 里，播放量在 `overlayMetadata.secondaryText` 里。它和长视频的 `lockupViewModel` 结构不同。
- **翻页**：continuation token 要去重。视频少于一页时，剩下的 token 全是排序按钮，不去重会无限循环。结果也要按 videoId 去重。
- **直播标签页**：频道没有 Live 标签时，streams 的 params 会回落成 Videos 列表。别把长视频算两遍。
- **播放量为 0 的新视频**一般是会员专属视频，播放数被隐藏了。
- 频道头部显示的视频数包含会员专属视频和直播，所以和“长视频 + Shorts”的条数对不上是正常的。

## 日期

- `next` 的 `dateText` 是美国太平洋时间的日期。按月统计时，月初、月末的视频可能差一天，落进另一个月。
- 要精确到时分（例如用户质疑“12 月真的发了 9 条吗”）时，用 yt-dlp 读 Unix 时间戳，再换算到观众所在时区：
  ```bash
  yt-dlp --skip-download --print "%(id)s %(timestamp)s %(duration_string)s %(availability)s" URL
  ```
- 频道页显示的是 “10 months ago” 这类相对时间，和日历月份对不上：12 月上旬的视频显示 “10 months ago”，中下旬的会和 1 月初的视频一起显示 “9 months ago”。用户按相对时间数，往往会少数。被质疑时，把那个月的视频连同精确日期逐条列出来。

## 被 YouTube 判定为机器人

症状：yt-dlp 提示 “Sign in to confirm you're not a bot”，`/player` 返回 `LOGIN_REQUIRED`，内置浏览器打开视频页是白屏；连续 curl 视频页约 150 次后，会被 302 跳转到 google.com/sorry。

- `browse` / `next` 端点通常还能用，本 skill 抓数据只依赖这两个。
- 要用 yt-dlp（精确时间戳、字幕、下载）时，借任意一台能 SSH 的服务器开 SOCKS 隧道。服务器上不用装任何东西，用完关掉隧道：
  ```bash
  ssh -D 127.0.0.1:1091 -N <host> &
  NO_PROXY='*' yt-dlp --proxy socks5://127.0.0.1:1091 --skip-download --print "%(id)s %(timestamp)s" URL
  ```
  走隧道 curl 视频页时，有时仍会遇到机器人检测，但 yt-dlp 一般能过。
- 2026-10-23：本机和多台 VPS（mrnocheat88、sulishi、c20261007、molly、jabbar、mly）同时被拦，换 `--extractor-args "youtube:player_client=tv_simply"`（或 `android_vr`、`mweb`、`web_embedded`）就能下，360p 以下够看画面。
- yt-dlp 报 403 时，通常是版本太旧，升级即可（`brew upgrade yt-dlp` 或 `pip install -U yt-dlp`）。

## 其他平台

- **TikTok**：`tiktok.com/@handle` 的 HTML 里有 `followerCount`、`heartCount`、`videoCount`。粉丝数可能已经被取整（例如 86000）。
- **Instagram**：匿名 curl 会被登录墙挡住；`i.instagram.com` 的 API 要登录；r.jina.ai 这类代理也会被封。用浏览器工具打开主页，读 `<meta property="og:description">` 就行。
- **Buy Me a Coffee**：页面上直接写着 “1,239 supporters”，这是去重后的支持者人数，不是打赏次数。
- **Social Blade / SpeakRJ**：用来看历史播放走势和最近 30 天的播放量。Social Blade 可以用 `r.jina.ai/https://socialblade.com/youtube/handle/<h>/monthly` 抓取。注意它的播放量包含 Shorts。
- **RSS**：`youtube.com/feeds/videos.xml?channel_id=UC…` 给出最近 15 条视频的精确发布时间和播放量。
- 截 1080p 单帧：`--download-sections` 报 ffmpeg 251、ffmpeg 读 googlevideo 地址报 “certificate verify failed” 时，下载整条画面（`-f "bv*[height=1080][ext=mp4]"`）再本地截，输出用 png（jpg 会报 mjpeg YUV 错误）。下载中途的 `.part` 文件也能截已下完的部分。

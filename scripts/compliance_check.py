#!/usr/bin/env python3
"""Flag wording in deck.json that is likely to get a 抖音 / 小红书 post limited or removed.

    python3 compliance_check.py OUT/deck.json

The decks (especially the two portrait ones) get posted to 抖音 and 小红书, so every visible
string — titles, cards, table cells, notes, speaker notes — is scanned. Exit code 1 when anything
is flagged. See references/compliance.md for why each rule exists and what to write instead.
"""
import json, re, sys

RULES = [
    # (category, regex, suggestion)
    ("站外平台名", r"YouTube|Youtube|youtube|TikTok|Instagram|Facebook|Patreon|Buy Me a Coffee|AdSense",
     "写成 油管 / 海外视频平台 / 海外短视频平台 / 海外打赏平台 / 广告分成"),
    ("站外账号/链接", r"@[A-Za-z0-9_.\-]{3,}|https?://|www\.|\.com\b",
     "删掉账号 handle 和链接，只写频道名"),
    ("引流词", r"引流|导流|私信|加微|微信|VX|vx|二维码|联系方式|主页链接|点击链接",
     "导流 → 带火 / 推荐；不留任何联系方式"),
    ("翻墙", r"翻墙|梯子|VPN|vpn|科学上网|代理",
     "整句删掉，不提怎么访问海外平台"),
    ("收益承诺/网赚", r"月入|日入|年入|躺赚|稳赚|暴富|搞钱|副业|赚钱|赚了|能赚|挣钱|变现秘籍|轻松.{0,4}收入",
     "写成 收益估算；数字旁注明“估算，不构成收益承诺”"),
    ("极限词", r"最强|最好|最佳|第一(?![条次期个天周步页集篇张]|人称|波|视角|印象|时间|眼)|唯一|顶级|全网|绝对|史上|必火|爆火秘诀|100%成功",
     "换成具体比较：播放更高 / 平均更高"),
    ("未成年人隐私与卖惨", r"离婚|出轨|被背叛|赌博|欠债|破产|前妻|真名|学校名|住址",
     "未成年人家庭隐私不写；只写“单亲家庭”这类概括"),
    ("募捐", r"捐款|捐钱|募捐|众筹|GoFundMe",
     "写成 打赏 / 想支持他们"),
    ("政治敏感", r"政府|官方操控|宣传|审查|墙",
     "删掉"),
]

SKIP_KEYS = {"type", "bg", "color", "align", "path", "fonts", "section"}


def strings(node, path=""):
    if isinstance(node, str):
        yield path, node
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from strings(v, f"{path}[{i}]")
    elif isinstance(node, dict):
        for k, v in node.items():
            if k in SKIP_KEYS:
                continue
            yield from strings(v, f"{path}.{k}" if path else k)


def main():
    deck = json.load(open(sys.argv[1]))
    hits = 0
    for where, s in strings(deck):
        for cat, pat, fix in RULES:
            for m in re.finditer(pat, s):
                hits += 1
                ctx = s[max(0, m.start() - 12): m.end() + 12].replace("\n", " ")
                print(f"[{cat}] {where}: …{ctx}…  → {fix}")
    print(f"{hits} flagged" if hits else "clean: no 抖音 / 小红书 risk words found")
    sys.exit(1 if hits else 0)


if __name__ == "__main__":
    main()

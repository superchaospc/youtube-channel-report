#!/usr/bin/env python3
"""观众是谁 / 观众评论 sections: who comments and what they say.

    python3 audience_scan.py COMMENTS_DIR --out OUT/audience.json --slides OUT/audience_slides.json

COMMENTS_DIR holds one yt-dlp info.json per video with its comments, e.g.
    yt-dlp --skip-download --write-info-json --write-comments -o "COMMENTS_DIR/%(id)s" URL…
(through a VPS SOCKS tunnel when the local IP is bot-checked, see references/data-gotchas.md).

Counts comment languages (script + stop words), self-reported countries ("I'm from India", "greetings
from Kenya", one count per commenter), life-stage cues (stated age, spouse / kids, single, fellow
drivers or workers, retired) and keyword themes over top-level comments, with the most-liked comment
per theme. The uploader's own replies are counted separately. Commenters are not the whole audience;
the slides say so. --slides writes four deck.json slides (two 观众是谁, two 观众评论) with keyword
"video" overrides; translate the English example comments in audience.json into the 意译 column.
"""
import argparse, collections, glob, json, os, re

ap = argparse.ArgumentParser()
ap.add_argument("comments_dir")
ap.add_argument("--out", required=True)
ap.add_argument("--slides")
args = ap.parse_args()
comments, uploader = [], 0
for f in glob.glob(os.path.join(args.comments_dir, "*.info.json")):
    d = json.load(open(f))
    for c in d.get("comments") or []:
        if c.get("author_is_uploader"):
            uploader += 1
            continue
        c["video"] = d["id"]
        comments.append(c)
top = [c for c in comments if c.get("parent") == "root"]

# ---------------------------------------------------------------- language
STOP = {
    "英语": "the and you is to this are your my it of in for that so very what with have was not".split(),
    "西班牙语": "que de el la los las y muy es mi tu por para con una un pero como gracias saludos hermano".split(),
    "葡萄牙语": "você não muito que de com uma um para é meu obrigado irmão parabéns".split(),
    "印尼 / 马来语": "yang dan ini saya tidak sangat itu ada dengan untuk di ke juga bang semangat".split(),
    "德语": "und ich nicht das ist ein eine sehr du die der zu mit auch".split(),
    "法语": "je et est les pas très tu le la une un des que pour avec".split(),
    "意大利语": "che di è non molto sei il la per una un con ciao".split(),
    "土耳其语": "ve bir bu çok için ama ben sen".split(),
    "菲律宾语": "ang ng mga sa ko po ka naman lang talaga".split(),
}
def lang(t):
    if re.search(r"[一-鿿]", t) and not re.search(r"[぀-ヿ]", t): return "中文"
    if re.search(r"[぀-ヿ]", t): return "日语"
    if re.search(r"[가-힯]", t): return "韩语"
    if re.search(r"[ऀ-ॿ]", t): return "印地语"
    if re.search(r"[؀-ۿ]", t): return "阿拉伯语 / 乌尔都语"
    if re.search(r"[Ѐ-ӿ]", t): return "俄语"
    if re.search(r"[฀-๿]", t): return "泰语"
    if re.search(r"[ăâđêôơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]", t.lower()): return "越南语"
    w = re.findall(r"[a-záéíóúñçãõâêôàèìòùäöüß]+", t.lower())
    if not w: return "表情 / 其他"
    score = {k: sum(x in set(v) for x in w) for k, v in STOP.items()}
    best = max(score, key=score.get)
    return best if score[best] > 0 else "英语"
langs = collections.Counter(lang(c["text"]) for c in comments)

# ---------------------------------------------------------------- self-reported country
COUNTRIES = {
    "印度": r"india|indian", "巴基斯坦": r"pakistan|pakistani", "孟加拉": r"bangladesh|bangladeshi", "尼泊尔": r"nepal|nepali",
    "斯里兰卡": r"sri lanka", "菲律宾": r"philippines|filipino|pinoy", "印尼": r"indonesia|indonesian", "马来西亚": r"malaysia|malaysian",
    "越南": r"vietnam|vietnamese", "泰国": r"thailand|thai", "日本": r"japan|japanese", "韩国": r"korea|korean",
    "美国": r"usa|u\.s\.a?|united states|america|american", "加拿大": r"canada|canadian", "墨西哥": r"mexico|mexican",
    "巴西": r"brazil|brazilian|brasil", "阿根廷": r"argentina", "哥伦比亚": r"colombia", "秘鲁": r"peru", "智利": r"chile",
    "英国": r"uk|united kingdom|england|britain|british|scotland", "德国": r"germany|german", "法国": r"france|french",
    "意大利": r"italy|italian", "西班牙": r"spain|spanish", "荷兰": r"netherlands|holland|dutch", "波兰": r"poland|polish",
    "俄罗斯": r"russia|russian", "乌克兰": r"ukraine", "土耳其": r"turkey|türkiye|turkish", "伊朗": r"iran|iranian",
    "尼日利亚": r"nigeria|nigerian", "肯尼亚": r"kenya|kenyan", "南非": r"south africa", "埃及": r"egypt|egyptian",
    "澳大利亚": r"australia|australian|aussie", "新西兰": r"new zealand", "爱尔兰": r"ireland|irish", "瑞典": r"sweden|swedish",
}
SELF = r"(?:i'?m|i am|we are|we're|im|from|here in|live in|living in|in my country|greetings from|love from|watching from|hello from|hi from|as an?|my country)\s+(?:the\s+)?"
country_authors = collections.defaultdict(set)
for c in comments:
    t = c["text"].lower()
    for name, pat in COUNTRIES.items():
        if re.search(SELF + r"(?:" + pat + r")\b", t):
            country_authors[name].add(c["author_id"])
countries = sorted(((k, len(v)) for k, v in country_authors.items()), key=lambda x: -x[1])

# ---------------------------------------------------------------- life stage / who they are
LIFE = {
    "报年龄": r"\b(?:i'?m|i am|im)\s+(\d{2})\b(?!\s*(?:km|kg|min|hours|dollars|\$|%))|\b(\d{2})\s*(?:years old|yrs old|yo)\b",
    "单身 / 离婚": r"\b(?:i'?m|i am|im)\s+(?:also\s+)?(?:single|divorced|separated)\b|\bas a (?:single|divorced)\b|\bi(?:'m| am) (?:a )?(?:single dad|single mom|single father|single mother)",
    "已婚 / 有家庭": r"\bmy (?:wife|husband|kids|children|son|daughter)\b",
    "也是打工人 / 送外卖": r"\b(?:i'?m|i am|i was|i work as)\s+(?:a |an )?(?:delivery|driver|rider|courier|uber|doordash|factory worker|construction)",
    "退休 / 长辈": r"\b(?:i'?m|i am)\s+(?:retired|a grandma|a grandpa|a grandmother|a grandfather)|\bmy grandkids\b",
}
life_authors = {k: set() for k in LIFE}
ages = []
for c in comments:
    t = c["text"].lower()
    for k, pat in LIFE.items():
        m = re.search(pat, t)
        if m:
            if k == "报年龄":
                a = int(next(g for g in m.groups() if g))
                if not 16 <= a <= 85:
                    continue
                ages.append(a)
            life_authors[k].add(c["author_id"])
life = {k: len(v) for k, v in life_authors.items()}
age_bands = collections.Counter(("20 多" if a < 30 else "30 多" if a < 40 else "40 多" if a < 50 else "50 多" if a < 60 else "60 以上") for a in ages)

# ---------------------------------------------------------------- themes (top-level comments)
THEMES = {
    "加油 / 祝福": r"keep (?:going|it up|up)|good luck|god bless|bless you|stay strong|take care|don'?t give up|wish you|best wishes|proud of you|you deserve|you got this|fighting|praying",
    "真实 / 真诚": r"\breal\b|reality|honest|genuine|authentic|\btruth|realistic|no fake",
    "辛苦 / 心疼": r"hard ?work|hardworking|tough|struggl|tired|exhaust|respect|so hard|difficult|sad|heart ?break|feel for you",
    "收入 / 物价": r"salary|income|wage|\bpaid\b|\bpay\b|dollars|\$|cost|price|expensive|cheap|afford|rent",
    "夸中国": r"china (?:is|looks) (?:so )?(?:beautiful|clean|safe|developed|amazing|great|modern)|love china|beautiful country|so clean|infrastructure",
    "和我们那儿一样": r"same (?:in|as|here)|just like (?:in )?(?:my|our|india|mexico|the philippines|pakistan)|relate|my country too|same situation|same life",
    "家人 / 妈妈": r"\bmom\b|\bmother\b|\bmum\b|grandparent|grandma|grandpa|family|good son",
    "找对象 / 婚姻": r"\bmarr|wife|girlfriend|\bwoman\b|find (?:a|the) (?:right|good)|love will|soulmate|lonely",
    "谁在拍": r"camera ?man|who(?:'s| is) (?:filming|recording|holding)|tripod|who films|filming you|camera person|the camera",
    "吃的": r"\bfood|delicious|\beat|noodle|dumpling|tasty|yummy|meal",
    "想请他吃饭 / 打赏": r"super thanks|donat|treat you|buy you|send you|paypal|support you|tip\b|i'?ll pay",
}
theme_cnt, theme_best = collections.Counter(), {}
for c in top:
    t = c["text"].lower()
    for k, pat in THEMES.items():
        if re.search(pat, t):
            theme_cnt[k] += 1
            if k not in theme_best or (c.get("like_count") or 0) > (theme_best[k].get("like_count") or 0):
                theme_best[k] = c
themes = [{"theme": k, "count": n, "share": round(n / len(top), 4),
           "best": {"text": theme_best[k]["text"][:300], "likes": theme_best[k].get("like_count"), "video": theme_best[k]["video"]}}
          for k, n in theme_cnt.most_common()]

out = {"comments": len(comments), "top_level": len(top), "authors": len({c["author_id"] for c in comments}), "uploader_replies": uploader,
       "languages": langs.most_common(), "countries": countries, "country_total": sum(n for _, n in countries),
       "life": life, "ages": {"n": len(ages), "median": sorted(ages)[len(ages) // 2] if ages else None, "bands": age_bands.most_common()},
       "themes": themes}
json.dump(out, open(args.out, "w"), ensure_ascii=False, indent=1)
print(f"{len(comments):,} viewer comments ({len(top):,} top-level) from {out['authors']:,} people; uploader replied {uploader}")
print("languages:", ", ".join(f"{k} {n}" for k, n in langs.most_common(6)))
print("countries:", ", ".join(f"{k} {n}" for k, n in countries[:8]), f"(of {out['country_total']})")
print("life:", life, "ages:", out["ages"])
for t in themes:
    print(f"{t['theme']:<12} {t['count']:>5} {t['share']*100:5.1f}%  [{t['best']['likes']}赞] {t['best']['text'][:110]!r}")

if args.slides:
    n_all, n_top = len(comments), len(top)
    pct = lambda n, t: (f"{n / t * 100:.0f}%" if n / t >= 0.1 else f"{n / t * 100:.1f}%") if t else "—"
    cols = lambda *s: [dict(label=l, align=al, width=w) for l, al, w in s]
    lang = dict(langs)
    main = [(k, n) for k, n in langs.most_common() if k != "表情 / 其他"][:4]
    other = n_all - sum(n for _, n in main)
    lang_items = main + [("其他", other)]
    ct = out["country_total"]
    over40 = sum(n for b, n in age_bands.items() if b in ("40 多", "50 多", "60 以上"))
    first = main[0]
    slides = [
        {"type": "topic_bars", "eyebrow": "观众是谁", "section": "观众是谁",
         "title": f"评论 {pct(first[1], n_all)} 是{first[0]}" + (f"，自报国家最多的是{countries[0][0]}" if countries else ""),
         "left": {"title": f"评论用的语言（{n_all:,} 条）",
                  "items": [{"label": f"{i + 1}. {k}", "value": n, "text": pct(n, n_all), "highlight": i == 0} for i, (k, n) in enumerate(lang_items)]},
         "right": {"title": f"评论里自报国家（{ct} 人）",
                   "items": [{"label": f"{i + 1}. {k}", "value": n, "text": f"{n} 人 · {pct(n, ct)}"} for i, (k, n) in enumerate(countries[:5])]},
         "insight": "说了自己国家的人里，" + "、".join(k for k, _ in countries[:3]) + " 最多。",
         "note": "评论者不等于全部观众：观众国家的准确数据只有博主在后台能看到。自报国家按“我来自 / 我是 X 人 / 在 X 看”这类说法统计，每人只算一次。",
         "video": {"insight": f"{first[0]}观众为主 · {countries[0][0] if countries else ''}最多"}},
        {"type": "stats4", "eyebrow": "观众是谁",
         "title": f"报了年龄的人，一半在 {out['ages']['median']} 岁以上" if ages else "评论里的观众画像",
         "tiles": [{"label": "自报年龄的中位数", "value": f"{out['ages']['median']} 岁" if ages else "—", "sub": f"{len(ages)} 人报了年龄", "dark": True},
                   {"label": "40 岁以上", "value": pct(over40, len(ages)), "sub": f"{over40} / {len(ages)} 人"},
                   {"label": "提到妻子孩子", "value": f"{life['已婚 / 有家庭']} 人", "sub": "有家庭的人"},
                   {"label": "也在打工送货", "value": f"{life['也是打工人 / 送外卖']} 人", "sub": "自称司机、骑手、工人"}],
         "bullets": [f"说自己单身 / 离婚的 {life['单身 / 离婚']} 人，退休或当了祖父母的 {life['退休 / 长辈']} 人"],
         "note": "按评论里的自我描述统计（“我 45 岁”“我妻子”“我也是送货司机”），只覆盖主动说起的人。",
         "video": {"bullets": []}},
        {"type": "stats4", "eyebrow": "观众评论", "section": "观众评论",
         "title": f"{n_all:,} 条评论，博主自己回了 {uploader} 条",
         "tiles": [{"label": "观众评论", "value": f"{n_all:,}", "sub": "含回复"},
                   {"label": "一级评论", "value": f"{n_top:,}", "sub": "不含楼中楼"},
                   {"label": "评论的人", "value": f"{out['authors']:,}", "sub": "按账号去重"},
                   {"label": "博主回复", "value": f"{uploader} 条", "sub": f"约每 {n_all // max(uploader, 1)} 条回 1 条", "dark": True}],
         "bullets": [f"{k}评论 {n} 条" for k, n in main[1:3]],
         "video": {"bullets": []}},
        {"type": "table", "eyebrow": "观众评论", "title": f"评论最多聊{themes[0]['theme'].split(' / ')[0]}" if themes else "评论聊什么",
         "columns": cols(("话题", "left", 0.2), ("占比", "right", 0.12), ("条数", "right", 0.12), ("点赞最高的一条（意译）", "left", 0.44), ("赞", "right", 0.12)),
         "rows": [[t["theme"], pct(t["count"], n_top), f"{t['count']:,}", "", str(t["best"]["likes"])] for t in themes[:8]],
         "bold_col": 1, "font_size": 13, "row_h": 0.42,
         "note": f"{n_top:,} 条一级评论按关键词归类，一条可以归进几类；代表评论取该类点赞最高的一条，中文为意译。",
         "portrait": {"columns": cols(("话题", "left", 0.62), ("占比", "right", 0.38)), "rows": [[t["theme"], pct(t["count"], n_top)] for t in themes[:8]], "bold_col": 1},
         "video": {"columns": cols(("话题", "left", 0.62), ("占比", "right", 0.38)), "rows": [[t["theme"], pct(t["count"], n_top)] for t in themes[:6]], "bold_col": 1}},
    ]
    json.dump(slides, open(args.slides, "w"), ensure_ascii=False, indent=1)
    print(f"wrote {len(slides)} slides to {args.slides} — fill the 意译 column and one or two findings per page, then splice them in")

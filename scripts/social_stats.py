#!/usr/bin/env python3
"""Public follower counts for the rest of a creator's account matrix.

    python3 social_stats.py --tiktok zazainchina --bmc zazainchina

TikTok and Buy Me a Coffee pages answer plain HTTP requests. Instagram does
not (login wall / rate limits); open https://www.instagram.com/<handle>/ in a
browser tool and read <meta property="og:description">, which says
"218K Followers, 10 Following, 97 Posts".
"""
import argparse
import json
import re
import urllib.request

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US"})
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")


def tiktok(handle):
    s = get(f"https://www.tiktok.com/@{handle.lstrip('@')}")
    num = lambda k: int(m.group(1)) if (m := re.search(rf'"{k}":(\d+)', s)) else None
    nick = re.search(r'"nickname":"([^"]+)"', s)
    return {"platform": "TikTok", "handle": "@" + handle.lstrip("@"), "nickname": nick.group(1) if nick else None,
            "followers": num("followerCount"), "likes": num("heartCount"), "videos": num("videoCount")}


def bmc(slug):
    s = get(f"https://buymeacoffee.com/{slug}")
    m = re.search(r"([\d,]+)\s+supporters?", s)
    return {"platform": "Buy Me a Coffee", "handle": slug, "supporters": int(m.group(1).replace(",", "")) if m else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tiktok")
    ap.add_argument("--bmc", help="buymeacoffee.com/<slug>")
    a = ap.parse_args()
    out = []
    if a.tiktok:
        out.append(tiktok(a.tiktok))
    if a.bmc:
        out.append(bmc(a.bmc))
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

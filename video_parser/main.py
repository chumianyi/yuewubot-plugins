# -*- coding: utf-8 -*-
"""视频解析器 · YueWuBot 原生插件

把 B站 / 抖音 / 小红书 / 快手 的分享链接解析成「标题 + 视频直链 + 封面」，
不下载、不落盘，解析完直接回复。

参考了 astrbot_plugin_video_analysis 的解析思路与公开接口：
- B站：finger/spi 取 buvid 降低风控 -> view 取标题封面 -> playurl 取直链
- 抖音：短链重定向取 aweme_id -> slidesinfo 接口 -> 分享页 _ROUTER_DATA 兜底
- 小红书：短链重定向 -> 笔记页 __INITIAL_STATE__ -> originVideoKey / stream
- 快手：短链重定向 -> 作品页 __APOLLO_STATE__ -> photoUrl
"""

import asyncio
import json
import re
import time

import aiohttp

UA_PC = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
UA_MB = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
         "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
UA_ANDROID = ("Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36")

TIMEOUT = aiohttp.ClientTimeout(total=15, connect=6)

H_BILI = {
    "User-Agent": UA_PC,
    "Referer": "https://www.bilibili.com/",
    "Origin": "https://www.bilibili.com",
    "Accept": "application/json, text/plain, */*",
}
H_DY_MB = {
    "User-Agent": UA_MB,
    "Referer": "https://www.douyin.com/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}
H_DY_PC = dict(H_DY_MB, **{"User-Agent": UA_PC})
H_XHS = {
    "User-Agent": UA_PC,
    "Referer": "https://www.xiaohongshu.com/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}
H_KS = {
    "User-Agent": UA_PC,
    "Referer": "https://www.kuaishou.com/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

URL_RE = re.compile(r"https?://[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+")
URL_TRIM = " \t\r\n.,;:!?)]}>'\"。，；：！？）】》」』、"

PLATFORMS = {
    "bilibili": "B站",
    "douyin": "抖音",
    "xiaohongshu": "小红书",
    "kuaishou": "快手",
}

_LAST = {}


# ---------------------------------------------------------------- 基础工具

def _clip(text, limit=80):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text[:limit] + ("…" if len(text) > limit else "")


def _https(url):
    url = str(url or "").strip()
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http://"):
        return "https://" + url[7:]
    return url


def _pick_urls(text):
    out = []
    for m in URL_RE.finditer(str(text or "")):
        u = m.group(0).rstrip(URL_TRIM)
        # 分享文案里常见「链接+表情」，去掉尾部非 ASCII
        u = re.sub(r"[^\x00-\x7f]+$", "", u)
        if u and u not in out:
            out.append(u)
    return out


def _platform_of(url):
    host = ""
    try:
        host = (re.sub(r"^https?://", "", url).split("/")[0] or "").lower()
    except Exception:
        return ""
    if "bilibili.com" in host or "b23.tv" in host or "bili2233.cn" in host:
        return "bilibili"
    if "douyin.com" in host or "iesdouyin.com" in host or "amemv.com" in host:
        return "douyin"
    if "xiaohongshu.com" in host or "xhslink.com" in host or "xhslink.cn" in host:
        return "xiaohongshu"
    if "kuaishou.com" in host or "gifshow.com" in host or "kuaishouapp.com" in host:
        return "kuaishou"
    return ""


def _truthy(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on", "y")


def _json_block(text, marker):
    """从 HTML 里抠出 marker 后面第一个完整的 JSON 对象（按括号配对，跳过字符串）。"""
    start = text.find(marker)
    if start < 0:
        return None
    begin = text.find("{", start)
    if begin < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(begin, len(text)):
        ch = text[i]
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                raw = text[begin:i + 1]
                for candidate in (raw, raw.replace("undefined", "null")):
                    try:
                        return json.loads(candidate)
                    except Exception:
                        continue
                return None
    return None


def _walk_find(obj, predicate, depth=0):
    """深度优先找第一个满足条件的 dict。"""
    if depth > 12:
        return None
    if isinstance(obj, dict):
        try:
            if predicate(obj):
                return obj
        except Exception:
            pass
        for value in obj.values():
            found = _walk_find(value, predicate, depth + 1)
            if found:
                return found
    elif isinstance(obj, (list, tuple)):
        for value in obj:
            found = _walk_find(value, predicate, depth + 1)
            if found:
                return found
    return None


async def _get_json(session, url, headers, cookie=""):
    h = dict(headers)
    if cookie:
        h["Cookie"] = cookie
    try:
        async with session.get(url, headers=h, timeout=TIMEOUT) as resp:
            if resp.status >= 400:
                return None
            return await resp.json(content_type=None)
    except Exception:
        return None


async def _get_text(session, url, headers, cookie=""):
    h = dict(headers)
    if cookie:
        h["Cookie"] = cookie
    try:
        async with session.get(url, headers=h, timeout=TIMEOUT) as resp:
            if resp.status >= 400:
                return ""
            raw = await resp.read()
            return raw.decode("utf-8", "ignore")
    except Exception:
        return ""


async def _follow(session, url, headers):
    try:
        async with session.get(url, headers=headers, allow_redirects=True, timeout=TIMEOUT) as resp:
            return str(resp.url)
    except Exception:
        return url


# ---------------------------------------------------------------- B站

_BILI_COOKIE = {"value": "", "at": 0.0}

# av 号转 BV 号（B站公开算法）
_BV_ALPHABET = "FcwAPNKTMug3GV5Lj7EJnHpWsx4tb8haYeviqBz6rkCy12mUSDQX9RdoZf"
_BV_ORDER = (8, 7, 0, 5, 1, 3, 2, 4, 6)


def _av2bv(av):
    try:
        aid = int(av)
    except Exception:
        return ""
    if aid <= 0 or aid > (1 << 51):
        return ""
    table = [""] * 9
    tmp = ((1 << 51) | aid) ^ 23442827791579
    for i in range(9):
        table[_BV_ORDER[i]] = _BV_ALPHABET[tmp % 58]
        tmp //= 58
    return "BV1" + "".join(table)


async def _bili_cookie(session):
    if _BILI_COOKIE["value"] and time.time() - _BILI_COOKIE["at"] < 1800:
        return _BILI_COOKIE["value"]
    cookie = ""
    data = await _get_json(session, "https://api.bilibili.com/x/frontend/finger/spi", H_BILI)
    if data and data.get("code") == 0:
        d = data.get("data") or {}
        if d.get("b_3"):
            cookie = "buvid3=%s; buvid4=%s" % (d.get("b_3"), d.get("b_4") or "")
    _BILI_COOKIE["value"] = cookie
    _BILI_COOKIE["at"] = time.time()
    return cookie


async def parse_bilibili(session, url, cfg):
    real = url
    if re.search(r"b23\.tv|bili2233\.cn", url):
        real = await _follow(session, url, H_DY_MB)

    if re.search(r"live\.bilibili\.com", real or ""):
        return {"platform": "B站", "title": "直播间", "url": real, "cover": "",
                "page": real, "note": "直播间不支持解析，点链接直接看"}

    bv_match = re.search(r"(BV1[0-9A-Za-z]{9})", real or url)
    av_match = re.search(r"[?&]aid=(\d+)", real or url) or re.search(r"(?:/|\b)av(\d+)", real or url, re.I)
    if bv_match:
        param = "bvid=" + bv_match.group(1)
    elif av_match:
        bvid = _av2bv(av_match.group(1))
        param = "bvid=" + bvid if bvid else "aid=" + av_match.group(1)
    else:
        return None

    cookie = await _bili_cookie(session)
    view = await _get_json(session,
                           "https://api.bilibili.com/x/web-interface/view?" + param,
                           H_BILI, cookie)
    if not view or view.get("code") != 0:
        return None
    info = view.get("data") or {}
    cid = info.get("cid") or (((info.get("pages") or [{}])[0] or {}).get("cid") or 0)
    bvid = info.get("bvid") or (bv_match.group(1) if bv_match else "")
    page = "https://www.bilibili.com/video/" + bvid if bvid else (real or url)

    try:
        qn = int(cfg.get("bili_quality") or 64)
    except Exception:
        qn = 64
    if qn not in (16, 32, 64, 80, 112, 116, 120):
        qn = 64

    direct = ""
    note = ""
    if cid:
        api = ("https://api.bilibili.com/x/player/playurl?%s&cid=%s&qn=%d"
               "&fnval=0&fnver=0&fourk=0" % (param, cid, qn))
        play = await _get_json(session, api, H_BILI, cookie)
        if play and play.get("code") == 0:
            pdata = play.get("data") or {}
            durl = pdata.get("durl") or []
            if durl:
                direct = (durl[0] or {}).get("url") or ""
                if len(durl) > 1:
                    note = "视频共 %d 段，这里是第 1 段" % len(durl)
        if not direct:
            # 退回 DASH：只有视频轨，没有音轨
            api = ("https://api.bilibili.com/x/player/playurl?%s&cid=%s&qn=%d"
                   "&fnval=4048&fnver=0&fourk=1" % (param, cid, qn))
            play = await _get_json(session, api, H_BILI, cookie)
            if play and play.get("code") == 0:
                dash = (play.get("data") or {}).get("dash") or {}
                tracks = [x for x in (dash.get("video") or []) if isinstance(x, dict)]
                if tracks:
                    best = max(tracks, key=lambda x: (x.get("height") or 0, x.get("bandwidth") or 0))
                    direct = best.get("baseUrl") or best.get("base_url") or ""
                    if direct:
                        note = "该清晰度为 DASH 视频轨（无音轨），完整播放建议用页面链接"

    return {
        "platform": "B站",
        "title": info.get("title") or "",
        "url": direct,
        "page": page,
        "cover": _https(info.get("pic") or ""),
        "note": note,
    }


# ---------------------------------------------------------------- 抖音

def _find_aweme(data):
    def hit(obj):
        video = obj.get("video")
        if isinstance(video, dict) and (video.get("play_addr") or video.get("bit_rate")):
            return True
        return bool(obj.get("aweme_id") and obj.get("desc") is not None and obj.get("images"))

    return _walk_find(data, hit)


def _douyin_urls(video):
    """按清晰度取播放地址：bit_rate 高的优先，跳过 ByteVC2。"""
    candidates = []
    for item in (video.get("bit_rate") or []):
        if not isinstance(item, dict):
            continue
        addr = item.get("play_addr") or {}
        if not isinstance(addr, dict):
            continue
        codec = str(item.get("codec_id") or addr.get("codec_id") or "").lower()
        if "bytevc2" in codec or item.get("is_bytevc1") == 2:
            continue
        size = (addr.get("width") or 0) * (addr.get("height") or 0)
        candidates.append((size, item.get("bit_rate") or 0, addr))
    for key in ("play_addr_265", "play_addr"):
        addr = video.get(key)
        if isinstance(addr, dict):
            candidates.append((0, 0, addr))
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)

    out = []
    for _, _, addr in candidates:
        for u in (addr.get("url_list") or []):
            if isinstance(u, str) and u.startswith("http"):
                u = u.replace("playwm", "play")
                if u not in out:
                    out.append(u)
    return out


def _aweme_item(aw):
    video = aw.get("video") or {}
    title = aw.get("desc") or aw.get("title") or ""
    author = ((aw.get("author") or {}).get("nickname") or "")
    cover = ""
    for key in ("cover", "origin_cover", "dynamic_cover"):
        addr = video.get(key) or {}
        urls = addr.get("url_list") or []
        if urls:
            cover = _https(urls[-1])
            break

    images = aw.get("images") or []

    urls = _douyin_urls(video) if video else []
    if urls:
        item = {"platform": "抖音", "title": title, "url": _https(urls[0]), "page": "",
                "cover": cover, "author": author, "note": ""}
        if len(urls) > 1:
            item["alt"] = _https(urls[1])
        return item

    if images:
        first = ""
        for img in images:
            for key in ("url_list", "urlList"):
                seq = img.get(key) or []
                if seq:
                    first = _https(seq[-1])
                    break
            if first:
                break
        return {"platform": "抖音", "title": title, "url": first, "page": "",
                "cover": cover, "author": author,
                "note": "图集共 %d 张" % len(images)}

    return None


async def parse_douyin(session, url, cfg):
    real = url
    if re.search(r"v\.douyin\.com|iesdouyin\.com/share", url):
        real = await _follow(session, url, H_DY_MB)

    if re.search(r"webcast|live\.douyin", real or ""):
        return {"platform": "抖音", "title": "直播间", "url": real, "cover": "",
                "page": real, "note": "直播间不支持解析，点链接直接看"}

    aid = ""
    for pattern in (r"/(?:video|note|slides)/(\d{15,25})",
                    r"[?&]modal_id=(\d{15,25})",
                    r"/(\d{15,25})"):
        m = re.search(pattern, real or url)
        if m:
            aid = m.group(1)
            break
    if not aid:
        return None

    cookie = (cfg.get("douyin_cookie") or "").strip()

    # 1) 结构化接口（无需签名，命中率最高）
    api = ("https://www.iesdouyin.com/web/api/v2/aweme/slidesinfo/"
           "?aweme_ids=%5B" + aid + "%5D&request_source=200")
    data = await _get_json(session, api, H_DY_MB, cookie)
    if data:
        aweme = _find_aweme(data)
        if aweme:
            item = _aweme_item(aweme)
            if item:
                return item

    # 2) 分享页 SSR 数据
    for page_url, headers in (
        ("https://www.iesdouyin.com/share/video/%s/" % aid, H_DY_MB),
        ("https://www.douyin.com/video/%s" % aid, H_DY_PC),
    ):
        html = await _get_text(session, page_url, headers, cookie)
        if not html:
            continue
        for marker in ("window._ROUTER_DATA", "window.__INITIAL_STATE__"):
            data = _json_block(html, marker)
            if not data:
                continue
            aweme = _find_aweme(data)
            if aweme:
                item = _aweme_item(aweme)
                if item:
                    return item
        m = re.search(r'<script[^>]+id="RENDER_DATA"[^>]*>(.*?)</script>', html, re.S)
        if m:
            try:
                from urllib.parse import unquote
                data = json.loads(unquote(m.group(1)))
                aweme = _find_aweme(data)
                if aweme:
                    item = _aweme_item(aweme)
                    if item:
                        return item
            except Exception:
                pass

    return {"platform": "抖音", "title": "", "url": "", "cover": "",
            "page": "https://www.douyin.com/video/" + aid, "note": ""}


# ---------------------------------------------------------------- 小红书

def _xhs_note(state, note_id):
    if not isinstance(state, dict):
        return None
    note = None
    try:
        note = state["note"]["noteDetailMap"][note_id]["note"]
    except Exception:
        note = None
    if not note:
        detail = (state.get("noteData") or {}).get("data") or {}
        note = detail.get("noteData")
    if not note:
        mapping = (state.get("note") or {}).get("noteDetailMap") or {}
        for entry in mapping.values():
            if isinstance(entry, dict) and isinstance(entry.get("note"), dict):
                note = entry["note"]
                break
    return note if isinstance(note, dict) else None


def _xhs_stream_url(stream):
    tracks = []
    for codec in ("h264", "h265", "av1", "h266"):
        seq = stream.get(codec)
        if isinstance(seq, list):
            tracks.extend([x for x in seq if isinstance(x, dict)])
    if not tracks:
        return ""
    tracks.sort(key=lambda x: x.get("height") or x.get("width") or 0, reverse=True)
    for track in tracks:
        for key in ("masterUrl", "master_url"):
            if track.get(key):
                return _https(track[key])
        for u in (track.get("backupUrls") or []):
            if u:
                return _https(u)
    return ""


def _xhs_item(note):
    title = note.get("title") or ""
    desc = note.get("desc") or ""
    if not title:
        title = (desc.split("\n")[0] if desc else "")
    video = note.get("video") or {}
    url = ""

    consumer = video.get("consumer") or {}
    origin_key = consumer.get("originVideoKey") or ""
    if origin_key:
        url = "https://sns-video-bd.xhscdn.com/" + str(origin_key).lstrip("/")

    if not url:
        url = _xhs_stream_url(((video.get("media") or {}).get("stream") or {}))
    if not url:
        url = _xhs_stream_url(video.get("stream") or {})

    images = note.get("imageList") or []
    cover = ""
    for img in images:
        if not isinstance(img, dict):
            continue
        cover = _https(img.get("urlDefault") or img.get("url") or "")
        if cover:
            break

    note_text = ""
    if not url and images:
        # 图文笔记：把第一张图当链接，注明张数
        url = ""
        note_text = "图文笔记共 %d 张" % len(images)

    return {
        "platform": "小红书",
        "title": title,
        "url": url,
        "page": "",
        "cover": cover,
        "note": note_text,
        "images": [_https((img.get("urlDefault") or img.get("url") or ""))
                   for img in images if isinstance(img, dict)],
    }


async def parse_xhs(session, url, cfg):
    real = url
    if "xhslink" in url:
        real = await _follow(session, url, H_DY_MB)

    note_id = ""
    for pattern in (r"/(?:explore|discovery/item|item)/([0-9a-fA-F]{24})",
                    r"[?&]noteId=([0-9a-fA-F]{24})"):
        m = re.search(pattern, real or url)
        if m:
            note_id = m.group(1)
            break
    if not note_id:
        return None

    page = real if "xiaohongshu.com" in (real or "") else \
        "https://www.xiaohongshu.com/explore/" + note_id
    cookie = (cfg.get("xhs_cookie") or "").strip()
    html = await _get_text(session, page, H_XHS, cookie)
    if not html:
        return {"platform": "小红书", "title": "", "url": "", "cover": "", "page": page,
                "note": ""}

    state = _json_block(html, "window.__INITIAL_STATE__")
    note = _xhs_note(state, note_id) if state else None
    if not note:
        return {"platform": "小红书", "title": "", "url": "", "cover": "", "page": page,
                "note": ""}

    item = _xhs_item(note)
    item["page"] = page
    return item


# ---------------------------------------------------------------- 快手

def _ks_item(html):
    data = _json_block(html, "window.__APOLLO_STATE__") or \
        _json_block(html, "window.__INITIAL_STATE__")
    if not data:
        return None

    def hit(obj):
        return bool(obj.get("photoUrl") and (obj.get("caption") or obj.get("photoId")))

    photo = _walk_find(data, hit)
    if not photo:
        return None

    cover = ""
    for key in ("coverUrl", "coverUrls", "webpCoverUrl"):
        value = photo.get(key)
        if isinstance(value, str) and value.startswith("http"):
            cover = value
            break
        if isinstance(value, list) and value:
            cover = value[0] if isinstance(value[0], str) else ""
            if cover:
                break

    return {
        "platform": "快手",
        "title": photo.get("caption") or "",
        "url": _https(photo.get("photoUrl")),
        "page": "",
        "cover": _https(cover),
        "note": "",
    }


async def parse_kuaishou(session, url, cfg):
    real = url
    if re.search(r"v\.kuaishou\.com|kuaishouapp\.com", url):
        real = await _follow(session, url, H_DY_MB)

    m = re.search(r"/(?:short-video|photo|fw/photo)/([A-Za-z0-9_-]{6,48})", real or "")
    if not m:
        return None
    photo_id = m.group(1)
    page = "https://www.kuaishou.com/short-video/" + photo_id
    html = await _get_text(session, page, H_KS)
    if not html:
        return {"platform": "快手", "title": "", "url": "", "cover": "", "page": page,
                "note": ""}
    item = _ks_item(html)
    if not item:
        return {"platform": "快手", "title": "", "url": "", "cover": "", "page": page,
                "note": ""}
    item["page"] = page
    return item


# ---------------------------------------------------------------- 调度与发送

PARSERS = {
    "bilibili": parse_bilibili,
    "douyin": parse_douyin,
    "xiaohongshu": parse_xhs,
    "kuaishou": parse_kuaishou,
}


async def _parse_one(session, url, cfg):
    key = _platform_of(url)
    if not key:
        return None
    if not _truthy(cfg.get(key), True):
        return None
    parser = PARSERS.get(key)
    if not parser:
        return None
    try:
        return await parser(session, url, cfg)
    except Exception:
        return None


def _format(item):
    lines = []
    title = _clip(item.get("title") or "", 70)
    head = "【%s】" % item["platform"]
    lines.append(head + title if title else head)
    url = item.get("url") or ""
    page = item.get("page") or ""
    if url:
        lines.append(url)
    if page and page != url:
        lines.append(page)
    if item.get("note"):
        lines.append(item["note"])
    return "\n".join(lines)


async def _deliver(ctx, items):
    sent = False
    with_cover = _truthy(ctx.cfg.get("with_cover"), True)

    for item in items:
        if not item:
            continue
        link = item.get("url") or item.get("page") or ""
        if not link:
            continue
        text = _format(item)
        try:
            await ctx.reply(text)
            sent = True
        except Exception:
            continue

        cover = item.get("cover") or ""
        images = [x for x in (item.get("images") or []) if x]
        extra = images[:3] if images else ([cover] if cover else [])
        if not with_cover or not extra:
            continue
        for src in extra[:3]:
            if not str(src).startswith("http"):
                continue
            try:
                await ctx.send_image(src)
            except Exception:
                pass
    return sent


async def _parse_and_send(ctx, urls):
    try:
        max_links = int(ctx.cfg.get("max_links") or 1)
    except Exception:
        max_links = 1
    urls = urls[:max(1, min(max_links, 3))]

    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(
            *[_parse_one(session, u, ctx.cfg) for u in urls],
            return_exceptions=True,
        )

    items = [r for r in results if isinstance(r, dict)]
    if not items:
        return False
    return await _deliver(ctx, items)


# ---------------------------------------------------------------- 钩子

def on_startup(bot):
    print("[video_parser] 视频解析器已加载（B站 / 抖音 / 小红书 / 快手）")


async def on_message(ctx):
    if not _truthy(ctx.cfg.get("auto_parse"), True):
        return False

    text = ctx.text or ""
    urls = [u for u in _pick_urls(text) if _platform_of(u)]
    if not urls:
        return False

    key = "g:" + ctx.group_id if ctx.group_id else "u:" + ctx.user_id
    try:
        cooldown = float(ctx.cfg.get("cooldown") or 0)
    except Exception:
        cooldown = 0.0
    now = time.time()
    if cooldown > 0 and now - _LAST.get(key, 0) < cooldown:
        return False
    _LAST[key] = now

    return await _parse_and_send(ctx, urls)


async def cmd_parse(ctx, args):
    text = args if isinstance(args, str) else ""
    urls = _pick_urls(text) or _pick_urls(ctx.text or "")
    supported = [u for u in urls if _platform_of(u)]

    if not urls:
        await ctx.reply("用法：/解析 <分享链接>\n支持 B站、抖音、小红书、快手")
        return True
    if not supported:
        await ctx.reply("这个链接不在支持范围，目前支持 B站、抖音、小红书、快手")
        return True

    ok = await _parse_and_send(ctx, supported)
    if not ok:
        await ctx.reply("解析失败了，可能是作品已删除、私密，或者平台改版了")
    return True


async def cmd_status(ctx, args):
    enabled = [PLATFORMS[k] for k in PLATFORMS if _truthy(ctx.cfg.get(k), True)]
    lines = [
        "视频解析器",
        "已启用：%s" % ("、".join(enabled) if enabled else "无"),
        "自动解析：%s" % ("开" if _truthy(ctx.cfg.get("auto_parse"), True) else "关"),
        "附带封面：%s" % ("开" if _truthy(ctx.cfg.get("with_cover"), True) else "关"),
        "B站清晰度：%s" % (ctx.cfg.get("bili_quality") or 64),
        "用法：/解析 <链接>，或直接把分享链接发到群里",
    ]
    await ctx.reply("\n".join(lines))
    return True

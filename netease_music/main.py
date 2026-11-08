"""网易云点歌 · YueWuBot 原生版

移植自 https://github.com/xiaoyunsha/astrbot_plugin_netease_music
原版依赖 NeteaseCloudMusic SDK + requests，这里改为纯 aiohttp 直连官方接口，
不引入任何额外依赖。功能保持一致：搜索、点歌、封面、播放直链、音乐卡片、
VIP Cookie、结果缓存。

命令：
  /网易搜歌 关键词    搜索
  /网易点歌 序号      点播
  /网易点歌帮助       帮助
不带斜杠的「网易搜歌 晴天」「网易点歌 1」同样可用。
"""

import asyncio
import json
import re
import time
from pathlib import Path

import aiohttp

VERSION = "1.0.0"
BASE = "https://music.163.com"
API_SEARCH = BASE + "/api/search/get"
API_SEARCH_PC = BASE + "/api/cloudsearch/pc"
API_DETAIL = BASE + "/api/song/detail"
API_PLAY = BASE + "/api/song/enhance/player/url"
API_OUTER = BASE + "/song/media/outer/url"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

HEADERS = {
    "User-Agent": UA,
    "Referer": BASE + "/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

CACHE_FILE = Path(__file__).parent / "data" / "cache.json"

_SESSION = None
_CACHE = {}


# ------------------------------------------------------------------ 会话
def _session():
    global _SESSION
    if _SESSION is None or _SESSION.closed:
        _SESSION = aiohttp.ClientSession(headers=HEADERS)
    return _SESSION


async def on_startup(bot):
    _load_cache()
    print("[netease_music] 网易云点歌插件已加载（缓存 %d 组）" % len(_CACHE))


async def on_shutdown(bot):
    global _SESSION
    if _SESSION is not None and not _SESSION.closed:
        try:
            await _SESSION.close()
        except Exception:
            pass
    _SESSION = None


# ------------------------------------------------------------------ 配置
def _cfg_int(ctx, key, default, low=0, high=1000000):
    try:
        v = int((ctx.cfg or {}).get(key, default))
    except Exception:
        v = default
    return max(low, min(v, high))


def _cfg_bool(ctx, key, default=True):
    v = (ctx.cfg or {}).get(key, default)
    if isinstance(v, bool):
        return v
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on", "是", "开")


def _cookie(ctx):
    return str((ctx.cfg or {}).get("cookie") or "").strip()


# ------------------------------------------------------------------ 网络
def _headers(cookie=""):
    h = dict(HEADERS)
    # 匿名也带一个最简 Cookie，能显著降低 -462 风控概率
    h["Cookie"] = cookie if cookie else "os=pc; appver=8.9.70"
    return h


async def _get_json(url, params, cookie="", timeout=12):
    async with _session().get(url, params=params, headers=_headers(cookie),
                              timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
        if resp.status >= 400:
            raise RuntimeError("HTTP %d" % resp.status)
        return json.loads(await resp.text())


def _parse_songs(raw):
    songs = []
    for s in raw or []:
        artists = s.get("ar") or s.get("artists") or []
        album = s.get("al") or s.get("album") or {}
        names = [a.get("name", "") for a in artists if isinstance(a, dict) and a.get("name")]
        songs.append({
            "id": s.get("id"),
            "name": s.get("name") or "未知歌曲",
            "artists": "/".join(names) or "未知歌手",
            "album": album.get("name") or "未知专辑",
            "cover": album.get("picUrl") or "",
            "duration": s.get("dt") or s.get("duration") or 0,
        })
    return songs


async def _search(keyword, limit, cookie):
    params = {"s": keyword, "type": 1, "limit": limit, "offset": 0}
    data = {}
    delays = (0.8, 1.6)
    for attempt in range(3):
        try:
            data = await _get_json(API_SEARCH, params, cookie)
        except Exception:
            data = {}
        if data.get("code") == 200:
            raw = ((data.get("result") or {}).get("songs")) or []
            if raw:
                return _parse_songs(raw)
        if attempt < len(delays):
            await asyncio.sleep(delays[attempt])

    # 兜底：PC 云搜索接口，字段结构一致
    try:
        data = await _get_json(API_SEARCH_PC, params, cookie or "os=pc; appver=8.9.70")
        raw = ((data.get("result") or {}).get("songs")) or []
        if data.get("code") == 200 and raw:
            return _parse_songs(raw)
    except Exception:
        pass

    raise RuntimeError("接口返回 %s" % (data.get("code") if isinstance(data, dict) else "?"))


async def _detail(song_id, cookie):
    data = await _get_json(API_DETAIL, {"ids": "[%s]" % song_id}, cookie)
    songs = data.get("songs") or []
    if not songs:
        return {}
    s = songs[0]
    album = s.get("al") or s.get("album") or {}
    return {
        "cover": album.get("picUrl") or "",
        "duration": s.get("dt") or s.get("duration") or 0,
    }


async def _play_url(song_id, br, cookie):
    try:
        data = await _get_json(API_PLAY, {"ids": "[%s]" % song_id, "br": br}, cookie, timeout=15)
    except Exception:
        data = {}

    arr = data.get("data") or []
    if arr and isinstance(arr[0], dict):
        item = arr[0]
        if item.get("url"):
            return {
                "url": item["url"],
                "br": item.get("br") or br,
                "trial": bool(item.get("freeTrialInfo")),
            }

    # 兜底：outer 链，免费歌曲可直接 302 到音频
    try:
        async with _session().get(API_OUTER, params={"id": "%s.mp3" % song_id},
                                  headers=_headers(cookie), allow_redirects=False,
                                  timeout=aiohttp.ClientTimeout(total=10)) as resp:
            loc = resp.headers.get("Location") or ""
            if resp.status in (301, 302) and loc and "404" not in loc:
                if loc.startswith("/"):
                    loc = BASE + loc
                return {"url": loc, "br": 0, "trial": False}
    except Exception:
        pass
    return None


# ------------------------------------------------------------------ 缓存
def _cache_key(ctx):
    return "%s:%s" % (ctx.group_id or "private", str(ctx.user_id or ""))


def _load_cache():
    global _CACHE
    if not CACHE_FILE.exists():
        return
    try:
        data = json.loads(CACHE_FILE.read_text("utf-8"))
        if isinstance(data, dict):
            _CACHE = {k: v for k, v in data.items() if isinstance(v, dict)}
    except Exception:
        _CACHE = {}


def _save_cache():
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = CACHE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(_CACHE, ensure_ascii=False), "utf-8")
        tmp.replace(CACHE_FILE)
    except Exception:
        pass


def _cache_put_key(key, songs):
    now = time.time()
    for k in [k for k, v in _CACHE.items() if now - float(v.get("ts") or 0) > 6 * 3600]:
        _CACHE.pop(k, None)
    _CACHE[key] = {"ts": now, "songs": songs}
    _save_cache()


def _cache_get_key(key, timeout):
    item = _CACHE.get(key)
    if not item:
        return None
    if time.time() - float(item.get("ts") or 0) > timeout:
        _CACHE.pop(key, None)
        return None
    songs = item.get("songs")
    return songs if isinstance(songs, list) else None


def _cache_put(ctx, songs):
    _cache_put_key(_cache_key(ctx), songs)


def _cache_get(ctx, timeout):
    return _cache_get_key(_cache_key(ctx), timeout)


def _kw_key(keyword, limit):
    return "kw:%s:%d" % (str(keyword).strip().lower(), limit)


# ------------------------------------------------------------------ 工具
def _fmt_duration(ms):
    try:
        ms = int(ms or 0)
    except Exception:
        ms = 0
    if ms <= 0:
        return "00:00"
    s = ms // 1000
    return "%02d:%02d" % (s // 60, s % 60)


def _https(url):
    url = str(url or "")
    if url.startswith("http://"):
        return "https://" + url[7:]
    return url


def _cover(url, size=500):
    url = _https(url)
    if not url:
        return ""
    if "?param=" in url:
        url = url.split("?param=")[0]
    return "%s?param=%dy%d" % (url, size, size)


async def _send_segments(ctx, segments):
    ob = getattr(ctx, "ob", None)
    if ob is None or not hasattr(ob, "send_rich"):
        return None
    return await ob.send_rich(ctx.message_type, ctx.target, segments,
                              socket=getattr(ctx, "_ws", None))


# ------------------------------------------------------------------ 帮助
async def cmd_help(ctx, args):
    has_cookie = bool(_cookie(ctx))
    vip = "已配置，可点 VIP 完整版" if has_cookie else "未配置，仅免费歌曲或 30 秒试听"
    lines = [
        "网易云点歌 v%s" % VERSION,
        "",
        "/网易搜歌 关键词    搜索歌曲",
        "   例：/网易搜歌 晴天",
        "/网易点歌 序号      点播歌曲",
        "   例：/网易点歌 1",
        "/网易点歌帮助       查看本帮助",
        "",
        "VIP Cookie：%s" % vip,
        "也可以不带斜杠：网易搜歌 晴天",
    ]
    return await ctx.reply("\n".join(lines))


# ------------------------------------------------------------------ 搜索
async def cmd_search(ctx, args):
    keyword = (args or "").strip()
    if not keyword:
        return await ctx.reply("请提供搜索关键词，例如：/网易搜歌 晴天")
    if len(keyword) > 50:
        keyword = keyword[:50]

    limit = _cfg_int(ctx, "search_limit", 10, low=1, high=30)
    cookie = _cookie(ctx)
    timeout = _cfg_int(ctx, "cache_timeout", 300, low=30, high=86400)

    songs = _cache_get_key(_kw_key(keyword, limit), timeout)
    if songs is None:
        try:
            songs = await _search(keyword, limit, cookie)
        except Exception:
            return await ctx.reply("搜索失败，网易云接口可能繁忙，稍后再试")
        if not songs:
            return await ctx.reply("没有找到与「%s」相关的歌曲" % keyword)
        _cache_put_key(_kw_key(keyword, limit), songs)

    _cache_put(ctx, songs)

    lines = ["搜索「%s」的结果（%d 首）：" % (keyword, len(songs)), ""]
    for i, s in enumerate(songs, 1):
        lines.append("%d. %s - %s" % (i, s["name"], s["artists"]))
        lines.append("   专辑：%s · %s" % (s["album"], _fmt_duration(s["duration"])))
    lines.append("")
    lines.append("回复 /网易点歌 序号 即可点播")
    if not cookie:
        lines.append("提示：配置 Cookie 后可点 VIP 歌曲完整版")
    return await ctx.reply("\n".join(lines))


# ------------------------------------------------------------------ 点歌
async def cmd_play(ctx, args):
    text = (args or "").strip()
    if not text:
        return await ctx.reply("请提供歌曲序号，例如：/网易点歌 1\n先用 /网易搜歌 搜索歌曲")

    m = re.match(r"^#?(\d+)", text)
    if not m:
        return await ctx.reply("序号必须是数字，例如：/网易点歌 1")

    index = int(m.group(1)) - 1
    timeout = _cfg_int(ctx, "cache_timeout", 300, low=30, high=86400)
    songs = _cache_get(ctx, timeout)
    if not songs:
        return await ctx.reply("请先搜索歌曲：/网易搜歌 关键词，再 /网易点歌 序号")
    if index < 0 or index >= len(songs):
        return await ctx.reply("序号超出范围（1-%d），请重新输入" % len(songs))

    song = songs[index]
    sid = song.get("id")
    name = song.get("name") or "未知歌曲"
    artists = song.get("artists") or "未知歌手"
    album = song.get("album") or "未知专辑"
    cover = song.get("cover") or ""
    duration = song.get("duration") or 0
    cookie = _cookie(ctx)
    br = _cfg_int(ctx, "bitrate", 320000, low=64000, high=999000)

    # 搜索接口偶尔缺封面/时长，用详情补齐并回写缓存
    if not cover or not duration:
        try:
            detail = await _detail(sid, cookie)
            if detail.get("cover"):
                cover = detail["cover"]
                song["cover"] = cover
            if detail.get("duration"):
                duration = detail["duration"]
                song["duration"] = duration
            _save_cache()
        except Exception:
            pass

    try:
        play = await _play_url(sid, br, cookie)
    except Exception:
        play = None

    lines = [
        "%s - %s" % (name, artists),
        "专辑：%s" % album,
        "时长：%s" % _fmt_duration(duration),
    ]

    if play and play.get("url"):
        if play.get("br"):
            lines.append("音质：%dkbps" % (int(play["br"]) // 1000))
        lines.append("链接：%s" % _https(play["url"]))
        if play.get("trial"):
            lines.append("注意：VIP 歌曲，当前仅 30 秒试听")
        elif cookie:
            lines.append("会员 Cookie 已生效")
    else:
        lines.append("暂时拿不到播放直链")
        lines.append("可能是 VIP 或版权限制，配置 Cookie 后可重试" if not cookie else "Cookie 可能已过期")

    message_text = "\n".join(lines)

    # 优先音乐卡片，失败自动降级为图文
    if play and play.get("url") and _cfg_bool(ctx, "music_card", True) and cover:
        seg = {
            "type": "music",
            "data": {
                "type": "custom",
                "url": "https://music.163.com/song?id=%s" % sid,
                "audio": _https(play["url"]),
                "title": name,
                "content": artists,
                "image": _cover(cover, 300),
            },
        }
        try:
            resp = await _send_segments(ctx, [seg])
            if isinstance(resp, dict) and str(resp.get("status", "")).lower() in ("ok", "async") \
                    and int(resp.get("retcode") or 0) == 0:
                return
        except Exception:
            pass

    await ctx.reply(message_text)
    if cover:
        try:
            await ctx.send_image(_cover(cover, 500))
        except Exception:
            pass


# ------------------------------------------------------------------ 无斜杠入口
async def on_message(ctx):
    text = (getattr(ctx, "text", "") or "").strip()
    if not text:
        return False

    m = re.match(r"^(?:网易搜歌|网易搜索)\s+(.+)$", text, re.S)
    if m:
        await cmd_search(ctx, m.group(1))
        return True

    m = re.match(r"^(?:网易点歌|网易播放)\s+#?(\d+)$", text)
    if m:
        await cmd_play(ctx, m.group(1))
        return True

    if re.match(r"^(?:网易点歌帮助|网易帮助)$", text):
        await cmd_help(ctx, "")
        return True

    return False

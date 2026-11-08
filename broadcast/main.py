"""广播插件

管理员引用（回复）一条消息后发送 /广播，机器人把这条消息原样转发到
它当前加入的所有群。

用法：
  （先引用一条消息）/广播
  别名：/群发  /broadcast

权限：仅机器人管理员（控制台「管理员」列表中的账号，或插件配置里指定的 admin_qq）。
"""

import asyncio
import time

VERSION = "1.0.0"
DEFAULT_ADMIN = ""

# 广播过程中拒绝重复触发
_LOCK = {"until": 0.0}
_COOLDOWN = 8.0

# 不参与转发的消息段：引用标记、@、骰子/猜拳等跨群无意义或会失效的内容
_DROP = {"reply", "source", "at", "rps", "dice", "mface", "bface", "sface"}


def _log(msg):
    try:
        print("[broadcast] " + str(msg), flush=True)
    except Exception:
        pass


# ------------------------------------------------------------------ 工具
def _cfg(ctx, key, default=None):
    try:
        conf = getattr(ctx, "cfg", None) or {}
        return conf.get(key, default)
    except Exception:
        return default


def _is_admin(ctx):
    uid = str(getattr(ctx, "user_id", "") or "").strip()
    if not uid:
        return False
    owner = str(_cfg(ctx, "admin_qq", DEFAULT_ADMIN) or "").strip()
    if owner and uid == owner:
        return True
    try:
        return bool(ctx.bot.plugins.is_admin(uid))
    except Exception:
        return False


def _interval(ctx):
    try:
        v = float(_cfg(ctx, "interval", 1.2))
    except Exception:
        v = 1.2
    return max(0.3, min(v, 10.0))


def _max_groups(ctx):
    try:
        v = int(_cfg(ctx, "max_groups", 0) or 0)
    except Exception:
        v = 0
    return max(0, v)


def _skip_source(ctx):
    v = _cfg(ctx, "skip_source", True)
    if isinstance(v, str):
        return v.strip().lower() not in ("0", "false", "no", "否", "关")
    return bool(v)


def _segments(ctx):
    try:
        segs = ctx.bot.segments(ctx.raw)
        return segs if isinstance(segs, list) else []
    except Exception:
        msg = (getattr(ctx, "raw", None) or {}).get("message")
        return msg if isinstance(msg, list) else []


def _as_segments(bot, msg):
    """get_msg 返回的 message 可能是数组，也可能是 CQ 字符串。"""
    if isinstance(msg, list):
        return msg
    try:
        return bot.segments({"raw_message": str(msg or "")})
    except Exception:
        return []


def _reply_id(ctx):
    for seg in _segments(ctx):
        if seg.get("type") != "reply":
            continue
        data = seg.get("data") or {}
        rid = data.get("id") or data.get("message_id") or data.get("msg_id")
        if rid:
            return str(rid)
    return ""


def _clean(segs):
    """去掉引用/@ 等段，图片、语音、视频优先改用 url，方便跨群重发。"""
    out = []
    for seg in segs or []:
        if not isinstance(seg, dict):
            continue
        typ = str(seg.get("type") or "")
        if not typ or typ in _DROP:
            continue
        data = dict(seg.get("data") or {})
        if typ in ("image", "record", "video"):
            url = str(data.get("url") or "")
            if url:
                data["file"] = url
            elif not data.get("file"):
                continue
        out.append({"type": typ, "data": data})
    return out


def _preview(segs, limit=40):
    parts = []
    for seg in segs:
        typ = seg.get("type")
        if typ == "text":
            parts.append(str((seg.get("data") or {}).get("text") or ""))
        elif typ == "image":
            parts.append("[图片]")
        elif typ == "record":
            parts.append("[语音]")
        elif typ == "video":
            parts.append("[视频]")
        else:
            parts.append("[%s]" % typ)
    text = "".join(parts).strip()
    return (text[:limit] + "…") if len(text) > limit else (text or "（无文字）")


# ------------------------------------------------------------------ OneBot
async def _fetch(ctx, mid):
    try:
        mid_val = int(mid)
    except Exception:
        mid_val = mid
    resp = await ctx.api("get_msg", message_id=mid_val)
    if not isinstance(resp, dict):
        raise RuntimeError("接口没有返回数据")
    code = resp.get("retcode")
    if resp.get("status") not in (None, "ok") or (code not in (None, 0)):
        raise RuntimeError(str(resp.get("wording") or resp.get("message") or "取消息失败")[:80])
    return resp.get("data") or {}


async def _group_list(ctx):
    resp = await ctx.api("get_group_list")
    if not isinstance(resp, dict):
        raise RuntimeError("群列表接口没有返回数据")
    code = resp.get("retcode")
    if resp.get("status") not in (None, "ok") or (code not in (None, 0)):
        raise RuntimeError(str(resp.get("wording") or resp.get("message") or "取群列表失败")[:80])
    data = resp.get("data")
    if not isinstance(data, list):
        raise RuntimeError("群列表格式异常")
    seen, out = set(), []
    for g in data:
        if not isinstance(g, dict):
            continue
        gid = g.get("group_id") or g.get("group") or g.get("id")
        if not gid:
            continue
        gid = str(gid)
        if gid in seen:
            continue
        seen.add(gid)
        out.append((gid, str(g.get("group_name") or g.get("name") or "")))
    return out


async def _send_group(ctx, gid, segs):
    return await ctx.ob.send_rich("group", gid, segs, socket=getattr(ctx, "_ws", None))


# ------------------------------------------------------------------ 主流程
async def cmd_broadcast(ctx, args):
    if not _is_admin(ctx):
        return await ctx.reply("权限不足：广播仅限机器人管理员使用")

    now = time.time()
    if now < _LOCK["until"]:
        return await ctx.reply("上一条广播还在发送中，请稍等…")

    mid = _reply_id(ctx)
    if not mid:
        return await ctx.reply("请先引用（回复）一条要广播的消息，再发送 /广播\n用法：（引用一条消息）/广播")

    try:
        src = await _fetch(ctx, mid)
    except Exception as e:
        return await ctx.reply("取不到被引用的消息：%s" % str(e)[:100])

    raw_msg = src.get("message")
    if not raw_msg:
        raw_msg = src.get("raw_message")
    segs = _clean(_as_segments(ctx.bot, raw_msg))
    if not segs:
        return await ctx.reply("这条消息没有可广播的内容（纯引用、纯表情或已失效）")

    try:
        groups = await _group_list(ctx)
    except Exception as e:
        return await ctx.reply("获取群列表失败：%s" % str(e)[:100])
    if not groups:
        return await ctx.reply("机器人还没有加入任何群")

    source = str(getattr(ctx, "group_id", "") or "")
    if source and _skip_source(ctx):
        groups = [g for g in groups if g[0] != source]
    if not groups:
        return await ctx.reply("除当前群外没有其他群可广播")

    max_n = _max_groups(ctx)
    cut = 0
    if max_n and len(groups) > max_n:
        cut = len(groups) - max_n
        groups = groups[:max_n]

    total = len(groups)
    interval = _interval(ctx)
    # 锁按预计耗时释放，群多时也不会中途被重复触发
    _LOCK["until"] = time.time() + total * (interval + 1.5) + 30
    await ctx.reply("开始广播：共 %d 个群\n内容：%s" % (total, _preview(segs)))

    ok, fails = 0, []
    started = time.time()

    for idx, (gid, gname) in enumerate(groups, 1):
        err = ""
        for attempt in (1, 2):
            try:
                await _send_group(ctx, gid, segs)
                ok += 1
                err = ""
                break
            except Exception as e:
                err = str(e)
                if attempt == 1:
                    await asyncio.sleep(0.8)
        if err:
            fails.append((gid, gname, err[:60]))
            _log("发送失败 %s(%s): %s" % (gname or "?", gid, err[:120]))
        if idx < total:
            await asyncio.sleep(interval)

    _LOCK["until"] = 0
    cost = time.time() - started

    lines = ["广播完成（%.1fs）" % cost,
             "目标群：%d　成功：%d　失败：%d" % (total, ok, len(fails))]
    if cut:
        lines.append("已达到单次上限，另有 %d 个群未发送" % cut)
    if fails:
        lines.append("")
        for gid, gname, err in fails[:10]:
            lines.append("✗ %s（%s）%s" % (gname or "未命名群", gid, err))
        if len(fails) > 10:
            lines.append("……另有 %d 个群发送失败" % (len(fails) - 10))
    _log("广播完成：%d/%d，失败 %d" % (ok, total, len(fails)))
    return await ctx.reply("\n".join(lines))


async def on_startup(bot):
    _log("广播插件已加载 v%s" % VERSION)

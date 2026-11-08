import json
import re
import time
from pathlib import Path

ASSETS = Path(__file__).parent / "assets"
DB = ASSETS / "pending.json"
DEFAULT_OWNER = "3835347820"


def _load():
    try:
        data = json.loads(DB.read_text("utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save(data):
    try:
        ASSETS.mkdir(parents=True, exist_ok=True)
        DB.write_text(json.dumps(data, ensure_ascii=False), "utf-8")
    except Exception:
        pass


def _expire(data, hours):
    try:
        limit = max(float(hours or 48), 0.1) * 3600
    except Exception:
        limit = 48 * 3600
    now = time.time()
    return {k: v for k, v in data.items() if now - float(v.get("ts") or now) < limit}


def _owner(ctx):
    return str((ctx.cfg or {}).get("owner") or DEFAULT_OWNER)


def _is_owner(ctx):
    return bool(ctx.user_id) and str(ctx.user_id) == _owner(ctx)


def _text(ev):
    return str(ev.get("comment") or "").strip()[:120]


def on_startup(bot):
    print("[request_approve] 入群与好友审批已加载")


async def on_request(ctx):
    ev = ctx.raw or {}
    kind = str(ev.get("request_type") or "")
    flag = str(ev.get("flag") or "")
    if not flag or kind not in ("friend", "group"):
        return False
    sub = str(ev.get("sub_type") or "")
    if kind == "friend":
        key = str(ev.get("user_id") or "")
        title = "好友申请"
    else:
        key = str(ev.get("group_id") or "")
        title = "入群邀请" if sub == "invite" else "入群申请"
    if not key:
        return False
    conf = ctx.cfg or {}
    data = _expire(_load(), conf.get("expire_hours"))
    rec = {
        "type": kind,
        "sub_type": sub,
        "flag": flag,
        "key": key,
        "user_id": str(ev.get("user_id") or ""),
        "group_id": str(ev.get("group_id") or ""),
        "ts": time.time(),
    }
    data[kind + ":" + key] = rec
    _save(data)
    lines = [
        "[待审批 · %s]" % title,
        "号码：%s" % key,
        "申请人：%s" % (rec["user_id"] or "-"),
    ]
    if _text(ev):
        lines.append("验证消息：%s" % _text(ev))
    lines.append("同意请回复 /同意 %s" % key)
    lines.append("拒绝请回复 /拒绝（默认拒绝全部）")
    try:
        await ctx.api("send_private_msg", user_id=int(_owner(ctx)), message="\n".join(lines))
    except Exception:
        pass
    return True


def _pick(data, key):
    return [(k, v) for k, v in data.items() if str(v.get("key")) == key or k.endswith(":" + key)]


async def _apply(ctx, rec, approve):
    if rec.get("type") == "friend":
        return await ctx.api("set_friend_add_request", flag=rec["flag"], approve=approve, remark="")
    return await ctx.api("set_group_add_request", flag=rec["flag"], sub_type=rec.get("sub_type") or "invite",
                         approve=approve, reason="")


async def cmd_agree(ctx, args):
    if not _is_owner(ctx):
        return True
    m = re.search(r"\d{5,12}", args or "")
    if not m:
        await ctx.reply("请带上 QQ 号或群号，例如 /同意 123456，可先发 /待审批 查看")
        return True
    key = m.group(0)
    data = _expire(_load(), (ctx.cfg or {}).get("expire_hours"))
    hits = _pick(data, key)
    if not hits:
        await ctx.reply("没有找到 %s 对应的待审批请求" % key)
        return True
    done = 0
    for k, rec in hits:
        try:
            await _apply(ctx, rec, True)
            data.pop(k, None)
            done += 1
        except Exception:
            pass
    _save(data)
    await ctx.reply("已同意 %s 的请求（%d 条）" % (key, done))
    return True


async def cmd_refuse(ctx, args):
    if not _is_owner(ctx):
        return True
    m = re.search(r"\d{5,12}", args or "")
    data = _expire(_load(), (ctx.cfg or {}).get("expire_hours"))
    hits = _pick(data, m.group(0)) if m else list(data.items())
    if not hits:
        await ctx.reply("当前没有待审批的请求" if not m else "没有找到 %s 对应的待审批请求" % m.group(0))
        return True
    done = 0
    for k, rec in hits:
        try:
            await _apply(ctx, rec, False)
            data.pop(k, None)
            done += 1
        except Exception:
            pass
    _save(data)
    await ctx.reply("已拒绝 %d 个请求" % done if not m else "已拒绝 %s 的请求（%d 条）" % (m.group(0), done))
    return True


async def cmd_pending(ctx, args):
    if not _is_owner(ctx):
        return True
    data = _expire(_load(), (ctx.cfg or {}).get("expire_hours"))
    _save(data)
    if not data:
        await ctx.reply("当前没有待审批的请求")
        return True
    lines = ["待审批请求（%d 条）" % len(data)]
    for rec in data.values():
        label = "好友" if rec.get("type") == "friend" else "入群"
        lines.append("%s %s  /同意 %s" % (label, rec.get("key"), rec.get("key")))
    lines.append("/拒绝 可拒绝全部")
    await ctx.reply("\n".join(lines))
    return True

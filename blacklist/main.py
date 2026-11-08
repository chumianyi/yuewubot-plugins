import json
import re
from pathlib import Path

ASSETS = Path(__file__).parent / "assets"
DB = ASSETS / "blacklist.json"
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


def _truthy(value):
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in ("1", "true", "yes", "on", "是", "开")


def _ids(ctx):
    conf = ctx.cfg or {}
    out = set()
    for part in re.split(r"[,\s，;；、]+", str(conf.get("extra") or "")):
        part = part.strip()
        if part.isdigit():
            out.add(part)
    for k in _load().keys():
        if str(k).isdigit():
            out.add(str(k))
    owner = str(conf.get("owner") or DEFAULT_OWNER)
    out.discard(owner)
    return out


def _is_owner(ctx):
    return bool(ctx.user_id) and str(ctx.user_id) == str((ctx.cfg or {}).get("owner") or DEFAULT_OWNER)


def _digits(args):
    m = re.search(r"\d{5,12}", args or "")
    return m.group(0) if m else ""


async def on_filter(ctx):
    uid = str(ctx.user_id or "")
    if not uid or uid not in _ids(ctx):
        return False
    if _truthy((ctx.cfg or {}).get("notify")):
        try:
            await ctx.reply("你暂时不能和我聊天哦")
        except Exception:
            pass
    return True


async def cmd_add(ctx, args):
    if not _is_owner(ctx):
        return True
    uid = _digits(args)
    if not uid:
        await ctx.reply("格式：/拉黑 123456")
        return True
    if uid == str((ctx.cfg or {}).get("owner") or DEFAULT_OWNER):
        await ctx.reply("主人不能拉黑自己")
        return True
    data = _load()
    if uid in data:
        await ctx.reply("%s 已经在黑名单里了" % uid)
        return True
    data[uid] = {"reason": "manual"}
    _save(data)
    await ctx.reply("已拉黑 %s" % uid)
    return True


async def cmd_del(ctx, args):
    if not _is_owner(ctx):
        return True
    uid = _digits(args)
    if not uid:
        await ctx.reply("格式：/解封 123456")
        return True
    data = _load()
    data.pop(uid, None)
    _save(data)
    await ctx.reply("已解封 %s" % uid)
    return True


async def cmd_list(ctx, args):
    ids = sorted(_ids(ctx))
    if not ids:
        await ctx.reply("黑名单是空的")
        return True
    await ctx.reply("黑名单（%d 个）\n%s" % (len(ids), "  ".join(ids[:60])))
    return True

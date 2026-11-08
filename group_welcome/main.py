DEFAULT_OWNER = "3835347820"
DEFAULT_TEXT = "，你好呀，我是小鸟游星野，我的主人是{owner}"


def _truthy(value, default=True):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on", "是", "开")


async def on_notice(ctx):
    ev = ctx.raw or {}
    if ev.get("notice_type") != "group_increase":
        return False
    gid = str(ev.get("group_id") or "")
    uid = str(ev.get("user_id") or "")
    if not gid or not uid:
        return False
    self_id = str(getattr(ctx.ob, "self_id", "") or "")
    if self_id and uid == self_id:
        return False
    conf = ctx.cfg or {}
    owner = str(conf.get("owner") or DEFAULT_OWNER)
    text = str(conf.get("welcome") or DEFAULT_TEXT).replace("{owner}", owner)
    segs = []
    if _truthy(conf.get("at_user")):
        segs.append({"type": "at", "data": {"qq": uid}})
    segs.append({"type": "text", "data": {"text": text}})
    try:
        await ctx.api("send_group_msg", group_id=int(gid), message=segs)
    except Exception:
        return False
    return True

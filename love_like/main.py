import json
import time
from pathlib import Path

ASSETS = Path(__file__).parent / "assets"
DB = ASSETS / "like.json"

REPLY_OK = "我给你点了十下哦，记得给我回。"
REPLY_DUP = "今天好像点过了哈，明天再点吧～"
REPLY_FAIL = "点赞没成功，等会儿再试试吧（%s）"


def _load():
    try:
        data = json.loads(DB.read_text("utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save(data):
    ASSETS.mkdir(parents=True, exist_ok=True)
    DB.write_text(json.dumps(data, ensure_ascii=False), "utf-8")


def _norm(text):
    return (text or "").strip().strip(" \t\r\n!！。.~～?？,，、…·")


def _failed(resp):
    """判定平台是否拒绝了这次点赞，返回 (失败?, 原因)"""
    if not isinstance(resp, dict):
        return True, "平台没有回应"
    try:
        code = int(resp.get("retcode", 0))
    except Exception:
        code = -1
    status = str(resp.get("status") or "").lower()
    if code == 0 and status in ("", "ok", "async"):
        return False, ""
    why = str(resp.get("wording") or resp.get("message") or resp.get("msg") or "").strip()
    if not why:
        why = ("retcode %s" % code) if code else "平台拒绝了这次点赞"
    return True, why


def on_startup(bot):
    print("[love_like] 爱点赞插件已加载")


async def on_message(ctx):
    if _norm(ctx.text) != "赞我":
        return False

    uid = str(ctx.user_id or "")
    if not uid.isdigit():
        return False

    try:
        times = int(ctx.cfg.get("times") or 10)
    except Exception:
        times = 10
    times = max(1, min(times, 20))

    # 不做本地冷却判断：是否已经点过由平台接口的结果决定，避免误判
    try:
        resp = await ctx.api("send_like", user_id=int(uid), times=times)
    except Exception as exc:
        await ctx.reply(REPLY_FAIL % str(exc)[:60])
        return True

    failed, why = _failed(resp)
    if failed:
        # 接口失败基本都是「今天已经点过了 / 次数已达上限」
        await ctx.reply(REPLY_DUP)
        return True

    db = _load()
    rec = db.get(uid) or {}
    db[uid] = {"last": time.time(), "total": int(rec.get("total") or 0) + 1}
    _save(db)
    await ctx.reply(REPLY_OK)
    return True

import json
import time
from pathlib import Path

ASSETS = Path(__file__).parent / "assets"
DB = ASSETS / "signin.json"

def _load():
    if DB.exists():
        try:
            return json.loads(DB.read_text("utf-8"))
        except Exception:
            return {}
    return {}

def _save(d):
    DB.parent.mkdir(parents=True, exist_ok=True)
    DB.write_text(json.dumps(d, ensure_ascii=False), "utf-8")

def on_startup(bot):
    print("[signin] 签到插件已加载")

async def cmd_signin(ctx, args):
    db = _load()
    today = time.strftime("%Y-%m-%d")
    rec = db.setdefault(ctx.user_id, {"days": 0, "last": "", "total": 0})
    if rec.get("last") == today:
        return await ctx.reply("今天已经签过啦，明天再来～")
    rec["days"] = int(rec.get("days", 0)) + 1
    rec["total"] = int(rec.get("total", 0)) + 1
    rec["last"] = today
    _save(db)
    bonus = ctx.cfg.get("bonus", 10)
    return await ctx.reply("签到成功！已连续 %d 天，获得 %s 积分" % (rec["days"], bonus))

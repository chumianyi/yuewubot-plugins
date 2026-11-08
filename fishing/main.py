import json
import math
import random
import re
import sqlite3
import time
from pathlib import Path

ASSETS = Path(__file__).parent / "assets"
DB = ASSETS / "fishing.db"
OWNER = "3835347820"
LINE = "-" * 28

SPECIES = [
    ("小鲫鱼", 1, 8, 0.1, 0.6, 1), ("白条鱼", 1, 10, 0.1, 0.5, 1),
    ("麦穗鱼", 1, 9, 0.1, 0.4, 1), ("泥鳅", 1, 12, 0.2, 0.8, 1),
    ("河虾", 1, 11, 0.1, 0.3, 1), ("小鲤鱼", 2, 22, 0.4, 1.6, 1),
    ("草鱼", 2, 28, 0.8, 3.2, 1), ("鲢鱼", 2, 26, 0.9, 3.6, 1),
    ("罗非鱼", 2, 24, 0.5, 2.0, 1), ("黄颡鱼", 2, 32, 0.3, 1.2, 1),
    ("鲈鱼", 3, 60, 1.0, 4.5, 1), ("鳜鱼", 3, 78, 0.8, 3.5, 1),
    ("黑鱼", 3, 66, 1.2, 5.0, 1), ("鲶鱼", 3, 58, 1.5, 6.0, 1),
    ("鳗鲡", 3, 88, 0.9, 3.0, 1), ("石斑鱼", 4, 160, 2.0, 8.0, 2),
    ("真鲷", 4, 180, 1.8, 7.0, 2), ("比目鱼", 4, 150, 1.5, 6.0, 2),
    ("金枪鱼", 4, 210, 8.0, 30.0, 2), ("剑鱼", 4, 195, 6.0, 22.0, 2),
    ("海鳗", 5, 360, 2.5, 9.0, 2), ("鲨鱼幼崽", 5, 420, 12.0, 40.0, 2),
    ("翻车鱼", 5, 390, 20.0, 80.0, 2), ("魔鬼鱼", 5, 450, 10.0, 35.0, 2),
    ("蓝鳍金枪鱼", 6, 900, 30.0, 120.0, 2), ("旗鱼", 6, 820, 25.0, 90.0, 2),
    ("皇带鱼", 6, 980, 15.0, 60.0, 3), ("腔棘鱼", 6, 1100, 20.0, 70.0, 3),
    ("深海鮟鱇", 7, 2200, 5.0, 25.0, 3), ("巨型乌贼", 7, 2600, 40.0, 150.0, 3),
    ("龙宫使者", 7, 2400, 8.0, 35.0, 3), ("月光水母", 8, 5200, 2.0, 12.0, 3),
    ("幽灵鲨", 8, 6000, 30.0, 110.0, 3), ("沧海龙鲤", 8, 6800, 12.0, 45.0, 3),
    ("星海鲸", 9, 15000, 200.0, 800.0, 3), ("深渊之主", 9, 18000, 150.0, 600.0, 3),
    ("幻海麒麟", 10, 42000, 60.0, 260.0, 3), ("创世鱼神", 10, 66000, 300.0, 1200.0, 3),
]

ZONES = [
    ("近岸浅滩", 1, 0, 1.0, "无门槛"),
    ("远海渔场", 2, 5, 1.35, "等级 5 或持有通行证"),
    ("深渊秘境", 3, 12, 1.8, "等级 12 且持有通行证"),
]

RARITY_WEIGHTS = [4000, 2500, 1500, 900, 500, 300, 160, 80, 40, 20]
RARITY_NAMES = ["一星", "二星", "三星", "四星", "五星", "六星", "七星", "八星", "九星", "十星"]

ITEMS = {
    1: ("普通鱼饵", "补充 5 次当日钓鱼次数"),
    2: ("通行证", "解锁远海与深渊钓场"),
    3: ("幸运护符", "下一次钓鱼稀有度提升"),
    4: ("精炼石", "精炼装备的必备材料"),
    5: ("扩容卡", "水族箱容量 +20"),
    6: ("擦弹炸弹", "电鱼失败时免除惩罚"),
    7: ("驱灵香", "驱散对方的海灵守护"),
    8: ("高级鱼饵", "补充 20 次当日钓鱼次数"),
}

SHOPS = {
    1: ("普通商店", "金币", [
        (1, "rod", "竹制鱼竿", 1, 120, 0),
        (2, "rod", "碳素鱼竿", 2, 680, 0),
        (3, "item", "普通鱼饵", 1, 20, 0),
        (4, "item", "通行证", 2, 480, 0),
        (5, "item", "幸运护符", 3, 150, 0),
        (6, "item", "扩容卡", 5, 400, 0),
        (7, "acc", "银鳞吊坠", 1, 300, 0),
    ]),
    2: ("高级商店", "高级货币", [
        (1, "rod", "深海战竿", 4, 60, 0),
        (2, "rod", "星陨之竿", 6, 180, 0),
        (3, "acc", "海王之戒", 4, 90, 0),
        (4, "item", "精炼石", 4, 25, 0),
        (5, "item", "高级鱼饵", 8, 15, 0),
        (6, "item", "擦弹炸弹", 6, 20, 0),
        (7, "item", "驱灵香", 7, 20, 0),
    ]),
    3: ("限时商店", "金币", [
        (1, "item", "幸运护符", 3, 110, 3),
        (2, "item", "精炼石", 4, 260, 5),
        (3, "acc", "潮汐护符", 3, 1800, 2),
        (4, "rod", "潮汐长竿", 3, 2400, 1),
    ]),
}

COMMODITIES = [("鱼干", 1200), ("鱼油", 2800), ("鱼卵", 4600)]

ACHIEVEMENTS = [
    ("first", "初次下竿", 1, "钓到第一条鱼", 100, "新人钓手"),
    ("ten", "小有收获", 10, "累计钓到 10 条鱼", 300, "钓鱼佬"),
    ("hundred", "熟练钓手", 100, "累计钓到 100 条鱼", 1500, "海之子"),
    ("thousand", "千鱼斩", 1000, "累计钓到 1000 条鱼", 8000, "传说钓手"),
    ("star10", "星海之遇", 1, "钓到一条十星鱼", 5000, "星海行者"),
    ("rich", "身家万贯", 1, "金币达到 100000", 2000, "富甲一方"),
    ("collector", "图鉴大师", 1, "解锁全部鱼种图鉴", 10000, "图鉴大师"),
    ("refiner", "精炼宗师", 1, "任意装备精炼到 +10", 3000, "锻造宗师"),
]

GACHA_POOL = [
    ("item", 3, 30, "幸运护符"),
    ("item", 4, 24, "精炼石"),
    ("item", 5, 14, "扩容卡"),
    ("item", 8, 10, "高级鱼饵"),
    ("rod", 3, 10, "惊喜鱼竿"),
    ("acc", 3, 8, "惊喜饰品"),
    ("premium", 20, 4, "高级货币 x20"),
]

DEFAULTS = {
    "owner": OWNER,
    "daily_limit": 30,
    "cooldown": 3,
    "tax_rate": 0.05,
    "reset_hour": 4,
    "zone_pass_item": 2,
    "gacha_cost": 2000,
    "steal_rate": 0.45,
    "zap_rate": 0.35,
    "announce": "",
}


def _b36(n):
    s = ""
    n = int(n)
    if n == 0:
        return "0"
    while n:
        n, r = divmod(n, 36)
        s = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"[r] + s
    return s


def _unb36(s):
    try:
        return int(str(s), 36)
    except Exception:
        return 0


def _now():
    return time.time()


def _reset_hour():
    try:
        r = _one("SELECT v FROM settings WHERE k='reset_hour'")
        return int(_num(r["v"], DEFAULTS["reset_hour"])) if r else int(DEFAULTS["reset_hour"])
    except Exception:
        return int(DEFAULTS["reset_hour"])


def _today():
    return time.strftime("%Y-%m-%d", time.localtime(_now() - _reset_hour() * 3600))


def _db():
    ASSETS.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(DB), timeout=15)
    c.row_factory = sqlite3.Row
    return c


def _q(sql, args=()):
    c = _db()
    try:
        return [dict(r) for r in c.execute(sql, args).fetchall()]
    finally:
        c.close()


def _one(sql, args=()):
    r = _q(sql, args)
    return r[0] if r else None


def _x(sql, args=()):
    c = _db()
    try:
        cur = c.execute(sql, args)
        c.commit()
        return cur.lastrowid
    finally:
        c.close()


def _tx(fn):
    c = _db()
    try:
        r = fn(c)
        c.commit()
        return r
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def _init():
    ASSETS.mkdir(parents=True, exist_ok=True)
    c = _db()
    try:
        c.executescript("""
CREATE TABLE IF NOT EXISTS users(
 uid TEXT PRIMARY KEY, nickname TEXT DEFAULT '', coins INTEGER DEFAULT 500,
 premium INTEGER DEFAULT 0, exp INTEGER DEFAULT 0, fish_count INTEGER DEFAULT 0,
 total_weight REAL DEFAULT 0, today_count INTEGER DEFAULT 0, today TEXT DEFAULT '',
 daily_streak INTEGER DEFAULT 0, last_fish REAL DEFAULT 0, last_daily TEXT DEFAULT '',
 banned INTEGER DEFAULT 0, aquarium_cap INTEGER DEFAULT 20, rod_id INTEGER DEFAULT 0,
 acc_id INTEGER DEFAULT 0, title TEXT DEFAULT '', lucky INTEGER DEFAULT 0,
 created REAL DEFAULT 0);
CREATE TABLE IF NOT EXISTS fish(
 id INTEGER PRIMARY KEY AUTOINCREMENT, uid TEXT, species INTEGER, rarity INTEGER,
 weight REAL, quality INTEGER DEFAULT 0, value INTEGER, zone INTEGER,
 place TEXT DEFAULT 'pond', locked INTEGER DEFAULT 0, caught REAL);
CREATE INDEX IF NOT EXISTS ix_fish_uid ON fish(uid);
CREATE TABLE IF NOT EXISTS gear(
 id INTEGER PRIMARY KEY AUTOINCREMENT, uid TEXT, kind TEXT, name TEXT,
 rarity INTEGER, bonus REAL, refine INTEGER DEFAULT 0, locked INTEGER DEFAULT 0);
CREATE INDEX IF NOT EXISTS ix_gear_uid ON gear(uid);
CREATE TABLE IF NOT EXISTS items(uid TEXT, iid INTEGER, qty INTEGER DEFAULT 0, PRIMARY KEY(uid,iid));
CREATE TABLE IF NOT EXISTS market(
 id INTEGER PRIMARY KEY AUTOINCREMENT, seller TEXT, kind TEXT, ref_id INTEGER,
 qty INTEGER, price INTEGER, anonymous INTEGER DEFAULT 0, created REAL, label TEXT);
CREATE TABLE IF NOT EXISTS catalog(uid TEXT, species INTEGER, best REAL, first REAL,
 PRIMARY KEY(uid,species));
CREATE TABLE IF NOT EXISTS holdings(uid TEXT, name TEXT, qty INTEGER, cost INTEGER,
 PRIMARY KEY(uid,name));
CREATE TABLE IF NOT EXISTS redpack(
 id INTEGER PRIMARY KEY AUTOINCREMENT, sender TEXT, amount INTEGER, total INTEGER,
 rest INTEGER, word TEXT, created REAL, taken TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS achievements(uid TEXT, key TEXT, progress INTEGER, done INTEGER,
 PRIMARY KEY(uid,key));
CREATE TABLE IF NOT EXISTS titles(uid TEXT, title TEXT, PRIMARY KEY(uid,title));
CREATE TABLE IF NOT EXISTS pool(rarity INTEGER PRIMARY KEY, quota INTEGER, left INTEGER, day TEXT);
CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS logs(id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, uid TEXT,
 action TEXT, detail TEXT);
CREATE INDEX IF NOT EXISTS ix_logs_ts ON logs(ts);
""")
        c.commit()
        for i in range(1, 11):
            quota = max(1, int(60000 / (i * i * i)))
            c.execute("INSERT OR IGNORE INTO pool(rarity,quota,left,day) VALUES(?,?,?,?)",
                      (i, quota, quota, _today()))
        c.commit()
    finally:
        c.close()


def _conf(ctx=None):
    out = dict(DEFAULTS)
    if ctx is not None and isinstance(getattr(ctx, "cfg", None), dict):
        out.update(ctx.cfg)
    return out


def _num(v, default=0):
    try:
        return float(v)
    except Exception:
        return float(default)


def _log(uid, action, detail=""):
    try:
        _x("INSERT INTO logs(ts,uid,action,detail) VALUES(?,?,?,?)",
           (_now(), str(uid), action, str(detail)[:300]))
    except Exception:
        pass


def _user(uid, nick=""):
    r = _one("SELECT * FROM users WHERE uid=?", (uid,))
    if not r:
        _x("INSERT OR IGNORE INTO users(uid,nickname,coins,created,today) VALUES(?,?,?,?,?)",
           (uid, nick or "", 500, _now(), _today()))
        r = _one("SELECT * FROM users WHERE uid=?", (uid,))
    if r and r.get("today") != _today():
        _x("UPDATE users SET today=?,today_count=0 WHERE uid=?", (_today(), uid))
        r["today"] = _today()
        r["today_count"] = 0
    return r or {}


def _set(uid, **kw):
    if not kw:
        return
    sql = "UPDATE users SET " + ",".join("%s=?" % k for k in kw) + " WHERE uid=?"
    _x(sql, tuple(kw.values()) + (uid,))


def _item(uid, iid):
    r = _one("SELECT qty FROM items WHERE uid=? AND iid=?", (uid, iid))
    return int(r["qty"]) if r else 0


def _give(uid, iid, qty):
    _x("INSERT INTO items(uid,iid,qty) VALUES(?,?,?) ON CONFLICT(uid,iid) DO UPDATE SET qty=qty+?",
       (uid, iid, qty, qty))


def _take(uid, iid, qty):
    have = _item(uid, iid)
    if have < qty:
        return False
    _x("UPDATE items SET qty=qty-? WHERE uid=? AND iid=?", (qty, uid, iid))
    return True


def _pick_rarity():
    r = random.randint(1, sum(RARITY_WEIGHTS))
    acc = 0
    for i, w in enumerate(RARITY_WEIGHTS):
        acc += w
        if r <= acc:
            return i + 1
    return 1


def _gear_bonus(uid):
    out = {"rarity": 0.0, "coins": 0.0, "weight": 0.0}
    for g in _q("SELECT * FROM gear WHERE uid=? AND (id=(SELECT rod_id FROM users WHERE uid=?) OR id=(SELECT acc_id FROM users WHERE uid=?))",
                (uid, uid, uid)):
        k = g.get("kind")
        b = float(g.get("bonus") or 0) + int(g.get("refine") or 0) * 0.03
        if k == "rod":
            out["rarity"] += b
            out["weight"] += b
        else:
            out["coins"] += b
    return out


def _check_ach(uid):
    u = _user(uid)
    vals = {
        "first": u.get("fish_count", 0), "ten": u.get("fish_count", 0),
        "hundred": u.get("fish_count", 0), "thousand": u.get("fish_count", 0),
        "star10": _one("SELECT COUNT(*) n FROM fish WHERE uid=? AND rarity=10", (uid,))["n"],
        "rich": 1 if u.get("coins", 0) >= 100000 else 0,
        "collector": 1 if _one("SELECT COUNT(*) n FROM catalog WHERE uid=?", (uid,))["n"] >= len(SPECIES) else 0,
        "refiner": _one("SELECT COUNT(*) n FROM gear WHERE uid=? AND refine>=10", (uid,))["n"],
    }
    got = []
    for key, title, need, desc, reward, tname in ACHIEVEMENTS:
        row = _one("SELECT * FROM achievements WHERE uid=? AND key=?", (uid, key))
        if row and row.get("done"):
            continue
        pv = vals.get(key, 0)
        done = 1 if pv >= need else 0
        _x("INSERT INTO achievements(uid,key,progress,done) VALUES(?,?,?,?) "
           "ON CONFLICT(uid,key) DO UPDATE SET progress=?,done=?", (uid, key, pv, done, pv, done))
        if done:
            _x("INSERT OR IGNORE INTO titles(uid,title) VALUES(?,?)", (uid, tname))
            _set(uid, coins=int(u.get("coins", 0)) + reward)
            got.append("%s (+%d金币)" % (tname, reward))
    return got


def _value(species, weight, quality, zone_mult):
    base = SPECIES[species][2]
    return int(base * (0.6 + weight / max(0.3, SPECIES[species][4])) * (2 if quality else 1) * zone_mult)


def _at_uid(ctx, args):
    raw = str((ctx.raw or {}).get("raw_message") or "")
    if not raw:
        msg = (ctx.raw or {}).get("message")
        raw = json.dumps(msg, ensure_ascii=False) if isinstance(msg, (list, dict)) else str(msg or "")
    m = re.search(r"qq=(\d{5,12})", raw)
    if m:
        return m.group(1)
    m = re.search(r"(\d{5,12})", args or "")
    return m.group(1) if m else ""


def _is_admin(ctx):
    return str(ctx.user_id) == str(_conf(ctx).get("owner"))


def _fmt_fish(rows, cap=20):
    if not rows:
        return "空空如也，先去 /钓鱼 吧"
    out = []
    for f in rows[:cap]:
        sp = SPECIES[f["species"]]
        out.append("[F%s] %s %s %s %.2fkg %d金币%s" % (
            _b36(f["id"]), RARITY_NAMES[sp[1] - 1], sp[0],
            "高品质" if f["quality"] else "普通", f["weight"], f["value"],
            " 锁定" if f["locked"] else ""))
    if len(rows) > cap:
        out.append("...共 %d 条，仅显示前 %d 条" % (len(rows), cap))
    return "\n".join(out)


def on_startup(bot):
    _init()


_init()


def _zone_of(args):
    a = (args or "").strip()
    if a in ("2", "远海", "远海渔场", "深海"):
        return 2
    if a in ("3", "深渊", "深渊秘境", "秘境"):
        return 3
    return 1


def _pool_ok(rarity):
    row = _one("SELECT * FROM pool WHERE rarity=?", (rarity,))
    if row and row.get("day") != _today():
        _x("UPDATE pool SET left=quota,day=? WHERE rarity=?", (_today(), rarity))
        row = _one("SELECT * FROM pool WHERE rarity=?", (rarity,))
    return bool(row and int(row.get("left") or 0) > 0)


def _pool_take(rarity):
    _x("UPDATE pool SET left=MAX(0,left-1) WHERE rarity=?", (rarity,))


async def cmd_fish(ctx, args):
    uid = ctx.user_id
    cfg = _conf(ctx)
    u = _user(uid, ctx.sender)
    if u.get("banned"):
        return await ctx.reply("账号已被限制，请联系管理员")
    cd = float(cfg.get("cooldown") or 0)
    if _now() - float(u.get("last_fish") or 0) < cd:
        left = cd - (_now() - float(u.get("last_fish") or 0))
        return await ctx.reply("鱼竿还没收回来，等 %.1f 秒再下竿" % left)
    limit = int(_num(cfg.get("daily_limit"), 30))
    used = int(u.get("today_count") or 0)
    if used >= limit:
        if _item(uid, 1) >= 1:
            _take(uid, 1, 1)
            _set(uid, today_count=0)
            used = 0
        elif _item(uid, 8) >= 1:
            _take(uid, 8, 1)
            _set(uid, today_count=0)
            used = 0
        else:
            return await ctx.reply("今天 %d 次机会用完啦，明天再来，或用 /购买 1 3 买鱼饵" % limit)
    zone = _zone_of(args)
    z = ZONES[zone - 1]
    need_lv = z[2]
    if need_lv and int(u.get("exp") or 0) // 100 + 1 < need_lv and not _item(uid, int(cfg.get("zone_pass_item") or 2)):
        return await ctx.reply("%s 需要 %s" % (z[0], z[4]))
    bonus = _gear_bonus(uid)
    rarity = _pick_rarity()
    if int(u.get("lucky") or 0):
        rarity = min(10, rarity + 2)
        _set(uid, lucky=0)
    if bonus["rarity"] > 0 and random.random() < min(0.5, bonus["rarity"]):
        rarity = min(10, rarity + 1)
    while rarity >= 6 and not _pool_ok(rarity):
        rarity -= 1
    pool = [i for i, s in enumerate(SPECIES) if s[5] <= zone and s[1] == rarity]
    if not pool:
        pool = [i for i, s in enumerate(SPECIES) if s[5] <= zone and s[1] <= rarity]
    if not pool:
        pool = [i for i, s in enumerate(SPECIES) if s[5] <= zone]
    sid = random.choice(pool)
    sp = SPECIES[sid]
    wmin, wmax = sp[3], sp[4]
    weight = round(random.uniform(wmin, wmax) * (1 + bonus["weight"]), 2)
    quality = 1 if random.random() < 0.15 else 0
    value = _value(sid, weight, quality, z[3])
    reward = int(value * 0.12 * (1 + bonus["coins"]))
    exp = 2 + rarity * 3
    fid = _x("INSERT INTO fish(uid,species,rarity,weight,quality,value,zone,place,caught) "
             "VALUES(?,?,?,?,?,?,?,'pond',?)",
             (uid, sid, rarity, weight, quality, value, zone, _now()))
    _set(uid, coins=int(u.get("coins") or 0) + reward,
         exp=int(u.get("exp") or 0) + exp,
         fish_count=int(u.get("fish_count") or 0) + 1,
         total_weight=float(u.get("total_weight") or 0) + weight,
         today_count=used + 1, last_fish=_now(),
         nickname=ctx.sender or u.get("nickname") or "")
    if rarity >= 6:
        _pool_take(rarity)
    _x("INSERT INTO catalog(uid,species,best,first) VALUES(?,?,?,?) "
       "ON CONFLICT(uid,species) DO UPDATE SET best=MAX(best,excluded.best)",
       (uid, sid, weight, _now()))
    _log(uid, "钓鱼", "%s R%d %.2fkg" % (sp[0], rarity, weight))
    got = _check_ach(uid)
    lines = [
        "[%s] 下竿结果" % z[0],
        LINE,
        "鱼获  %s" % sp[0],
        "稀有度  %s [%d星]" % (RARITY_NAMES[rarity - 1], rarity),
        "品质  %s" % ("高品质 价值翻倍" if quality else "普通"),
        "重量  %.2f kg" % weight,
        "估值  %d 金币" % value,
        "编号  [F%s]" % _b36(fid),
        "收益  +%d 金币  +%d 经验" % (reward, exp),
        "今日  %d/%d 次" % (used + 1, limit),
    ]
    if got:
        lines.append("达成  " + " / ".join(got))
    ann = str(cfg.get("announce") or "")
    if ann:
        lines.append("公告  " + ann[:80])
    return await ctx.reply("\n".join(lines))


async def cmd_pond(ctx, args):
    uid = ctx.user_id
    _user(uid, ctx.sender)
    rows = _q("SELECT * FROM fish WHERE uid=? AND place='pond' ORDER BY rarity DESC,id DESC", (uid,))
    total = sum(int(f["value"]) for f in rows)
    head = "[我的鱼塘] 共 %d 条 | 总估值 %d 金币" % (len(rows), total)
    return await ctx.reply(head + "\n" + LINE + "\n" + _fmt_fish(rows))


async def cmd_sell(ctx, args):
    uid = ctx.user_id
    u = _user(uid, ctx.sender)
    a = (args or "").strip()
    rows = _q("SELECT * FROM fish WHERE uid=? AND place='pond' AND locked=0", (uid,))
    if not rows:
        return await ctx.reply("鱼塘里没有可售的鱼")
    picked = []
    if a in ("", "全部", "all", "出售全部"):
        picked = rows
    elif a.startswith("星") or a.startswith("R") or a.startswith("r"):
        m = re.search(r"(\d{1,2})", a)
        lv = int(m.group(1)) if m else 0
        picked = [f for f in rows if f["rarity"] == lv]
        if not picked:
            return await ctx.reply("没有 %d 星的鱼" % lv)
    else:
        code = a.split()[0].upper().lstrip("F")
        qty = 1
        parts = a.split()
        if len(parts) > 1 and parts[1].isdigit():
            qty = int(parts[1])
        fid = _unb36(code)
        picked = [f for f in rows if f["id"] == fid][:qty]
        if not picked:
            return await ctx.reply("短码 [F%s] 不在鱼塘里" % _b36(fid))
    gain = sum(int(f["value"]) for f in picked)
    cfg = _conf(ctx)
    tax = int(gain * float(cfg.get("tax_rate") or 0))
    net = gain - tax
    ids = [f["id"] for f in picked]
    _tx(lambda c: c.executemany("DELETE FROM fish WHERE id=?", [(i,) for i in ids]))
    _set(uid, coins=int(u.get("coins") or 0) + net)
    _log(uid, "出售", "%d条 得%d 税%d" % (len(picked), net, tax))
    _check_ach(uid)
    return await ctx.reply("[出售完成] %d 条\n%s\n售价 %d | 税 %d | 实收 %d 金币\n当前余额 %d" %
                          (len(picked), LINE, gain, tax, net, int(u.get("coins") or 0) + net))


async def cmd_tank(ctx, args):
    uid = ctx.user_id
    u = _user(uid, ctx.sender)
    a = (args or "").strip().split()
    cap = int(u.get("aquarium_cap") or 20)
    if not a or a[0] in ("查看", "状态"):
        rows = _q("SELECT * FROM fish WHERE uid=? AND place='aquarium' ORDER BY rarity DESC", (uid,))
        return await ctx.reply("[水族箱] %d/%d 容量\n%s\n%s" % (len(rows), cap, LINE, _fmt_fish(rows)))
    act = a[0]
    if act == "升级":
        cost = 300 * (cap // 20)
        if int(u.get("coins") or 0) < cost:
            return await ctx.reply("升级需要 %d 金币，余额不足" % cost)
        _set(uid, coins=int(u.get("coins") or 0) - cost, aquarium_cap=cap + 20)
        return await ctx.reply("水族箱扩容成功，容量 %d -> %d，花费 %d 金币" % (cap, cap + 20, cost))
    if act in ("存入", "取出") and len(a) >= 2:
        fid = _unb36(a[1].upper().lstrip("F"))
        qty = int(a[2]) if len(a) > 2 and a[2].isdigit() else 1
        place = "pond" if act == "存入" else "aquarium"
        target = "aquarium" if act == "存入" else "pond"
        rows = _q("SELECT * FROM fish WHERE uid=? AND id>0 AND place=?", (uid, place))
        if act == "存入":
            rows = [f for f in rows if f["id"] == fid][:qty]
            used = _one("SELECT COUNT(*) n FROM fish WHERE uid=? AND place='aquarium'", (uid,))["n"]
            if used + len(rows) > cap:
                return await ctx.reply("水族箱容量不足（%d/%d），先 /水族箱 升级" % (used, cap))
        else:
            rows = [f for f in rows if f["id"] == fid][:qty]
        if not rows:
            return await ctx.reply("没有找到对应的鱼")
        _tx(lambda c: c.executemany("UPDATE fish SET place=? WHERE id=?",
                                    [(target, f["id"]) for f in rows]))
        return await ctx.reply("%s %d 条完成，当前水族箱 %d 条" %
                              (act, len(rows),
                               _one("SELECT COUNT(*) n FROM fish WHERE uid=? AND place='aquarium'", (uid,))["n"]))
    return await ctx.reply("用法：/水族箱 查看 | 存入 F码 [数量] | 取出 F码 [数量] | 升级")


async def cmd_book(ctx, args):
    uid = ctx.user_id
    _user(uid, ctx.sender)
    got = _q("SELECT species,best FROM catalog WHERE uid=? ORDER BY species", (uid,))
    have = set(g["species"] for g in got)
    out = ["[鱼类图鉴] %d/%d 种" % (len(have), len(SPECIES)), LINE]
    for i, sp in enumerate(SPECIES):
        mark = "已解锁" if i in have else "未发现"
        nm = sp[0] if i in have else "???"
        best = ""
        if i in have:
            b = [g["best"] for g in got if g["species"] == i]
            best = " 最大 %.2fkg" % b[0] if b else ""
        out.append("%2d星 %-10s %s%s" % (sp[1], nm, mark, best))
    return await ctx.reply("\n".join(out[:60]))


async def cmd_bag(ctx, args):
    uid = ctx.user_id
    u = _user(uid, ctx.sender)
    items = _q("SELECT * FROM items WHERE uid=? AND qty>0 ORDER BY iid", (uid,))
    out = ["[背包] 金币 %d | 高级货币 %d | 等级 %d" %
           (u.get("coins", 0), u.get("premium", 0), int(u.get("exp") or 0) // 100 + 1), LINE]
    out.append("道具：")
    if items:
        for it in items:
            nm = ITEMS.get(it["iid"], ("未知", ""))[0]
            out.append("  [%d] %s x%d" % (it["iid"], nm, it["qty"]))
    else:
        out.append("  暂无")
    gear = _q("SELECT * FROM gear WHERE uid=? ORDER BY id", (uid,))
    out.append("装备：")
    if gear:
        for g in gear:
            tag = "R" if g["kind"] == "rod" else "A"
            eq = " 已装备" if (g["kind"] == "rod" and g["id"] == u.get("rod_id")) or \
                              (g["kind"] == "acc" and g["id"] == u.get("acc_id")) else ""
            out.append("  [%s%s] %s %d星 加成%.2f 精炼+%d%s%s" %
                       (tag, _b36(g["id"]), g["name"], g["rarity"], g["bonus"],
                        g["refine"], eq, " 锁定" if g["locked"] else ""))
    else:
        out.append("  暂无，去 /商店 逛逛")
    return await ctx.reply("\n".join(out[:50]))


async def _gear_cmd(ctx, args, kind):
    uid = ctx.user_id
    u = _user(uid, ctx.sender)
    a = (args or "").strip().split()
    word = "鱼竿" if kind == "rod" else "饰品"
    tag = "R" if kind == "rod" else "A"
    key = "rod_id" if kind == "rod" else "acc_id"
    rows = _q("SELECT * FROM gear WHERE uid=? AND kind=? ORDER BY rarity DESC,id", (uid, kind))
    if not a:
        if not rows:
            return await ctx.reply("还没有%s，去 /商店 买一个" % word)
        out = ["[我的%s] 当前装备 ID %s" % (word, _b36(int(u.get(key) or 0))), LINE]
        for g in rows:
            out.append("[%s%s] %s %d星 加成%.2f 精炼+%d%s" %
                       (tag, _b36(g["id"]), g["name"], g["rarity"], g["bonus"], g["refine"],
                        " 已装备" if g["id"] == u.get(key) else ""))
        return await ctx.reply("\n".join(out))
    act = a[0]
    if len(a) < 2:
        return await ctx.reply("用法：/%s 装备|精炼|锁定 <短码>" % word)
    gid = _unb36(a[1].upper().lstrip(tag))
    g = _one("SELECT * FROM gear WHERE id=? AND uid=? AND kind=?", (gid, uid, kind))
    if not g:
        return await ctx.reply("没有找到这件装备")
    if act == "装备":
        _set(uid, **{key: gid})
        return await ctx.reply("已装备 %s（%d星 加成%.2f 精炼+%d）" % (g["name"], g["rarity"], g["bonus"], g["refine"]))
    if act == "锁定":
        _x("UPDATE gear SET locked=? WHERE id=?", (0 if g["locked"] else 1, gid))
        return await ctx.reply("%s 已%s" % (g["name"], "解锁" if g["locked"] else "锁定"))
    if act == "丢弃":
        if g["locked"]:
            return await ctx.reply("装备已锁定，先解锁")
        if g["id"] == u.get(key):
            return await ctx.reply("正在使用中，先换下")
        gain = 30 * g["rarity"] * (1 + g["refine"])
        _x("DELETE FROM gear WHERE id=?", (gid,))
        _set(uid, coins=int(u.get("coins") or 0) + gain)
        return await ctx.reply("已丢弃 %s，回收 %d 金币" % (g["name"], gain))
    return await ctx.reply("用法：/%s 装备|精炼|锁定|丢弃 <短码>" % word)


async def cmd_rod(ctx, args):
    return await _gear_cmd(ctx, args, "rod")


async def cmd_acc(ctx, args):
    return await _gear_cmd(ctx, args, "acc")


async def cmd_shop(ctx, args):
    a = (args or "").strip()
    if not a:
        out = ["[商店列表]", LINE]
        for sid, (nm, cur, goods) in SHOPS.items():
            out.append("[%d] %s（%s） %d 件商品" % (sid, nm, cur, len(goods)))
        out.append("查看：/商店 1  购买：/购买 <商店> <编号> [数量]")
        return await ctx.reply("\n".join(out))
    sid = int(a) if a.isdigit() else 0
    if sid not in SHOPS:
        return await ctx.reply("没有这家商店，/商店 查看列表")
    nm, cur, goods = SHOPS[sid]
    out = ["[%d] %s（结算：%s）" % (sid, nm, cur), LINE]
    for gid, kind, gname, rarity, price, limited in goods:
        suffix = " 限购%d" % limited if limited else ""
        out.append("  [%d] %-10s %d星  %d %s%s" % (gid, gname, rarity, price, cur, suffix))
    out.append("购买：/购买 %d <编号> [数量]" % sid)
    return await ctx.reply("\n".join(out))


async def cmd_buy(ctx, args):
    uid = ctx.user_id
    u = _user(uid, ctx.sender)
    a = (args or "").strip().split()
    if len(a) < 2:
        return await ctx.reply("用法：/购买 <商店编号> <商品编号> [数量]，/商店 查看")
    sid, gid = int(a[0]) if a[0].isdigit() else 0, int(a[1]) if a[1].isdigit() else 0
    qty = int(a[2]) if len(a) > 2 and a[2].isdigit() else 1
    qty = max(1, min(99, qty))
    if sid not in SHOPS:
        return await ctx.reply("商店编号无效")
    nm, cur, goods = SHOPS[sid]
    g = [x for x in goods if x[0] == gid]
    if not g:
        return await ctx.reply("商品编号无效")
    _, kind, gname, rarity, price, limited = g[0]
    if limited and qty > limited:
        return await ctx.reply("该商品限购 %d 件" % limited)
    total = price * qty
    field = "coins" if cur == "金币" else "premium"
    if int(u.get(field) or 0) < total:
        return await ctx.reply("余额不足，需要 %d %s，当前 %d" % (total, cur, u.get(field) or 0))
    _set(uid, **{field: int(u.get(field) or 0) - total})
    for _ in range(qty):
        if kind == "item":
            _give(uid, rarity, 1)
        elif kind in ("rod", "acc"):
            _x("INSERT INTO gear(uid,kind,name,rarity,bonus) VALUES(?,?,?,?,?)",
               (uid, kind, gname, rarity, round(random.uniform(0.03, 0.12) + rarity * 0.02, 3)))
    _log(uid, "购买", "%s %s x%d 花%d" % (nm, gname, qty, total))
    if kind == "item":
        iid = rarity
    else:
        iid = 0
    return await ctx.reply("购买成功：%s x%d\n花费 %d %s\n剩余 %d %s\n%s" %
                          (gname, qty, total, cur, int(u.get(field) or 0) - total, cur,
                           "道具已入 /背包" if kind == "item" else "装备已入 /背包，记得 /鱼竿 装备"))


async def cmd_refine(ctx, args):
    uid = ctx.user_id
    u = _user(uid, ctx.sender)
    a = (args or "").strip().split()
    if len(a) < 2:
        return await ctx.reply("用法：/精炼 <鱼竿|饰品> <短码>")
    kind = "rod" if a[0] in ("鱼竿", "rod", "R") else "acc"
    tag = "R" if kind == "rod" else "A"
    gid = _unb36(a[1].upper().lstrip(tag))
    g = _one("SELECT * FROM gear WHERE id=? AND uid=? AND kind=?", (gid, uid, kind))
    if not g:
        return await ctx.reply("没有找到装备")
    if g["locked"]:
        return await ctx.reply("装备已锁定，先 /%s 锁定 %s 解锁" % (a[0], a[1]))
    lv = int(g["refine"])
    cost_stone = 1 + lv // 2
    cost_coin = 200 * (lv + 1)
    if _item(uid, 4) < cost_stone:
        return await ctx.reply("精炼石不足，需要 %d 个（/购买 2 4）" % cost_stone)
    if int(u.get("coins") or 0) < cost_coin:
        return await ctx.reply("金币不足，需要 %d" % cost_coin)
    rate = max(0.2, 0.95 - lv * 0.07)
    ok = random.random() < rate
    _take(uid, 4, cost_stone)
    _set(uid, coins=int(u.get("coins") or 0) - cost_coin)
    if ok:
        _x("UPDATE gear SET refine=refine+1 WHERE id=?", (gid,))
        _check_ach(uid)
        return await ctx.reply("精炼成功 %s -> +%d\n成功率 %.0f%% | 消耗 %d 精炼石 %d 金币" %
                              (g["name"], lv + 1, rate * 100, cost_stone, cost_coin))
    return await ctx.reply("精炼失败，装备未损坏\n成功率 %.0f%% | 消耗 %d 精炼石 %d 金币" %
                          (rate * 100, cost_stone, cost_coin))


async def cmd_rank(ctx, args):
    key = (args or "").strip()
    col = "coins"
    title = "金币榜"
    if key in ("鱼获", "重量", "weight"):
        col, title = "total_weight", "鱼获重量榜"
    elif key in ("数量", "count"):
        col, title = "fish_count", "钓鱼数量榜"
    elif key in ("图鉴", "book"):
        rows = _q("SELECT uid,COUNT(*) n FROM catalog GROUP BY uid ORDER BY n DESC LIMIT 10")
        out = ["[图鉴榜]", LINE]
        for i, r in enumerate(rows, 1):
            out.append("%2d. %s  %d 种" % (i, r["uid"], r["n"]))
        return await ctx.reply("\n".join(out) if rows else "暂无数据")
    rows = _q("SELECT uid,nickname,%s v FROM users WHERE banned=0 ORDER BY %s DESC LIMIT 10" % (col, col))
    out = ["[%s]" % title, LINE]
    for i, r in enumerate(rows, 1):
        v = "%d 金币" % r["v"] if col == "coins" else ("%.2f kg" % r["v"] if col == "total_weight" else "%d 条" % r["v"])
        out.append("%2d. %s  %s" % (i, r.get("nickname") or r["uid"][:6], v))
    return await ctx.reply("\n".join(out) if rows else "暂无数据")


async def cmd_daily(ctx, args):
    uid = ctx.user_id
    u = _user(uid, ctx.sender)
    if u.get("last_daily") == _today():
        return await ctx.reply("今天已经领过啦，明天再来\n当前连续 %d 天" % (u.get("daily_streak") or 0))
    yesterday = time.strftime("%Y-%m-%d", time.localtime(_now() - 86400 - _reset_hour() * 3600))
    streak = 1 if u.get("last_daily") != yesterday else int(u.get("daily_streak") or 0) + 1
    coin = 200 + min(20, streak) * 50
    premium = 5 if streak % 7 == 0 else 0
    _set(uid, last_daily=_today(), daily_streak=streak,
         coins=int(u.get("coins") or 0) + coin,
         premium=int(u.get("premium") or 0) + premium)
    _give(uid, 1, 1)
    _log(uid, "每日", "连续%d 得%d" % (streak, coin))
    return await ctx.reply("[每日补给] 连续 %d 天\n%s\n+%d 金币  +%d 高级货币  +普通鱼饵 x1\n当前 %d 金币" %
                          (streak, LINE, coin, premium, int(u.get("coins") or 0) + coin))


async def cmd_market(ctx, args):
    a = (args or "").strip()
    page = int(a) if a.isdigit() else 1
    off = max(0, (page - 1) * 15)
    rows = _q("SELECT * FROM market ORDER BY id DESC LIMIT 15 OFFSET ?", (off,))
    total = _one("SELECT COUNT(*) n FROM market")["n"]
    if not rows:
        return await ctx.reply("[鱼类市场] 暂无在售商品\n用 /上架 F码 价格 [数量] [匿名] 挂单")
    out = ["[鱼类市场] 共 %d 单 | 第 %d 页" % (total, page), LINE]
    for m in rows:
        seller = "匿名" if m["anonymous"] else (m["seller"][:6] + "...")
        out.append("[M%s] %s x%d  %d 金币  卖家 %s" %
                   (_b36(m["id"]), m["label"], m["qty"], m["price"], seller))
    out.append("购买：/收购 M码 [数量] | 下架：/下架 M码")
    return await ctx.reply("\n".join(out))


async def cmd_list(ctx, args):
    uid = ctx.user_id
    u = _user(uid, ctx.sender)
    a = (args or "").strip().split()
    if len(a) < 2:
        return await ctx.reply("用法：/上架 <F码|C码> <单价> [数量] [匿名]")
    code = a[0].upper()
    price = int(a[1]) if a[1].isdigit() else 0
    qty = int(a[2]) if len(a) > 2 and a[2].isdigit() else 1
    anon = 1 if "匿名" in a else 0
    if price <= 0:
        return await ctx.reply("单价要大于 0")
    cfg = _conf(ctx)
    fee = int(price * qty * 0.02)
    if int(u.get("coins") or 0) < fee:
        return await ctx.reply("上架手续费 %d 金币不足" % fee)
    label = ""
    kind = ""
    ref = 0
    if code.startswith("F"):
        fid = _unb36(code[1:])
        f = _one("SELECT * FROM fish WHERE id=? AND uid=? AND place='pond'", (fid, uid))
        if not f:
            return await ctx.reply("短码不存在或不在鱼塘")
        kind, ref = "fish", fid
        label = SPECIES[f["species"]][0]
        _x("UPDATE fish SET place='market' WHERE id=?", (fid,))
    elif code.startswith("C"):
        cname = COMMODITIES[_unb36(code[1:]) % len(COMMODITIES)][0]
        h = _one("SELECT * FROM holdings WHERE uid=? AND name=?", (uid, cname))
        if not h or h["qty"] < qty:
            return await ctx.reply("持仓不足")
        kind, ref, label = "commodity", 0, cname
        _x("UPDATE holdings SET qty=qty-? WHERE uid=? AND name=?", (qty, uid, cname))
        _x("DELETE FROM holdings WHERE uid=? AND name=? AND qty<=0", (uid, cname))
    else:
        return await ctx.reply("只支持 F 码（鱼）和 C 码（大宗商品）")
    mid = _x("INSERT INTO market(seller,kind,ref_id,qty,price,anonymous,created,label) "
             "VALUES(?,?,?,?,?,?,?,?)", (uid, kind, ref, qty, price, anon, _now(), label))
    _set(uid, coins=int(u.get("coins") or 0) - fee)
    _log(uid, "上架", "M%s %s x%d @%d" % (_b36(mid), label, qty, price))
    return await ctx.reply("上架成功 [M%s]\n%s x%d 单价 %d 金币\n手续费 %d 金币（下架不退）" %
                          (_b36(mid), label, qty, price, fee))


async def cmd_unlist(ctx, args):
    uid = ctx.user_id
    code = (args or "").strip().upper().lstrip("M")
    mid = _unb36(code)
    m = _one("SELECT * FROM market WHERE id=?", (mid,))
    if not m:
        return await ctx.reply("挂单不存在")
    if m["seller"] != uid and not _is_admin(ctx):
        return await ctx.reply("只能下架自己的挂单")
    if m["kind"] == "fish":
        _x("UPDATE fish SET place='pond' WHERE id=?", (m["ref_id"],))
    else:
        _x("INSERT INTO holdings(uid,name,qty,cost) VALUES(?,?,?,?) "
           "ON CONFLICT(uid,name) DO UPDATE SET qty=qty+excluded.qty",
           (uid, m["label"], m["qty"], m["price"]))
    _x("DELETE FROM market WHERE id=?", (mid,))
    return await ctx.reply("已下架 [M%s]，手续费不返还" % _b36(mid))


async def cmd_purchase(ctx, args):
    uid = ctx.user_id
    u = _user(uid, ctx.sender)
    a = (args or "").strip().split()
    if not a:
        return await ctx.reply("用法：/收购 M码 [数量]")
    mid = _unb36(a[0].upper().lstrip("M"))
    qty = int(a[1]) if len(a) > 1 and a[1].isdigit() else 1
    m = _one("SELECT * FROM market WHERE id=?", (mid,))
    if not m:
        return await ctx.reply("挂单不存在")
    if m["seller"] == uid:
        return await ctx.reply("不能买自己挂的")
    qty = min(qty, m["qty"])
    total = m["price"] * qty
    if int(u.get("coins") or 0) < total:
        return await ctx.reply("余额不足，需要 %d 金币" % total)
    cfg = _conf(ctx)
    tax = int(total * float(cfg.get("tax_rate") or 0))
    _set(uid, coins=int(u.get("coins") or 0) - total)
    seller = _one("SELECT * FROM users WHERE uid=?", (m["seller"],))
    if seller:
        _set(m["seller"], coins=int(seller.get("coins") or 0) + total - tax)
    if m["kind"] == "fish":
        f = _one("SELECT * FROM fish WHERE id=?", (m["ref_id"],))
        if f:
            _x("UPDATE fish SET uid=?,place='pond' WHERE id=?", (uid, m["ref_id"]))
    else:
        _x("INSERT INTO holdings(uid,name,qty,cost) VALUES(?,?,?,?) "
           "ON CONFLICT(uid,name) DO UPDATE SET qty=qty+excluded.qty,cost=((cost*qty)+excluded.cost*excluded.qty)/(qty+excluded.qty)",
           (uid, m["label"], qty, m["price"]))
    if qty >= m["qty"]:
        _x("DELETE FROM market WHERE id=?", (mid,))
    else:
        _x("UPDATE market SET qty=qty-? WHERE id=?", (qty, mid))
    _log(uid, "收购", "M%s x%d 花%d" % (_b36(mid), qty, total))
    return await ctx.reply("收购成功\n%s x%d | 支付 %d 金币 | 卖家实收 %d（税 %d）" %
                          (m["label"], qty, total, total - tax, tax))


def _price(name, day=None):
    day = day or _today()
    k = "price_%s_%s" % (name, day)
    r = _one("SELECT v FROM settings WHERE k=?", (k,))
    if r:
        return int(r["v"])
    base = dict((c[0], c[1]) for c in COMMODITIES)[name]
    p = max(100, int(base * random.uniform(0.75, 1.35)))
    _x("INSERT OR REPLACE INTO settings(k,v) VALUES(?,?)", (k, str(p)))
    return p


async def cmd_exchange(ctx, args):
    uid = ctx.user_id
    u = _user(uid, ctx.sender)
    a = (args or "").strip().split()
    act = a[0] if a else "状态"
    if act == "状态" or not a:
        out = ["[交易所行情] %s" % _today(), LINE]
        for i, (nm, base) in enumerate(COMMODITIES):
            p = _price(nm)
            out.append("[C%s] %-6s  %d 金币/份  基准 %d" % (_b36(i), nm, p, base))
        out.append("买入：/交易所 买入 鱼油 10 | 卖出：/交易所 卖出 鱼油")
        return await ctx.reply("\n".join(out))
    if act in ("买入", "buy") and len(a) >= 2:
        nm = a[1]
        if nm not in [c[0] for c in COMMODITIES]:
            return await ctx.reply("商品名无效：鱼干 / 鱼油 / 鱼卵")
        qty = int(a[2]) if len(a) > 2 and a[2].isdigit() else 1
        qty = max(1, min(1000, qty))
        p = _price(nm)
        total = p * qty
        held = _one("SELECT COALESCE(SUM(qty),0) n FROM holdings WHERE uid=?", (uid,))["n"]
        if held + qty > 1000:
            return await ctx.reply("总持仓上限 1000 份，当前 %d" % held)
        if int(u.get("coins") or 0) < total:
            return await ctx.reply("余额不足，需要 %d 金币" % total)
        _set(uid, coins=int(u.get("coins") or 0) - total)
        _x("INSERT INTO holdings(uid,name,qty,cost) VALUES(?,?,?,?) "
           "ON CONFLICT(uid,name) DO UPDATE SET cost=((cost*qty)+excluded.cost*excluded.qty)/(qty+excluded.qty),qty=qty+excluded.qty",
           (uid, nm, qty, p))
        _log(uid, "买入", "%s x%d @%d" % (nm, qty, p))
        return await ctx.reply("买入成功 %s x%d\n单价 %d | 支出 %d 金币" % (nm, qty, p, total))
    if act in ("卖出", "sell") and len(a) >= 2:
        nm = a[1]
        h = _one("SELECT * FROM holdings WHERE uid=? AND name=?", (uid, nm))
        if not h or h["qty"] <= 0:
            return await ctx.reply("没有 %s 持仓" % nm)
        p = _price(nm)
        gross = p * h["qty"]
        cfg = _conf(ctx)
        profit = gross - h["cost"] * h["qty"]
        tax = int(max(0, profit) * float(cfg.get("tax_rate") or 0))
        net = gross - tax
        _set(uid, coins=int(u.get("coins") or 0) + net)
        _x("DELETE FROM holdings WHERE uid=? AND name=?", (uid, nm))
        _log(uid, "卖出", "%s x%d 得%d" % (nm, h["qty"], net))
        return await ctx.reply("卖出 %s x%d\n%s\n毛收入 %d | 成本 %d | 盈亏 %+d | 税 %d | 实收 %d" %
                              (nm, h["qty"], LINE, gross, int(h["cost"] * h["qty"]), profit, tax, net))
    if act == "历史" and len(a) >= 2:
        nm = a[1]
        days = int(a[2]) if len(a) > 2 and a[2].isdigit() else 7
        out = ["[%s 近 %d 日价格]" % (nm, days), LINE]
        for d in range(days, 0, -1):
            day = time.strftime("%Y-%m-%d", time.localtime(_now() - d * 86400 - 14400))
            r = _one("SELECT v FROM settings WHERE k=?", ("price_%s_%s" % (nm, day),))
            if r:
                out.append("  %s  %s" % (day, r["v"]))
        if len(out) == 2:
            out.append("  暂无历史数据")
        return await ctx.reply("\n".join(out))
    return await ctx.reply("用法：/交易所 状态 | 买入 商品 数量 | 卖出 商品 | 历史 商品 [天数]")


async def cmd_holdings(ctx, args):
    uid = ctx.user_id
    u = _user(uid, ctx.sender)
    rows = _q("SELECT * FROM holdings WHERE uid=? AND qty>0", (uid,))
    if not rows:
        return await ctx.reply("[持仓] 空\n去 /交易所 买入")
    total_cost = total_now = 0
    out = ["[持仓]", LINE]
    for h in rows:
        p = _price(h["name"])
        cost = int(h["cost"] * h["qty"])
        now = p * h["qty"]
        total_cost += cost
        total_now += now
        out.append("%s x%d | 成本 %d | 现值 %d | 盈亏 %+d" % (h["name"], h["qty"], cost, now, now - cost))
    out.append("合计 成本 %d | 现值 %d | 盈亏 %+d" % (total_cost, total_now, total_now - total_cost))
    return await ctx.reply("\n".join(out))


async def cmd_clear(ctx, args):
    uid = ctx.user_id
    u = _user(uid, ctx.sender)
    rows = _q("SELECT * FROM holdings WHERE uid=? AND qty>0", (uid,))
    if not rows:
        return await ctx.reply("没有持仓可清")
    total = 0
    for h in rows:
        total += _price(h["name"]) * h["qty"]
    cfg = _conf(ctx)
    tax = int(total * float(cfg.get("tax_rate") or 0))
    _x("DELETE FROM holdings WHERE uid=?", (uid,))
    _set(uid, coins=int(u.get("coins") or 0) + total - tax)
    return await ctx.reply("清仓完成，卖出 %d 种持仓\n收入 %d | 税 %d | 实收 %d" % (len(rows), total, tax, total - tax))


async def cmd_gacha(ctx, args):
    uid = ctx.user_id
    u = _user(uid, ctx.sender)
    cfg = _conf(ctx)
    cost = int(_num(cfg.get("gacha_cost"), 2000))
    ten = "十连" in (args or "") or (args or "").strip() in ("10", "ten")
    n = 10 if ten else 1
    total = cost * n
    if int(u.get("coins") or 0) < total:
        return await ctx.reply("%s需要 %d 金币，当前 %d" % ("十连" if ten else "单抽", total, u.get("coins") or 0))
    _set(uid, coins=int(u.get("coins") or 0) - total)
    out = ["[抽卡 x%d]" % n, LINE]
    weights = [g[2] for g in GACHA_POOL]
    for i in range(n):
        g = random.choices(GACHA_POOL, weights=weights)[0]
        kind, val, _, label = g
        if kind == "premium":
            _set(uid, premium=int(u.get("premium") or 0) + val)
        elif kind == "item":
            _give(uid, val, 1)
        elif kind == "rod":
            _x("INSERT INTO gear(uid,kind,name,rarity,bonus) VALUES(?,?,?,?,?)",
               (uid, "rod", label, 3, round(random.uniform(0.1, 0.25), 3)))
        else:
            _x("INSERT INTO gear(uid,kind,name,rarity,bonus) VALUES(?,?,?,?,?)",
               (uid, "acc", label, 3, round(random.uniform(0.1, 0.25), 3)))
        out.append("%2d. %s" % (i + 1, label))
    out.append("消耗 %d 金币 | 余额 %d" % (total, int(u.get("coins") or 0) - total))
    _log(uid, "抽卡", "x%d 花%d" % (n, total))
    return await ctx.reply("\n".join(out))


async def cmd_steal(ctx, args):
    uid = ctx.user_id
    u = _user(uid, ctx.sender)
    target = _at_uid(ctx, args)
    if not target or target == uid:
        return await ctx.reply("用法：/偷鱼 @某人 或 /偷鱼 QQ号")
    t = _one("SELECT * FROM users WHERE uid=?", (target,))
    if not t:
        return await ctx.reply("对方还没开始钓鱼")
    cfg = _conf(ctx)
    if _now() - float(u.get("last_fish") or 0) < 60:
        return await ctx.reply("刚动过手，歇一分钟再来")
    rate = float(cfg.get("steal_rate") or 0.45)
    if t.get("nickname") and _item(target, 7) > 0:
        _take(target, 7, 1)
        return await ctx.reply("对方持有驱灵香，海灵守护挡住了你")
    if random.random() > rate:
        _set(uid, last_fish=_now())
        fine = min(200, int(u.get("coins") or 0) // 10)
        _set(uid, coins=int(u.get("coins") or 0) - fine)
        return await ctx.reply("失手了，被巡逻发现，罚款 %d 金币" % fine)
    f = _one("SELECT * FROM fish WHERE uid=? AND place='pond' AND locked=0 ORDER BY value DESC", (target,))
    if not f:
        return await ctx.reply("对方鱼塘是空的")
    _x("UPDATE fish SET uid=? WHERE id=?", (uid, f["id"]))
    _set(uid, last_fish=_now())
    _log(uid, "偷鱼", "从 %s 得 %s" % (target, SPECIES[f["species"]][0]))
    return await ctx.reply("得手了\n从 %s 的鱼塘带走 %s [%d星] 估值 %d 金币" %
                          (target[:6], SPECIES[f["species"]][0], f["rarity"], f["value"]))


async def cmd_zap(ctx, args):
    uid = ctx.user_id
    u = _user(uid, ctx.sender)
    target = _at_uid(ctx, args)
    if not target or target == uid:
        return await ctx.reply("用法：/电鱼 @某人 或 /电鱼 QQ号")
    t = _one("SELECT * FROM users WHERE uid=?", (target,))
    if not t:
        return await ctx.reply("对方还没开始钓鱼")
    cfg = _conf(ctx)
    rate = float(cfg.get("zap_rate") or 0.35)
    if random.random() > rate:
        if _take(uid, 6, 1):
            return await ctx.reply("电鱼失败，擦弹炸弹抵消了惩罚")
        loss = min(500, max(10, int(random.gauss(150, 60))))
        _set(uid, coins=max(0, int(u.get("coins") or 0) - loss))
        return await ctx.reply("电鱼失败，遭天罚损失 %d 金币" % loss)
    rows = _q("SELECT * FROM fish WHERE uid=? AND place='pond' AND locked=0 ORDER BY value", (target,))
    if not rows:
        return await ctx.reply("对方鱼塘是空的")
    take = rows[:max(1, min(3, len(rows) // 5 + 1))]
    gain = sum(int(f["value"]) for f in take) // 2
    _tx(lambda c: c.executemany("UPDATE fish SET uid=? WHERE id=?", [(uid, f["id"]) for f in take]))
    _set(uid, coins=int(u.get("coins") or 0) + gain)
    _log(uid, "电鱼", "对 %s 获 %d" % (target, gain))
    return await ctx.reply("电鱼成功\n卷走 %d 条鱼，折算 %d 金币" % (len(take), gain))


async def cmd_peek(ctx, args):
    target = _at_uid(ctx, args)
    if not target:
        return await ctx.reply("用法：/偷看 @某人 或 /偷看 QQ号")
    t = _one("SELECT * FROM users WHERE uid=?", (target,))
    if not t:
        return await ctx.reply("对方还没开始钓鱼")
    pond = _q("SELECT * FROM fish WHERE uid=? AND place='pond' ORDER BY rarity DESC LIMIT 10", (target,))
    tank = _one("SELECT COUNT(*) n FROM fish WHERE uid=? AND place='aquarium'", (target,))["n"]
    return await ctx.reply("[偷看鱼塘] %s\n%s\n金币 %d | 累计 %d 条 | 水族箱 %d 条 | 称号 %s\n%s\n%s" %
                          (target, LINE, t.get("coins", 0), t.get("fish_count", 0), tank,
                           t.get("title") or "无", LINE, _fmt_fish(pond, 10)))


async def cmd_ach(ctx, args):
    uid = ctx.user_id
    _user(uid, ctx.sender)
    rows = _q("SELECT * FROM achievements WHERE uid=?", (uid,))
    done = dict((r["key"], r) for r in rows)
    out = ["[成就]", LINE]
    for key, title, need, desc, reward, tname in ACHIEVEMENTS:
        r = done.get(key)
        pv = r["progress"] if r else 0
        mark = "已完成" if r and r["done"] else "进行中"
        out.append("%-8s %s  %d/%d  %s" % (title, mark, pv, need, desc))
    return await ctx.reply("\n".join(out))


async def cmd_title(ctx, args):
    uid = ctx.user_id
    u = _user(uid, ctx.sender)
    rows = _q("SELECT title FROM titles WHERE uid=?", (uid,))
    names = [r["title"] for r in rows]
    a = (args or "").strip()
    if not a:
        out = ["[称号] 当前：%s" % (u.get("title") or "无"), LINE]
        for i, n in enumerate(names, 1):
            out.append("  [%d] %s%s" % (i, n, " 使用中" if n == u.get("title") else ""))
        out.append("装备：/称号 <编号>")
        return await ctx.reply("\n".join(out) if names else "还没有称号，去 /成就 看看")
    i = int(a) if a.isdigit() else 0
    if i < 1 or i > len(names):
        return await ctx.reply("编号无效")
    _set(uid, title=names[i - 1])
    return await ctx.reply("已装备称号：%s" % names[i - 1])


async def cmd_transfer(ctx, args):
    uid = ctx.user_id
    u = _user(uid, ctx.sender)
    a = (args or "").strip().split()
    if len(a) < 2 or not a[0].isdigit() or not a[1].isdigit():
        return await ctx.reply("用法：/转账 <QQ号> <金币数量>")
    target, amount = a[0], int(a[1])
    if amount <= 0:
        return await ctx.reply("金额要大于 0")
    if int(u.get("coins") or 0) < amount:
        return await ctx.reply("余额不足")
    t = _one("SELECT * FROM users WHERE uid=?", (target,))
    if not t:
        return await ctx.reply("对方还不是玩家")
    _set(uid, coins=int(u.get("coins") or 0) - amount)
    _set(target, coins=int(t.get("coins") or 0) + amount)
    _log(uid, "转账", "给 %s %d" % (target, amount))
    return await ctx.reply("已向 %s 转账 %d 金币\n余额 %d" % (target, amount, int(u.get("coins") or 0) - amount))


async def cmd_me(ctx, args):
    uid = ctx.user_id
    u = _user(uid, ctx.sender)
    cat = _one("SELECT COUNT(*) n FROM catalog WHERE uid=?", (uid,))["n"]
    pond = _one("SELECT COUNT(*) n FROM fish WHERE uid=? AND place='pond'", (uid,))["n"]
    tank = _one("SELECT COUNT(*) n FROM fish WHERE uid=? AND place='aquarium'", (uid,))["n"]
    rod = _one("SELECT * FROM gear WHERE id=?", (u.get("rod_id") or 0,))
    acc = _one("SELECT * FROM gear WHERE id=?", (u.get("acc_id") or 0,))
    return await ctx.reply("[我的档案] %s\n%s\nQQ      %s\n称号    %s\n等级    %d（经验 %d）\n金币    %d\n高级货币 %d\n累计钓鱼 %d 条 / %.2f kg\n今日    %d 次\n鱼塘    %d 条 | 水族箱 %d/%d\n图鉴    %d/%d\n鱼竿    %s\n饰品    %s" %
                          (u.get("nickname") or "未设置昵称", LINE, uid, u.get("title") or "无",
                           int(u.get("exp") or 0) // 100 + 1, u.get("exp") or 0,
                           u.get("coins") or 0, u.get("premium") or 0,
                           u.get("fish_count") or 0, u.get("total_weight") or 0,
                           u.get("today_count") or 0, pond, tank, u.get("aquarium_cap") or 20,
                           cat, len(SPECIES), rod["name"] if rod else "无", acc["name"] if acc else "无"))


async def cmd_redpack(ctx, args):
    uid = ctx.user_id
    u = _user(uid, ctx.sender)
    a = (args or "").strip().split()
    act = a[0] if a else "列表"
    if act == "发" and len(a) >= 3 and a[1].isdigit() and a[2].isdigit():
        amount, cnt = int(a[1]), int(a[2])
        word = a[3] if len(a) > 3 else ""
        if amount < cnt or cnt < 1 or cnt > 50:
            return await ctx.reply("金额至少等于份数，份数 1-50")
        if int(u.get("coins") or 0) < amount:
            return await ctx.reply("余额不足")
        _set(uid, coins=int(u.get("coins") or 0) - amount)
        rid = _x("INSERT INTO redpack(sender,amount,total,rest,word,created) VALUES(?,?,?,?,?,?)",
                 (uid, amount, cnt, cnt, word, _now()))
        return await ctx.reply("[红包已发出] 编号 RP%s\n%s\n金额 %d 金币 | %d 份%s\n领取：/红包 领 RP%s%s" %
                              (_b36(rid), LINE, amount, cnt,
                               " | 口令 " + word if word else "", _b36(rid),
                               " " + word if word else ""))
    if act in ("领", "抢", "拿") and len(a) >= 2:
        rid = _unb36(a[1].upper().lstrip("RP"))
        r = _one("SELECT * FROM redpack WHERE id=?", (rid,))
        if not r or r["rest"] <= 0:
            return await ctx.reply("红包不存在或已领完")
        if r["word"] and (len(a) < 3 or a[2] != r["word"]):
            return await ctx.reply("口令不对，用法：/红包 领 RP%s <口令>" % _b36(rid))
        taken = (r.get("taken") or "").split(",")
        if uid in taken:
            return await ctx.reply("你已经领过这个红包了")
        amount = int(r["amount"]) // int(r["total"])
        if int(r["rest"]) == 1:
            amount = int(r["amount"]) - amount * (int(r["total"]) - 1)
        _x("UPDATE redpack SET rest=rest-1,taken=? WHERE id=?",
           (",".join(taken + [uid]), rid))
        _set(uid, coins=int(u.get("coins") or 0) + amount)
        return await ctx.reply("领到 %d 金币 | 红包剩余 %d 份" % (amount, int(r["rest"]) - 1))
    rows = _q("SELECT * FROM redpack WHERE rest>0 ORDER BY id DESC LIMIT 10")
    if not rows:
        return await ctx.reply("[红包列表] 暂无活跃红包\n发红包：/红包 发 金额 份数 [口令]")
    out = ["[红包列表]", LINE]
    for r in rows:
        out.append("[RP%s] %d 金币 / 剩 %d 份 %s" %
                   (_b36(r["id"]), r["amount"], r["rest"], "口令" if r["word"] else ""))
    return await ctx.reply("\n".join(out))


async def cmd_fishhelp(ctx, args):
    return await ctx.reply("[钓鱼游戏 指令手册]\n" + LINE + "\n"
        "基础   /钓鱼 [2|3]  /鱼塘  /我的  /日常  /渔助\n"
        "资产   /出售 [F码|全部|星N]  /水族箱 存入|取出|升级  /图鉴  /背包\n"
        "装备   /鱼竿 装备|丢弃 <R码>  /饰品 装备|丢弃 <A码>  /精炼 鱼竿|饰品 <短码>\n"
        "商店   /商店 [1|2|3]  /购买 <商店> <编号> [数量]\n"
        "市场   /市场 [页]  /上架 F码 价格 [数量] [匿名]  /收购 M码 [数量]  /下架 M码\n"
        "交易所 /交易所 状态|买入 商品 数量|卖出 商品|历史 商品  /持仓  /清仓\n"
        "娱乐   /抽卡 [十连]  /偷鱼 @人  /电鱼 @人  /偷看 @人  /转账 QQ 金额\n"
        "社交   /排行榜 [金币|鱼获|数量|图鉴]  /成就  /称号 [编号]\n"
        "红包   /红包 发 金额 份数 [口令]  /红包 领 RP码 [口令]\n"
        "管理员 /渔管 金币 QQ 数量 | 封禁 QQ | 解封 QQ | 重置鱼池 | 公告 文本\n"
        "后台   http://103.236.99.177:24512/yuewu/fish")


async def cmd_admin(ctx, args):
    if not _is_admin(ctx):
        return
    a = (args or "").strip().split()
    if not a:
        return await ctx.reply("用法：/渔管 金币 QQ 数量 | 高级 QQ 数量 | 经验 QQ 数量 | 封禁 QQ | 解封 QQ | 名单 | 重置鱼池 | 重置每日 | 发道具 QQ 编号 数量 | 公告 文本 | 清公告")
    act = a[0]
    if act in ("金币", "高级", "经验") and len(a) >= 3 and a[2].lstrip("-").isdigit():
        qq, val = a[1], int(a[2])
        u = _one("SELECT * FROM users WHERE uid=?", (qq,))
        if not u:
            return await ctx.reply("用户不存在")
        field = {"金币": "coins", "高级": "premium", "经验": "exp"}[act]
        _set(qq, **{field: max(0, int(u.get(field) or 0) + val)})
        _log(ctx.user_id, "管理", "%s %s %+d" % (act, qq, val))
        return await ctx.reply("已为 %s 调整 %s %+d" % (qq, act, val))
    if act in ("封禁", "解封") and len(a) >= 2:
        qq = a[1]
        _set(qq, banned=1 if act == "封禁" else 0)
        _log(ctx.user_id, "管理", "%s %s" % (act, qq))
        return await ctx.reply("已%s %s" % (act, qq))
    if act == "名单":
        rows = _q("SELECT uid,coins,fish_count,banned FROM users ORDER BY fish_count DESC LIMIT 20")
        return await ctx.reply("[用户名单]\n" + LINE + "\n" +
                               "\n".join("%s 金币%d 鱼%d%s" % (r["uid"], r["coins"], r["fish_count"], " 已封禁" if r["banned"] else "") for r in rows))
    if act == "重置鱼池":
        for i in range(1, 11):
            r = _one("SELECT quota FROM pool WHERE rarity=?", (i,))
            q = r["quota"] if r else max(1, int(60000 / (i ** 3)))
            _x("UPDATE pool SET left=?,day=? WHERE rarity=?", (q, _today(), i))
        _log(ctx.user_id, "管理", "重置鱼池")
        return await ctx.reply("所有稀有度鱼池配额已补满")
    if act == "重置每日":
        _x("UPDATE users SET today_count=0,today=?", (_today(),))
        return await ctx.reply("全体今日钓鱼次数已重置")
    if act == "发道具" and len(a) >= 4:
        qq, iid, qty = a[1], int(a[2]) if a[2].isdigit() else 0, int(a[3]) if a[3].isdigit() else 1
        if iid not in ITEMS:
            return await ctx.reply("道具编号 1-%d" % len(ITEMS))
        _give(qq, iid, qty)
        return await ctx.reply("已给 %s 发放 %s x%d" % (qq, ITEMS[iid][0], qty))
    if act in ("公告", "清公告"):
        text = " ".join(a[1:]) if act == "公告" else ""
        bot = ctx.bot
        bot.plugins.save_plugin_config("fishing", {"announce": text})
        return await ctx.reply("公告已" + ("更新" if text else "清空"))
    return await ctx.reply("未知管理动作，发 /渔助 查看")


TABLES = ["users", "fish", "gear", "items", "market", "catalog", "holdings",
          "redpack", "achievements", "titles", "pool", "settings"]


def _cfg_read(bot):
    out = dict(DEFAULTS)
    try:
        out.update(bot.plugins.plugin_config("fishing") or {})
    except Exception:
        pass
    return out


def admin_overview(bot, data):
    _init()
    u = _one("SELECT COUNT(*) n,COALESCE(SUM(coins),0) c,COALESCE(SUM(fish_count),0) f FROM users")
    fish = _one("SELECT COUNT(*) n,COALESCE(SUM(value),0) v FROM fish")
    mk = _one("SELECT COUNT(*) n FROM market")
    today = _one("SELECT COUNT(*) n FROM logs WHERE action='钓鱼' AND ts>=?", (_now() - 86400,))
    rp = _one("SELECT COUNT(*) n FROM redpack WHERE rest>0")
    size = DB.stat().st_size if DB.exists() else 0
    top = _q("SELECT uid,nickname,coins,fish_count FROM users ORDER BY coins DESC LIMIT 5")
    return {"users": u["n"], "coins": u["c"], "total_fish": u["f"],
            "fish_rows": fish["n"], "fish_value": fish["v"], "market": mk["n"],
            "today_fish": today["n"], "redpack": rp["n"], "db_size": size,
            "species": len(SPECIES), "shops": len(SHOPS), "top": top,
            "config": _cfg_read(bot)}


def admin_users(bot, data):
    q = str(data.get("q") or "").strip()
    limit = max(1, min(200, int(_num(data.get("limit"), 50))))
    if q:
        rows = _q("SELECT * FROM users WHERE uid LIKE ? OR nickname LIKE ? ORDER BY fish_count DESC LIMIT ?",
                  ("%" + q + "%", "%" + q + "%", limit))
    else:
        rows = _q("SELECT * FROM users ORDER BY fish_count DESC LIMIT ?", (limit,))
    return {"total": _one("SELECT COUNT(*) n FROM users")["n"], "users": rows}


def admin_user(bot, data):
    uid = str(data.get("uid") or "")
    u = _one("SELECT * FROM users WHERE uid=?", (uid,))
    if not u:
        raise ValueError("用户不存在")
    return {"user": u,
            "fish": _q("SELECT * FROM fish WHERE uid=? ORDER BY rarity DESC,id DESC LIMIT 100", (uid,)),
            "gear": _q("SELECT * FROM gear WHERE uid=? ORDER BY id DESC LIMIT 50", (uid,)),
            "items": _q("SELECT * FROM items WHERE uid=? AND qty>0", (uid,)),
            "holdings": _q("SELECT * FROM holdings WHERE uid=? AND qty>0", (uid,)),
            "titles": _q("SELECT * FROM titles WHERE uid=?", (uid,)),
            "achievements": _q("SELECT * FROM achievements WHERE uid=?", (uid,))}


def admin_user_update(bot, data):
    uid = str(data.get("uid") or "")
    u = _one("SELECT * FROM users WHERE uid=?", (uid,))
    if not u:
        raise ValueError("用户不存在")
    patch = {}
    for k in ("coins", "premium", "exp", "today_count", "aquarium_cap", "fish_count"):
        if k in data:
            patch[k] = max(0, int(_num(data.get(k), 0)))
    if "banned" in data:
        bv = str(data.get("banned"))
        patch["banned"] = 0 if bv in ("0", "", "false", "False", "None") else 1
    if "nickname" in data:
        patch["nickname"] = str(data.get("nickname"))[:32]
    if "title" in data:
        patch["title"] = str(data.get("title"))[:32]
    if patch:
        _set(uid, **patch)
    _log("admin", "后台改用户", "%s %s" % (uid, json.dumps(patch, ensure_ascii=False)[:150]))
    return {"ok": True, "user": _one("SELECT * FROM users WHERE uid=?", (uid,))}


def admin_config(bot, data):
    return {"config": _cfg_read(bot), "schema": {k: {"type": "number" if isinstance(v, (int, float)) else "string", "default": v} for k, v in DEFAULTS.items()}}


def admin_config_update(bot, data):
    patch = data.get("config") or {}
    if not isinstance(patch, dict):
        raise ValueError("配置格式错误")
    clean = {}
    for k, v in patch.items():
        if k not in DEFAULTS:
            continue
        clean[k] = str(v) if k in ("owner", "announce") else _num(v, DEFAULTS[k])
    bot.plugins.save_plugin_config("fishing", clean)
    if "reset_hour" in clean:
        _x("INSERT OR REPLACE INTO settings(k,v) VALUES('reset_hour',?)", (str(clean["reset_hour"]),))
    _log("admin", "后台改配置", json.dumps(clean, ensure_ascii=False)[:150])
    return {"ok": True, "config": _cfg_read(bot)}


def admin_pool(bot, data):
    rows = _q("SELECT * FROM pool ORDER BY rarity")
    out = []
    for r in rows:
        out.append({"rarity": r["rarity"], "name": RARITY_NAMES[r["rarity"] - 1],
                    "quota": r["quota"], "left": r["left"], "day": r["day"]})
    return {"pool": out, "today": _today()}


def admin_pool_reset(bot, data):
    for r in _q("SELECT * FROM pool"):
        _x("UPDATE pool SET left=?,day=? WHERE rarity=?", (r["quota"], _today(), r["rarity"]))
    _log("admin", "后台重置鱼池", "")
    return {"ok": True, "pool": admin_pool(bot, data)["pool"]}


def admin_market_clear(bot, data):
    days = _num(data.get("days"), 7)
    n = _x("DELETE FROM market WHERE created<?", (_now() - days * 86400,))
    _log("admin", "清理市场", "删除 %d 单" % n)
    return {"ok": True, "deleted": n}


def admin_logs(bot, data):
    limit = max(1, min(500, int(_num(data.get("limit"), 100))))
    rows = _q("SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limit,))
    for r in rows:
        r["time"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["ts"]))
    return {"logs": rows}


def admin_export(bot, data):
    out = {}
    for t in TABLES:
        out[t] = _q("SELECT * FROM %s" % t)
    return {"version": 1, "exported": _now(), "tables": out}


def admin_import(bot, data):
    payload = data.get("payload") or {}
    tables = payload.get("tables") or {}
    if not isinstance(tables, dict):
        raise ValueError("数据格式错误")
    if DB.exists():
        import shutil
        shutil.copy2(str(DB), str(DB) + ".bak")
    imported = {}

    def work(c):
        for t in TABLES:
            if t not in tables:
                continue
            rows = tables[t]
            if not isinstance(rows, list):
                continue
            cols = [r["name"] for r in c.execute("PRAGMA table_info(%s)" % t).fetchall()]
            c.execute("DELETE FROM %s" % t)
            n = 0
            for row in rows:
                if not isinstance(row, dict):
                    continue
                ks = [k for k in cols if k in row]
                if not ks:
                    continue
                c.execute("INSERT INTO %s(%s) VALUES(%s)" % (t, ",".join(ks), ",".join("?" for _ in ks)),
                          tuple(row[k] for k in ks))
                n += 1
            imported[t] = n
        return True

    _tx(work)
    _log("admin", "后台导入数据", json.dumps(imported, ensure_ascii=False)[:150])
    return {"ok": True, "imported": imported}


def admin_broadcast(bot, data):
    text = str(data.get("text") or "")[:200]
    bot.plugins.save_plugin_config("fishing", {"announce": text})
    _log("admin", "后台公告", text[:100])
    return {"ok": True, "announce": text}


def admin_adjust(bot, data):
    uid = str(data.get("uid") or "").strip()
    if not uid.isdigit():
        raise ValueError("QQ 号格式不正确")
    delta = int(_num(data.get("delta"), 0))
    u = _user(uid)
    coins = max(0, int(u.get("coins") or 0) + delta)
    _set(uid, coins=coins)
    _log("admin", "后台调整金币", "%s %+d -> %d" % (uid, delta, coins))
    return {"ok": True, "uid": uid, "coins": coins}

"""专业模式插件

/专家 <内容>
把内容原样作为唯一一条 user 消息发给独立配置的模型接口，不注入任何
系统提示词，也不带聊天上下文，因此完全不受机器人原本人格设定的影响。

特点：
  · 无系统提示词：请求体里只有一条 user 消息
  · 无长度限制：max_tokens 默认 0（不传该字段），长回复自动分段发送
  · 独立接口：自己配置 base_url / api_key / model，与机器人主模型互不影响

配置项全部留空，安装后需要在控制台「插件 → 专业模式 → 配置」里填写。
"""

import asyncio
import json
import time

try:
    import aiohttp
except Exception:  # pragma: no cover
    aiohttp = None

VERSION = "1.0.0"

DEFAULT_BASE = ""
DEFAULT_KEY = ""
DEFAULT_MODEL = ""

# 单条消息的字符上限，超过则分段发送（QQ 单条约 4500 字节，中文按 3 字节算）
CHUNK = 1200
MAX_CHUNKS = 8

# 同一用户两次调用之间的最小间隔
_COOL = {}


def _log(msg):
    try:
        print("[expert] " + str(msg), flush=True)
    except Exception:
        pass


# ------------------------------------------------------------------ 配置
def _cfg(ctx, key, default=None):
    try:
        conf = getattr(ctx, "cfg", None) or {}
        return conf.get(key, default)
    except Exception:
        return default


def _s(ctx, key, default=""):
    v = _cfg(ctx, key, default)
    if v is None:
        return default
    return str(v).strip()


def _num(ctx, key, default, lo=None, hi=None):
    try:
        v = float(_cfg(ctx, key, default))
    except Exception:
        v = float(default)
    if lo is not None:
        v = max(lo, v)
    if hi is not None:
        v = min(hi, v)
    return v


def _is_admin(ctx):
    uid = str(getattr(ctx, "user_id", "") or "").strip()
    if not uid:
        return False
    try:
        return bool(ctx.bot.plugins.is_admin(uid))
    except Exception:
        return False


# ------------------------------------------------------------------ 请求
def _endpoint(base, proto):
    b = (base or "").strip().rstrip("/")
    if not b:
        raise RuntimeError("未配置接口地址")
    if proto == "anthropic":
        if b.endswith("/messages"):
            return b
        if b.endswith("/v1"):
            return b + "/messages"
        return b + "/v1/messages"
    if b.endswith("/chat/completions"):
        return b
    return b + "/chat/completions"


def _payload(model, prompt, proto, temp, mtok):
    if proto == "anthropic":
        body = {
            "model": model,
            "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
            # Anthropic 的 max_tokens 为必填，0 表示按模型上限给一个稳妥值
            "max_tokens": int(mtok) if mtok and mtok > 0 else 8192,
        }
    else:
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        # 0 = 不传，交给服务端按模型上限处理
        if mtok and mtok > 0:
            body["max_tokens"] = int(mtok)
    if temp is not None:
        body["temperature"] = temp
    return body


def _headers(key, proto):
    if proto == "anthropic":
        return {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
    return {"Authorization": "Bearer " + key, "content-type": "application/json"}


def _pick_text(data, proto):
    """从响应里取出正文，兼容几种常见返回结构"""
    if proto == "anthropic":
        err = data.get("error")
        if isinstance(err, dict):
            raise RuntimeError(str(err.get("message") or "接口返回错误")[:200])
        blocks = data.get("content")
        if isinstance(blocks, list):
            text = "".join(str(b.get("text") or "") for b in blocks
                           if isinstance(b, dict) and b.get("type") == "text")
            if text.strip():
                return text.strip()
        raise RuntimeError("接口返回内容为空")

    err = data.get("error")
    if err:
        if isinstance(err, dict):
            raise RuntimeError(str(err.get("message") or "接口返回错误")[:200])
        raise RuntimeError(str(err)[:200])

    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("接口返回内容为空")
    msg = choices[0].get("message") or {}
    content = msg.get("content")
    if isinstance(content, str):
        return content.strip()
    # 部分服务把正文放在 content 数组里
    if isinstance(content, list):
        text = "".join(str(p.get("text") or "") for p in content
                       if isinstance(p, dict) and p.get("type") in ("text", "output_text"))
        if text.strip():
            return text.strip()
    text = choices[0].get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    raise RuntimeError("接口返回内容为空")


async def _ask(base, key, model, prompt, proto, temp, mtok, timeout):
    if aiohttp is None:
        raise RuntimeError("缺少 aiohttp 依赖")
    url = _endpoint(base, proto)
    body = _payload(model, prompt, proto, temp, mtok)
    headers = _headers(key, proto)
    timeout = aiohttp.ClientTimeout(total=timeout)

    last = None
    for i in range(2):
        try:
            async with aiohttp.ClientSession(timeout=timeout) as sess:
                async with sess.post(url, headers=headers, json=body) as resp:
                    raw = await resp.text()
                    status = resp.status
            if status >= 400:
                detail = raw[:300].replace("\n", " ")
                if status in (401, 403):
                    raise RuntimeError("接口鉴权失败（%s），请检查 API Key" % status)
                if status == 404:
                    raise RuntimeError("接口地址不存在（404）：%s" % url)
                if status == 429:
                    raise RuntimeError("接口限流（429），稍后再试")
                if status >= 500 and i == 0:
                    last = RuntimeError("接口出错（%s）：%s" % (status, detail))
                    await asyncio.sleep(1.2)
                    continue
                raise RuntimeError("接口出错（%s）：%s" % (status, detail))
            try:
                data = json.loads(raw)
            except Exception:
                raise RuntimeError("接口响应不是 JSON：%s" % raw[:160])
            return _pick_text(data, proto)
        except asyncio.TimeoutError:
            last = RuntimeError("接口超时（%d 秒）" % int(timeout.total or 0))
            if i == 0:
                continue
            raise last
        except aiohttp.ClientError as e:
            last = RuntimeError("连接失败：%s" % str(e)[:140])
            if i == 0:
                await asyncio.sleep(1.0)
                continue
            raise last
    raise last or RuntimeError("调用失败")


# ------------------------------------------------------------------ 发送
def _mid(res):
    """从 OneBot 返回里取 message_id"""
    try:
        if isinstance(res, dict):
            data = res.get("data")
            if isinstance(data, dict) and data.get("message_id") is not None:
                return data["message_id"]
            if res.get("message_id") is not None:
                return res["message_id"]
    except Exception:
        pass
    return None


def _split(text, limit=CHUNK, max_parts=MAX_CHUNKS):
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= limit:
        return [text]
    parts, rest = [], text
    while rest and len(parts) < max_parts:
        if len(rest) <= limit:
            parts.append(rest)
            rest = ""
            break
        cut = rest.rfind("\n", 0, limit)
        if cut < limit * 0.55:
            mark = max(rest.rfind("。", 0, limit), rest.rfind("！", 0, limit),
                       rest.rfind("？", 0, limit), rest.rfind("；", 0, limit))
            cut = mark + 1 if mark >= limit * 0.55 else limit
        parts.append(rest[:cut].strip())
        rest = rest[cut:].strip()
    if rest:
        parts[-1] = parts[-1] + "\n\n…（回复过长，余下部分已省略）"
    return [p for p in parts if p]


async def _send_long(ctx, text):
    chunks = _split(text)
    for i, part in enumerate(chunks):
        if i:
            await asyncio.sleep(0.4)
        await ctx.reply(part)


async def _hint(ctx, state, delay):
    """请求稍慢时给个提示，拿到结果后撤回

    state["done"] 由主流程置位。若提示刚发出结果就回来了，这里自己撤回，
    避免主流程在 mid 尚未写回时错过撤回、留下一条「正在思考…」。
    """
    try:
        await asyncio.sleep(delay)
    except asyncio.CancelledError:
        return
    if state.get("done"):
        return
    try:
        res = await ctx.reply("正在思考…")
    except Exception:
        return
    mid = _mid(res)
    state["mid"] = mid
    if mid is not None and state.get("done"):
        await _recall(ctx, mid)
        state["mid"] = None


# ------------------------------------------------------------------ 命令
async def cmd_expert(ctx, args):
    prompt = (args or "").strip()

    if not prompt:
        await ctx.reply(
            "用法：/专家 你的问题\n"
            "直接把内容写在后面，机器人会用独立接口原样提问，不套任何人设和提示词。"
        )
        return True

    if _cfg(ctx, "admin_only", False) and not _is_admin(ctx):
        await ctx.reply("专业模式当前仅限管理员使用。")
        return True

    base = _s(ctx, "api_base", DEFAULT_BASE)
    key = _s(ctx, "api_key", DEFAULT_KEY)
    model = _s(ctx, "model", DEFAULT_MODEL)

    if not base or not key or not model:
        miss = []
        if not base:
            miss.append("接口地址")
        if not key:
            miss.append("API Key")
        if not model:
            miss.append("模型名")
        await ctx.reply("专业模式还没配置好，缺少：%s\n请在控制台「插件 → 专业模式 → 配置」里填写。" % "、".join(miss))
        return True

    # 冷却
    uid = str(getattr(ctx, "user_id", "") or "")
    cool = _num(ctx, "cooldown", 5, 0, 600)
    now = time.time()
    if cool > 0 and uid:
        last = _COOL.get(uid, 0)
        if now - last < cool:
            await ctx.reply("别急，%.0f 秒后再问。" % (cool - (now - last) + 0.5))
            return True
    if uid:
        _COOL[uid] = now

    proto = _s(ctx, "protocol", "openai").lower()
    if proto in ("anthropic", "claude", "messages"):
        proto = "anthropic"
    else:
        proto = "openai"
    temp = _num(ctx, "temperature", 0.7, 0, 2)
    mtok = _num(ctx, "max_tokens", 0, 0, 2000000)
    timeout = _num(ctx, "timeout", 180, 10, 1800)

    state = {"mid": None, "done": False}
    timer = asyncio.ensure_future(_hint(ctx, state, 2.6))
    t0 = time.time()
    try:
        text = await _ask(base, key, model, prompt, proto, temp, mtok, timeout)
    except Exception as e:
        state["done"] = True
        timer.cancel()
        if state["mid"] is not None:
            await _recall(ctx, state["mid"])
        _log("调用失败：%s" % e)
        await ctx.reply("调用失败：%s" % str(e)[:300])
        return True
    state["done"] = True
    timer.cancel()
    if state["mid"] is not None:
        await _recall(ctx, state["mid"])
        state["mid"] = None

    if not text:
        await ctx.reply("模型没有返回内容。")
        return True

    _log("成功 %.1fs，%d 字" % (time.time() - t0, len(text)))
    try:
        await _send_long(ctx, text)
    except Exception as e:
        _log("发送失败：%s" % e)
    return True


async def _recall(ctx, mid):
    try:
        await ctx.api("delete_msg", message_id=mid)
    except Exception:
        pass


# ------------------------------------------------------------------ 钩子
async def on_startup(bot):
    _log("专业模式已加载 v%s" % VERSION)

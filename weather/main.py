import urllib.parse

async def on_startup(bot):
    print("[weather] 天气插件已加载")

async def cmd_weather(ctx, args):
    from aiohttp import ClientSession
    city = (args or "").strip() or (ctx.cfg.get("default_city") or "北京")
    url = "https://wttr.in/" + urllib.parse.quote(city) + "?format=3&lang=zh"
    try:
        async with ClientSession() as s:
            async with s.get(url, timeout=15) as r:
                text = (await r.text()).strip()
    except Exception as e:
        return await ctx.reply("查询失败了：" + str(e)[:80])
    if not text or "Unknown" in text:
        return await ctx.reply("没找到这个城市，换个名字试试？")
    return await ctx.reply(text)

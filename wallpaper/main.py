async def cmd_pic(ctx, args):
    parts = (args or "").split()
    w = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else int(ctx.cfg.get("width") or 800)
    h = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else int(w * 0.62)
    url = "https://picsum.photos/%d/%d" % (w, h)
    try:
        await ctx.send_image(url)
    except Exception as e:
        await ctx.reply("图片发送失败：" + str(e)[:80])

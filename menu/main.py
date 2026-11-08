WORDS = ("菜单", "功能", "功能列表", "菜单列表")


def _build(ctx):
    conf = ctx.cfg or {}
    lines = [str(conf.get("title") or "YueWuBot 功能菜单"), ""]
    lines.append("常用")
    lines.append("  菜单           查看本菜单")
    lines.append("  赞我           点十个赞（24 小时一次）")
    lines.append("  #内容         群聊快速对话")
    lines.append("  #YueWu        查看版本与运行状态")
    lines.append("")
    lines.append("群管理")
    lines.append("  新人进群       自动 @ 并问好")
    lines.append("  入群 / 好友    主人审批后放行")
    lines.append("")
    cmds = []
    try:
        cmds = ctx.bot.plugins.all_commands()
    except Exception:
        pass
    seen = set()
    items = []
    for c in cmds:
        n = str(c.get("name") or "")
        if n and n not in seen:
            seen.add(n)
            items.append(("/%s" % n, str(c.get("description") or "")))
    if items:
        lines.append("指令")
        for name, desc in items[:26]:
            lines.append("  %s %s" % (name, desc))
        lines.append("")
    lines.append(str(conf.get("tip") or "发 /帮助 查看全部指令"))
    return "\n".join(lines)


async def on_message(ctx):
    if (ctx.text or "").strip() not in WORDS:
        return False
    await ctx.reply(_build(ctx))
    return True


async def cmd_menu(ctx, args):
    await ctx.reply(_build(ctx))
    return True

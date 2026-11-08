# YueWuBot 插件仓库

YueWuBot 官方插件集合。每个插件一个目录，目录内是完整的 `m.json` + `main.py` + `icon.png`。

插件索引发布在 **https://chumianyi.github.io/p.json**，YueWuBot 控制台的「插件市场」直接读取这个索引，点安装即可拉取本仓库并完成安装。

## 插件列表

| 插件 | 目录 | 说明 |
| --- | --- | --- |
| 视频解析器 | `video_parser/` | 发 B站 / 抖音链接（或 `/解析 链接`）自动回标题 + 直链 + 封面，不下载文件 |
| 网易云点歌 | `netease_music/` | `/网易搜歌 关键词` 搜歌、`/网易点歌 序号` 发歌，支持封面、播放直链与音乐卡片 |
| 群广播 | `broadcast/` | 引用一条消息后发 `/广播`，一键转发到机器人加入的所有群（仅管理员） |
| 天气查询 | `weather/` | 查询指定城市的实时天气，数据来自 wttr.in |
| 随机壁纸 | `wallpaper/` | 随机来一张图，支持自定义尺寸 |
| 每日签到 | `signin/` | 每日签到，记录连续签到天数，数据落盘 |
| 爱点赞 | `love_like/` | 发送「赞我」给发送者点 10 个赞，是否点过以接口返回为准 |
| 入群欢迎 | `group_welcome/` | 有人进群时自动 @ 新人并发送欢迎语 |
| 入群审批 | `request_approve/` | 好友申请与入群邀请先私聊主人审批 |
| 黑名单 | `blacklist/` | 名单内的 QQ 无法与机器人交互 |
| 功能菜单 | `menu/` | 发送「菜单」查看全部功能 |
| 钓鱼 | `fishing/` | 纯文本钓鱼游戏：鱼塘、装备、商店、交易所、抽卡、成就 |

## 安装方式

**控制台（推荐）**：打开 YueWuBot 控制台 → 插件市场 → 找到插件 → 安装。安装过程优先下载仓库压缩包（失败自动改用 `git clone`），解压后复制到 `plugins/` 目录，已安装的插件会显示「已安装」。

**手动**：把对应目录整个复制到 YueWuBot 根目录的 `plugins/` 下，重启或让控制台重新扫描即可。目录名就是插件标识，不要改名。

## 插件规范

一个插件目录至少包含：

```
<plugin_id>/
  m.json      # 元数据：name / version / author / description / hooks / commands / config
  main.py     # 入口：on_startup / on_message / on_command 等钩子函数
  icon.png    # 可选，控制台与市场展示用
  assets/     # 可选，插件自己的数据文件
```

钩子返回值约定：`on_message` 返回 `True` 表示该条消息已被处理，不再向下传递。

## 许可证

MIT，见 [LICENSE](LICENSE)。

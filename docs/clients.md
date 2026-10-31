# 连接播放器

先确认 HomeCast 已完成首次刷新，页面能看到真实频道和节目单。

播放器只需要订阅链接。不用填写电信账号、SN、MAC 或抓包信息。

## 先复制两条链接

1. 打开 HomeCast 页面。
2. 点击 **订阅链接**。
3. 分别复制 M3U 和 XMLTV 地址。

| 播放器里的字段 | 填什么 | 用途 |
| --- | --- | --- |
| M3U / Playlist URL / 频道列表 | 刚复制的 M3U 链接 | 获取频道和播放地址 |
| XMLTV / EPG URL / 节目单 | 刚复制的 XMLTV 链接 | 获取节目名称和时间 |

通用链接分别以 `/m3u/xteve.m3u` 和 `/xmltv/xteve.xml` 结尾。

复制的地址由 `HOMECAST_PUBLIC_URL` 决定，不会随浏览器访问别名改变。配置方法见 [配置指南](configuration.md)。

浏览器不允许自动复制时，地址会被选中。Windows / Linux 按 `Ctrl+C`，macOS 按 `Command+C`。

优先使用 **URL 订阅**。下载后导入的文件只是一次快照，不会自动跟随服务更新。

播放器必须能访问 HomeCast 和外部 udpxy。能打开页面，不代表视频链路已经可用。

## Apple TV、智能电视和手机

选择支持远程 **M3U + XMLTV** 的 IPTV 播放器。

1. 添加播放列表，类型选 **M3U**。不要选 Xtream Codes 或 Stalker Portal。
2. 名称可填“家庭 IPTV”，频道地址填复制的 M3U 链接。
3. 打开该来源的 EPG / 节目单设置，填 XMLTV 链接。
4. 将节目单关联到同一播放列表。
5. 保存，更新频道和节目单，再选一个已订阅频道播放。

**成功检查：** 能看到频道和节目时间，播放时有画面和声音。

这是第三方 IPTV 播放器的设置，不是系统自带“Apple TV”影视订阅页面。

Apple 设备弹出本地网络权限请求时，允许访问家庭网络。设备不要接隔离的访客 Wi-Fi。

不要填写 `localhost` 或 `127.0.0.1`。它们指向播放器自己。

客户端还要支持 HTTP MPEG-TS 和 302 跳转。只支持 HLS 的 App 可能无法使用，HomeCast 不会转码。

## Jellyfin

### 已有用户先看这里

不用改现有用户、媒体库目录或可见权限。
原订阅能用就可以继续用，通常只需刷新现有源。

**换 M3U 地址前，先备份 Jellyfin 配置。**
记录频道收藏、录制计划和系列录制计划。
换地址会让 Jellyfin 重新识别频道，切换后要核对这些绑定。

<details>
<summary>为什么换地址会影响频道收藏？</summary>

Jellyfin 的内部频道 ID 包含播放列表 URL 的哈希。
它不等于 M3U 中的 `tvg-id`。
即使 `tvg-id` 没变，更换 M3U 地址也会生成新的内部 ID。
原收藏和录制绑定可能需要重建。
见 [Jellyfin 频道身份实现](https://github.com/jellyfin/jellyfin/blob/v10.11.0/src/Jellyfin.LiveTv/TunerHosts/M3UTunerHost.cs#L57-L66)。

</details>

### 选择链接

通用链接可以直接使用。需要在频道名称中显示分组时，使用下面这对 Jellyfin 专用链接。

把示例的 `http://192.0.2.1:34400` 整体换成自己的 `HOMECAST_PUBLIC_URL`，保留后面的路径。示例地址不能直接播放。

```text
M3U:   http://192.0.2.1:34400/m3u/jellyfin.m3u
XMLTV: http://192.0.2.1:34400/xmltv/jellyfin.xml
```

### 添加到直播电视

1. 打开“管理控制台 -> 直播电视”。
2. 添加调谐器，选择 **M3U Tuner**，不是 HDHomeRun 自动发现。
3. 在“文件或 URL”中填 M3U 链接并保存。
4. 添加节目单提供程序，选择 **XMLTV**，填配套 XMLTV 链接。
5. 刷新节目单，再进入“直播电视 / 节目表”。

**成功检查：** 频道和节目能对应，至少一个已订阅频道能播放。

这些地址由 **Jellyfin 服务端** 拉取。它所在的容器或主机也必须能访问 HomeCast 和 udpxy。

个别频道未匹配时，检查节目单提供程序的频道映射。不要单独改动 M3U 的 `tvg-id` 或 XMLTV 的 `channel id`。

菜单以安装版本为准。[Jellyfin 官方接入说明](https://jellyfin.org/docs/general/server/live-tv/setup-guide/)

<details>
<summary>Jellyfin 专用链接有什么不同？</summary>

Jellyfin 原生直播页不按 M3U 的 `group-title` 显示分组栏目。

专用导出保留全部频道，名称显示为 `[央视] CCTV-1` 等。它不是新的可折叠分组控件。

频道按央视、卫视、专题、地方与其他排序。未知分组排在末尾。

编号从 1 开始连续生成。在 Jellyfin 中按频道编号排序，就能连续浏览各组。

官方增减频道时，连续编号可能调整。已有频道的 `tvg-id`、节目映射和视频地址不因这种排序改变。

专用 XMLTV 也使用带分组前缀的名称，所以建议成对填写。

通用 `/m3u/xteve.m3u` 和 `/xmltv/xteve.xml` 的名称、编号和顺序不受影响。Apple TV 等现有客户端不用跟着改订阅。

</details>

## Kodi

1. 启用 **IPTV Simple Client**，添加一个来源。
2. 将 M3U 位置设为远程 URL，填复制的 M3U 链接。
3. 在 EPG 设置中填 XMLTV 链接。
4. 保存并启用来源，刷新频道和节目单。
5. 打开“电视”菜单，选择频道。

**成功检查：** 能看到节目表，也能播放频道。

不同插件版本可能使用多个配置实例。[IPTV Simple Client 官方说明](https://github.com/kodi-pvr/pvr.iptvsimple)

## VLC：先试能不能播放

VLC 适合快速检查播放链路，不需要填写 XMLTV。

1. Windows / Linux 打开“媒体 -> 打开网络串流”。macOS 打开“文件 -> 打开网络”。
2. 填入复制的 M3U 链接。
3. 打开播放列表，选择一个已订阅频道。

**成功检查：** 有画面和声音。

XMLTV 不是视频地址，不能用它播放。需要完整节目表时，使用支持 EPG 的 IPTV 客户端。[VideoLAN 官方网络串流说明](https://docs.videolan.me/vlc-user/desktop/3.0/en/basic/media.html)

## 设置自动更新

HomeCast 按自己的计划更新频道和节目单。播放器也要开启定期更新或启动时更新。

把播放器的更新时间放在 HomeCast 更新完成之后。例如 HomeCast 05:00 更新，播放器可设为 06:00。

HomeCast 不会主动推送更新给播放器。看电视也不需要重新抓包。

官方接口异常时，HomeCast 继续提供旧缓存。节目覆盖时间已过，就要检查刷新错误。

节目单只说明播出时间。HomeCast 没有时移或回看功能。

## 常见问题

| 现象 | 下一步 |
| --- | --- |
| 订阅返回 403 | 检查 `HOMECAST_ALLOWED_NETWORKS`，以及 `HOMECAST_PUBLIC_URL` / `HOMECAST_ALLOWED_HOSTS` |
| 首次访问返回 503 | 等待首次刷新成功；查看页面错误提示 |
| 有频道，没有节目单 | 单独填 XMLTV，关联到同一来源，再刷新 |
| 页面正常，直播黑屏 | 检查 udpxy、频道权限和客户端格式支持 |
| 电脑能看，电视不能看 | 检查访客网隔离、本地网络权限、DNS、VPN 和 udpxy 连通性 |
| 迁移后仍是旧列表 | 刷新客户端缓存；确认使用 URL 订阅而不是静态文件 |
| 时间相差数小时 | 检查设备时区；XMLTV 已带 `+0800`，通常不用另加 EPG 时差 |
| 多台同时看卡顿 | 检查 udpxy 会话上限、组播链路和运营商并发限制 |

不要把 HomeCast 或 udpxy 端口开放到公网。订阅地址只用于自己的家庭网络。

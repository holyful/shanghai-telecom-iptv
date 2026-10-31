# 设置外部 udpxy

udpxy 把 IPTV 视频转成播放器能访问的 HTTP 地址。

它与 HomeCast 独立运行。HomeCast 的 Compose 不会安装、启动或重启 udpxy。

先完成 [IPTV 网络设置](network.md)。本页的 `192.0.2.1` 和 `br-iptv` 都是示例，必须换成自己的地址和接口。

## 1. 已经能播放？直接沿用

已有 udpxy 正常播放，就跳到第 3 步。记下它的 LAN 地址和端口即可。

已有服务但不能播放时，先看本页下方的检查方法。不要盲目重启，也不要再开第二个实例。

## 2. 首次设置 udpxy

以下适用于尚未运行 udpxy 的 OpenWrt / iStoreOS 软路由。

使用当前固件的软件源安装 `udpxy`。不需要为此更换软件源、升级固件或修改家庭 VLAN。

### 填写配置

先备份已有的 `/etc/config/udpxy`，再编辑对应配置节。不要重复添加相同端口的配置。

```text
config udpxy
    option disabled '0'
    option respawn '1'
    option status '1'
    option bind '192.0.2.1'
    option port '4022'
    option source 'br-iptv'
    option max_clients '4'
```

主要检查这四项：

| 项目 | 填什么 |
| --- | --- |
| `bind` | udpxy 所在主机的家庭 LAN 地址 |
| `port` | HTTP 端口，示例为 4022 |
| `source` | 接收 IPTV 视频的实际接口，例如 `br-iptv` |
| `max_clients` | 同时转发的连接数，示例为 4 |

提高连接数不会增加运营商的频道权限。

### 首次启动

确认端口没有被占用，且没有运行中的 udpxy，再执行：

```bash
/etc/init.d/udpxy enable
/etc/init.d/udpxy start
```

在家庭 LAN 的浏览器中打开 `http://192.0.2.1:4022/status/`，记得替换地址。

**检查结果：** 能看到 udpxy 状态页。这里只证明服务能访问，还没证明视频能播放。

打不开时，展开下方“服务状态检查”。不要反复启动服务。

## 3. 把地址填入 HomeCast

在 Compose 的 `environment` 中填写：

```yaml
HOMECAST_UDPXY_URL: "http://192.0.2.1:4022"
```

填写 udpxy 的实际 LAN 地址和端口，不要加频道路径。

这个值只告诉 HomeCast 去哪里播放，不会修改 udpxy 配置。

`HOMECAST_INTERFACE` 是 HomeCast 获取频道和节目单的接口。udpxy 的 `source` 是接收视频的接口，两处需分别确认。

播放器或 Jellyfin 服务端必须能直接访问 udpxy。仅 HomeCast 能访问还不够。

两项服务都只开放给可信家庭 LAN。HomeCast 的访问限制不会自动保护 udpxy。

## 4. 实际播放一个频道

按 [客户端教程](clients.md) 添加订阅，选一个自己有权限的频道。

**成功标准：** 目标播放器有画面、有声音，并能持续播放。状态页能打开不算播放成功。

打不开频道时，再做下面的限时检查。使用 Jellyfin 时，应从其服务端所在网络检查，不要只在浏览器电脑上测试。

## 限时播放检查

<details>
<summary>无法播放时：检查跳转，并最多接收 10 秒视频</summary>

这会占用一个播放连接。请避开家里正在使用的频道或连接上限。

从自己的 M3U 中取一个完整 HomeCast 播放 URL，替换下面的占位地址。只测试自己有权限的频道。

### Linux / macOS

先看播放请求会跳转到哪里：

```bash
STREAM_URL='http://192.0.2.1:34400/stream/CHANGE_ME'
curl --noproxy '*' --silent --show-error --head --connect-timeout 3 --max-time 5 "$STREAM_URL"
```

应返回 `302`，`Location` 指向自己配置的 udpxy。

再接收最多 10 秒，只计字节，不保存视频：

```bash
curl --noproxy '*' --location --fail --silent --show-error --connect-timeout 3 --max-time 10 --output /dev/null --write-out 'HTTP %{http_code}; received %{size_download} bytes\n' "$STREAM_URL"
```

### Windows PowerShell

第一条 curl 命令查看跳转，第二条接收最多 10 秒：

```powershell
$StreamUrl = 'http://192.0.2.1:34400/stream/CHANGE_ME'
curl.exe --noproxy "*" --silent --show-error --head --connect-timeout 3 --max-time 5 $StreamUrl
curl.exe --noproxy "*" --location --fail --silent --show-error --connect-timeout 3 --max-time 10 --output NUL --write-out "HTTP %{http_code}; received %{size_download} bytes\n" $StreamUrl
```

### 怎么判断结果

| 结果 | 含义 |
| --- | --- |
| 最终 HTTP 200，收到字节大于零 | 这次测试收到数据，还需播放器确认画面和声音 |
| 零字节、连接失败、4xx 或 5xx | 未通过，不能认为可播放 |
| curl 退出码 28 | 到了时间上限；必须同时看 HTTP 状态和接收字节 |

直播不会自己结束，所以 10 秒后超时可能是正常的。**不能只看到退出码 28 就判定成功。**

播放 URL、跳转地址和输出可能暴露家庭信息，分享前请脱敏。

</details>

## 其他检查方法

<details>
<summary>服务状态检查：不会修改配置或重启服务</summary>

在 Linux / OpenWrt 主机上执行，先替换接口名：

```bash
ip -4 addr show dev br-iptv
ip -4 route show
command -v udpxy
ss -lntp
```

看 IPTV 接口是否有地址、udpxy 是否已安装、端口是否在监听。

没有 `ss` 时，可用 `netstat -lntp`。

OpenWrt 还可查看配置和启动状态：

```bash
uci show udpxy
/etc/init.d/udpxy status
/etc/init.d/udpxy enabled
```

未运行或未启用时，命令可能返回非零退出码。

在 LAN 客户端检查状态页：

```bash
curl --noproxy '*' --fail --show-error --connect-timeout 3 --max-time 5 http://192.0.2.1:4022/status/
```

状态页能打开，只说明 HTTP 服务可达。

不要用 `/restart/` 做检查，它会断开现有播放连接。状态页也可能显示家庭地址和正在播放的频道，分享前请脱敏。

接口行为见 [udpxy 官方手册](https://github.com/pcherenkov/udpxy/blob/master/chipmunk/doc/en/udpxy.1)。

</details>

<details>
<summary>配置项与命令参数对照</summary>

| 配置 | 含义 | 命令参数 |
| --- | --- | --- |
| `disabled '0'` | 启用实例；上游示例默认禁用 | 由启动脚本处理 |
| `respawn '1'` | 进程退出后，由系统服务管理器重新拉起 | 由 procd 处理 |
| `status '1'` | 启用客户端统计 | `-S` |
| `bind` | LAN HTTP 监听地址 | `-a` |
| `port` | HTTP 端口 | `-p` |
| `source` | IPTV 视频来源接口 | `-m` |
| `max_clients` | 最大并发连接数 | `-c` |

OpenWrt 的启动脚本会添加 `-T`，让进程保持前台运行，再由 procd 管理。

依据：[OpenWrt 包配置](https://github.com/openwrt/packages/blob/master/net/udpxy/files/udpxy.conf)、[启动脚本](https://github.com/openwrt/packages/blob/master/net/udpxy/files/udpxy.init)。使用前也要核对自己固件的版本。

</details>

<details>
<summary>其他 Linux 主机：前台试运行</summary>

这类部署尚未验证，也必须先接通 IPTV 网络。普通互联网接入不够。

确认已安装 udpxy、端口空闲且没有运行实例后，可在前台试运行：

```bash
udpxy -T -S -a 192.0.2.1 -m br-iptv -p 4022 -c 4
```

参数含义见上表。`-T` 保持前台，关闭进程就会结束这次运行。

确认能播放后，交给主机现有的服务管理器管理。不要和 OpenWrt procd 或其他实例同时运行。

参数说明见 [官方手册](https://github.com/pcherenkov/udpxy/blob/master/chipmunk/doc/en/udpxy.1)。

</details>

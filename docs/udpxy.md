# 外部 udpxy

HomeCast 负责频道与节目单，udpxy 负责把 IPTV 组播转为 HTTP 视频。udpxy 必须独立部署；HomeCast 的 Compose 不安装、启动或重启它。推荐先在已接通 IPTV 的 Linux 软路由上确认 udpxy 可用，再安装 HomeCast。

## 先检查现有服务

已有服务正常播放时，沿用其地址和接口，不要为了安装 HomeCast 重建或盲目重启。以下是 Linux / OpenWrt 上的只读检查；`br-iptv` 和文档地址均须替换为自己的值：

```bash
ip -4 addr show dev br-iptv
ip -4 route show
command -v udpxy
ss -lntp
```

没有 `ss` 的固件可用 `netstat -lntp` 查看监听。OpenWrt 还可读取配置与服务状态：

```bash
uci show udpxy
/etc/init.d/udpxy status
/etc/init.d/udpxy enabled
```

未启用或未运行时，状态命令可能返回非零退出码。先确认已有配置及端口占用，不要启动第二个实例。

从预期的 LAN 播放客户端检查 HTTP：

```bash
curl --noproxy '*' --fail --show-error --connect-timeout 3 --max-time 5 http://192.0.2.1:4022/status/
```

`/status/` 返回服务状态；它可达不等于已收到频道视频。不要把 `/restart/` 当作健康检查，它会断开现有播放连接。状态页可能含家庭地址和正在播放的频道，分享前需脱敏。接口行为见 [udpxy 官方手册](https://github.com/pcherenkov/udpxy/blob/master/chipmunk/doc/en/udpxy.1)。

## 初次配置 OpenWrt

**仅适用于尚未运行 udpxy、且 IPTV 网络已配置好的主机。** 使用当前固件配套的软件源和包管理器安装 `udpxy`；不要为此更换软件源、升级固件或照抄其他家庭的 VLAN / 防火墙规则。已有服务请跳过本节。

先私下备份已有的 `/etc/config/udpxy`，再编辑其中对应的配置节；不要追加多个监听相同端口的实例。最小示例：

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

| UCI 项 | 作用 |
| --- | --- |
| `disabled '0'` | 启用该实例；上游示例默认禁用 |
| `respawn '1'` | 由 procd 在进程退出后重新拉起 |
| `status '1'` | 启用客户端统计，对应 `-S` |
| `bind` | HTTP 监听的 LAN 地址，对应 `-a` |
| `port` | HTTP 端口，对应 `-p` |
| `source` | 接收 IPTV 组播的 Linux 接口，对应 `-m` |
| `max_clients` | 最大并发转发客户端数，对应 `-c`，不是增加运营商授权 |

字段及参数映射已按 [OpenWrt 官方包配置](https://github.com/openwrt/packages/blob/master/net/udpxy/files/udpxy.conf) 和 [启动脚本](https://github.com/openwrt/packages/blob/master/net/udpxy/files/udpxy.init) 核对；固件分支可能有差异。procd 自行添加前台运行参数 `-T`。

替换地址和接口、确认端口空闲后，仅对这个尚未运行的新服务执行首次启用：

```bash
/etc/init.d/udpxy enable
/etc/init.d/udpxy start
```

再执行前面的只读检查。若现有服务需要改配置，应另行安排维护时间，不要自动重启正在使用的服务。

## 其他 Linux 主机

只有同等 IPTV 网络条件才可能工作；本项目没有验证普通 Linux / NAS 部署方案。已安装 udpxy 且确认没有运行实例时，可先在前台启动一次：

```bash
udpxy -T -S -a 192.0.2.1 -m br-iptv -p 4022 -c 4
```

`-T` 保持前台，`-S` 启用统计，`-a` 是 LAN HTTP 监听地址，`-m` 是 IPTV 组播来源接口，`-p` 是 HTTP 端口，`-c` 是并发上限。关闭前台进程会结束这次运行。确认有效后交由该主机现有的服务管理器管理，不要与 OpenWrt procd 或另一个实例同时启动。参数含义见 [官方手册](https://github.com/pcherenkov/udpxy/blob/master/chipmunk/doc/en/udpxy.1)。

## 与 HomeCast 对接

在 HomeCast Compose 中填写外部服务地址：

```yaml
HOMECAST_UDPXY_URL: "http://192.0.2.1:4022"
```

这只是地址，不会配置 udpxy。HomeCast 的 `HOMECAST_INTERFACE` 选择认证/节目单请求接口；udpxy 的 `source` / `-m` 选择组播接口。两项服务独立配置，不能靠修改其中一个自动改变另一个。

HomeCast 返回 302 后，真正接收视频的是播放器或 Jellyfin 服务端，因此它必须直接访问 udpxy。仅让 HomeCast 容器能访问 udpxy 不够。HomeCast 和 udpxy 的端口都只应对可信 LAN 开放；HomeCast 的访问控制不会保护独立的 udpxy。网络检查见 [网络条件](network.md)。

## 限时播放检查

以下测试会短暂建立一个真实播放会话，占用 udpxy 的一个连接；不是纯状态查询。只选自己已获授权的频道，避免影响正在播放的设备。从自己的 M3U 中取一个完整 HomeCast 播放 URL，替换下面占位值；不要把真实地址贴到公共 issue。

Linux / macOS 客户端，先只查看 HomeCast 重定向：

```bash
STREAM_URL='http://192.0.2.1:34400/stream/CHANGE_ME'
curl --noproxy '*' --silent --show-error --head --connect-timeout 3 --max-time 5 "$STREAM_URL"
```

预期为 302，`Location` 指向自己配置的 udpxy。随后限时跟随重定向，只计接收字节，不保存视频：

```bash
curl --noproxy '*' --location --fail --silent --show-error --connect-timeout 3 --max-time 10 --output /dev/null --write-out 'HTTP %{http_code}; received %{size_download} bytes\n' "$STREAM_URL"
```

Windows PowerShell 客户端：

```powershell
$StreamUrl = 'http://192.0.2.1:34400/stream/CHANGE_ME'
curl.exe --noproxy "*" --silent --show-error --head --connect-timeout 3 --max-time 5 $StreamUrl
curl.exe --noproxy "*" --location --fail --silent --show-error --connect-timeout 3 --max-time 10 --output NUL --write-out "HTTP %{http_code}; received %{size_download} bytes\n" $StreamUrl
```

直播不会自然结束，10 秒限时可能产生 curl 退出码 28。**只有最终 HTTP 200 且接收字节大于零，才说明这次检查收到数据**；零字节、连接失败或 4xx/5xx 不能视为成功。该检查仍不能保证编码可解或所有频道有权限，最后应在目标播放器确认画面与声音。Jellyfin 场景尽量从其服务端网络检查，不要只在浏览器电脑上测试。

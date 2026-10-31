# 先接通 IPTV 网络

先把网络接好，再安装 HomeCast。HomeCast 不会替你配置光猫或路由器。

**已有接口能认证、udpxy 能播放，就沿用现有配置。** 不需要按本页重新建网。

推荐使用 **64 位 x86（amd64）Linux 软路由**。
发布镜像只支持这个架构。
其他 Linux 主机需具备同样的 IPTV 网络条件，目前未验证。

这些要求针对部署 HomeCast 的主机。
只有普通互联网接入的 NAS、PC、VPS，不能直接作为部署主机。
电脑、手机等播放设备接普通家庭网络即可。
它们只需能访问 HomeCast 和 udpxy。

## 日常使用的接线

```mermaid
flowchart LR
  ONT[光猫 IPTV 下行口] --> ROUTER[软路由: HomeCast + udpxy]
  ROUTER -->|家庭网络| CLIENT[电脑 / 手机 / 电视 / Apple TV]
```

HomeCast 获取频道和节目单，udpxy 转发电视画面。
光猫哪个口提供 IPTV，以自己家的配置为准。

## 软路由的 IPTV 桥怎么准备

下面以 64 位 x86 OpenWrt / iStoreOS 为例。界面名称可能略有不同。

**本例同时配置 VLAN 51 和 85，再合到一个 `br-iptv` 桥。**

前提是光猫输出带标签的 51 和 85，也就是 tagged 51/85。若光猫已经去标签或做了其他映射，不要直接套用。不确定时先请装维确认。

变更前备份网络、DHCP、防火墙配置。保留本地管理口和恢复办法，安排在家里不用网络时操作。

### 1. 确认连接光猫的网口

本例用 `eth0` 连接光猫。
先换成自己的实际设备名。
家庭播放器继续使用普通 LAN，不需要接 IPTV 专用端口。

不要删除现有 Internet WAN。**不要把整个 WAN 和家庭 `br-lan` 直接合桥。**

### 2. 创建两个 VLAN，再合桥

在“网络 -> 接口 -> 设备”中操作：

1. 添加 802.1Q VLAN 设备。在 `eth0` 上分别建 51 和 85，得到 `eth0.51`、`eth0.85`。
2. 新建桥设备 `br-iptv`，加入 `eth0.51` 和 `eth0.85`。

```text
光猫侧 eth0.51 ----+
                  +---- br-iptv ---- iptv（DHCP 客户端）
光猫侧 eth0.85 ----+        |
                    HomeCast + udpxy
```

**检查结果：** 本例的桥中有两个 VLAN 子接口。
没有完整物理 WAN、`br-lan` 或 Wi-Fi。
已有可用桥不用为匹配本例而删除其他成员。

这个例子把 51 和 85 合在一起，不再隔离。若已有另一条映射或桥接路径，不要再叠加，避免网络环路。

合桥思路见 [王延炯的原文](https://yanjiong.wang/articles/shanghai-telecom-and-asuswrt-merlin-support-iptv)。原文使用梅林固件，命令不能直接在 OpenWrt 执行。

如果设备使用 DSA 或 swconfig，需在对应的交换机或桥 VLAN 页面设置。不要原样照抄上面的设备名。

### 3. 有交换机时，检查沿途端口

光猫直接接软路由时，可跳过这一步。
本节只涉及光猫与软路由之间的 IPTV 链路。
家庭播放器接普通 LAN，不需要配置这两个 VLAN。

需要添加或去除 VLAN 标签时，才需要管理型交换机。普通交换机不能替你拆分 VLAN，也不能保证透明传递标签。

在承载这条 IPTV 链路的管理型交换机上：

1. 创建 VLAN 51 和 85。
2. 将连接光猫、软路由及沿途中继的端口加入两个 VLAN。
   本例设为 tagged，界面通常标为 `T`。
3. 保持原有普通 LAN 的 untagged / PVID 设置。一个 PVID 不能代替两个 VLAN。

**检查结果：** 从光猫到软路由，51 和 85 都能通过。
如果光猫已经去除标签，不能套用本例的 tagged 端口表。

参考 [aRAY 原文及作者补充](https://aray.cn/14234)。其中也提醒了上联口需要加入 VLAN。

### 4. 让软路由自己获取 IPTV 地址

在“网络 -> 接口”新增接口：

| 项目 | 填写 |
| --- | --- |
| 名称 | `iptv` |
| 协议 | **DHCP 客户端** |
| 设备 | `br-iptv`，或自己的实际 IPTV 设备 |

这里是向运营商获取地址的 **DHCP 客户端**。不要在 IPTV 网络上启用家庭 DHCP 服务器，也不要手填家庭 LAN 地址。

**检查结果：** `iptv` 获得 IPv4 地址，家里的普通上网仍正常。

IPTV 路由不能抢走普通上网出口，也不能缺少到认证、节目单服务的路由。有冲突时看下方的进阶说明，不要直接关闭所有默认路由。

### 5. 填入 HomeCast 和 udpxy

HomeCast 的 `HOMECAST_INTERFACE` 填实际设备名，例如 `br-iptv`，不是逻辑接口名 `iptv`。

udpxy 独立设置自己的来源接口 `source`。两处不会自动同步，见 [udpxy 设置](udpxy.md)。

如果认证和组播使用不同设备，分别验证后再填写。

## 完成后检查

1. IPTV 接口有 IPv4，HomeCast 能完成认证并取得节目单。
2. udpxy 能播放频道，不只是状态页能打开。
3. 播放器或 Jellyfin 服务端能直接访问 HomeCast 和 udpxy。
4. HomeCast 只允许可信 LAN 网段，两项服务都没有开放到公网。

HomeCast 容器使用 Linux host 网络，才能访问宿主机的 IPTV 接口。沿用项目 Compose 即可，不需要 `privileged` 或 Docker socket。

监听地址、订阅地址和视频地址的区别见 [三个地址](configuration.md#三个地址)。

## 需要排查时再看

<details>
<summary>路由、DNS 和防火墙</summary>

### 路由和 DNS

不要复制别人的 IPTV 地址或网关。

若 IPTV 和 Internet 都取得默认路由，可把 IPTV 的 metric 设得更大，让它优先级更低。也可以按已确认的运营商网关设置专用路由。

不能只取消 IPTV 默认路由，却不保留到认证和节目单服务的路径。

不要让 IPTV 下发的 DNS 意外覆盖家庭 DNS。相关选项见 [OpenWrt LuCI 接口实现](https://github.com/openwrt/luci/blob/master/modules/luci-mod-network/htdocs/luci-static/resources/view/network/interfaces.js)，无需修改源码。

### 防火墙和组播

IPTV 网络应与家庭管理网络分开。

按实际需要允许 DHCP 应答、IGMP、直播组播和认证/节目单回包。不要把防火墙所有方向都改成 ACCEPT。

已有组播服务正常时，不要再启动第二套 IGMP proxy。

snooping、查询器和硬件卸载要按实际网络检查。不要把全局开关当成通用修复。

</details>

<details>
<summary>只读检查桥和接口</summary>

用 macOS / Linux 终端或 Windows PowerShell，通过 SSH 登录软路由。

换成自己的接口名后执行：

```sh
ip -d link show
ip -4 addr show dev br-iptv
ip -4 route show
ubus call network.interface.iptv status
bridge link show
bridge vlan show
```

重点看三项：VLAN 51/85 是否存在、桥成员是否正确、IPTV 接口是否取得地址。

没有 `bridge` 的旧固件，可用 `brctl show` 查看桥成员。

`bridge vlan show` 只显示桥的 VLAN 过滤信息。查看 802.1Q 子接口还要结合 `ip -d link show`。

这些命令不会修改配置或重启服务。输出含地址和 MAC，对外分享前请脱敏。

账号获取与临时抓包接线见 [账号获取教程](account-discovery.md)。

</details>

<details>
<summary>原文参考与适用范围</summary>

- [aRAY（2022）](https://aray.cn/14234)：OpenWrt 双 VLAN 与交换机端口设置。
- [王延炯（2022）](https://yanjiong.wang/articles/shanghai-telecom-and-asuswrt-merlin-support-iptv)：梅林固件上的双 VLAN 合桥实例。
- [u128393（2019，可选阅读）](https://www.cnblogs.com/u128393/p/11629969.html)：更换光猫后，51/85 组播表现不同的记录。

这些是作者的实测记录，不是电信官方规范。不同光猫、线路和固件可能不同；已有可用网络无需重做。

</details>

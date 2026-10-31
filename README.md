# HomeCast · 上海电信 IPTV

**不用电信机顶盒，在自己的家庭网络里观看 IPTV。**

配置好后，可以用电脑、手机、平板、电视或 Apple TV 观看。
使用兼容的 IPTV 播放器，也可以通过 Jellyfin 接入。
HomeCast 自动更新频道和节目单，提供固定的订阅链接。

**仅适用于已开通 IPTV 的上海电信用户。**
使用自己的 IPTV 账号，不提供公共电视源。

## 部署前置条件

推荐装在 **64 位 x86（amd64）软路由**上。
例如运行 OpenWrt / iStoreOS 的小主机。
软路由需要安装 Docker 和 Docker Compose。

先准备好这三项：

| 准备什么 | 怎么完成 |
| --- | --- |
| IPTV 网络 | 配好 VLAN **51 和 85**，接入 IPTV 桥。见 [网络设置](docs/network.md) |
| IPTV 账号、SN、MAC | 不知道账号很正常，按 [账号获取教程](docs/account-discovery.md) 操作 |
| udpxy | 它负责转发电视画面，需要单独安装。见 [udpxy 设置](docs/udpxy.md) |

日常接线：**光猫 → 软路由（HomeCast + udpxy）→ 家庭播放器**。
电脑、手机、电视等播放设备接普通家庭网络。

VLAN 配置参考 [aRAY 的教程](https://aray.cn/14234) 和 [双 VLAN 合桥实例](https://yanjiong.wang/articles/shanghai-telecom-and-asuswrt-merlin-support-iptv)。
本文按光猫提供带标签的 51/85 配置。已有可用网络不用重配。

上面的网络要求针对 **部署 HomeCast 的主机**。
只接普通网络的 NAS、电脑或云服务器，不能直接当部署主机。
用来观看的设备只需能访问家里的 HomeCast 和 udpxy。
其他部署方式未验证，详见 [网络说明](docs/network.md)。

## 快速开始

### 1. 填写配置

在软路由上新建一个部署目录，将 [compose.yaml](compose.yaml) 放进去。
使用的是已打包镜像，不需要下载源码或自己构建。

打开文件，只修改 `environment` 中的值。
先填抓包取得的三项身份，再填家庭网络信息：

| 配置项 | 填什么 |
| --- | --- |
| `HOMECAST_USER_ID` | IPTV 账号 |
| `HOMECAST_PROTOCOL_SN` | 登录请求中的 SN，不一定是机身贴纸上的号码 |
| `HOMECAST_MAC` | 机顶盒的业务 MAC |
| `HOMECAST_BIND_ADDRESS` | 软路由的家庭内网 IP，不带端口 |
| `HOMECAST_ALLOWED_NETWORKS` | 家庭网段，例如 `192.0.2.0/24` |
| `HOMECAST_PUBLIC_URL` | HomeCast 地址，例如 `http://192.0.2.1:34400` |
| `HOMECAST_UDPXY_URL` | udpxy 地址，例如 `http://192.0.2.1:4022` |
| `HOMECAST_INTERFACE` | 前面配置的 IPTV 网络设备，通常为 `br-iptv` |

**示例中的 `192.0.2.1` 和网段必须换成自己的。**
`PUBLIC_URL` 也是内网地址，不是让你开放公网。
其他项目先保持默认。[填写示例与完整参数](docs/configuration.md)

### 2. 启动

在软路由 SSH 中进入部署目录，执行：

```bash
chmod 600 compose.yaml
docker compose config --quiet
docker compose pull homecast
docker compose up -d --no-build homecast
```

浏览器打开刚填的 `HOMECAST_PUBLIC_URL`。
等待首次更新完成。页面出现频道和节目单，就可以接播放器了。

### 3. 接入播放器

点击页面的 **订阅链接**，复制两个地址：

| HomeCast 链接 | 填到播放器哪里 |
| --- | --- |
| M3U | 频道列表 / 播放列表 |
| XMLTV | EPG / 电视节目单 |

选择 **URL 订阅**，不用下载文件。
保存后更新频道，打开一个频道试播。
具体菜单见 [Apple TV、Jellyfin、Kodi、VLC 接入说明](docs/clients.md)。

默认每天 05:00 更新频道和节目单，可在页面调整。
看电视时不需要重新抓包。

## 遇到问题

| 情况 | 看这里 |
| --- | --- |
| 不知道账号，或抓包找不到字段 | [账号获取教程](docs/account-discovery.md) |
| 页面有频道，但播放黑屏 | [检查 udpxy](docs/udpxy.md#限时播放检查) |
| 容器启动失败，或需要升级 | [配置与维护](docs/configuration.md) |
| 想自己构建镜像 | [开发文档](docs/development.md) |

![HomeCast 频道与节目单页面](docs/images/homecast-desktop.png)

## 使用提醒

仅在可信家庭网络内使用。不要把 HomeCast 或 udpxy 开放到公网。
不要公开填写后的配置和抓包文件。

本项目非电信官方产品。只提供直播接入，不提供回看、录制或转码。
采用 MIT 许可。更多边界见 [安全说明](SECURITY.md)。

协议调查参考 [pcg-iptv](https://github.com/pcg562240/pcg-iptv)，未打包其实现。
Lucide 图标及许可证随包提供。

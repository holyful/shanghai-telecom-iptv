# 配置与维护

HomeCast 仅从环境变量读取部署配置。日常安装只编辑 [compose.yaml](../compose.yaml) 的 `environment`，没有额外应用配置文件。先完成 [部署前置条件](../README.md#部署前置条件)。

## 三个地址

| 变量 | 作用 | 示例 |
| --- | --- | --- |
| `HOMECAST_BIND_ADDRESS` | HomeCast 在本机哪个 LAN IPv4 上监听；不含协议、端口，不是 IPTV 接口地址 | `192.0.2.1` |
| `HOMECAST_PUBLIC_URL` | 客户端使用的 HomeCast 统一地址；页面复制的订阅 URL 和 M3U 内播放 URL 都以它为基础 | `http://192.0.2.1:34400` |
| `HOMECAST_UDPXY_URL` | 独立 udpxy 服务的地址；HomeCast 将播放请求 302 重定向到这里 | `http://192.0.2.1:4022` |

`PUBLIC` 指客户端可见地址，**不是公网地址**。两个 URL 都应包含协议、LAN 主机名或地址及端口，不附加路径、账号密码、查询参数。不要把 M3U 的完整路径填进来。默认使用 HTTP；把字符串改为 HTTPS 并不会为服务启用 TLS。

不设置时，`HOMECAST_PUBLIC_URL` 默认由监听地址与 `HOMECAST_PORT` 组成，`HOMECAST_UDPXY_URL` 默认由监听地址与端口 4022 组成。Compose 将两项显式列出，便于检查。修改监听地址或端口时，也要同步检查这两个 URL；显式值不会自动跟随变化。udpxy 可在另一台已接通 IPTV 的主机上独立运行。

可以把订阅地址设为 `http://router.local:34400`，但必须先确认所有播放器及 Jellyfin 服务端都能解析并访问它。浏览器能访问不代表 Jellyfin 容器也能访问。`HOMECAST_ALLOWED_HOSTS` 仅放行额外 HTTP Host 别名，不负责 DNS、监听或改变订阅地址；配置的订阅主机名本身会加入 Host 允许列表。

## 环境变量

所有值在 YAML 中按字符串填写并加引号。示例 IP、网段、`CHANGE_ME` 不是可用部署配置。身份来自自己的机顶盒，见 [账号发现](account-discovery.md)。

| 变量 | 必填 / 默认 | 含义 |
| --- | --- | --- |
| `HOMECAST_USER_ID` | 必填 | IPTV 协议 UserID，不一定是宽带账号 |
| `HOMECAST_PROTOCOL_SN` | 必填 | 协议登录 SN，不一定等于机身贴纸 S/N |
| `HOMECAST_MAC` | 必填 | 协议 MAC，六组冒号分隔的十六进制数 |
| `HOMECAST_BIND_ADDRESS` | 必填 | 本机特定 LAN IPv4，不能监听所有接口 |
| `HOMECAST_ALLOWED_NETWORKS` | 必填 | 可信 IPv4 CIDR，多个用逗号分隔；须包含监听地址所在网段，不允许全网 |
| `HOMECAST_PUBLIC_URL` | 默认由监听地址和端口派生 | 统一订阅地址，Compose 中显式填写 |
| `HOMECAST_UDPXY_URL` | 默认监听地址的 4022 端口 | 客户端可直达的外部 udpxy 地址，Compose 中显式填写 |
| `HOMECAST_INTERFACE` | `br-iptv` | 实际 Linux IPTV 网络设备名，须按主机调整，不是 UCI 逻辑网络名 |
| `HOMECAST_PORT` | `34400` | HomeCast 监听端口，1 至 65535；host 网络没有端口映射 |
| `HOMECAST_ALLOWED_HOSTS` | 空 | 额外主机名，多个用逗号分隔，不含协议、端口或路径 |
| `HOMECAST_REFRESH_TIME` | `05:00` | 上海时区每日更新时间，格式 HH:MM，显式设置会锁定页面字段 |
| `HOMECAST_AUTO_REFRESH` | `true` | 自动更新开关，建议填写 `"true"` 或 `"false"`，显式设置会锁定页面字段 |
| `HOMECAST_MIN_CHANNELS` | `80` | 拒绝异常小频道列表的下限，1 至 10000，按自己的订阅调整 |
| `HOMECAST_TUNER_COUNT` | `4` | 设备发现元数据中的调谐器数量，1 至 128；不会调整 udpxy 并发限制或增加频道权限 |
| `HOMECAST_AUTH_HOST` | 内置上海电信入口 | 认证主机与端口，不带协议；仅在确认当地入口不同后调整 |
| `HOMECAST_DATA_DIR` | `/data` | 持久化状态目录；使用本仓库 Compose 时保持默认 |
| `HOMECAST_DEVICE_ID` | `12345678` | 设备发现元数据标识，不是机顶盒 SN |

未知的 `HOMECAST_*` 变量、缺少必填值、占位值或错误格式会导致启动失败，不会静默忽略。具体校验以 [配置实现](../iptv_lan/config.py) 为准。不要把空字符串当成“使用默认值”；不需要的可选变量应整行删除或注释。

## 编辑与应用

在独立的私有部署目录中编辑，避免直接将已填写的 Compose 留在准备提交的源码工作区。

Linux / macOS 编辑端：

```bash
vi compose.yaml
chmod 600 compose.yaml
```

Windows PowerShell 编辑端：

```powershell
notepad.exe .\compose.yaml
```

Windows 文件也应仅允许本人和管理员读取；通过受控方式传到 Linux 部署主机。macOS / Windows 的编辑支持不代表 Docker Desktop 已具备 IPTV 网络条件。使用 UTF-8 文本和空格缩进。

Compose 会处理 `$` 插值；身份值含字面量 `$` 时，在 Compose 中写成 `$$`，不能仅靠 YAML 引号阻止插值。不要将真实身份放进命令行参数或公开截图。此行为见 [Docker Compose 插值规则](https://docs.docker.com/reference/compose-file/interpolation/)。

在 Linux 部署目录检查并应用修改：

```bash
docker compose config --quiet
docker compose up -d --no-build homecast
docker compose ps
docker compose logs --tail 50 homecast
```

只执行 `restart` 不会把修改后的环境变量带入已有容器；需用 `up` 重新创建。不要公开完整 `docker compose config` 或 `docker inspect` 输出，其中可能包含身份。Compose 保存的是明文，环境变量也不加密；拥有 Docker 管理权限的人能够读取。

## 调度设置

没有显式调度变量时，默认上海时间每天 05:00 自动更新；页面保存的设置会持久化到数据卷，并在后续启动继续使用。

显式设置 `HOMECAST_REFRESH_TIME` 或 `HOMECAST_AUTO_REFRESH` 时，该项覆盖页面已保存值，并锁定对应页面字段。两项独立管理，例如只固定更新时间时，页面仍可切换自动更新。关闭自动更新后可手动刷新；无缓存的首次启动也不会自动抓取。

想交回页面管理，删除对应环境变量并重新创建容器；随后以数据卷里保存的设置为准，没有保存值时才用默认值。不要依赖它自动恢复某次历史设置。

## 数据与备份

默认 Compose 只有一个命名卷 `data`，挂载到 `/data`，保存频道/EPG 缓存、状态和页面调度设置。默认项目名为 `homecast`，Docker 卷名为 `homecast_data`。不要随意更换项目名或使用 `down -v`，否则可能切换到空卷或删除数据。

升级前，在私有位置保存填写后的 Compose 和完整数据目录。在 Linux 主机上安排短暂的 HomeCast 停机，向一个新的备份目录复制数据：

```bash
mkdir -p backup
docker compose stop homecast
docker compose cp homecast:/data ./backup/data
docker compose up -d --no-build homecast
```

确认复制成功后再升级；若复制失败，先启动 HomeCast 恢复服务，再排查备份。此过程不操作 udpxy。备份含私有数据，不要提交或作为 issue 附件上传。恢复时使用匹配版本和完整备份，避免仅覆盖部分缓存文件。

Jellyfin 专用导出与 Apple TV 等终端使用的通用导出分开；设置方法见 [客户端说明](clients.md)。

## 镜像升级

使用已确认公开发布的固定版本。修改 Compose 中的 `image` 标签后执行：

```bash
docker compose pull homecast
docker compose up -d --no-build homecast
docker compose ps
```

检查页面最新成功时间、频道、节目单与实际播放。镜像升级不替代数据备份，也不应重启外部 udpxy。需要自行构建时，使用独立的 [源码构建流程](development.md)，不要给默认 Compose 添加 `build`。

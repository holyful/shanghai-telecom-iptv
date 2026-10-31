# 配置与维护

日常安装只需编辑 [compose.yaml](../compose.yaml) 的 `environment`。
不需要另建应用配置文件。
还没准备网络和账号？先看 [安装前的准备](../README.md#部署前置条件)。

## 三个地址

假设软路由的内网 IP 是 `192.0.2.1`。
HomeCast 和 udpxy 都运行在这台软路由上：

```yaml
HOMECAST_BIND_ADDRESS: "192.0.2.1"
HOMECAST_PUBLIC_URL: "http://192.0.2.1:34400"
HOMECAST_UDPXY_URL: "http://192.0.2.1:4022"
```

**这是示例地址，必须换成自己的。**

| 配置 | 简单理解 |
| --- | --- |
| `BIND_ADDRESS` | HomeCast 使用本机哪个内网 IP |
| `PUBLIC_URL` | 你和播放器从哪个地址访问 HomeCast |
| `UDPXY_URL` | 播放器去哪里接收电视画面 |

后两个地址要带 `http://` 和端口。
不要填 M3U 的完整路径。
`PUBLIC` 不代表公网，仍填家庭内网地址。

<details>
<summary>使用域名、不同端口或另一台 udpxy 主机</summary>

`PUBLIC_URL` 决定页面复制的订阅地址，也决定 M3U 中的播放地址。
显式填写后，它不会跟随 `BIND_ADDRESS` 自动变化。
修改 IP 或端口时，请一起检查这三个值。

可以使用 `http://router.local:34400` 这样的内网域名。
先确认电视和 Jellyfin 服务端也能访问它。
浏览器电脑能访问，不代表其他设备都能访问。

`HOMECAST_ALLOWED_HOSTS` 用于允许额外域名。
它不会帮你设置 DNS，也不会改变订阅地址。
`PUBLIC_URL` 中的主机名会自动获准使用。

udpxy 可以运行在另一台已接通 IPTV 的主机上。
将 `UDPXY_URL` 改为那台主机的地址即可。
播放器必须能直接访问它。

地址不能包含账号密码、路径、查询参数或 `#` 片段。
把 `http://` 改成 `https://` 不会自动启用加密服务。

</details>

## 怎么填写

保留 YAML 缩进，所有值都用引号包住。
将 `CHANGE_ME`、示例 IP 和示例网段换成自己的。
不需要的可选参数保持注释，不要填写空字符串。

账号、SN、MAC 从 [账号教程](account-discovery.md) 获取。
IPTV 设备名从软路由网络设置中查看。
例如 `br-iptv`，不是普通上网的 WAN，也不是逻辑接口名 `iptv`。

网段示例：家庭网络是 `192.0.2.0/24`，就填写这个值。
它必须包含 `BIND_ADDRESS`。
不确定网段时，查看软路由的 LAN 设置，不要写成允许所有地址。

<details>
<summary>在电脑上编辑配置</summary>

Linux / macOS：

```bash
vi compose.yaml
chmod 600 compose.yaml
```

Windows PowerShell：

```powershell
notepad.exe .\compose.yaml
```

文件使用 UTF-8 和空格缩进。
Windows 上也应限制为本人和管理员可读。
编辑后通过 SSH / SFTP 传到软路由。
在电脑上编辑，不代表 Docker Desktop 能接入 IPTV 网络。

配置值若包含字面量 `$`，在 Compose 中写成 `$$`。
仅加引号不能阻止 Compose 处理它。
见 [Docker Compose 插值规则](https://docs.docker.com/reference/compose-file/interpolation/)。

</details>

## 修改后怎么生效

在软路由的部署目录执行：

```bash
docker compose config --quiet
docker compose up -d --no-build homecast
docker compose ps
```

只执行 `restart` 不会更新容器里的环境变量。
应使用上面的 `up` 命令。

启动失败时查看最近日志：

```bash
docker compose logs --tail 50 homecast
```

常见原因是漏填参数、留着占位值，或拼错变量名。
不要公开完整配置或 `docker inspect` 输出，里面可能有账号。

## 调度设置

默认每天上海时间 05:00 更新。
一般直接在 HomeCast 页面调整即可，设置会保存。

<details>
<summary>用环境变量固定更新时间</summary>

取消下面两行的注释，即可由 Compose 管理：

```yaml
HOMECAST_REFRESH_TIME: "05:00"
HOMECAST_AUTO_REFRESH: "true"
```

显式填写的选项会锁定页面中对应的控件。
只填一项，就只锁定那一项。
关闭自动更新后，首次启动也不会自动获取频道。
仍可点击页面的“立即更新”。

想恢复页面管理，就删除对应变量，再执行 `up`。
之后使用数据卷里保存的设置；没有保存值才使用默认值。

</details>

## 数据与备份

频道、节目单和页面设置保存在 `/data` 数据卷。
默认卷名是 `homecast_data`。
**不要执行 `docker compose down -v`，它会删除数据。**
也不要随意更改 Compose 项目名。

升级前保留两样东西：填写后的 `compose.yaml` 和完整 `/data`。

<details>
<summary>备份命令，会短暂停止 HomeCast</summary>

在部署目录操作。每次使用一个新的备份目录：

```bash
mkdir -p backup
docker compose stop homecast
docker compose cp homecast:/data ./backup/data
docker compose up -d --no-build homecast
```

已有 `backup/data` 时，先改用另一个备份目录。
确认复制成功后再升级。
复制失败也应先启动 HomeCast，恢复服务后再排查。
这些命令不操作 udpxy。

备份含私有信息，不要上传到公开仓库或 issue。
恢复时使用匹配版本和完整备份。

</details>

## 镜像升级

先备份，再将 Compose 的 `image` 改成 [已发布版本](https://github.com/holyful/shanghai-telecom-iptv/releases)。
然后执行：

```bash
docker compose pull homecast
docker compose up -d --no-build homecast
docker compose ps
```

打开页面，检查频道、节目单和更新时间。
再实际播放一个频道。
不需要重启 udpxy。

## 完整参数表

新安装只需填写 README 中的八项。
其他参数按需查看：

<details>
<summary>展开全部 HOMECAST_* 参数</summary>

| 变量 | 必填 / 默认 | 含义 |
| --- | --- | --- |
| `HOMECAST_USER_ID` | 必填 | IPTV UserID |
| `HOMECAST_PROTOCOL_SN` | 必填 | 登录请求中的 SN |
| `HOMECAST_MAC` | 必填 | 六组冒号分隔的业务 MAC |
| `HOMECAST_BIND_ADDRESS` | 必填 | 本机特定 LAN IPv4 |
| `HOMECAST_ALLOWED_NETWORKS` | 必填 | 可信 IPv4 网段；多个用逗号分隔 |
| `HOMECAST_PUBLIC_URL` | 监听地址和端口 | HomeCast 的统一访问地址 |
| `HOMECAST_UDPXY_URL` | 监听地址的 4022 端口 | 外部 udpxy 地址 |
| `HOMECAST_INTERFACE` | `br-iptv` | 本机 IPTV 网络设备名 |
| `HOMECAST_PORT` | `34400` | 监听端口，1 至 65535 |
| `HOMECAST_ALLOWED_HOSTS` | 空 | 额外域名；多个用逗号分隔 |
| `HOMECAST_REFRESH_TIME` | `05:00` | 上海时间；填写后锁定页面选项 |
| `HOMECAST_AUTO_REFRESH` | `true` | 自动更新；填写后锁定页面选项 |
| `HOMECAST_MIN_CHANNELS` | `80` | 有效频道数下限，1 至 10000 |
| `HOMECAST_TUNER_COUNT` | `4` | 设备发现信息中的数量，1 至 128 |
| `HOMECAST_AUTH_HOST` | 内置上海电信入口 | 认证主机和端口，不带协议 |
| `HOMECAST_DATA_DIR` | `/data` | 数据目录；默认 Compose 不用改 |
| `HOMECAST_DEVICE_ID` | `12345678` | 设备发现标识，不是机顶盒 SN |
| `HOMECAST_LEGACY_FILE` | 不设置 | 已有频道标识映射文件的路径 |

`TUNER_COUNT` 不会增加 udpxy 或运营商的并发上限。
`ALLOWED_HOSTS` 不带协议、端口或路径。
未填写两个 URL 时，才使用表中的默认规则。
格式校验见 [配置实现](../iptv_lan/config.py)。

已有频道标识映射时，保留同一份文件。
例如放入 `/data/legacy.json`，并设置 `HOMECAST_LEGACY_FILE` 指向它。
漏配路径会改变默认频道 ID，旧播放地址可能失效。
新安装不需要这一项。

</details>

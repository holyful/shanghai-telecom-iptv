# 获取 IPTV 账号

仅用于自己已开通的上海电信 IPTV。
先找出机顶盒登录时使用的信息，再填写 HomeCast 配置。

先查看机顶盒的网络或业务信息页，也可以询问运营商。已经拿到完整字段，可以直接看第 5 步。

**宽带账号、手机号、机身贴纸 S/N，不一定是 IPTV 登录使用的账号和协议 SN。**

**机顶盒只在获取账号时临时接入。**
取得信息后即可断开，不是 HomeCast 日常运行的依赖。
已经有完整信息，就不需要再接机顶盒抓包。

下面推荐在软路由的 IPTV 桥上抓包。

只抓自己的设备。不要公开抓包文件、登录地址、账号或 token，也不要上传到在线解析网站。

## 1. 确认接口和机顶盒 MAC

抓包时临时使用这条接线，先确认机顶盒能正常播放：

```text
光猫 -> 软路由 IPTV 桥 -> 自己的机顶盒
```

接线还没通，先完成 [网络准备](network.md)。
下面的抓包命令不会修改网络配置。

<details>
<summary>机顶盒还没接在软路由后面，怎么临时接？</summary>

已有可用接线就沿用，不必重配。
也可用文末的端口镜像方法，观察光猫旁的机顶盒。

要临时通过软路由接入，可按下列示例规划。
前提是这条链路使用带标签的 VLAN 51 和 85。
先备份配置，确认没有另一条桥接路径。

假设光猫接 `eth0`，临时机顶盒口为 `eth1`：

```text
光猫侧 eth0.51 ----+                 +---- eth1.51 临时机顶盒侧
                  +---- br-iptv ----+
光猫侧 eth0.85 ----+                 +---- eth1.85 临时机顶盒侧
```

在临时下联口创建 `.51` 和 `.85`，接入已有 IPTV 桥。
网口名要换成自己的，不要把整个 WAN 和家庭 LAN 直接合桥。
已有映射或桥接路径时不要叠加，避免环路。

经过管理型交换机时，上联和临时机顶盒链路都要放行 51/85。
本例保留 tagged 标签；要求 untagged 的出口要另行适配。

部分机顶盒还需要普通 LAN 和 DHCP Option 125 才能启动。
这些只用于机顶盒引导，不是 HomeCast 配置。
参考 [aRAY 的接线与引导教程](https://aray.cn/14234)。
参数以自己的线路为准，不要强加给全家设备。

抓包并取回文件后，可拔掉机顶盒。
保留软路由到光猫的 IPTV 网络，不要删除运行服务所需的桥。

</details>

准备好软路由的 root 管理权限、路由器上的 `tcpdump`，以及电脑上的 Wireshark。

用 SSH 登录软路由，查看可抓包的接口：

```bash
tcpdump -D
```

选择机顶盒流量实际经过的 IPTV 桥或物理接口。后文的 `YOUR_CAPTURE_INTERFACE` 要换成这个名称。

在机顶盒网络页确认有线 MAC。后文的 `02:00:00:00:00:01` 也要换成它。

贴纸可能有多个 MAC。可以用交换机 MAC 表或 DHCP 记录核对，不要填电脑或软路由的 MAC。

**成功检查：** 机顶盒能播放，你已记下观察接口和机顶盒 MAC。

## 2. 抓一次开机认证

先关闭机顶盒。下面的命令在**软路由的 root 管理 shell** 中运行，不是在电脑终端本地运行。

替换接口和 MAC 后执行：

```bash
umask 077
mkdir -p /root/iptv-private
chmod 700 /root/iptv-private
timeout 120 tcpdump -i YOUR_CAPTURE_INTERFACE -s 0 -U -c 10000 \
  -w - 'ether host 02:00:00:00:00:01' > /root/iptv-private/bootstrap.pcap
```

看到 `listening on` 后，再打开机顶盒。

命令最多运行 120 秒，或抓取 10000 个包。哪个先达到，就先停止。

超时退出不等于抓包失败。仍要检查包数和第 4 步的登录内容。

出现首页并正常播放后，也可以提前按 `Ctrl+C`。不要等登录完成后才开始抓包。

`>` 不能省略。它让 root shell 先打开私有文件，再接收 tcpdump 输出。无需关闭 tcpdump 的降权保护。

提示没有 `timeout` 时，使用文末的 [备用方法](#备用方法)。

**成功检查：** 退出时的 `packets captured` 数量大于零。第 4 步还要确认其中有登录请求，不能只看包数。

## 3. 把文件取回电脑

下面的命令在**电脑**上运行。将 `ROUTER_LAN_IP` 换成软路由的 LAN 地址。

macOS / Linux：

```bash
umask 077
mkdir -p "$HOME/iptv-private"
chmod 700 "$HOME/iptv-private"
scp root@ROUTER_LAN_IP:/root/iptv-private/bootstrap.pcap "$HOME/iptv-private/"
```

Windows PowerShell，需要先安装 OpenSSH 客户端：

```powershell
New-Item -ItemType Directory -Force "$HOME\iptv-private"
scp root@ROUTER_LAN_IP:/root/iptv-private/bootstrap.pcap "$HOME\iptv-private\bootstrap.pcap"
```

电脑上的目录也只应让自己和管理员访问。不要放到共享目录或公开同步目录。

**成功检查：** 电脑上有 `bootstrap.pcap`，Wireshark 能打开它。

## 4. 在 Wireshark 找登录字段

1. 打开 `bootstrap.pcap`。
2. 输入显示过滤器 `eth.addr == 02:00:00:00:00:01`，将 MAC 换成自己的值。确认是这台机顶盒的流量。
3. 将过滤器改为 `http.request`，查看 HTTP 请求。
4. 再用 `http.request.uri contains "4kLogAuth.do"` 查找已验证的登录入口。
5. 选中请求，展开 **Hypertext Transfer Protocol**。查看 URI、查询参数和 `Host`。
6. 从同一请求中记下 `UserID`、`SN`，以及认证主机和端口。

需要看完整请求时，右键选择 **Follow / TCP Stream（追踪 TCP 流）**，以 ASCII 或 UTF-8 查看。

下面是虚构示例，不能用来认证：

```http
GET /iptv3a/4kLogAuth.do?UserID=example%40etv2&Action=Login&SN=EXAMPLE1234 HTTP/1.1
Host: 192.0.2.2:7001
```

`%40` 解码后是 `@`，所以上例的 UserID 是 `example@etv2`。不要把整条 URI 填成账号。

SN 要保留原字符串，包括前导零。不要用贴纸 S/N 替代登录请求中的 SN。

这个请求没有 MAC。用以太网源 MAC 与机顶盒网络页核对。两者不一致时先查明原因，不要猜。

找不到 HTTP 或登录入口时，展开文末的“HTTP 请求找不到”一节。

**只有 TLS 加密流量时，这套方法不能读出账号。** 不要尝试重放加密数据。请回到设备管理页或运营商支持渠道确认。

**成功检查：** 已取得同一设备、同一次成功登录的 UserID、协议 SN、认证地址，并核对了 MAC。

## 5. 填入 HomeCast 并验证

编辑私有部署目录中 `compose.yaml` 的 `environment`。不要把填好的文件提交到公开仓库。

| 找到的内容 | 填入的变量 | 上例对应值 |
| --- | --- | --- |
| 登录参数 `UserID` | `HOMECAST_USER_ID` | `example@etv2` |
| 登录参数 `SN` | `HOMECAST_PROTOCOL_SN` | `EXAMPLE1234` |
| 已核对的机顶盒 MAC | `HOMECAST_MAC` | 需自行核对，格式为六组冒号分隔的十六进制数 |
| 初始认证 `Host` | `HOMECAST_AUTH_HOST` | `192.0.2.2:7001`，不加协议或路径 |
| 部署主机的 IPTV 设备名 | `HOMECAST_INTERFACE` | 来自本机网络配置，不是抓到的账号字段 |

抓包接口不一定就是 `HOMECAST_INTERFACE`。后者必须是 HomeCast 主机实际用于访问 IPTV 的设备。

**不要把临时 token 当配置。** `UserToken`、`JSESSIONID`、BIMS token、`encrytoken` 和抓到的 `authenticator` 都不用填写。

HomeCast 会用自己的身份重新认证，不是反复重放旧抓包。

LAN 地址、允许网段和接口设置见 [配置指南](configuration.md)。`HOMECAST_PUBLIC_URL` 是播放器访问 HomeCast 的地址，不是运营商认证地址。

填好后回到 [快速开始](../README.md#快速开始) 启动服务。

**成功检查：**

1. 页面显示真实频道、节目单和最近成功时间。
2. M3U 和 XMLTV 两条订阅都能读取。
3. 客户端能播放至少一个已订阅频道。
4. 再次刷新也能成功，不需要重新抓包。

**断开机顶盒后，再做一次刷新和播放检查。**
之后由 HomeCast 自己认证、更新节目单，udpxy 负责视频。
日常看电视不需要让机顶盒开机或联网。

只有列表、没有画面时，先查 [外部 udpxy](udpxy.md)。频道在列表中，不代表账号有全部频道的权限。

运营商分配的 IPTV 地址变化时，HomeCast 会读取接口当前 IPv4。仅地址变化不需要重抓身份。

## 备用方法

<details>
<summary>软路由抓不到包：改用端口镜像</summary>

硬件交换或卸载可能让路由器看不到经过的流量。先核对接口和 MAC，不要直接关闭全家的硬件加速。

已有管理型交换机时，可以使用端口镜像：

1. 将机顶盒端口的双向流量镜像到一个专用端口。
2. 把电脑的有线网卡接到这个镜像端口。
3. 在 Wireshark 选择该网卡，设置捕获过滤器 `ether host 02:00:00:00:00:01`。替换 MAC。
4. 打开“捕获 -> 选项”的 Options 页，设置自动停止：120 秒或 10000 个包，先达到即停止。
5. 先开始抓包，再开机顶盒。完成后保存 PCAP，从第 4 步继续。

选项位置见 [Wireshark 捕获选项说明](https://www.wireshark.org/docs/wsug_html_chunked/ChCapCaptureOptions.html)。

普通交换机旁边插一台电脑，通常看不到机顶盒的单播登录流量。镜像端口不要接回家庭网络，以免成环。

专用网络 TAP 也可作为观察点，不必为此同时购买多种设备。

不要将 tcpdump 改成 `-i any` 后照搬以太网 MAC 过滤。它可能使用不同的链路格式。

</details>

<details>
<summary>路由器没有 timeout</summary>

在软路由的 root 管理 shell 中执行。仍须替换接口和 MAC：

```bash
umask 077
mkdir -p /root/iptv-private
chmod 700 /root/iptv-private
tcpdump -i YOUR_CAPTURE_INTERFACE -s 0 -U -c 10000 \
  -w - 'ether host 02:00:00:00:00:01' > /root/iptv-private/bootstrap.pcap
```

看到 `listening on` 后开机顶盒。正常播放后，或达到约 120 秒时，手动按 `Ctrl+C`。

10000 个包只是包数上限，不是时间上限。这个方法不能无人值守。

</details>

<details>
<summary>HTTP 请求找不到</summary>

先确认 PCAP 有机顶盒与服务器的双向 TCP 流量。只有 UDP 视频时，可能抓得太晚，或提前达到包数上限。

非标准端口可能未被识别成 HTTP。确认内容是明文 HTTP 后，选择 **Analyze / Decode As（分析 / 解码为）**，将对应 TCP 端口指定为 HTTP。

再用 `http.request` 查看请求。找不到 `4kLogAuth.do` 时，在同一次开机的 TCP 流中搜索 `UserID`、`SN` 或 `ottauth`。

请求可能分成多个包。使用 **Follow / TCP Stream** 查看重组内容，不要只读一个包。

这些名称只是已验证协议的线索，不保证适用于所有固件。Decode As 不会解密 TLS。

</details>

## 仍然卡住时

| 现象 | 下一步 |
| --- | --- |
| 没有抓到包 | 核对接口、MAC 和观察位置；必要时用端口镜像 |
| 有 UserID，没有 SN | 查同一次登录的完整请求，不要用贴纸 S/N 凑数 |
| 身份已填，认证失败 | 查 IPTV IPv4、认证服务连通性、协议 SN、MAC 和系统时间 |
| 有频道，不能播放 | 查客户端到 udpxy 的连通性和频道权限 |

求助时提供设备型号、固件版本和出错步骤即可。不要附上原始 PCAP、完整登录 URI、身份、token 或 cookie。

验证后删除不需要的临时抓包。确需保留时，加密保存并限制访问。

## 工具参考

- [Wireshark：追踪与重组协议流](https://www.wireshark.org/docs/wsug_html_chunked/ChAdvFollowStreamSection.html)
- [Wireshark：HTTP 过滤器字段](https://www.wireshark.org/docs/dfref/h/http.html)
- [Wireshark：Decode As](https://www.wireshark.org/docs/wsug_html_chunked/ChAdvDecodeAs.html)
- [tcpdump 官方手册源码](https://github.com/the-tcpdump-group/tcpdump/blob/master/tcpdump.1.in)

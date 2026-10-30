# 开发与源码构建

普通部署使用预构建镜像和单份 [compose.yaml](../compose.yaml)，见 [快速开始](../README.md#快速开始)。本页仅用于开发或主动选择源码构建的情况，不改变 Linux IPTV 网络前置条件。

## 可选源码构建

取得完整源码，在仓库根目录按 [配置指南](configuration.md) 填写私有运行环境。不要提交填写后的 Compose。

```bash
docker compose -f compose.yaml -f compose.build.yaml config --quiet
docker compose -f compose.yaml -f compose.build.yaml up -d --build --pull never homecast
```

[compose.build.yaml](../compose.build.yaml) 只添加构建上下文，并将应用镜像切换为 `homecast-shanghai:local`，不会拉取同名应用镜像。Dockerfile 的基础镜像及构建依赖仍需可获取。环境变量、host 网络和唯一的 `/data` 命名卷沿用默认文件；不会构建或启动 udpxy。

在源码构建模式下，后续管理命令也显式带上两份 `-f` 参数；该 override 不会被自动加载。切回已发布镜像时，使用默认 Compose 的 `pull homecast` 和 `up -d --no-build homecast`，保留同一项目名与数据卷。

## 本地测试

需要 Python 3.11+、Node.js 与 Chromium。以下命令可在 Linux / macOS shell 或 Windows PowerShell 执行；如系统将 Python 命名为 `python3`，相应替换。

```bash
python -m pip install -r requirements.lock
python -m pip install --no-deps .
python -m unittest discover -s tests -v
npm install --no-save playwright@1.58.2
npx playwright install chromium
FRONTEND_BROWSER=chromium node --test tests/frontend.test.cjs
```

PowerShell 的最后一步改为：

```powershell
$env:FRONTEND_BROWSER = 'chromium'
node --test tests/frontend.test.cjs
```

Linux Docker 主机还可运行纯合成数据的镜像测试，不需要实际 IPTV 账号：

```bash
docker build -t homecast-review .
python tests/docker_smoke.py homecast-review
```

测试使用合成身份与文档示例地址，浏览器测试拦截 API，不需要也不应填入家庭账号。真实线路认证、组播以及播放器解码必须另行验证，不能用单元测试通过或容器 healthy 代替。不得将私有抓包、身份、运行缓存写入测试夹具或镜像。

前端为原生 HTML / CSS / JavaScript，无构建步骤；Lucide 在本地随包提供。项目不打包上游 IPTV 项目的 Python 实现。贡献边界见 [CONTRIBUTING.md](../CONTRIBUTING.md)。

## Docker 文档参考

本项目借鉴以下官方文档的组织方式：先说明运行前提，再提供镜像、环境配置、持久化数据和验证步骤。它们不是 HomeCast 的运行依赖，参数和网络模式不能照搬。

- [Navidrome Docker 安装](https://www.navidrome.org/docs/installation/docker/) 将镜像、环境变量和数据挂载放在同一份 Compose 中；[配置选项](https://www.navidrome.org/docs/usage/configuration/options/) 单独解释变量。
- [LinuxServer 容器运行指南](https://docs.linuxserver.io/general/running-our-containers/) 明确说明持久化目录的用途。HomeCast 的数据目录是 `/data`，不使用其镜像约定。
- [ntfy Docker 安装](https://docs.ntfy.sh/install/#docker) 区分基本运行、持久化缓存和健康检查；HomeCast 同样分别验证进程、频道更新与视频传输。

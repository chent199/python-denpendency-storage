# 离线 Python 包索引

运行在 RHEL 8.7 x86_64 Docker 上，无需主机 Python、网络或外部数据库。
镜像内置 fastapi、deepagents、aiofiles、httpx、loguru、python-dotenv、python-multipart、requests、uvicorn、openai、langchain-openai、pydantic、openpyxl、python-docx 及完整依赖，只分发 wheel，不在离线主机编译源码。

当前 1.3 交付包含 tiktoken 的全部 6 个官方词表文件，已核对 wheel 中声明的 SHA256。两个 Linux 包集已通过断网分词编码及 LangChain token 计数测试。客户端仍须按下文部署词表目录并设置 TIKTOKEN_CACHE_DIR；只执行 pip install 不会复制这些外部词表。真实 Windows、RHEL 和 openEuler 系统尚需执行目标机验证。

新增数据和工具包：pandas、numpy、pypdf、Pillow、beautifulsoup4、pydantic-settings、pytest。按最新要求，跳过 MySQL、Oracle、PostgreSQL 驱动，未包含 SQLAlchemy。

## 已配置的目标

| 索引 ID | 系统 | Python | ABI / libc |
|---|---|---|---|
| win10-cp314 | Windows 10 AMD64 | CPython 3.14.4 64 位 | cp314 / win_amd64 |
| rhel87-cp312 | RHEL 8.7 x86_64 | CPython 3.12.8 64 位 | cp312 / glibc 2.28 |
| openeuler-cp312 | openEuler x86_64，内核 6.6 | CPython 3.12.7 64 位 | cp312 / glibc 2.38 |

默认包不带 extras，不含 GPU/CUDA。deepagents 的模型权重、模型服务和 API 凭据不在 Python 包内；完全离线使用时需要另行配置可访问的内网模型服务。

## 离线部署

解压交付包，在 RHEL 主机执行（Podman 未作为本次验收目标）：

```bash
sha256sum -c SHA256SUMS
docker load -i offline-pypi-image.tar.gz
docker volume create offline-pypi-data
docker run -d --name offline-pypi --restart unless-stopped \
  -p 8080:8080 -v offline-pypi-data:/data offline-pypi:1.3
docker logs offline-pypi
curl --fail http://127.0.0.1:8080/healthz
```

镜像首次启动会校验内置包并初始化数据卷。已有数据卷保留原索引；加载新镜像不会自动覆盖已有数据。服务无上传接口或认证，仅用于可信内网。按需配置 RHEL 防火墙允许客户端访问 TCP 8080；不要关闭 SELinux。命名卷避免宿主目录的 SELinux 挂载问题。

## 客户端安装

以下以 RHEL 客户端为例，把 `SERVER` 替换为服务主机 IP。必须使用目标对应索引，不能把三个索引混合使用。Windows 用 `py` 或对应虚拟环境的 `python` 代替 `python3`。

推荐在新虚拟环境安装完整锁定集合，避免已有包冲突：

```bash
python3 -m venv app-env
app-env/bin/python -m pip install --only-binary=:all: --require-hashes \
  --index-url http://SERVER:8080/rhel87-cp312/simple/ --trusted-host SERVER \
  -r http://SERVER:8080/rhel87-cp312/requirements.txt
app-env/bin/python -m pip check
```

单独安装包也可使用 `pip install --only-binary=:all: --index-url http://SERVER:8080/目标ID/simple/ --trusted-host SERVER fastapi deepagents`。完整锁文件安装才复现本次测试集合。不要使用 `--extra-index-url`，避免访问互联网。内网 HTTP 用于传输，wheel 哈希用于内容校验；如需跨不可信网络访问，请在前面配置 HTTPS。

客户端使用 LangChain/OpenAI 分词或 token 计数之前，把交付包的词表目录复制到该电脑，并在运行应用的终端中设置路径：

Linux（当前目录为解压后的交付目录）：

```bash
export TIKTOKEN_CACHE_DIR="$PWD/bundle/runtime-cache/tiktoken"
```

Windows PowerShell（当前目录为解压后的交付目录）：

```powershell
$env:TIKTOKEN_CACHE_DIR = (Resolve-Path .\bundle\runtime-cache\tiktoken).Path
```

这些命令作用于当前终端及其子进程；若通过系统服务运行应用，请在该服务的环境配置中设置同一个绝对路径。不要只把变量设在包索引容器里。

## 在真实目标电脑验证

把交付目录（包含 bundle、tools、tests）复制到目标电脑，在目录内执行：

```bash
python3 tools/verify_target.py --target rhel87-cp312 --bundle bundle --venv verify-env
```

Windows：

```powershell
py -3.14 tools/verify_target.py --target win10-cp314 --bundle bundle --venv verify-env
```

openEuler 用 `--target openeuler-cp312`。脚本先检查解释器、架构和 libc，再在新环境中完全离线安装、运行 `pip check`、FastAPI HTTP 测试和 deepagents 模拟模型调用。若失败，保留输出用于诊断，不要混用其他索引或绕过检查。Linux wheel 标签无法证明 Windows 10 的底层 API 兼容性；本地测试通过之前不要视为已验收。

## 命令行添加包、更新

离线主机无法自行获取未导入的包。先在联网机器上运行下载工具，然后把补充目录复制到 RHEL。联网机器需 Python 3.12+、pip 26.2.1 和 uv 0.12.23（本次使用版本）。uv 按目标平台解析环境标记，再由 pip 只下载匹配 wheel 并核验 PyPI 哈希，避免直接跨平台 pip 解析造成漏依赖。

在本仓库目录执行；`--previous` 指向上次 bundle，保留之前的顶层包，并重新联合解析整个集合：

```bash
python3 tools/prepare.py --previous /path/to/old-bundle --output /path/to/new-bundle requests
```

更新当前完整包集合（不传 --previous 时需完整列出）：

```bash
python3 tools/prepare.py --output /path/to/new-bundle fastapi deepagents aiofiles httpx loguru python-dotenv python-multipart requests uvicorn openai langchain-openai pydantic openpyxl python-docx pandas numpy pypdf Pillow beautifulsoup4 pydantic-settings pytest
```

不传 `--previous` 表示完整替换顶层包集合，输出目录必须不存在。每个目标选择依赖约束内的最新稳定版本；不接受预发行版、任意 URL 或源码编译。某目标没有兼容解会使整个准备失败，不发布半成品。可选扩展用 `'fastapi[standard]'` 等名称显式添加。添加新目标时编辑 targets.json 后重新准备，并在真实目标验证。

复制 `new-bundle` 到 RHEL 后，完整校验并导入（命名卷无需把目录暴露给运行中的容器）：

```bash
docker create --name offline-pypi-import --network none \
  -v offline-pypi-data:/data offline-pypi:1.3 import /incoming
docker cp /path/to/new-bundle offline-pypi-import:/incoming
docker start -a offline-pypi-import
docker inspect offline-pypi-import --format '{{.State.ExitCode}}'
docker rm offline-pypi-import
```

导入退出码必须为 0。数据先复制、逐文件校验，再原子切换索引；失败保留原索引。当前索引每个包只有本次选定版本。历史文件保留以保护正在下载的客户端，不自动删除；当前服务不提供历史版本选择。更新后重新在目标电脑验证，已有虚拟环境不会自动升级。

## 从源码重建与测试（联网准备机）

下载器会从选定 tiktoken wheel 的元数据提取官方词表 URL 和预期 SHA256，校验后存放在 `bundle/runtime-cache/tiktoken`。对尚缺词表的现有 bundle，可在网络权限生效后补齐：

```bash
python3 tools/tokenizer_cache.py dist/bundle
```

从官方域名下载需要联网，词表已完整的交付包无需再次下载。之后重建镜像并重新运行测试。每台离线客户端还需复制 `bundle/runtime-cache/tiktoken` 目录，并在应用启动前设置 `TIKTOKEN_CACHE_DIR` 为该目录的绝对路径（Linux 用 `export`，PowerShell 用 `$env:TIKTOKEN_CACHE_DIR = '路径'`）。目标机验证脚本在目录存在时自动设置该变量；缺少目录时测试会失败，不能忽略。词表不是 pip wheel 的组成部分，仅执行 pip install 不会部署词表。

```bash
python3 tools/prepare.py --output dist/bundle fastapi deepagents aiofiles httpx loguru python-dotenv python-multipart requests uvicorn openai langchain-openai pydantic openpyxl python-docx pandas numpy pypdf Pillow beautifulsoup4 pydantic-settings pytest
docker build --network=none --pull=false -t offline-pypi:1.3 .
python3 -m unittest discover -s tests -v
docker run --rm --network none --entrypoint python \
  -v "$PWD/tests:/tests:ro" offline-pypi:1.3 /tests/offline_install.py
```

构建前需下载 Dockerfile 固定 digest 的基础镜像；构建阶段无网络安装。受限云环境可把 `UV_CACHE_DIR`、`DOCKER_CONFIG` 设置到 `/workspace` 内可写路径。交付包的 bundle 可复制为 dist/bundle，直接复用已下载文件重建，无需重新下载。

环境验证边界：本次在 Debian bookworm / CPython 3.12.8 容器中断网验证 Linux 包集，未运行实际 RHEL、openEuler 或 Windows。跨平台下载及哈希通过不等于这些系统已经通过运行测试。真实模型调用、业务测试和用户自选 extras 未验证。

## 从已有版本更新

`docker load` 只加载镜像，不会更新现有数据卷。若已经运行 1.0、1.1 或 1.2，请使用上文的一次性导入命令，将本次交付的 `bundle` 目录完整导入同一数据卷；导入退出码必须是 0。首次部署则直接运行 1.3 镜像。所有客户端还需复制新版词表目录并配置变量。

## 新增包验证

新增测试覆盖 NumPy 线性代数、pandas CSV/XLSX、PDF 元数据与页数读写、PNG 编解码、HTML CSS 选择、dotenv 配置加载，并由 pytest 实际执行。`pypdf` 不执行扫描件 OCR，图像/文档处理未包含 OCR 模型或系统引擎。SQLAlchemy 与 MySQL/Oracle/PostgreSQL 驱动按要求未包含。

# Debian 一键启动：uv + 后台服务

适用：Debian 11+ / Ubuntu 22.04+，x86_64 或 ARM64，单人使用、1 GB RAM、已开启 8 GiB Swap。首次运行需联网，系统依赖安装需要 root 或 sudo；推荐以普通用户运行，让脚本仅在 apt 安装时调用 sudo。

在项目根目录执行：

```bash
bash start.sh
```

脚本自动安装 Debian 运行库，准备 uv，使用 `uv venv --python 3.11 .venv-server` 创建独立环境，再通过 `uv pip install` 安装后端依赖。如果没有可用的 Node.js 20+，会下载并校验官方 Node.js 22 包；随后执行 `npm ci` 和前端构建。Python 环境、工具及前端构建完成后会复用，后台服务运行期间不需要 Node.js。

Python 3.11 用于兼容当前 `pdf2zh==1.9.11` 的 Python 版本要求，不会覆盖开发环境 `.venv`。uv 的自动 Python 安装机制及安装路径配置见 [uv 安装 Python 文档](https://docs.astral.sh/uv/guides/install-python/) 和 [uv 安装文档](https://docs.astral.sh/uv/getting-started/installation/)；Node 下载源为 [Node.js 官方发布目录](https://nodejs.org/dist/latest-v22.x/)。

安装结束后，脚本以独立会话启动服务，等待 `/api/health` 返回成功。SSH 断开或终端关闭后仍会运行。默认访问 **`http://服务器IP:8080`**，已有 `config/config.yaml` 的端口会保留；在云平台安全组中开放对应 TCP 端口。如果端口已被其他服务占用，启动会明确报错。

首次部署会生成随机访问密码并保存到 `.env`，可在服务器上查看：

```bash
grep '^PAPER_TRANSLATOR_PASSWORD=' .env
```

已有密码和翻译 API 密钥会保留。首次生成的 `.env` 中翻译密钥为空，可登录后在页面“设置”填写，或编辑 `.env` 的 `TRANSLATION_API_KEY` 后重启。脚本不会将 `.env` 当 shell 脚本执行。

## 常用命令

```bash
bash start.sh status    # 查看状态
bash start.sh logs      # 跟踪日志，Ctrl+C 退出查看
bash start.sh stop      # 停止服务及翻译子进程
bash start.sh restart   # 重启，依赖和前端未变更时跳过安装/构建
bash start.sh update    # 停止后检查 Python 依赖、重新构建前端并启动
bash start.sh install   # 仅安装与初始化，运行中的服务不能执行此命令
```

日志保存在 `data/logs/server.log`；启动时超过 10 MiB 的日志会轮转，保留三份历史文件。PID 记录位于 `data/run/server.json`，脚本会验证进程身份，避免误停止 PID 被复用后的其他服务。启动失败会清理刚创建的后台进程。

此方式支持断开 SSH 后运行；机器重启或服务崩溃后不会自动启动。需要开机自启和崩溃重启时，先用脚本完成安装，再 `bash start.sh stop`，然后采用 `deploy/paper-translator.service`，避免同时运行两套启动方式。

## 兼顾速度的默认配置

| 参数 | 默认值 |
| --- | --- |
| 同时翻译的论文 | 1 篇，其余排队 |
| 文本翻译线程 | 4 |
| CPU / ONNX 推理线程 | 1 |
| 每批翻译页数 | 5 页 |
| 运行及排队任务总数 | 10 |
| PDF 文件上限 | 100 MiB / 1000 页 |
| 单篇任务超时 | 2 小时（包括模型/字体下载） |
| 前端构建 Node.js 堆上限 | 1536 MiB |

文本翻译主要等待远程 API，4 线程能减少等待；版面推理保持单线程，适合一个共享核心。5 页分批减少重复合并开销，同时保留完成后退出子进程、释放模型内存的机制。Swap 是内存余量，大量换页时速度会下降；图片密集的论文可把 `PT_TRANSLATION_BATCH_PAGES` 降为 2。

`start.sh` 的后台方式不设置 768 MiB 内存限制或 75% CPU 限制，直接使用操作系统已有的 RAM 和 Swap。可选 Docker 配置放宽为 1 GiB RAM + 最多 4 GiB Swap，CPU 上限 1 核；systemd 模板采用相同上限。不会创建、格式化或修改已有 Swap。

首次执行会将上一版保守的默认值升级为上表配置，保留不同于旧默认值的自定义参数，并保存原 `.env` / YAML 到 `data/run/env-before-bootstrap`、`data/run/config-before-bootstrap.yaml`（权限 600）。后续执行不会反复覆盖手动调整。希望首次也完全保留已有资源配置时，使用：

```bash
PT_KEEP_RESOURCE_CONFIG=1 bash start.sh
```

资源参数以 `.env` 中的 `PT_*` 为优先，可参考 `.env.example`；Web 设置控制实际文本翻译线程，服务器上限仍由 `PT_MAX_TRANSLATION_THREADS` 控制。

系统依赖已由管理员安装、不具备 sudo 权限时，可使用 `PT_SKIP_SYSTEM_PACKAGES=1 bash start.sh`。临时修改监听地址或端口可用：

```bash
PAPER_TRANSLATOR_HOST=0.0.0.0 PAPER_TRANSLATOR_PORT=8080 bash start.sh
```

验证包含：离线模拟 uv 安装与前端构建、依赖未变时复用、源文件修改后重建、包含空格的项目路径、启动器退出后服务存活、重复启动、端口占用、启动失败与超时清理，以及凭证/配置迁移。未在你的 Debian 服务器上执行实际 apt 和网络下载。

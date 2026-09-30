#!/usr/bin/env bash
# Debian/Ubuntu bootstrap and background runner. Python dependencies use uv only.
set -Eeuo pipefail
umask 077

PT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PT_ACTION="${1:-start}"
PT_TOOLS="$PT_ROOT/.tools"
PT_VENV="$PT_ROOT/.venv-server"
PT_MANAGER="$PT_ROOT/deploy/server_manager.py"

usage() {
    cat <<'HELP'
用法：bash start.sh [start|stop|restart|status|logs|install|update]
  start    自动准备依赖和前端，然后后台启动（默认）
  stop     停止本脚本启动的服务
  restart  停止后启动，复用已安装依赖
  status   查看运行状态
  logs     跟踪后台日志（Ctrl+C 只退出日志查看）
  install  仅安装依赖、构建前端和初始化配置
  update   停止服务，重新检查依赖并构建前端，然后启动

默认端口使用 config/config.yaml，初始为 8080。
首次运行需要联网，安装系统依赖时可能要求 sudo 密码。
HELP
}

case "$PT_ACTION" in
    -h|--help|help) usage; exit 0 ;;
    start|stop|restart|status|logs|install|update) ;;
    *) usage >&2; exit 2 ;;
esac
[[ $# -le 1 ]] || { usage >&2; exit 2; }
[[ "$(uname -s)" == Linux ]] || { echo '此脚本用于 Debian/Ubuntu Linux。' >&2; exit 1; }
cd -- "$PT_ROOT"

manager_python() {
    if [[ -x "$PT_VENV/bin/python" ]]; then
        printf '%s\n' "$PT_VENV/bin/python"
    elif command -v python3 >/dev/null 2>&1; then
        command -v python3
    else
        echo '尚未安装运行环境，请先执行 bash start.sh。' >&2
        return 1
    fi
}

# Read-only commands do not install packages or require sudo.
if [[ "$PT_ACTION" == logs ]]; then
    [[ -f data/logs/server.log ]] || { echo '尚无日志，请先启动服务。'; exit 0; }
    exec tail -n 80 -F data/logs/server.log
fi
if [[ "$PT_ACTION" == status ]]; then
    exec "$(manager_python)" "$PT_MANAGER" status
fi

mkdir -p data/run data/logs "$PT_TOOLS"
if command -v flock >/dev/null 2>&1; then
    exec 9>data/run/start.lock
    flock -n 9 || { echo '另一个启动或安装操作正在运行，请稍后重试。' >&2; exit 1; }
else
    echo '缺少 flock，请安装 util-linux 后重试。' >&2
    exit 1
fi
trap 'printf "启动操作失败（第 %s 行），请检查上方错误；服务日志：%s/data/logs/server.log\n" "$LINENO" "$PT_ROOT" >&2' ERR

if [[ "$PT_ACTION" == stop ]]; then
    "$(manager_python)" "$PT_MANAGER" stop
    exit 0
fi
if [[ "$PT_ACTION" == restart || "$PT_ACTION" == update ]]; then
    if [[ -f data/run/server.json ]]; then
        "$(manager_python)" "$PT_MANAGER" stop
    fi
elif [[ "$PT_ACTION" == start && -f data/run/server.json ]]; then
    if "$(manager_python)" "$PT_MANAGER" status; then
        echo '服务已运行，无需重复启动。'
        exit 0
    fi
fi
if [[ "$PT_ACTION" == install && -f data/run/server.json ]]; then
    if "$(manager_python)" "$PT_MANAGER" status; then
        echo '服务正在运行，请用 bash start.sh update 更新依赖。' >&2
        exit 1
    fi
fi
if [[ "$PT_ACTION" == update ]]; then
    export PT_FORCE_INSTALL=1
fi

install_system_packages() {
    [[ "${PT_SKIP_SYSTEM_PACKAGES:-0}" == 1 ]] && return 0
    [[ -f "$PT_TOOLS/system-deps-v1" ]] && return 0
    if ! command -v apt-get >/dev/null 2>&1; then
        echo '自动安装仅支持 Debian/Ubuntu；已准备系统依赖时可设 PT_SKIP_SYSTEM_PACKAGES=1。' >&2
        return 1
    fi
    local -a pt_admin=()
    if [[ "$EUID" -ne 0 ]]; then
        command -v sudo >/dev/null 2>&1 || { echo '安装系统依赖需要 root 或 sudo。' >&2; return 1; }
        pt_admin=(sudo)
    fi
    echo '[1/5] 安装 Debian 系统依赖...'
    # apt calls intentionally require system privilege; uv/Node/project files
    # below are installed as the user invoking this script.
    "${pt_admin[@]}" apt-get update
    "${pt_admin[@]}" env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates curl tar xz-utils util-linux libglib2.0-0 libgl1 fontconfig build-essential
    touch "$PT_TOOLS/system-deps-v1"
}

install_uv_and_python() {
    echo '[2/5] 准备 uv 和独立 Python 3.11 环境...'
    export UV_CACHE_DIR="$PT_ROOT/data/cache/uv"
    export UV_PYTHON_INSTALL_DIR="$PT_TOOLS/python"
    export UV_CONCURRENT_DOWNLOADS=2 UV_CONCURRENT_INSTALLS=1 UV_CONCURRENT_BUILDS=1
    if command -v uv >/dev/null 2>&1; then
        PT_UV="$(command -v uv)"
    elif [[ -x "$PT_TOOLS/bin/uv" ]]; then
        PT_UV="$PT_TOOLS/bin/uv"
    else
        mkdir -p "$PT_TOOLS/bin"
        curl --fail --location --retry 3 --connect-timeout 20 --max-time 180 \
            https://astral.sh/uv/install.sh -o "$PT_TOOLS/uv-install.sh"
        UV_INSTALL_DIR="$PT_TOOLS/bin" UV_NO_MODIFY_PATH=1 sh "$PT_TOOLS/uv-install.sh"
        PT_UV="$PT_TOOLS/bin/uv"
    fi
    if [[ ! -x "$PT_VENV/bin/python" ]]; then
        if [[ -e "$PT_VENV" ]]; then
            echo '.venv-server 已存在但损坏，请移走该目录后重试；脚本不会覆盖它。' >&2
            return 1
        fi
        "$PT_UV" venv --python 3.11 "$PT_VENV"
    fi
    "$PT_VENV/bin/python" -c 'import sys; assert (3, 10) <= sys.version_info[:2] < (3, 13), "pdf2zh 1.9.11 要求 Python 3.10–3.12"'
    PT_BACKEND_HASH="$(sha256sum backend/requirements.txt | cut -d ' ' -f 1):$("$PT_VENV/bin/python" -c 'import sys; print(sys.version.split()[0])')"
    if [[ "${PT_FORCE_INSTALL:-0}" == 1 || ! -f data/run/backend-deps.sha256 ]] || \
            [[ "$(cat data/run/backend-deps.sha256)" != "$PT_BACKEND_HASH" ]] || \
            ! "$PT_VENV/bin/python" -c 'import fastapi, uvicorn, sqlalchemy, yaml, fitz, multipart, requests, aiofiles; import importlib.metadata as m; assert m.version("pdf2zh") == "1.9.11"' 2>/dev/null; then
        echo '[3/5] 使用 uv 安装 Python 依赖...'
        "$PT_UV" pip install --no-cache --python "$PT_VENV/bin/python" -r backend/requirements.txt
        "$PT_UV" pip check --python "$PT_VENV/bin/python"
        printf '%s\n' "$PT_BACKEND_HASH" >data/run/backend-deps.sha256
    else
        echo '[3/5] Python 依赖已就绪。'
    fi
}

ensure_node() {
    if [[ -x "$PT_TOOLS/node22/bin/node" ]]; then
        export PATH="$PT_TOOLS/node22/bin:$PATH"
    fi
    if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1 && \
            node -e 'process.exit(Number(process.versions.node.split(".")[0]) >= 20 ? 0 : 1)'; then
        return 0
    fi
    local pt_arch pt_file pt_hash
    case "$(uname -m)" in
        x86_64) pt_arch=x64 ;;
        aarch64|arm64) pt_arch=arm64 ;;
        *) echo 'Node 自动安装支持 x86_64 和 ARM64。' >&2; return 1 ;;
    esac
    curl --fail --location --retry 3 --connect-timeout 20 --max-time 180 \
        https://nodejs.org/dist/latest-v22.x/SHASUMS256.txt -o "$PT_TOOLS/node-shasums.txt"
    pt_file="$(awk -v arch="$pt_arch" '$2 ~ ("^node-v22[.].*-linux-" arch "[.]tar[.]xz$") {print $2; exit}' "$PT_TOOLS/node-shasums.txt")"
    [[ -n "$pt_file" ]] || { echo '无法解析 Node.js 下载版本。' >&2; return 1; }
    pt_hash="$(awk -v file="$pt_file" '$2 == file {print $1}' "$PT_TOOLS/node-shasums.txt")"
    curl --fail --location --retry 3 --connect-timeout 20 --max-time 600 \
        "https://nodejs.org/dist/latest-v22.x/$pt_file" -o "$PT_TOOLS/$pt_file"
    (cd "$PT_TOOLS" && printf '%s  %s\n' "$pt_hash" "$pt_file" | sha256sum --check --status)
    mkdir -p "$PT_TOOLS/node22"
    tar -xJf "$PT_TOOLS/$pt_file" --strip-components=1 -C "$PT_TOOLS/node22"
    export PATH="$PT_TOOLS/node22/bin:$PATH"
    node --version
}

build_frontend() {
    echo '[4/5] 检查前端构建...'
    PT_FRONTEND_HASH="$("$PT_VENV/bin/python" "$PT_MANAGER" frontend-hash)"
    if [[ "${PT_FORCE_INSTALL:-0}" == 1 || ! -f frontend/dist/index.html || ! -f data/run/frontend.sha256 ]] || \
            [[ "$(cat data/run/frontend.sha256)" != "$PT_FRONTEND_HASH" ]]; then
        ensure_node
        export NODE_OPTIONS="${NODE_OPTIONS:---max-old-space-size=1536}"
        (cd frontend && npm ci --no-audit --no-fund && npm run build)
        printf '%s\n' "$PT_FRONTEND_HASH" >data/run/frontend.sha256
    else
        echo '前端未变更，复用已有静态资源。'
    fi
}

install_system_packages
install_uv_and_python
build_frontend
echo '[5/5] 初始化配置...'
"$PT_VENV/bin/python" "$PT_MANAGER" prepare
if [[ "$PT_ACTION" == install ]]; then
    echo '安装完成，可执行 bash start.sh 启动。'
else
    "$PT_VENV/bin/python" "$PT_MANAGER" start
fi

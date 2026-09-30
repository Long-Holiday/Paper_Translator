"""Helpers for start.sh: safe config migration and detached service lifecycle."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys
import time
import urllib.request


OLD_LIMITS = {
    "cpu_threads": 1, "max_translation_threads": 1, "translation_batch_pages": 2,
    "max_pending_tasks": 3, "max_upload_mb": 20, "max_pdf_pages": 200,
    "translation_timeout_seconds": 1800,
}
BALANCED_LIMITS = {
    "cpu_threads": 1, "max_translation_threads": 4, "translation_batch_pages": 5,
    "max_pending_tasks": 10, "max_upload_mb": 100, "max_pdf_pages": 1000,
    "translation_timeout_seconds": 7200,
}


def write_atomic(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        os.chmod(temporary, 0o600)
        stream.write(text)
    temporary.replace(path)


def env_values(path):
    values = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                values[key.strip()] = value
    return values


def prepare(project):
    import yaml

    run = project / "data/run"
    run.mkdir(parents=True, exist_ok=True)
    marker = run / "balanced-profile-v1"
    migrate = not marker.exists() and os.environ.get("PT_KEEP_RESOURCE_CONFIG") != "1"
    config_path = project / "config/config.yaml"
    config = yaml.safe_load(config_path.read_text()) if config_path.exists() else {}
    config = config or {}
    if not isinstance(config, dict):
        raise ValueError("config/config.yaml 顶层必须是配置映射")
    old_config = yaml.safe_dump(config, allow_unicode=True, sort_keys=False)
    template = yaml.safe_load((project / "config/config.example.yaml").read_text())
    for section, defaults in template.items():
        values = config.setdefault(section, {})
        if not isinstance(values, dict):
            raise ValueError(f"config/config.yaml 的 {section} 必须是配置映射")
        for key, value in defaults.items():
            values.setdefault(key, value)
    for key, value in BALANCED_LIMITS.items():
        if migrate and config["resources"].get(key) == OLD_LIMITS[key]:
            config["resources"][key] = value
    if migrate and config["translation"].get("thread") == 1:
        config["translation"]["thread"] = 4
    config_text = yaml.safe_dump(config, allow_unicode=True, sort_keys=False)
    if config_text != old_config or not config_path.exists():
        if config_path.exists() and not (run / "config-before-bootstrap.yaml").exists():
            write_atomic(run / "config-before-bootstrap.yaml", config_path.read_text())
        write_atomic(config_path, config_text)

    env_path = project / ".env"
    existing = env_values(env_path)
    updates = {}
    password = existing.get("PAPER_TRANSLATOR_PASSWORD") or existing.get("AUTH_PASSWORD")
    if not password or password == "your_secure_password_here":
        updates["PAPER_TRANSLATOR_PASSWORD"] = secrets.token_urlsafe(18)
    if not env_path.exists() or existing.get("TRANSLATION_API_KEY") == "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx":
        updates["TRANSLATION_API_KEY"] = ""
    for key, value in BALANCED_LIMITS.items():
        name = "PT_" + key.upper()
        if name not in existing:
            updates[name] = str(config["resources"].get(key, value))
        elif migrate and existing[name] == str(OLD_LIMITS[key]):
            updates[name] = str(value)
    # Match optional Docker deployment with the swap-enabled profile.
    for name, old, new in (("PT_CONTAINER_MEMORY", "768m", "1g"),
                           ("PT_CONTAINER_CPUS", "0.75", "1.0"),
                           ("PT_CONTAINER_MEMORY_SWAP", "", "5g")):
        if name not in existing or (migrate and existing[name] == old):
            updates[name] = new
    if updates:
        lines = env_path.read_text().splitlines() if env_path.exists() else []
        updated_lines = []
        for line in lines:
            key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else None
            if key in updates:
                updated_lines.append(f"{key}={updates.pop(key)}")
            else:
                updated_lines.append(line)
        updated_lines.extend(f"{key}={value}" for key, value in updates.items())
        if env_path.exists() and not (run / "env-before-bootstrap").exists():
            write_atomic(run / "env-before-bootstrap", env_path.read_text())
        write_atomic(env_path, "\n".join(updated_lines) + "\n")
    marker.touch(mode=0o600)
    print("配置已就绪：保留现有凭证与端口；初次运行的访问密码保存在 .env。")


def frontend_hash(project):
    frontend = project / "frontend"
    files = list((frontend / "src").rglob("*"))
    files.extend(path for path in frontend.iterdir() if path.is_file())
    digest = hashlib.sha256()
    for path in sorted(path for path in files if path.is_file()):
        digest.update(str(path.relative_to(frontend)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def process_identity(pid):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        if fields[0] == "Z":
            return None
        return fields[19]  # Linux starttime, guards against PID reuse.
    except (OSError, IndexError):
        return None


def running_record(project):
    try:
        record = json.loads((project / "data/run/server.json").read_text())
        pid = int(record["pid"])
        if pid <= 1 or process_identity(pid) != record["starttime"]:
            return None
        command = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
        if str(project / "start.py").encode() not in command:
            return None
        return record
    except (OSError, ValueError, KeyError, TypeError):
        return None


def find_project_pids(project):
    pids = []
    marker = str(project / "start.py").encode()
    proc = Path("/proc")
    if not proc.exists():
        return pids
    for entry in proc.iterdir():
        if entry.name.isdigit():
            try:
                cmd = (entry / "cmdline").read_bytes()
                if marker in cmd:
                    pids.append(int(entry.name))
            except (OSError, ValueError):
                continue
    return pids


def stop(project, timeout=20):
    record = running_record(project)
    state = project / "data/run/server.json"
    pids_to_kill = set()
    if record is not None:
        pids_to_kill.add(int(record["pid"]))
    # 兜底查找可能由于异常未记录在 server.json 的历史 start.py 孤儿进程
    pids_to_kill.update(find_project_pids(project))

    if not pids_to_kill:
        state.unlink(missing_ok=True)
        print("服务未运行。")
        return

    for pid in pids_to_kill:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        alive = [p for p in pids_to_kill if Path(f"/proc/{p}").exists()]
        if not alive:
            break
        time.sleep(0.2)

    for pid in pids_to_kill:
        if Path(f"/proc/{pid}").exists():
            try:
                os.killpg(pid, signal.SIGKILL)
            except OSError:
                try:
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass

    state.unlink(missing_ok=True)
    # 给操作系统内核释放 socket 留出短暂缓冲
    time.sleep(0.5)
    print("服务已停止。")


def start(project, timeout=60):
    import yaml

    record = running_record(project)
    if record:
        print(f"服务已运行，PID={record['pid']}，端口={record['port']}")
        return
    config = yaml.safe_load((project / "config/config.yaml").read_text())
    env = {**env_values(project / ".env"), **os.environ}
    server = config.get("server", {})
    host = env.get("PAPER_TRANSLATOR_HOST", server.get("host", "0.0.0.0"))
    port = int(env.get("PAPER_TRANSLATOR_PORT", server.get("port", 8080)))
    if not 1 <= port <= 65535:
        raise ValueError("服务器端口必须在 1–65535 之间")
    family, _, _, _, address = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)[0]

    # 带 SO_REUSEADDR 与 5 秒重试窗口探测端口，容纳刚停止时短暂的 TIME_WAIT 或清理延迟
    probe_deadline = time.monotonic() + 5
    bound = False
    last_exc = None
    while time.monotonic() < probe_deadline:
        with socket.socket(family, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(address)
                bound = True
                break
            except OSError as exc:
                last_exc = exc
                time.sleep(0.5)
    if not bound:
        raise RuntimeError(f"无法监听 {host}:{port}，请检查端口是否被占用：{last_exc}") from last_exc
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        env[key] = "1"
    env["NO_BROWSER"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    logfile = project / "data/logs/server.log"
    logfile.parent.mkdir(parents=True, exist_ok=True)
    if logfile.exists() and logfile.stat().st_size > 10 * 1024 * 1024:
        for number in (2, 1):
            source = logfile.with_suffix(f".log.{number}")
            if source.exists():
                source.replace(logfile.with_suffix(f".log.{number + 1}"))
        logfile.replace(logfile.with_suffix(".log.1"))
    python = project / ".venv-server/bin/python"
    with logfile.open("ab") as output:
        process = subprocess.Popen(
            [str(python), str(project / "start.py"), "--no-browser", "--skip-frontend-build",
             "--host", host, "--port", str(port)],
            cwd=project, env=env, stdin=subprocess.DEVNULL,
            stdout=output, stderr=subprocess.STDOUT, start_new_session=True,
        )
    record = {"pid": process.pid, "starttime": process_identity(process.pid), "port": port}
    try:
        write_atomic(project / "data/run/server.json", json.dumps(record))
        local_host = "127.0.0.1" if host == "0.0.0.0" else "::1" if host == "::" else host
        if ":" in local_host:
            local_host = f"[{local_host}]"
        url = f"http://{local_host}:{port}/api/health"
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"服务启动失败 (exit={process.returncode})，请查看 {logfile}")
            try:
                with opener.open(url, timeout=1) as response:
                    healthy = response.status == 200 and json.load(response).get("status") == "ok"
                if healthy and process.poll() is None:
                    print(f"后台启动成功，PID={process.pid}，访问：http://服务器IP:{port}")
                    print(f"日志：{logfile}；停止：bash start.sh stop")
                    return
            except (OSError, ValueError):
                pass
            time.sleep(0.5)
        raise RuntimeError(f"启动健康检查超时，请查看 {logfile}")
    except BaseException:
        # Own the Popen directly: even a failure to write the PID file must not
        # leave an untracked background server running.
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        (project / "data/run/server.json").unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "frontend-hash", "start", "stop", "status"])
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args()
    project = args.project.resolve()
    try:
        if args.action == "prepare":
            prepare(project)
        elif args.action == "frontend-hash":
            print(frontend_hash(project))
        elif args.action == "start":
            start(project)
        elif args.action == "stop":
            stop(project)
        else:
            record = running_record(project)
            if record is None:
                print("服务未运行。")
                return 3
            print(f"服务运行中，PID={record['pid']}，端口={record['port']}")
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

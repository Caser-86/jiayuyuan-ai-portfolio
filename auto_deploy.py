#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键部署脚本：用 paramiko SSH 到阿里云 ECS，部署个人主页项目。
"""
import os
import sys
import time
import paramiko
from pathlib import Path

# === 配置 ===
HOST = "121.41.169.43"
PORT = 22
USER = "root"
PASSWORD = "Jyy920220!"
LOCAL_DIR = Path(r"d:\Files\备用")
REMOTE_DIR = "/root/jiayuyuan"
SCRIPT_FILE = "deploy-aliyun.sh"
DOMAIN = "libaweiyu.xyz"
ADMIN_EMAIL = "776706958@qq.com"

# === 日志 ===
def log(msg, level="INFO"):
    icons = {"INFO": "•", "OK": "✓", "WARN": "!", "ERR": "✗", "STEP": "▶"}
    print(f"  {icons.get(level, '•')} {msg}", flush=True)

def step(msg):
    print(f"\n[STEP] {msg}\n", flush=True)

# === SSH 客户端 ===
def make_ssh():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    log(f"连接 {USER}@{HOST}:{PORT} ...")
    client.connect(HOST, PORT, USER, PASSWORD, timeout=15, banner_timeout=15, auth_timeout=15)
    log("SSH 连接成功", "OK")
    return client

def run(ssh, cmd, timeout=300, show=True):
    """执行远程命令，返回 (stdout, stderr, exit_code)"""
    if show:
        log(f"$ {cmd[:200]}{'...' if len(cmd) > 200 else ''}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if show and out:
        for line in out.splitlines()[-30:]:
            print(f"    {line}")
    if show and err.strip():
        for line in err.splitlines()[-10:]:
            print(f"    [stderr] {line}")
    return out, err, code

def sftp_put_dir(sftp, local_path: Path, remote_path: str):
    """递归上传整个目录（自动转换 Windows 行尾为 Unix）"""
    try:
        sftp.mkdir(remote_path)
    except IOError:
        pass  # 已存在则忽略
    for item in local_path.iterdir():
        remote_item = remote_path.rstrip("/") + "/" + item.name
        if item.is_dir():
            # 排除：Windows NSSM 工具 / 虚拟环境 / IDE 配置 / 缓存
            if item.name in ("venv", ".git", "__pycache__", "node_modules", "tools", ".idea", ".vscode"):
                continue
            sftp_put_dir(sftp, item, remote_item)
        else:
            # 排除：编译缓存、日志
            if item.name.endswith((".pyc", ".log")):
                continue
            # 只对文本文件做行尾转换
            text_ext = (".sh", ".py", ".html", ".css", ".js", ".json", ".md", ".txt", ".yml", ".yaml", ".conf", ".ini", ".xml", ".csp")
            try:
                if item.suffix.lower() in text_ext:
                    data = item.read_bytes()
                    data = data.replace(b'\r\n', b'\n').replace(b'\r', b'')
                    with sftp.open(remote_item, "wb") as f:
                        f.write(data)
                else:
                    sftp.put(str(item), remote_item)
            except Exception as e:
                print(f"    上传失败 {item.name}: {e}", flush=True)

# === 主流程 ===
def main():
    print("=" * 60)
    print(f"  贾玉元.AI 一键部署到 {HOST}")
    print(f"  域名：{DOMAIN}")
    print("=" * 60)

    ssh = make_ssh()
    sftp = ssh.open_sftp()

    # 1. 检查环境
    step("1/7  检查 ECS 环境")
    out, _, code = run(ssh, "cat /etc/os-release | head -3 && echo --- && which python3 dnf yum nginx systemctl 2>&1 | head -10 && echo --- && uname -a", show=False)
    print(out)

    # 2. 创建项目目录
    step("2/7  准备远程目录")
    run(ssh, f"rm -rf {REMOTE_DIR} && mkdir -p {REMOTE_DIR}")
    log(f"创建 {REMOTE_DIR}", "OK")

    # 3. 上传项目
    step("3/7  上传项目代码")
    log(f"扫描本地目录：{LOCAL_DIR}")
    files_count = 0
    for f in LOCAL_DIR.rglob("*"):
        if f.is_file() and not any(p in f.parts for p in ("venv", ".git", "__pycache__", "node_modules", "tools")):
            files_count += 1
    log(f"待上传文件：~{files_count} 个")
    sftp_put_dir(sftp, LOCAL_DIR, REMOTE_DIR)
    sftp.close()
    log("项目上传完成", "OK")

    # 4. 上传 deploy-aliyun.sh
    step("4/7  上传部署脚本")
    sftp = ssh.open_sftp()
    # 用二进制模式读取 + 写入，并去掉 Windows 行尾 \r
    local_bytes = (LOCAL_DIR / SCRIPT_FILE).read_bytes()
    # 去掉所有 \r（Windows -> Unix）
    local_bytes = local_bytes.replace(b'\r\n', b'\n').replace(b'\r', b'')
    with sftp.open(f"/root/{SCRIPT_FILE}", "wb") as f:
        f.write(local_bytes)
    sftp.chmod(f"/root/{SCRIPT_FILE}", 0o755)
    sftp.close()
    log("部署脚本上传完成（已转换 LF）", "OK")

    # 5. 跑部署脚本（耗时长，2-5 分钟）
    step("5/7  跑部署脚本（装依赖、配 Nginx、启动服务）")
    log("这一步大约 2-5 分钟，请耐心等待...", "WARN")
    out, err, code = run(ssh, f"bash /root/{SCRIPT_FILE}", timeout=900, show=True)
    if code != 0:
        log(f"部署脚本退出码：{code}", "ERR")
        if err:
            print("--- ERROR ---")
            print(err[-2000:])
        return code

    # 6. 申请 SSL
    step("6/7  申请 Let's Encrypt SSL 证书")
    out, err, code = run(ssh, "which certbot 2>/dev/null || (dnf install -y certbot python3-certbot-nginx -q && which certbot)", timeout=300)
    log(f"certbot 已就绪", "OK" if "certbot" in out else "WARN")

    log("申请证书（自动同意条款、自动 HTTPS）...")
    ssl_cmd = (
        f"certbot --nginx -d {DOMAIN} -d www.{DOMAIN} "
        f"--non-interactive --agree-tos -m {ADMIN_EMAIL} --redirect"
    )
    out, err, code = run(ssh, ssl_cmd, timeout=300, show=True)
    if code != 0:
        log("SSL 申请失败（可能域名 DNS 未生效），等 5 分钟后再试", "WARN")
        print(err[-1500:])

    # 7. 验证
    step("7/7  验证最终结果")
    log("测试 HTTP → HTTPS 重定向...")
    out, _, _ = run(ssh, f"curl -sI http://{DOMAIN}/ --max-time 10 | head -5", show=True)
    log("测试 HTTPS 主页...")
    out, _, _ = run(ssh, f"curl -sI https://{DOMAIN}/ --max-time 10 | head -5", show=True)
    log("测试 API...")
    out, _, _ = run(ssh, f"curl -s https://{DOMAIN}/api/projects --max-time 10 | head -c 200", show=True)
    log("查看 systemd 服务状态...")
    out, _, _ = run(ssh, "systemctl is-active jiayuyuan && systemctl status jiayuyuan --no-pager | head -10", show=True)

    ssh.close()

    print("\n" + "=" * 60)
    print("  🎉 部署完成！")
    print("=" * 60)
    print(f"  访问：https://{DOMAIN}")
    print(f"  访问：https://www.{DOMAIN}")
    print(f"  管理后台：https://{DOMAIN}/admin.html")
    print()
    print("  ⚠️  立即去阿里云 ECS 控制台重置密码为强密码！")
    print("=" * 60)
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n用户中断", "ERR")
        sys.exit(1)
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)

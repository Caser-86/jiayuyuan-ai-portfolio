#!/bin/bash
# ============================================================
#  贾玉元.AI 一键部署到阿里云 ECS（Ubuntu/Alibaba Cloud Linux）
#  使用方法：
#    1. 编辑本文件，把 DOMAIN 改成你的实际域名
#    2. 在 Windows PowerShell 里执行：
#         scp D:\Files\备用\deploy-aliyun.sh root@<ECS_IP>:/root/
#         ssh root@<ECS_IP> "bash /root/deploy-aliyun.sh"
# ============================================================

set -e
DOMAIN="libaweiyu.xyz"  # 阿里云 DNS 控制台显示的实际域名

if [ "$DOMAIN" = "你的域名" ]; then
    echo "❌ 请先编辑本文件，把 DOMAIN 改成你的实际域名！"
    exit 1
fi

echo "=================================================="
echo "  开始部署 贾玉元.AI 到阿里云 ECS"
echo "  域名：$DOMAIN"
echo "=================================================="

# ---- 1. 安装依赖 ----
echo ""
echo "[1/7] 安装系统依赖..."
if command -v dnf &> /dev/null; then
    # Alibaba Cloud Linux 3 / RHEL 8+ — 自带 Python 3.6 太老
    # fastapi>=0.100 需要 Python 3.8+，用 python3.11 模块
    dnf install -y python3.11 python3.11-pip nginx curl gcc
    # 设置默认 python3 → python3.11
    alternatives --set python3 /usr/bin/python3.11 2>/dev/null || true
elif command -v apt &> /dev/null; then
    # Ubuntu / Debian
    apt update -y
    apt install -y python3 python3-pip python3-venv python3-dev nginx curl
elif command -v yum &> /dev/null; then
    # CentOS 7 / RHEL 7
    yum install -y python3 python3-pip nginx curl gcc
else
    echo "❌ 不支持的发行版（需要 dnf / apt / yum）"
    exit 1
fi

# 验证 Python 版本
python3.11 --version 2>/dev/null || python3 --version
PYTHON_BIN=$(which python3.11 || which python3)
echo "  Python 路径：$PYTHON_BIN"

# ---- 2. 创建虚拟环境 + 安装 Python 依赖 ----
echo ""
echo "[2/7] 安装 Python 依赖..."
cd /root/jiayuyuan
# 用 python3.11 创建虚拟环境
if [ ! -d venv ]; then
    python3.11 -m venv venv
fi
source venv/bin/activate
# 确保 venv 里的 python 是 3.11
python --version
pip --version
pip install -i https://mirrors.aliyun.com/pypi/simple/ --upgrade pip -q
pip install -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt -q

# ---- 3. 注册 systemd 服务（开机自启 + 崩溃重启） ----
echo ""
echo "[3/7] 注册后端服务..."
cat > /etc/systemd/system/jiayuyuan.service << 'SVC'
[Unit]
Description=Jiayuyuan FastAPI
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/jiayuyuan
Environment="PATH=/root/jiayuyuan/venv/bin"
ExecStart=/root/jiayuyuan/venv/bin/gunicorn main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 127.0.0.1:8000 --access-logfile - --error-logfile -
Restart=always
RestartSec=5
StandardOutput=append:/var/log/jiayuyuan.log
StandardError=append:/var/log/jiayuyuan.error.log

[Install]
WantedBy=multi-user.target
SVC

systemctl daemon-reload
systemctl enable jiayuyuan
systemctl restart jiayuyuan
sleep 2
systemctl is-active jiayuyuan && echo "  ✓ 后端服务运行中" || (echo "  ✗ 后端启动失败，请查日志: journalctl -u jiayuyuan -n 50"; exit 1)

# ---- 4. 配置 Nginx 反向代理 ----
echo ""
echo "[4/7] 配置 Nginx..."

# 不同发行版，nginx 配置目录不同
if [ -d /etc/nginx/sites-available ]; then
    # Ubuntu / Debian
    NGINX_SITES_DIR="/etc/nginx/sites-available"
    NGINX_ENABLED_DIR="/etc/nginx/sites-enabled"
    NGINX_MAIN="/etc/nginx/nginx.conf"
elif [ -d /etc/nginx/conf.d ]; then
    # CentOS / RHEL / Alibaba Cloud Linux
    NGINX_SITES_DIR="/etc/nginx/conf.d"
    NGINX_ENABLED_DIR="/etc/nginx/conf.d"  # conf.d 本身就是 enabled
    NGINX_MAIN="/etc/nginx/nginx.conf"
else
    echo "❌ 找不到 nginx 配置目录"
    exit 1
fi

cat > $NGINX_SITES_DIR/jiayuyuan.conf << NGINX
server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;
    client_max_body_size 20M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
NGINX

# Ubuntu 需要 sites-enabled 软链接；CentOS 系列直接 conf.d
if [ "$NGINX_SITES_DIR" != "$NGINX_ENABLED_DIR" ]; then
    ln -sf $NGINX_SITES_DIR/jiayuyuan.conf $NGINX_ENABLED_DIR/jiayuyuan.conf
fi

# CentOS 系列的 nginx.conf 默认 include conf.d/*.conf；
# 但默认还有个 server 块监听 80，需要关掉避免冲突
if ! grep -q "include $NGINX_ENABLED_DIR" $NGINX_MAIN && [ -f $NGINX_MAIN ]; then
    # 检查是否已 include
    if ! grep -q "include /etc/nginx/conf.d" $NGINX_MAIN; then
        # 在 http 块里插入 include
        sed -i '/^http {/a\    include /etc/nginx/conf.d/*.conf;' $NGINX_MAIN
    fi
fi

nginx -t && systemctl restart nginx && echo "  ✓ Nginx 启动成功" || (echo "  ✗ Nginx 启动失败，请查日志: journalctl -u nginx -n 50"; exit 1)
rm -f /etc/nginx/sites-enabled/default 2>/dev/null

# 关掉 nginx.conf 默认的 server 块（避免占 80 端口冲突）
if grep -q "listen       80 default_server" /etc/nginx/nginx.conf; then
    sed -i 's/^    listen       80 default_server/    #listen       80 default_server/' /etc/nginx/nginx.conf
    nginx -t && systemctl restart nginx && echo "  ✓ Nginx 已重启（关闭默认 server）"
fi
echo "  ✓ Nginx 配置完成"

# ---- 5. 配置防火墙（如果用 firewalld/ufw） ----
echo ""
echo "[5/7] 配置防火墙..."
if command -v ufw &> /dev/null && ufw status 2>/dev/null | grep -q "active"; then
    ufw allow 22/tcp
    ufw allow 80/tcp
    ufw allow 443/tcp
    echo "  ✓ ufw 已放行 22/80/443"
elif command -v firewall-cmd &> /dev/null; then
    firewall-cmd --permanent --add-service=ssh
    firewall-cmd --permanent --add-service=http
    firewall-cmd --permanent --add-service=https
    firewall-cmd --reload
    echo "  ✓ firewalld 已放行 ssh/http/https"
else
    echo "  (未检测到防火墙，跳过——记得在阿里云安全组放行 80/443)"
fi

# ---- 6. 验证 ----
echo ""
echo "[6/7] 验证部署..."
sleep 2
echo "  后端测试："
PROJECTS=$(curl -s http://127.0.0.1:8000/api/projects)
COUNT=$(echo "$PROJECTS" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "?")
echo "    项目数：$COUNT"
echo "  Nginx 测试："
nginx -t 2>&1 | grep -v "^$"

# ---- 7. 输出后续步骤 ----
echo ""
echo "[7/7] 部署完成！"
echo ""
echo "=================================================="
echo "  📋 你还需要做："
echo "=================================================="
echo ""
echo "1️⃣  阿里云 DNS 解析（最重要）："
echo "   登录 https://dns.console.aliyun.com/"
echo "   找到 $DOMAIN 域名，添加 2 条 A 记录："
echo "     @   →  $(curl -s ifconfig.me 2>/dev/null || echo '<ECS公网IP>')"
echo "     www →  同上"
echo "   TTL 10 分钟"
echo ""
echo "2️⃣  阿里云 ECS 安全组放行："
echo "   控制台 → ECS → 安全组 → 入方向 → 添加："
echo "     80/TCP  (HTTP)"
echo "     443/TCP (HTTPS)"
echo ""
echo "3️⃣  等待 DNS 生效（5-30 分钟），然后测试："
echo "   curl http://$DOMAIN/api/projects"
echo "   浏览器访问 http://$DOMAIN"
echo ""
echo "4️⃣  申请免费 SSL 证书（让浏览器显示小绿锁）："
echo "   方式 A（推荐）：阿里云 SSL 控制台 → 申请免费证书 → DNS 验证"
echo "     下载 Nginx 格式证书，上传到 /etc/nginx/ssl/"
echo "   方式 B：SSH 里跑 certbot --nginx -d $DOMAIN -d www.$DOMAIN"
echo ""
echo "=================================================="
echo "  🛠  服务管理命令："
echo "=================================================="
echo "  systemctl status jiayuyuan    # 查看后端状态"
echo "  systemctl restart jiayuyuan  # 重启后端"
echo "  tail -f /var/log/jiayuyuan.log  # 实时看日志"
echo "  nginx -t && nginx -s reload    # 重载 Nginx"
echo "=================================================="

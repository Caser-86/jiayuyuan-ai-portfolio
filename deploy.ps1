# ============================================================
#  贾玉元.AI 一键部署脚本（管理员运行）
#  - 注册 uvicorn 为 Windows 服务（开机自启 + 崩溃重启）
#  - 注册 frpc 为 Windows 服务（开机自启）
#  - 域名解析后通过 ChmlFrp 国内中转访问
# ============================================================
# 用法：右键此文件 → 使用 PowerShell 运行（管理员）

$ErrorActionPreference = "Stop"
$RootPath = "D:\Files\备用"
$NssmPath = Join-Path $RootPath "tools\nssm-2.24\win64\nssm.exe"
$PythonPath = (Get-Command python).Source

# 校验管理员
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "[错误] 请右键此脚本 → 使用 PowerShell(管理员) 运行" -ForegroundColor Red
    pause
    exit 1
}

# 校验 nssm
if (-not (Test-Path $NssmPath)) {
    Write-Host "[错误] 找不到 $NssmPath" -ForegroundColor Red
    pause
    exit 1
}

$env:PATH = (Split-Path $NssmPath) + ";" + $env:PATH

# ---- 1. 停掉现有 uvicorn ----
Write-Host "`n[1/5] 停止 8000 端口上的 uvicorn..." -ForegroundColor Cyan
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
}
Start-Sleep 1
Write-Host "  ✓ 8000 端口已释放" -ForegroundColor Green

# ---- 2. 注册 uvicorn 服务 ----
Write-Host "`n[2/5] 注册 uvicorn 服务 JiayuyuanAPI..." -ForegroundColor Cyan
nssm install JiayuyuanAPI $PythonPath "-m uvicorn main:app --host 127.0.0.1 --port 8000" | Out-Null
nssm set JiayuyuanAPI AppDirectory $RootPath | Out-Null
nssm set JiayuyuanAPI DisplayName "Jiayuyuan.AI FastAPI" | Out-Null
nssm set JiayuyuanAPI Description "贾玉元.AI 个人主页 - FastAPI 后端（uvicorn）" | Out-Null
nssm set JiayuyuanAPI Start SERVICE_AUTO_START | Out-Null
nssm set JiayuyuanAPI AppStdout (Join-Path $RootPath "logs\api.out.log") | Out-Null
nssm set JiayuyuanAPI AppStderr (Join-Path $RootPath "logs\api.err.log") | Out-Null
nssm set JiayuyuanAPI AppRotateFiles 1 | Out-Null
nssm set JiayuyuanAPI AppRotateBytes 10485760 | Out-Null
nssm set JiayuyuanAPI AppStdoutCreationDisposition 4 | Out-Null
nssm set JiayuyuanAPI AppStderrCreationDisposition 4 | Out-Null

# 创建日志目录
New-Item -ItemType Directory -Force -Path (Join-Path $RootPath "logs") | Out-Null
Write-Host "  ✓ JiayuyuanAPI 服务已注册" -ForegroundColor Green

# ---- 3. 启动 uvicorn 服务 ----
Write-Host "`n[3/5] 启动 JiayuyuanAPI..." -ForegroundColor Cyan
nssm start JiayuyuanAPI | Out-Null
Start-Sleep 3
$status = nssm status JiayuyuanAPI
Write-Host "  状态：$status" -ForegroundColor $(if ($status -match "SERVICE_RUNNING") { "Green" } else { "Yellow" })

# ---- 4. 注册 frpc 服务（如果存在 frpc.exe）----
Write-Host "`n[4/5] 注册 frpc 隧道服务..." -ForegroundColor Cyan
$frpcPaths = @(
    (Join-Path $RootPath "frpc\frpc.exe"),
    (Join-Path $RootPath "frpc\frpc_windows_amd64.exe"),
    (Join-Path $RootPath "tools\frpc.exe")
)
$frpcExe = $frpcPaths | Where-Object { Test-Path $_ } | Select-Object -First 1
$frpcConfig = Join-Path $RootPath "frpc\frpc.ini"

if ($frpcExe) {
    if (-not (Test-Path $frpcConfig)) {
        Write-Host "  ! 找不到 $frpcConfig，先创建模板" -ForegroundColor Yellow
        New-Item -ItemType Directory -Force -Path (Split-Path $frpcConfig) | Out-Null
        @"
[common]
server_addr = frp-chmlfrp.com
server_port = 7000
token = 请到 ChmlFrp 用户中心复制你的 token

[jiayuyuan-web]
type = http
local_ip = 127.0.0.1
local_port = 8000
custom_domains = jiayuyuan.ai,www.jiayuyuan.ai
"@ | Out-File -FilePath $frpcConfig -Encoding UTF8
        Write-Host "  模板已生成：$frpcConfig" -ForegroundColor Cyan
        Write-Host "  请先到 https://www.chmlfrp.cn/ 注册+实名+创建隧道，把 token 填到这里" -ForegroundColor Yellow
    } else {
        nssm install JiayuyuanFRPC $frpcExe "-c $frpcConfig" | Out-Null
        nssm set JiayuyuanFRPC AppDirectory (Split-Path $frpcExe) | Out-Null
        nssm set JiayuyuanFRPC DisplayName "Jiayuyuan.AI FRP Tunnel" | Out-Null
        nssm set JiayuyuanFRPC Description "ChmlFrp 内网穿透客户端" | Out-Null
        nssm set JiayuyuanFRPC Start SERVICE_AUTO_START | Out-Null
        nssm set JiayuyuanFRPC AppStdout (Join-Path $RootPath "logs\frpc.out.log") | Out-Null
        nssm set JiayuyuanFRPC AppStderr (Join-Path $RootPath "logs\frpc.err.log") | Out-Null
        nssm set JiayuyuanFRPC AppRotateFiles 1 | Out-Null
        nssm set JiayuyuanFRPC AppRotateBytes 10485760 | Out-Null
        nssm set JiayuyuanFRPC AppStdoutCreationDisposition 4 | Out-Null
        nssm set JiayuyuanFRPC AppStderrCreationDisposition 4 | Out-Null
        nssm start JiayuyuanFRPC | Out-Null
        Start-Sleep 2
        $frpcStatus = nssm status JiayuyuanFRPC
        Write-Host "  状态：$frpcStatus" -ForegroundColor $(if ($frpcStatus -match "SERVICE_RUNNING") { "Green" } else { "Yellow" })
    }
} else {
    Write-Host "  ! 未检测到 frpc.exe，跳过注册" -ForegroundColor Yellow
    Write-Host "  下载地址：https://www.chmlfrp.cn/ → 客户端下载 → 解压到 D:\Files\备用\frpc\" -ForegroundColor Cyan
}

# ---- 5. 验证 ----
Write-Host "`n[5/5] 验证后端..." -ForegroundColor Cyan
Start-Sleep 2
try {
    $r = Invoke-RestMethod "http://127.0.0.1:8000/api/projects" -UseBasicParsing -TimeoutSec 5
    Write-Host "  ✓ 后端 API 正常返回（项目数：$($r.Count)）" -ForegroundColor Green
} catch {
    Write-Host "  ! 后端可能还在启动，5 秒后重试..." -ForegroundColor Yellow
    Start-Sleep 5
    try {
        $r = Invoke-RestMethod "http://127.0.0.1:8000/api/projects" -UseBasicParsing -TimeoutSec 5
        Write-Host "  ✓ 后端 API 正常（项目数：$($r.Count)）" -ForegroundColor Green
    } catch {
        Write-Host "  ✗ 后端无响应，请查看日志：$RootPath\logs\api.err.log" -ForegroundColor Red
    }
}

# ---- 完成 ----
Write-Host "`n========================================" -ForegroundColor Green
Write-Host "  部署完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "服务列表："
Get-Service JiayuyuanAPI,JiayuyuanFRPC -ErrorAction SilentlyContinue | Format-Table Name, Status, StartType -AutoSize

Write-Host ""
Write-Host "后续步骤（ChmlFrp 部分）："
Write-Host "  1. 打开 https://www.chmlfrp.cn/ → 注册 + 实名 + 创建隧道"
Write-Host "  2. 用户中心 → 域名绑定 → 添加 jiayuyuan.ai"
Write-Host "  3. 把 ChmlFrp 提供的 token 填到 D:\Files\备用\frpc\frpc.ini"
Write-Host "  4. 把 CNAME 记录加到阿里云/腾讯云域名解析"
Write-Host ""
Write-Host "服务管理命令（PowerShell 管理员）："
Write-Host "  查看状态：nssm status JiayuyuanAPI"
Write-Host "  重启服务：nssm restart JiayuyuanAPI"
Write-Host "  查看日志：Get-Content D:\Files\备用\logs\api.out.log -Tail 20"
Write-Host ""
pause

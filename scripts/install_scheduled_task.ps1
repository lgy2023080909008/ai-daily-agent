# 本机定时运行（Windows 任务计划程序）
#
# 用法（在当前用户下注册，不需要管理员）：
#   powershell -ExecutionPolicy Bypass -File scripts\install_scheduled_task.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\install_scheduled_task.ps1 -Time 08:00
#   powershell -ExecutionPolicy Bypass -File scripts\install_scheduled_task.ps1 -DryRun   # 只看参数不注册
#
# 卸载：
#   Unregister-ScheduledTask -TaskName "ai-daily-agent" -Confirm:$false

param(
    [string]$Time = "08:00",
    [string]$TaskName = "ai-daily-agent",
    [string]$Python = "",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

# 项目根目录 = 本脚本所在目录的上一级
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Bat = Join-Path $Root "scripts\run_daily.bat"
$LogDir = Join-Path $Root "data\logs"
$LogFile = Join-Path $LogDir "daily.log"

# 解释器优先级：命令行参数 > 项目内 .venv > PATH 里的 python
if (-not $Python) {
    $VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
    if (Test-Path $VenvPython) {
        $Python = $VenvPython
    } else {
        $cmd = Get-Command python -ErrorAction SilentlyContinue
        if ($cmd) { $Python = $cmd.Source }
    }
}

if (-not $Python -or -not (Test-Path $Python)) {
    Write-Host "找不到 Python 解释器。请先建虚拟环境：python -m venv .venv" -ForegroundColor Red
    Write-Host "或用 -Python 指定路径，例如：-Python C:\Python312\python.exe" -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path $Bat)) {
    Write-Host "缺少 scripts\run_daily.bat" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
}

Write-Host "项目目录 : $Root"
Write-Host "解释器   : $Python"
Write-Host "执行脚本 : $Bat"
Write-Host "日志文件 : $LogFile"
Write-Host "触发时间 : 每天 $Time（本机时间）"

if ($DryRun) {
    Write-Host ""
    Write-Host "[DryRun] 只打印，不注册任务。" -ForegroundColor Yellow
    exit 0
}

# 任务计划程序直接调 bat，把解释器路径当参数传进去，避免引号地狱
$Action = New-ScheduledTaskAction -Execute $Bat -Argument ('"' + $Python + '"') -WorkingDirectory $Root
$Trigger = New-ScheduledTaskTrigger -Daily -At $Time
# 电池供电也跑；错过时间后尽快补跑；最长 30 分钟
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger `
    -Settings $Settings -Force `
    -Description "AI 技术前沿日报：每天抓取、精选并推送" | Out-Null

Write-Host ""
Write-Host "已注册计划任务：$TaskName（每天 $Time）" -ForegroundColor Green
Write-Host "查看状态：Get-ScheduledTask -TaskName $TaskName | Get-ScheduledTaskInfo"
Write-Host "立即试跑：Start-ScheduledTask -TaskName $TaskName"
Write-Host "看日志  ：Get-Content '$LogFile' -Tail 40"

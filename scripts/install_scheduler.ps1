# =============================================================================
# Windows Task Scheduler 定时任务安装脚本
# =============================================================================
# 
# 功能: 在 Windows Task Scheduler 中创建一个每两天运行一次的任务，
#       自动执行 scraper.py 和 update_html.py 来更新招聘信息。
#
# 使用方法:
#   1. 右键以管理员身份运行 PowerShell
#   2. 执行: Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
#   3. 执行: .\install_scheduler.ps1
#
# 自定义:
#   - 修改 $ScriptDir 为项目实际路径
#   - 修改 $IntervalDays 为其他间隔天数（默认: 2天）
# =============================================================================

$ErrorActionPreference = "Stop"

# --- 配置 ---
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$TaskName = "CDU_TeacherJobs_Update"
$IntervalDays = 2  # 更新间隔（天）
$PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source

if (-not $PythonExe) {
    Write-Host "[ERROR] 未找到 Python，请确认已安装 Python 并加入 PATH。" -ForegroundColor Red
    exit 1
}

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  成都小学数学教师招聘追踪 - 定时任务安装" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "项目目录: $ProjectDir"
Write-Host "Python:    $PythonExe"
Write-Host "任务名称: $TaskName"
Write-Host "更新间隔: 每 $IntervalDays 天"
Write-Host ""

# --- 构建执行命令 ---
$ScraperScript = Join-Path $ProjectDir "scripts\scraper.py"
$UpdateScript = Join-Path $ProjectDir "scripts\update_html.py"
$LogFile = Join-Path $ProjectDir "logs\scheduler.log"

$ActionCommand = @"
cd /d "$ProjectDir"
echo [%date% %time%] === 开始更新 === >> "$LogFile"
"$PythonExe" "$ScraperScript" >> "$LogFile" 2>&1
"$PythonExe" "$UpdateScript" >> "$LogFile" 2>&1
echo [%date% %time%] === 更新完成 === >> "$LogFile"
"@

$BatchFile = Join-Path $ProjectDir "scripts\_update_task.bat"
Set-Content -Path $BatchFile -Value $ActionCommand -Encoding Default

Write-Host "已创建批处理文件: $BatchFile" -ForegroundColor Green

# --- 创建计划任务 ---
# 先删除旧任务
schtasks /Delete /TN $TaskName /F 2>$null

# 创建新任务
# 从今天开始，每两天运行一次，运行时间设为上午10:00
$StartTime = (Get-Date).Date.AddHours(10)

$Action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$BatchFile`""
$Trigger = New-ScheduledTaskTrigger -Daily -DaysInterval $IntervalDays -At $StartTime
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Highest
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew

$Task = Register-ScheduledTask -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Principal $Principal `
    -Settings $Settings `
    -Description "成都小学数学教师招聘信息自动更新任务 - 每$IntervalDays 天运行一次" `
    -Force

if ($?) {
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Green
    Write-Host "  安装成功！" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "任务详情:" -ForegroundColor Yellow
    Write-Host "  - 名称:     $TaskName"
    Write-Host "  - 下次运行: $StartTime"
    Write-Host "  - 频率:     每 $IntervalDays 天"
    Write-Host "  - 日志文件: $LogFile"
    Write-Host ""
    Write-Host "管理命令:" -ForegroundColor Yellow
    Write-Host "  手动运行:   schtasks /Run /TN `"$TaskName`""
    Write-Host "  查看状态:   schtasks /Query /TN `"$TaskName`" /V"
    Write-Host "  删除任务:   schtasks /Delete /TN `"$TaskName`" /F"
    Write-Host "  查看日志:   Get-Content `"$LogFile`" -Tail 20"
    Write-Host ""
} else {
    Write-Host "安装失败，请检查是否有管理员权限。" -ForegroundColor Red
}

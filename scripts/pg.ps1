<#
.SYNOPSIS
  本地 PostgreSQL 18 的启停脚本（kb-assistant 开发用）。

.DESCRIPTION
  本机的 PostgreSQL 是解压版，没有注册成 Windows 服务，所以用这个脚本管它。
  启动日志写到 %TEMP% 下——不能写进 data 目录：postmaster 自己会在 data 里建
  日志文件，两者冲突时会报 "could not open file: sharing violation" 并空转 30 秒。

.EXAMPLE
  powershell -ExecutionPolicy RemoteSigned -File .\scripts\pg.ps1 start
  powershell -ExecutionPolicy RemoteSigned -File .\scripts\pg.ps1 status
  powershell -ExecutionPolicy RemoteSigned -File .\scripts\pg.ps1 stop

  本机没装 PowerShell 7，所以写 powershell.exe（5.1）而不是 pwsh。
  若已执行过 Set-ExecutionPolicy -Scope CurrentUser RemoteSigned，可以直接：
  .\scripts\pg.ps1 status
#>
[CmdletBinding()]
param(
    [ValidateSet('start', 'stop', 'restart', 'status')]
    [string]$Action = 'status'
)

$ErrorActionPreference = 'Stop'

$Root  = if ($env:PGROOT) { $env:PGROOT } else { 'D:\postgresql\pgsql\1' }
$Data  = if ($env:PGDATA) { $env:PGDATA } else { Join-Path $Root 'data' }
$Log   = if ($env:PGLOG)  { $env:PGLOG }  else { Join-Path $env:TEMP 'pg-kb.log' }
$PgCtl = Join-Path $Root 'bin\pg_ctl.exe'

if (-not (Test-Path $PgCtl)) { throw "找不到 pg_ctl：$PgCtl（用环境变量 PGROOT 指定 PostgreSQL 安装目录）" }
if (-not (Test-Path (Join-Path $Data 'PG_VERSION'))) { throw "data 目录未初始化：$Data" }

function Test-Port {
    param([int]$Port = 5432)
    [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

switch ($Action) {
    'start' {
        if (Test-Port) { Write-Host "已在小跑：127.0.0.1:5432"; break }
        & $PgCtl -D $Data -l $Log -w -t 90 start
        if (Test-Port) { Write-Host "已启动：127.0.0.1:5432  (日志 $Log)" }
        else { Write-Host "启动失败，看日志：$Log"; exit 1 }
    }
    'stop' {
        & $PgCtl -D $Data -m fast -w -t 90 stop
    }
    'restart' {
        & $PgCtl -D $Data -m fast -w -t 90 restart -l $Log
        Write-Host "已重启：127.0.0.1:5432"
    }
    'status' {
        & $PgCtl -D $Data status
        if (-not (Test-Port)) { Write-Host "5432 未监听" }
    }
}

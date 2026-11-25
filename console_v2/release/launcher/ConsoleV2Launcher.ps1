# ConsoleV2 启动器（Windows PowerShell 5.1 兼容）
# 同时支持两种布局：
#   1) 源码树：<AppRoot>\console_v2\app\...（本仓库或复制出去的源码包，先用 编译并启动.cmd 构建）
#   2) 已发布目录：<AppRoot>\ConsoleV2.exe + service\AppService.exe
# 职责：读 config\console.json → 解析数据目录/会话/板端地址 → 启动 service → 等窗口关闭。
# 不构建、不联网下载、不写源会话；日志与标注状态写到可写目录。
[CmdletBinding()]
param(
    [string]$AppRoot = '',
    [string]$DataRoot = '',
    [string]$Session = '',
    [string]$LiveUrl = '',
    [string]$Python = '',
    [string]$StateRoot = '',
    [string]$LogsRoot = '',
    [string]$ConfigPath = '',
    [switch]$NoLive,
    [switch]$Diagnose,
    [switch]$KeepOpen
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { }

function Find-AppRoot([string]$Explicit) {
    if ($Explicit) { return (Resolve-Path -LiteralPath $Explicit).Path.TrimEnd('\') }
    $dir = (Resolve-Path -LiteralPath $PSScriptRoot).Path
    for ($i = 0; $i -lt 5; $i++) {
        $dir = Split-Path -Parent $dir
        if ([string]::IsNullOrEmpty($dir)) { break }
        if (Test-Path -LiteralPath (Join-Path $dir 'console_v2\app\native')) { return $dir.TrimEnd('\') }
    }
    throw '找不到源码/发布根目录：请用 -AppRoot 指定包含 console_v2 的目录。'
}

$script:AppRoot = Find-AppRoot $AppRoot
$script:ConfigPath = if ($ConfigPath) { (Resolve-Path -LiteralPath $ConfigPath).Path } else {
    $rootConfig = Join-Path $AppRoot 'config\console.json'
    $kitConfig = Join-Path $AppRoot 'console_v2\release\config\console.json'
    if (Test-Path -LiteralPath $rootConfig) { $rootConfig } elseif (Test-Path -LiteralPath $kitConfig) { $kitConfig } else { '' }
}

function Write-Step([string]$Text) { Write-Host ('[ConsoleV2] ' + $Text) }
function Write-Warn([string]$Text) { Write-Host ('[ConsoleV2] 警告：' + $Text) -ForegroundColor Yellow }

function Read-Config {
    if (-not $ConfigPath -or -not (Test-Path -LiteralPath $ConfigPath)) { return [pscustomobject]@{} }
    $raw = Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8
    if ([string]::IsNullOrWhiteSpace($raw)) { return [pscustomobject]@{} }
    return ($raw | ConvertFrom-Json)
}

$script:Config = Read-Config
function Cfg([string]$Name, $Default) {
    if ($null -eq $Config) { return $Default }
    $property = $Config.PSObject.Properties[$Name]
    if ($null -eq $property -or $null -eq $property.Value) { return $Default }
    if ($property.Value -is [string] -and [string]::IsNullOrWhiteSpace($property.Value)) { return $Default }
    return $property.Value
}

function Resolve-UserPath([string]$Path, [string]$Base) {
    if ([string]::IsNullOrWhiteSpace($Path)) { return '' }
    $expanded = [Environment]::ExpandEnvironmentVariables($Path.Trim())
    if ($expanded.StartsWith('~')) { $expanded = Join-Path $HOME $expanded.Substring(1).TrimStart('\', '/') }
    if ([IO.Path]::IsPathRooted($expanded)) { return [IO.Path]::GetFullPath($expanded).TrimEnd('\') }
    return [IO.Path]::GetFullPath((Join-Path $Base $expanded)).TrimEnd('\')
}

function Test-LocalWritable([string]$Directory) {
    try {
        $probe = Join-Path $Directory ('.write-probe-' + [Guid]::NewGuid().ToString('N'))
        New-Item -ItemType File -Path $probe -Force | Out-Null
        Remove-Item -LiteralPath $probe -Force
        return $true
    } catch { return $false }
}

function New-LogDirectory([string]$PreferredRoot) {
    $stamp = Get-Date -Format 'yyyyMMdd_HHmmss_fff'
    $fallback = Join-Path $env:LOCALAPPDATA ('ConsoleV2\logs\' + $stamp)
    foreach ($candidate in @($PreferredRoot, $fallback)) {
        if ([string]::IsNullOrWhiteSpace($candidate)) { continue }
        try {
            New-Item -ItemType Directory -Path $candidate -Force | Out-Null
            if (Test-LocalWritable $candidate) { return (Resolve-Path $candidate).Path }
        } catch { }
    }
    throw '找不到可写的日志目录（源码目录和 %LOCALAPPDATA% 都不允许写入）'
}

function Get-LocalIPv4 {
    $addresses = @()
    try {
        $addresses = @(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
            Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } |
            ForEach-Object { $_.IPAddress })
    } catch {
        $addresses = @([System.Net.Dns]::GetHostAddresses([System.Net.Dns]::GetHostName()) |
            Where-Object { $_.AddressFamily -eq 'InterNetwork' } |
            ForEach-Object { $_.IPAddressToString })
    }
    return @($addresses | Select-Object -Unique)
}

function Test-Tcp([string]$HostName, [int]$Port, [int]$TimeoutMs = 1200) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $task = $client.ConnectAsync($HostName, $Port)
        if (-not $task.Wait($TimeoutMs)) { return $false }
        return $client.Connected
    } catch { return $false }
    finally { try { $client.Close() } catch { } }
}

function Get-SessionList([string]$Root) {
    if ([string]::IsNullOrWhiteSpace($Root) -or -not (Test-Path -LiteralPath $Root)) { return @() }
    $items = @()
    foreach ($dir in @(Get-ChildItem -LiteralPath $Root -Directory -ErrorAction SilentlyContinue)) {
        $meta = Join-Path $dir.FullName 'meta.json'
        if (Test-Path -LiteralPath $meta) {
            $items += [pscustomobject]@{ Id = $dir.Name; Path = $dir.FullName; MetaTime = (Get-Item -LiteralPath $meta).LastWriteTimeUtc }
        }
    }
    return @($items | Sort-Object MetaTime -Descending)
}

function New-PlaceholderSession([string]$Root, [string]$NamesPath) {
    $sid = 'placeholder_live_only'
    $dir = Join-Path $Root $sid
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
    $meta = [ordered]@{
        format               = 'human_capture_session'
        version              = 1
        session_id           = $sid
        sensor               = [ordered]@{ model = 'IFW192S'; frame_id = 'innolidar' }
        time_domain          = 'placeholder_no_capture'
        topics               = @('/innolidar_points')
        point_file           = 'points.bin'
        point_stride_bytes   = 28
        point_layout         = [ordered]@{
            fields       = @('x', 'y', 'z', 'intensity', 'ring', 'timestamp')
            dtypes       = @('<f4', '<f4', '<f4', '<f4', '<u2', '<f4')
            endian       = 'little'
            stride_bytes = 28
        }
        total_points         = 0
        total_dropped_points = 0
        frames               = @([ordered]@{
            offset_points  = 0
            count_points   = 0
            dropped_points = 0
            seq            = 0
            stamp_sec      = 0
            stamp_nanosec  = 0
        })
        placeholder          = $true
        placeholder_reason   = '没有可用的会话库；此占位会话只用于实时锁定，不包含任何点云或识别结果'
    }
    # C# 端按 UTF-8 字节直接解析 meta.json，不能带 BOM；PowerShell 5.1 的 Set-Content -Encoding UTF8 会写 BOM。
    [IO.File]::WriteAllText((Join-Path $dir 'meta.json'), ($meta | ConvertTo-Json -Depth 8), (New-Object System.Text.UTF8Encoding($false)))
    New-Item -ItemType File -Path (Join-Path $dir 'points.bin') -Force | Out-Null
    if ($NamesPath) {
        $names = @{}
        if (Test-Path -LiteralPath $NamesPath) {
            try {
                $loaded = Get-Content -LiteralPath $NamesPath -Raw -Encoding UTF8 | ConvertFrom-Json
                foreach ($property in $loaded.PSObject.Properties) { $names[$property.Name] = [string]$property.Value }
            } catch { $names = @{} }
        }
        $names[$sid] = '空白占位会话（仅实时，无点云）'
        New-Item -ItemType Directory -Path (Split-Path -Parent $NamesPath) -Force | Out-Null
        [IO.File]::WriteAllText($NamesPath, ($names | ConvertTo-Json -Depth 4), (New-Object System.Text.UTF8Encoding($false)))
    }
    return $dir
}

function Resolve-Python([string]$Requested) {
    $candidates = @()
    if ($Requested) { $candidates += $Requested }
    $fromConfig = Cfg 'python' ''
    if ($fromConfig) { $candidates += $fromConfig }
    $candidates += (Join-Path $AppRoot 'python\python.exe')
    $candidates += 'python.exe'
    foreach ($candidate in $candidates) {
        $exe = $candidate
        if (-not [IO.Path]::IsPathRooted($exe)) {
            $command = Get-Command $exe -ErrorAction SilentlyContinue
            if ($null -eq $command) { continue }
            $exe = $command.Source
        }
        if (-not (Test-Path -LiteralPath $exe)) { continue }
        try {
            & $exe -c 'import sys; sys.exit(0)' 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) { return $exe }
        } catch { }
    }
    return ''
}

function Resolve-Layout {
    $hostCandidates = @(
        (Join-Path $AppRoot 'ConsoleV2.exe'),
        (Join-Path $AppRoot 'console_v2\app\runtime\ConsoleV2.exe')
    )
    $hostPath = $hostCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    $serviceCandidates = @(
        (Join-Path $AppRoot 'service\AppService.exe'),
        (Join-Path $AppRoot 'console_v2\app\service\bin\Release\net8.0-windows\AppService.exe')
    )
    $servicePath = $serviceCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    $dotnet = Get-Command 'dotnet' -ErrorAction SilentlyContinue
    if (-not $servicePath) {
        foreach ($dll in @(
            (Join-Path $AppRoot 'service\AppService.dll'),
            (Join-Path $AppRoot 'console_v2\app\service\bin\Release\net8.0-windows\AppService.dll'))) {
            if ((Test-Path -LiteralPath $dll) -and $dotnet) {
                return [pscustomobject]@{ Host = $hostPath; Service = $dll; Dotnet = $dotnet.Source }
            }
        }
    }
    return [pscustomobject]@{ Host = $hostPath; Service = $servicePath; Dotnet = $(if ($dotnet) { $dotnet.Source } else { '' }) }
}

function Show-Banner([string]$DataDir, [string]$SessionDir, [string]$LogDir, [string]$BoardUrl, [string]$PythonExe, [int]$SessionCount) {
    Write-Host ''
    Write-Host '============================================================'
    Write-Host ' 雷达控制台 ConsoleV2 · 源码构建版'
    Write-Host '============================================================'
    Write-Host (' 源码根目录 : ' + $AppRoot)
    Write-Host (' 本机地址   : ' + ((Get-LocalIPv4) -join ', '))
    Write-Host (' 数据目录   : ' + $DataDir + '  （' + $SessionCount + ' 个会话）')
    Write-Host (' 启动会话   : ' + $SessionDir)
    Write-Host (' 板端地址   : ' + $(if ($BoardUrl) { $BoardUrl } else { '未配置（可在界面里手动连接）' }))
    Write-Host (' 日志目录   : ' + $LogDir)
    Write-Host (' Python     : ' + $(if ($PythonExe) { $PythonExe } else { '未找到（视频/网页标注/离线分析不可用，其余功能正常）' }))
    Write-Host '------------------------------------------------------------'
    Write-Host ' 关闭窗口即结束；日志与报告保留在日志目录。'
    Write-Host '============================================================'
    Write-Host ''
}

function Invoke-Diagnose {
    $dataDir = if ($DataRoot) { Resolve-UserPath $DataRoot $AppRoot } else { Resolve-UserPath (Cfg 'dataRoot' 'console_v2\user_data\sessions') $AppRoot }
    $boardUrl = if ($LiveUrl) { $LiveUrl } else { Cfg 'boardUrl' '' }
    $sessions = Get-SessionList $dataDir
    $pythonExe = Resolve-Python $Python
    $layout = Resolve-Layout
    $boardHost = ''; $boardPort = 0
    if ($boardUrl) {
        try { $uri = [Uri]$boardUrl; $boardHost = $uri.Host; $boardPort = if ($uri.Port -gt 0) { $uri.Port } else { 8765 } } catch { }
    }
    $result = [ordered]@{
        checkedAt      = (Get-Date).ToString('o')
        appRoot        = $AppRoot
        configPath     = $ConfigPath
        host           = $env:COMPUTERNAME
        localIPv4      = @(Get-LocalIPv4)
        os             = [Environment]::OSVersion.VersionString
        qtHost         = $layout.Host
        qtHostExists   = ($layout.Host -and (Test-Path -LiteralPath $layout.Host))
        service        = $layout.Service
        serviceExists  = ($layout.Service -and (Test-Path -LiteralPath $layout.Service))
        dataRoot       = $dataDir
        dataRootExists = (Test-Path -LiteralPath $dataDir)
        dataRootIsUnc  = ($dataDir.StartsWith('\\'))
        sessionCount   = @($sessions).Count
        newestSession  = if (@($sessions).Count -gt 0) { @($sessions)[0].Id } else { '' }
        python         = $pythonExe
        boardUrl       = $boardUrl
        boardHost      = $boardHost
        boardPort      = $boardPort
        boardReachable = if ($boardHost) { Test-Tcp $boardHost $boardPort } else { $false }
    }
    $result | ConvertTo-Json -Depth 5 | Write-Host
    return $result
}

try {
    if ($Diagnose) {
        $result = Invoke-Diagnose
        $logsBase = Resolve-UserPath (Cfg 'logs' 'console_v2\user_data\logs') $AppRoot
        $logDir = New-LogDirectory (Join-Path $logsBase ((Get-Date -Format 'yyyyMMdd_HHmmss') + '_diagnose'))
        $result | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $logDir 'lan-check.json') -Encoding UTF8
        Write-Host ''
        Write-Host ('诊断结果已写入：' + (Join-Path $logDir 'lan-check.json'))
        if (-not $result.serviceExists -or -not $result.qtHostExists) { Write-Warn '还没有构建产物：先运行「编译并启动.cmd」。' }
        if (-not $result.boardReachable) { Write-Warn '板端端口不可达：确认同一局域网、板端地址和防火墙。' }
        if (-not $result.dataRootExists) { Write-Warn '数据目录不存在：启动时会自动创建占位会话，只用于实时锁定。' }
        exit 0
    }

    $layout = Resolve-Layout
    if (-not $layout.Service -or -not (Test-Path -LiteralPath $layout.Service)) {
        throw ('找不到服务程序：' + $layout.Service + '。源码树请先运行「编译并启动.cmd」或「构建.cmd」。')
    }
    if (-not $layout.Host -or -not (Test-Path -LiteralPath $layout.Host)) {
        throw ('找不到 Qt 程序：' + $layout.Host + '。请先构建并部署运行库。')
    }

    $dataDir = if ($DataRoot) { Resolve-UserPath $DataRoot $AppRoot } else { Resolve-UserPath (Cfg 'dataRoot' 'console_v2\user_data\sessions') $AppRoot }
    if (-not $dataDir) { throw '未配置数据目录' }
    if (-not (Test-Path -LiteralPath $dataDir)) {
        if ($dataDir.StartsWith('\\')) { throw ('共享数据目录不可访问：' + $dataDir) }
        New-Item -ItemType Directory -Path $dataDir -Force | Out-Null
    }
    if (-not (Test-LocalWritable $dataDir)) {
        Write-Warn ('数据目录不可写（' + $dataDir + '）：只读浏览和实时可用；删除/改名/保存标注会失败。')
    }

    $stateDir = if ($StateRoot) { Resolve-UserPath $StateRoot $AppRoot } else { Resolve-UserPath (Cfg 'state' 'console_v2\user_data\state') $AppRoot }
    try {
        New-Item -ItemType Directory -Path $stateDir -Force | Out-Null
        if (-not (Test-LocalWritable $stateDir)) { throw 'not writable' }
    } catch {
        $stateDir = Join-Path $env:LOCALAPPDATA 'ConsoleV2\user_data'
        New-Item -ItemType Directory -Path $stateDir -Force | Out-Null
    }
    $namesPath = Join-Path $stateDir 'session_names.json'
    $gtRoot = Join-Path $stateDir 'gt_store_v2'

    $logsBase = Resolve-UserPath (Cfg 'logs' 'console_v2\user_data\logs') $AppRoot
    $logs = if ($LogsRoot) { New-LogDirectory (Resolve-UserPath $LogsRoot $AppRoot) } else { New-LogDirectory (Join-Path $logsBase (Get-Date -Format 'yyyyMMdd_HHmmss')) }
    $localAnalysis = Join-Path $logs 'local-analysis'
    New-Item -ItemType Directory -Path $localAnalysis -Force | Out-Null

    $sessions = Get-SessionList $dataDir
    $sessionDir = ''
    if ($Session) {
        $candidate = if ([IO.Path]::IsPathRooted($Session)) { [IO.Path]::GetFullPath($Session) } else { Join-Path $dataDir $Session }
        if (-not (Test-Path -LiteralPath (Join-Path $candidate 'meta.json'))) { throw ('指定的会话不存在：' + $candidate) }
        $sessionDir = (Resolve-Path $candidate).Path
    } elseif (@($sessions).Count -gt 0) {
        $sessionDir = @($sessions)[0].Path
    } else {
        Write-Step '数据目录没有会话，创建仅用于实时模式的空白占位会话…'
        $sessionDir = New-PlaceholderSession $dataDir $namesPath
        $sessions = Get-SessionList $dataDir
    }

    $boardUrl = if ($LiveUrl) { $LiveUrl } else { Cfg 'boardUrl' '' }
    $autoLive = [bool](Cfg 'autoConnectLive' $true)
    if ($NoLive) { $autoLive = $false }
    if ($autoLive -and -not $boardUrl) { Write-Warn 'autoConnectLive=true 但 boardUrl 为空，改为手动连接。' }

    $pythonExe = Resolve-Python $Python
    if (-not $pythonExe) { Write-Warn '未找到 Python：实时/回放/原生标注正常，视频窗口、网页标注台与离线分析不可用。' }

    Show-Banner $dataDir $sessionDir $logs $boardUrl $pythonExe @($sessions).Count

    $report = Join-Path $logs 'service.json'
    $argv = @(
        '--root', $AppRoot,
        '--data-root', $dataDir,
        '--logs', $logs,
        '--report', $report,
        '--local-analysis', $localAnalysis,
        '--names-file', $namesPath,
        '--gt-root', $gtRoot,
        '--session', $sessionDir,
        '--host', $layout.Host,
        '--python', $(if ($pythonExe) { $pythonExe } else { 'python' })
    )
    if ($autoLive -and $boardUrl) { $argv += @('--live-url', $boardUrl) }

    $commandLine = ($argv | ForEach-Object { if ($_ -match '[\s"]') { '"' + ($_ -replace '"', '\"') + '"' } else { $_ } }) -join ' '
    Set-Content -LiteralPath (Join-Path $logs 'launch.txt') -Encoding UTF8 -Value @(
        ('startedAt=' + (Get-Date).ToString('o')),
        ('appRoot=' + $AppRoot),
        ('dataRoot=' + $dataDir),
        ('session=' + $sessionDir),
        ('liveUrl=' + $(if ($autoLive) { $boardUrl } else { '' })),
        ('python=' + $pythonExe),
        ('command=' + $layout.Service + ' ' + $commandLine)
    )
    $latest = Join-Path $logsBase 'LATEST.txt'
    try { Set-Content -LiteralPath $latest -Encoding UTF8 -Value $logs } catch { }

    Write-Step '启动服务与界面…'
    if ($layout.Service.EndsWith('.dll', [StringComparison]::OrdinalIgnoreCase)) {
        if (-not $layout.Dotnet) { throw '需要 dotnet 运行服务 DLL，但 PATH 中没有 dotnet。' }
        & $layout.Dotnet $layout.Service @argv
    } else {
        & $layout.Service @argv
    }
    $code = $LASTEXITCODE
    Write-Host ''
    if ($code -eq 0) {
        Write-Step ('界面已正常关闭。日志：' + $logs)
    } else {
        Write-Warn ('服务退出码 ' + $code + '；日志：' + $logs)
    }
    exit $code
}
catch {
    Write-Host ''
    Write-Warn $_.Exception.Message
    Write-Host '排查：运行「局域网诊断.cmd」；构建问题见「编译并启动.cmd」输出。'
    if ($KeepOpen) { Read-Host '按 Enter 退出' | Out-Null }
    exit 2
}
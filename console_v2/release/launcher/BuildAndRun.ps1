# ConsoleV2 源码构建 + 启动（Windows PowerShell 5.1 兼容）
# 在任意源码目录运行：发现 .NET 8 SDK / Qt 6.5 MinGW / CMake / MinGW → 构建 C# 服务与 Qt 程序
# → windeployqt 部署到 console_v2\app\runtime → 用 ConsoleV2Launcher.ps1 启动。
# 不修改驱动、不访问板端写接口、不采集；只编译本机源码。
[CmdletBinding()]
param(
    [string]$AppRoot = '',
    [string]$QtDir = '',
    [string]$Dotnet = '',
    [string]$Cmake = '',
    [string]$MinGW = '',
    [string]$DataRoot = '',
    [string]$Session = '',
    [string]$LiveUrl = '',
    [switch]$NoLive,
    [switch]$BuildOnly,
    [switch]$NoBuild,
    [switch]$Diagnose,
    [switch]$KeepOpen
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { }

function Write-Step([string]$Text) { Write-Host ('[build] ' + $Text) }
function Write-Ok([string]$Text) { Write-Host ('[build] OK  ' + $Text) -ForegroundColor Green }
function Write-Warn([string]$Text) { Write-Host ('[build] 警告：' + $Text) -ForegroundColor Yellow }

function Find-AppRoot([string]$Explicit) {
    if ($Explicit) { return (Resolve-Path -LiteralPath $Explicit).Path.TrimEnd('\') }
    $dir = (Resolve-Path -LiteralPath $PSScriptRoot).Path
    for ($i = 0; $i -lt 5; $i++) {
        $dir = Split-Path -Parent $dir
        if ([string]::IsNullOrEmpty($dir)) { break }
        if (Test-Path -LiteralPath (Join-Path $dir 'console_v2\app\native')) { return $dir.TrimEnd('\') }
    }
    throw '找不到源码根目录：请把本脚本放在 <源码根>\launcher\ 下，或用 -AppRoot 指定。'
}

$script:AppRoot = Find-AppRoot $AppRoot
$script:ConsoleDir = Join-Path $AppRoot 'console_v2'
$script:NativeDir = Join-Path $ConsoleDir 'app\native'
$script:ServiceProject = Join-Path $ConsoleDir 'app\service\AppService.csproj'
$script:BuildDir = Join-Path $ConsoleDir 'app\build-dist'
$script:RuntimeDir = Join-Path $ConsoleDir 'app\runtime'

function Expand-Candidate([string]$Value) {
    if ([string]::IsNullOrWhiteSpace($Value)) { return '' }
    return [Environment]::ExpandEnvironmentVariables($Value.Trim().Trim('"'))
}

function Test-DotnetSdk([string]$Exe) {
    if (-not $Exe -or -not (Test-Path -LiteralPath $Exe)) { return $false }
    try {
        $sdks = & $Exe --list-sdks 2>$null
        if ($LASTEXITCODE -ne 0) { return $false }
        return [bool]($sdks | Where-Object { $_ -match '^8\.' })
    } catch { return $false }
}

function Find-Dotnet([string]$Requested) {
    $candidates = @()
    if ($Requested) { $candidates += $Requested }
    if ($env:CONSOLEV2_DOTNET) { $candidates += $env:CONSOLEV2_DOTNET }
    $candidates += (Join-Path $ConsoleDir '.tools\dotnet\dotnet.exe')
    $candidates += 'dotnet.exe'
    foreach ($candidate in $candidates) {
        $expanded = Expand-Candidate $candidate
        if (-not $expanded) { continue }
        $exe = $expanded
        if (-not [IO.Path]::IsPathRooted($exe)) {
            $command = Get-Command $exe -ErrorAction SilentlyContinue
            if ($null -eq $command) { continue }
            $exe = $command.Source
        }
        if (Test-DotnetSdk $exe) { return $exe }
    }
    return ''
}

function Find-Qt([string]$Requested) {
    $candidates = @()
    if ($Requested) { $candidates += $Requested }
    if ($env:CONSOLEV2_QT) { $candidates += $env:CONSOLEV2_QT }
    if ($env:QTDIR) { $candidates += $env:QTDIR }
    $candidates += (Join-Path $ConsoleDir '.tools\qt\6.5.3\mingw_64')
    $candidates += (Join-Path $env:USERPROFILE 'Qt\6.5.3\mingw_64')
    $candidates += 'C:\Qt\6.5.3\mingw_64'
    foreach ($root in @('C:\Qt', (Join-Path $env:USERPROFILE 'Qt'))) {
        if (Test-Path -LiteralPath $root) {
            $candidates += @(Get-ChildItem -LiteralPath $root -Directory -ErrorAction SilentlyContinue |
                ForEach-Object { Join-Path $_.FullName 'mingw_64' })
        }
    }
    foreach ($candidate in $candidates) {
        $expanded = Expand-Candidate $candidate
        if (-not $expanded) { continue }
        if (-not (Test-Path -LiteralPath $expanded)) { continue }
        $prefix = (Resolve-Path -LiteralPath $expanded).Path.TrimEnd('\')
        if ((Test-Path -LiteralPath (Join-Path $prefix 'bin\windeployqt.exe')) -and
            (Test-Path -LiteralPath (Join-Path $prefix 'lib\cmake\Qt6\Qt6Config.cmake'))) { return $prefix }
    }
    return ''
}

function Find-MinGW([string]$Requested, [string]$QtPrefix) {
    $candidates = @()
    if ($Requested) { $candidates += $Requested }
    if ($env:CONSOLEV2_MINGW) { $candidates += $env:CONSOLEV2_MINGW }
    if ($QtPrefix) {
        $candidates += (Join-Path $QtPrefix '..\..\Tools\mingw1120_64\bin')
        $candidates += (Join-Path $QtPrefix '..\Tools\mingw1120_64\bin')
        $candidates += (Join-Path $QtPrefix 'bin')
    }
    $candidates += 'C:\Qt\Tools\mingw1120_64\bin'
    foreach ($candidate in $candidates) {
        $expanded = Expand-Candidate $candidate
        if (-not $expanded) { continue }
        if (-not (Test-Path -LiteralPath $expanded)) { continue }
        $bin = (Resolve-Path -LiteralPath $expanded).Path.TrimEnd('\')
        if ((Test-Path -LiteralPath (Join-Path $bin 'g++.exe')) -and
            (Test-Path -LiteralPath (Join-Path $bin 'mingw32-make.exe'))) { return $bin }
    }
    $gxx = Get-Command 'g++.exe' -ErrorAction SilentlyContinue
    $make = Get-Command 'mingw32-make.exe' -ErrorAction SilentlyContinue
    if ($gxx -and $make) { return (Split-Path -Parent $gxx.Source) }
    return ''
}

function Find-Cmake([string]$Requested) {
    $candidates = @()
    if ($Requested) { $candidates += $Requested }
    if ($env:CONSOLEV2_CMAKE) { $candidates += $env:CONSOLEV2_CMAKE }
    $candidates += 'C:\Program Files\CMake\bin\cmake.exe'
    $candidates += 'cmake.exe'
    foreach ($candidate in $candidates) {
        $expanded = Expand-Candidate $candidate
        if (-not $expanded) { continue }
        $exe = $expanded
        if (-not [IO.Path]::IsPathRooted($exe)) {
            $command = Get-Command $exe -ErrorAction SilentlyContinue
            if ($null -eq $command) { continue }
            $exe = $command.Source
        }
        if (Test-Path -LiteralPath $exe) { return $exe }
    }
    return ''
}

function Find-Python {
    foreach ($candidate in @((Join-Path $AppRoot 'python\python.exe'), 'python.exe')) {
        $exe = $candidate
        if (-not [IO.Path]::IsPathRooted($exe)) {
            $command = Get-Command $exe -ErrorAction SilentlyContinue
            if ($null -eq $command) { continue }
            $exe = $command.Source
        }
        if (Test-Path -LiteralPath $exe) {
            try { & $exe -c 'import sys; sys.exit(0)' 2>$null | Out-Null; if ($LASTEXITCODE -eq 0) { return $exe } } catch { }
        }
    }
    return ''
}

function Invoke-External([string]$Label, [string]$Exe, [string[]]$Arguments, [string]$WorkingDirectory) {
    Write-Step ($Label + ' …')
    Push-Location $WorkingDirectory
    try {
        & $Exe @Arguments
        $code = $LASTEXITCODE
    } finally { Pop-Location }
    if ($code -ne 0) { throw ($Label + ' 失败，退出码 ' + $code) }
    Write-Ok $Label
}

$dotnetExe = Find-Dotnet $Dotnet
$qtExe = Find-Qt $QtDir
$mingwBin = Find-MinGW $MinGW $qtExe
$cmakeExe = Find-Cmake $Cmake
$pythonExe = Find-Python

$toolchain = [ordered]@{
    appRoot   = $AppRoot
    dotnet    = $dotnetExe
    qt        = $qtExe
    mingw     = $mingwBin
    cmake     = $cmakeExe
    python    = $pythonExe
    checkedAt = (Get-Date).ToString('o')
}

Write-Host ''
Write-Host '工具链：'
Write-Host ('  .NET 8 SDK : ' + $(if ($dotnetExe) { $dotnetExe } else { '未找到' }))
Write-Host ('  Qt 6.5     : ' + $(if ($qtExe) { $qtExe } else { '未找到' }))
Write-Host ('  MinGW      : ' + $(if ($mingwBin) { $mingwBin } else { '未找到' }))
Write-Host ('  CMake      : ' + $(if ($cmakeExe) { $cmakeExe } else { '未找到' }))
Write-Host ('  Python     : ' + $(if ($pythonExe) { $pythonExe } else { '未找到（可选）' }))
Write-Host ''

$stateDir = Join-Path $ConsoleDir 'user_data\build'
try { New-Item -ItemType Directory -Path $stateDir -Force | Out-Null } catch { }
try { $toolchain | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $stateDir 'toolchain.json') -Encoding UTF8 } catch { }

if ($Diagnose) {
    Write-Host ('工具链诊断已写入：' + (Join-Path $stateDir 'toolchain.json'))
    if (-not $dotnetExe) { Write-Warn '.NET 8 SDK 缺失：https://dotnet.microsoft.com/download/dotnet/8.0' }
    if (-not $qtExe) { Write-Warn 'Qt 6.5 MinGW 缺失：Qt Online Installer 里勾选 Qt 6.5.3 > MinGW 64-bit' }
    if (-not $mingwBin) { Write-Warn 'MinGW 11.2 缺失：Qt 安装器同页勾选 MinGW 11.2.0 64-bit' }
    if (-not $cmakeExe) { Write-Warn 'CMake 缺失：https://cmake.org/download/（安装时加入 PATH）' }
    exit 0
}

$missing = @()
if (-not $dotnetExe) { $missing += '.NET 8 SDK' }
if (-not $qtExe) { $missing += 'Qt 6.5.x mingw_64' }
if (-not $mingwBin) { $missing += 'MinGW 11.2 (g++/mingw32-make)' }
if (-not $cmakeExe) { $missing += 'CMake 3.21+' }
if ($missing.Count -gt 0) {
    Write-Host ''
    Write-Warn ('缺少构建依赖：' + ($missing -join '、'))
    Write-Host '安装方法见《编译与运行.md》“准备工具链”一节；也可以用环境变量指向已安装位置：'
    Write-Host '  CONSOLEV2_DOTNET=<dotnet.exe>  CONSOLEV2_QT=<Qt\6.5.3\mingw_64>'
    Write-Host '  CONSOLEV2_MINGW=<Qt\Tools\mingw1120_64\bin>  CONSOLEV2_CMAKE=<cmake.exe>'
    exit 2
}

if (-not $NoBuild) {
    $env:PATH = $mingwBin + ';' + (Join-Path $qtExe 'bin') + ';' + $env:PATH
    $gxx = Join-Path $mingwBin 'g++.exe'
    $make = Join-Path $mingwBin 'mingw32-make.exe'
    $qtVersion = 'unknown'
    try {
        $versionFile = Join-Path $qtExe 'lib\cmake\Qt6\Qt6ConfigVersion.cmake'
        if (Test-Path -LiteralPath $versionFile) {
            $match = Select-String -LiteralPath $versionFile -Pattern 'PACKAGE_VERSION "([0-9.]+)"' | Select-Object -First 1
            if ($match) { $qtVersion = $match.Matches[0].Groups[1].Value }
        }
    } catch { }

    Invoke-External '还原并编译 C# 服务' $dotnetExe @('build', $ServiceProject, '-c', 'Release', '--nologo', '-v', 'minimal') $AppRoot

    New-Item -ItemType Directory -Path $BuildDir -Force | Out-Null
    $cacheFile = Join-Path $BuildDir 'CMakeCache.txt'
    if (Test-Path -LiteralPath $cacheFile) {
        $cachedQt = Select-String -LiteralPath $cacheFile -Pattern '^CMAKE_PREFIX_PATH:.*=(.*)$' | Select-Object -First 1
        $cachedCompiler = Select-String -LiteralPath $cacheFile -Pattern '^CMAKE_CXX_COMPILER:.*=(.*)$' | Select-Object -First 1
        if (($cachedQt -and $cachedQt.Matches[0].Groups[1].Value -ne $qtExe) -or
            ($cachedCompiler -and $cachedCompiler.Matches[0].Groups[1].Value -ne $gxx)) {
            Write-Warn '构建目录的工具链和当前检测到的不一致，清理 console_v2\app\build-dist 后重建。'
            Remove-Item -LiteralPath $BuildDir -Recurse -Force
            New-Item -ItemType Directory -Path $BuildDir -Force | Out-Null
        }
    }
    $configureArgs = @(
        '-S', $NativeDir, '-B', $BuildDir, '-G', 'MinGW Makefiles',
        '-DCMAKE_BUILD_TYPE=Release',
        ('-DCMAKE_CXX_COMPILER=' + $gxx),
        ('-DCMAKE_MAKE_PROGRAM=' + $make),
        ('-DCMAKE_PREFIX_PATH=' + $qtExe)
    )
    Invoke-External '配置 Qt 工程' $cmakeExe $configureArgs $AppRoot
    Invoke-External '编译 Qt 程序' $cmakeExe @('--build', $BuildDir, '--parallel', '8') $AppRoot

    $exe = Join-Path $BuildDir 'ConsoleV2.exe'
    if (-not (Test-Path -LiteralPath $exe)) { throw ('编译完成但找不到 ' + $exe) }
    New-Item -ItemType Directory -Path $RuntimeDir -Force | Out-Null
    Copy-Item -LiteralPath $exe -Destination (Join-Path $RuntimeDir 'ConsoleV2.exe') -Force
    Invoke-External '部署 Qt 运行库' (Join-Path $qtExe 'bin\windeployqt.exe') @(
        '--no-translations', '--no-opengl-sw', '--qmldir', $NativeDir,
        '--dir', $RuntimeDir, (Join-Path $RuntimeDir 'ConsoleV2.exe')
    ) $AppRoot

    $serviceExe = Join-Path $ConsoleDir 'app\service\bin\Release\net8.0-windows\AppService.exe'
    if (-not (Test-Path -LiteralPath $serviceExe)) { throw ('找不到服务构建产物：' + $serviceExe) }
    $buildInfo = [ordered]@{
        builtAt    = (Get-Date).ToString('o')
        appRoot    = $AppRoot
        qt         = $qtExe
        qtVersion  = $qtVersion
        mingw      = $mingwBin
        dotnet     = $dotnetExe
        cmake      = $cmakeExe
        runtime    = $RuntimeDir
        service    = $serviceExe
    }
    $buildInfo | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $stateDir 'build.json') -Encoding UTF8
    Write-Host ''
    Write-Ok '构建完成'
    Write-Host ('  Qt 程序 : ' + (Join-Path $RuntimeDir 'ConsoleV2.exe'))
    Write-Host ('  服务    : ' + $serviceExe)
}

if ($BuildOnly) { exit 0 }

$launcher = Join-Path $PSScriptRoot 'ConsoleV2Launcher.ps1'
$launchArgs = @('-AppRoot', $AppRoot)
if ($DataRoot) { $launchArgs += @('-DataRoot', $DataRoot) }
if ($Session) { $launchArgs += @('-Session', $Session) }
if ($LiveUrl) { $launchArgs += @('-LiveUrl', $LiveUrl) }
if ($NoLive) { $launchArgs += '-NoLive' }
if ($KeepOpen) { $launchArgs += '-KeepOpen' }
& $launcher @launchArgs
exit $LASTEXITCODE
# Compile-check the .ino with the local arduino-esp32 toolchain, using the exact
# flags from platform.txt (compile only, no link). Verifies syntax / IDF API names / format strings.
# ASCII only on purpose: Windows PowerShell 5.1 reads BOM-less UTF-8 as ANSI (GBK here).
# Usage:  powershell.exe -NoProfile -ExecutionPolicy Bypass -File build_check.ps1
$ErrorActionPreference = "Stop"

$pkg     = "C:\Users\30680\AppData\Local\Arduino15\packages\esp32"
$core    = Join-Path $pkg "hardware\esp32\3.1.1"
$libsDir = Get-ChildItem (Join-Path $pkg "tools\esp32-arduino-libs") -Directory |
           Sort-Object Name -Descending | Select-Object -First 1
$sdk     = Join-Path $libsDir.FullName "esp32s3"
$gxx     = Join-Path $pkg "tools\esp-x32\2405\bin\xtensa-esp32s3-elf-g++.exe"

$here = Split-Path -Parent $PSCommandPath
$ino  = Join-Path $here "scope_selftest\scope_selftest.ino"
$work = Join-Path $env:TEMP "scope_selftest_build"

New-Item -ItemType Directory -Force -Path $work | Out-Null
Copy-Item $ino (Join-Path $work "scope_selftest.cpp") -Force

# Equivalent to platform.txt recipe.cpp.o.pattern:
#   cpp_flags + defines + -iprefix + flags/includes + board headers
$lines = New-Object 'System.Collections.Generic.List[string]'
$lines.Add("@$sdk\flags\cpp_flags")
foreach ($x in @("-c", "-Wall", "-Wextra", "-O2")) { [void]$lines.Add($x) }
foreach ($x in @(
    "-DF_CPU=240000000", "-DARDUINO=10607", "-DARDUINO_ESP32S3_DEV",
    "-DARDUINO_ARCH_ESP32", '-DARDUINO_BOARD="ESP32S3_DEV"',
    '-DARDUINO_VARIANT="esp32s3"', "-DARDUINO_PARTITION_default",
    "-DCORE_DEBUG_LEVEL=0"
)) { [void]$lines.Add($x) }
[void]$lines.Add("-iprefix")
[void]$lines.Add("$sdk\include\")
[void]$lines.Add("@$sdk\flags\includes")        # IDF component -iwithprefixbefore list
[void]$lines.Add("-I$sdk\qio_qspi\include")     # sdkconfig.h (qio_qspi = default 4MB DIO build)
[void]$lines.Add("-I$core\cores\esp32")
[void]$lines.Add("-I$core\variants\esp32s3")
[void]$lines.Add((Join-Path $work "scope_selftest.cpp"))
[void]$lines.Add("-o")
[void]$lines.Add((Join-Path $work "scope_selftest.o"))

# Backslash is an escape character inside a gcc @response file: use forward slashes,
# one argument per line.
$rsp = Join-Path $work "args.rsp"
$normalized = @()
foreach ($x in $lines) { $normalized += ($x -replace '\\', '/') }
Set-Content -Path $rsp -Value ($normalized -join "`r`n") -Encoding ascii
Write-Host ("response file: {0} lines" -f (Get-Content $rsp | Measure-Object).Count)

Write-Host "compiler : $gxx"
Write-Host "sdk      : $sdk"
Write-Host "input    : $ino"
& $gxx "@$rsp"
$code = $LASTEXITCODE
Write-Host "exit=$code"
if ($code -eq 0) {
    $o = Get-Item (Join-Path $work "scope_selftest.o")
    Write-Host ("OK  no warnings  object: {0} bytes" -f $o.Length)
}
exit $code